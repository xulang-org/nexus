// SDL owns platform GPU commands and shaders; game policy remains in Xu.
#define SDL_MAIN_HANDLED
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include "xu_native.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#ifdef __APPLE__
#include <pthread.h>
#endif
#endif

#define API(name) XU_NATIVE_SYMBOL(xu_game_gpu_native_##name)
#define SDL_FUNCTIONS(X) \
    X(SDL_SetMainReady) X(SDL_IsMainThread) X(SDL_InitSubSystem) X(SDL_QuitSubSystem) \
    X(SDL_GetError) X(SDL_CreateWindow) X(SDL_DestroyWindow) X(SDL_GetWindowID) \
    X(SDL_CreateGPUDevice) X(SDL_DestroyGPUDevice) X(SDL_GetGPUDeviceDriver) \
    X(SDL_CreateGPURenderer) X(SDL_GetGPURendererDevice) X(SDL_DestroyRenderer) \
    X(SDL_SetRenderVSync) X(SDL_SetRenderDrawBlendMode) X(SDL_SetRenderDrawColor) \
    X(SDL_RenderClear) X(SDL_RenderGeometry) X(SDL_RenderPresent) X(SDL_GetRenderOutputSize) \
    X(SDL_PollEvent) X(SDL_RenderReadPixels) X(SDL_ReadSurfacePixel) X(SDL_DestroySurface) X(SDL_SavePNG) \
    X(SDL_CreateTexture) X(SDL_UpdateTexture) X(SDL_DestroyTexture) X(SDL_SetTextureBlendMode) X(SDL_SetTextureScaleMode)
#define DECLARE(name) static __typeof__(name) *p_##name;
SDL_FUNCTIONS(DECLARE)

enum { MAX_RENDERERS = 8, MAX_TEXTURES = 1024, MAX_VERTICES = 393216, VERTEX_WORDS = 5 };
typedef struct {
    SDL_Window *window;
    SDL_GPUDevice *device;
    SDL_Renderer *renderer;
    uint64_t generation;
    bool recording;
    int frame_vertices;
    int texture_pixels;
} Renderer;
typedef struct {
    SDL_Texture *texture;
    xu_int owner;
    uint64_t generation;
    int pixels;
} Texture;
static Renderer renderers[MAX_RENDERERS];
static Texture textures[MAX_TEXTURES];
static int live_renderers;
static char last_error[1024];
static bool library_ready;

static xu_int fail(const char *message) {
    snprintf(last_error, sizeof(last_error), "%s", message ? message : "unknown GPU error");
    return -1;
}
static xu_int sdl_fail(void) { return fail(p_SDL_GetError()); }
static bool main_thread(void) {
    if (!p_SDL_IsMainThread()) { fail("GPU operations must run on the application main thread"); return false; }
    return true;
}
static bool load_sdl(void) {
    if (library_ready) return true;
#ifdef __APPLE__
    if (!pthread_main_np()) { fail("open the GPU renderer on the application main thread"); return false; }
#endif
#ifdef _WIN32
    const char *override = getenv("XU_GAME_SDL_LIBRARY");
    HMODULE library = LoadLibraryA(override && *override ? override : "SDL3.dll");
#define FIND(name) GetProcAddress(library, #name)
#define UNLOAD() FreeLibrary(library)
#else
    void *library = NULL;
    const char *override = getenv("XU_GAME_SDL_LIBRARY");
    if (override && *override) library = dlopen(override, RTLD_NOW | RTLD_LOCAL);
#ifdef __APPLE__
    const char *candidates[] = {"libSDL3.dylib", "/opt/homebrew/lib/libSDL3.dylib", "/usr/local/lib/libSDL3.dylib"};
#else
    const char *candidates[] = {"libSDL3.so.0", "libSDL3.so"};
#endif
    if (!override || !*override) {
        for (size_t i = 0; !library && i < sizeof(candidates) / sizeof(candidates[0]); ++i)
            library = dlopen(candidates[i], RTLD_NOW | RTLD_LOCAL);
    }
#define FIND(name) dlsym(library, #name)
#define UNLOAD() dlclose(library)
#endif
    if (!library) { fail("SDL 3.4+ runtime not found; install SDL3 or set XU_GAME_SDL_LIBRARY"); return false; }
#define LOAD(name) p_##name = (__typeof__(name) *)FIND(name); \
    if (!p_##name) { fail("SDL 3.4+ is required: missing " #name); UNLOAD(); return false; }
    SDL_FUNCTIONS(LOAD)
    // This bridge is first entered by Xu's main function, never a worker.
    p_SDL_SetMainReady();
    library_ready = true;
    return true;
}
static Renderer *lookup(xu_int handle) {
    if (!library_ready) { fail("GPU renderer is not open"); return NULL; }
    if (!main_thread()) return NULL;
    if (handle <= 0) { fail("closed GPU renderer"); return NULL; }
    uint64_t value = (uint64_t)handle - 1;
    Renderer *r = &renderers[value % MAX_RENDERERS];
    if (!r->renderer || r->generation != value / MAX_RENDERERS) {
        fail("stale GPU renderer handle"); return NULL;
    }
    return r;
}
static bool copy_text(const xu_i64_span *source, char *out, size_t capacity) {
    if (!source || source->len < 1 || (uint64_t)source->len >= capacity || !source->data) {
        fail("text length outside native limit"); return false;
    }
    for (xu_int i = 0; i < source->len; ++i) {
        if (source->data[i] <= 0 || source->data[i] > 255) { fail("invalid UTF-8 byte or embedded NUL"); return false; }
        out[i] = (char)source->data[i];
    }
    out[source->len] = 0;
    return true;
}
static void destroy(Renderer *r) {
    xu_int owner = (xu_int)(r->generation * MAX_RENDERERS + (r - renderers) + 1);
    for (int i = 0; i < MAX_TEXTURES; ++i) {
        if (textures[i].texture && textures[i].owner == owner) {
            p_SDL_DestroyTexture(textures[i].texture);
            textures[i].texture = NULL;
        }
    }
    if (r->renderer) p_SDL_DestroyRenderer(r->renderer);
    if (r->device) p_SDL_DestroyGPUDevice(r->device);
    if (r->window) p_SDL_DestroyWindow(r->window);
    r->renderer = NULL; r->device = NULL; r->window = NULL;
    r->recording = false; r->frame_vertices = 0;
    r->texture_pixels = 0;
}
xu_int API(error_len)(void) { return (xu_int)strlen(last_error); }
xu_int API(error_byte)(xu_int index) {
    if (index < 0 || (uint64_t)index >= strlen(last_error)) return 0;
    return (unsigned char)last_error[index];
}
xu_int API(open)(const xu_i64_span *title, xu_int width, xu_int height, xu_int backend, xu_int hidden) {
    char title_text[512];
    if (!load_sdl() || !main_thread() || !copy_text(title, title_text, sizeof(title_text))) return -1;
    if (width < 1 || width > 16384 || height < 1 || height > 16384 || backend < 0 || backend > 3)
        return fail("invalid window size or GPU backend");
    int slot = -1;
    for (int i = 0; i < MAX_RENDERERS; ++i) if (!renderers[i].renderer) { slot = i; break; }
    if (slot < 0) return fail("GPU renderer capacity exceeded");
    if (!live_renderers && !p_SDL_InitSubSystem(SDL_INIT_VIDEO)) return sdl_fail();
    Renderer *r = &renderers[slot];
    const char *drivers[] = {NULL, "metal", "vulkan", "direct3d12"};
    r->window = p_SDL_CreateWindow(title_text, (int)width, (int)height,
        SDL_WINDOW_RESIZABLE | (hidden ? SDL_WINDOW_HIDDEN : 0));
    if (r->window) r->device = p_SDL_CreateGPUDevice(
        SDL_GPU_SHADERFORMAT_SPIRV | SDL_GPU_SHADERFORMAT_DXIL | SDL_GPU_SHADERFORMAT_MSL, false, drivers[backend]);
    if (r->device) r->renderer = p_SDL_CreateGPURenderer(r->device, r->window);
    if (!r->renderer) {
        sdl_fail(); destroy(r);
        if (!live_renderers) p_SDL_QuitSubSystem(SDL_INIT_VIDEO);
        return -1;
    }
    if (!p_SDL_GetGPURendererDevice(r->renderer)) {
        fail("SDL did not create a GPU renderer"); destroy(r);
        if (!live_renderers) p_SDL_QuitSubSystem(SDL_INIT_VIDEO);
        return -1;
    }
    if (!p_SDL_SetRenderVSync(r->renderer, 1) || !p_SDL_SetRenderDrawBlendMode(r->renderer, SDL_BLENDMODE_BLEND)) {
        sdl_fail(); destroy(r);
        if (!live_renderers) p_SDL_QuitSubSystem(SDL_INIT_VIDEO);
        return -1;
    }
    ++r->generation;
    ++live_renderers;
    return (xu_int)(r->generation * MAX_RENDERERS + (unsigned)slot + 1);
}
xu_int API(close)(xu_int handle) {
    Renderer *r = lookup(handle);
    if (!r) return -1;
    destroy(r);
    if (--live_renderers == 0) p_SDL_QuitSubSystem(SDL_INIT_VIDEO);
    return 0;
}
xu_int API(backend)(xu_int handle) {
    Renderer *r = lookup(handle);
    if (!r) return -1;
    const char *name = p_SDL_GetGPUDeviceDriver(r->device);
    if (!strcmp(name, "metal")) return 1;
    if (!strcmp(name, "vulkan")) return 2;
    if (!strcmp(name, "direct3d12")) return 3;
    return fail("unrecognized SDL GPU backend");
}
xu_int API(size)(xu_int handle, xu_int axis) {
    Renderer *r = lookup(handle);
    if (!r) return -1;
    int width, height;
    if (!p_SDL_GetRenderOutputSize(r->renderer, &width, &height)) return sdl_fail();
    return axis == 0 ? width : height;
}
xu_int API(begin)(xu_int handle, xu_int color) {
    Renderer *r = lookup(handle);
    if (!r) return -1;
    if (r->recording) return fail("frame already active");
    if (!p_SDL_SetRenderDrawColor(r->renderer, (Uint8)(color >> 24), (Uint8)(color >> 16),
        (Uint8)(color >> 8), (Uint8)color) || !p_SDL_RenderClear(r->renderer)) return sdl_fail();
    r->recording = true; r->frame_vertices = 0;
    return 0;
}
// Fixed-point positions (1/1024 pixel), packed RGBA8. Never retain Xu storage.
xu_int API(triangles)(xu_int handle, xu_int texture_handle, const xu_i64_span *words) {
    Renderer *r = lookup(handle);
    if (!r) return -1;
    if (!r->recording) return fail("begin a frame before submitting a batch");
    SDL_Texture *texture = NULL;
    if (texture_handle) {
        if (texture_handle < 0) return fail("invalid texture handle");
        uint64_t value = (uint64_t)texture_handle - 1;
        Texture *t = &textures[value % MAX_TEXTURES];
        if (!t->texture || t->generation != value / MAX_TEXTURES || t->owner != handle)
            return fail("stale texture or texture belongs to a different renderer");
        texture = t->texture;
    }
    if (!words || words->len < 0 || words->len % (VERTEX_WORDS * 3) ||
        words->len > (xu_int)MAX_VERTICES * VERTEX_WORDS || (words->len && !words->data))
    {
        snprintf(last_error, sizeof(last_error), "invalid triangle vertex span: words=%lld", words ? words->len : -1LL);
        return -1;
    }
    int count = (int)(words->len / VERTEX_WORDS);
    if (count > MAX_VERTICES - r->frame_vertices) return fail("GPU frame vertex limit exceeded");
    if (!count) return 0;
    SDL_Vertex *vertices = malloc((size_t)count * sizeof(*vertices));
    if (!vertices) return fail("GPU staging allocation failed");
    for (int i = 0; i < count; ++i) {
        xu_int x = words->data[i * VERTEX_WORDS], y = words->data[i * VERTEX_WORDS + 1];
        uint32_t c = (uint32_t)words->data[i * VERTEX_WORDS + 2];
        xu_int u = words->data[i * VERTEX_WORDS + 3], v = words->data[i * VERTEX_WORDS + 4];
        if (x < -1024000000LL || x > 1024000000LL || y < -1024000000LL || y > 1024000000LL ||
            u < 0 || u > 1048576 || v < 0 || v > 1048576) {
            free(vertices); return fail("GPU vertex coordinate out of range");
        }
        vertices[i].position = (SDL_FPoint){(float)x / 1024.0f, (float)y / 1024.0f};
        vertices[i].color = (SDL_FColor){(float)(c >> 24) / 255.0f, (float)((c >> 16) & 255) / 255.0f,
            (float)((c >> 8) & 255) / 255.0f, (float)(c & 255) / 255.0f};
        vertices[i].tex_coord = (SDL_FPoint){(float)u / 1048576.0f, (float)v / 1048576.0f};
    }
    bool ok = p_SDL_RenderGeometry(r->renderer, texture, vertices, count, NULL, 0);
    free(vertices);
    if (!ok) return sdl_fail();
    r->frame_vertices += count;
    return count / 3;
}
xu_int API(texture_new)(xu_int handle, xu_int width, xu_int height, const xu_i64_span *pixels, xu_int linear) {
    Renderer *r = lookup(handle);
    if (!r) return -1;
    if (width < 1 || width > 4096 || height < 1 || height > 4096 || width * height > 4194304 ||
        !pixels || pixels->len != width * height || !pixels->data) return fail("invalid texture dimensions or RGBA span");
    if (width * height > 16777216 - r->texture_pixels) return fail("renderer texture budget exceeds 64 MiB");
    int slot = -1;
    for (int i = 0; i < MAX_TEXTURES; ++i) if (!textures[i].texture) { slot = i; break; }
    if (slot < 0) return fail("texture capacity exceeded");
    Uint8 *bytes = malloc((size_t)(width * height * 4));
    if (!bytes) return fail("texture staging allocation failed");
    for (xu_int i = 0; i < pixels->len; ++i) {
        xu_int color = pixels->data[i];
        if (color < 0 || (xu_uint)color > UINT32_MAX) { free(bytes); return fail("invalid RGBA pixel"); }
        bytes[i * 4] = (Uint8)(color >> 24); bytes[i * 4 + 1] = (Uint8)(color >> 16);
        bytes[i * 4 + 2] = (Uint8)(color >> 8); bytes[i * 4 + 3] = (Uint8)color;
    }
    SDL_Texture *texture = p_SDL_CreateTexture(r->renderer, SDL_PIXELFORMAT_RGBA32, SDL_TEXTUREACCESS_STATIC, (int)width, (int)height);
    bool ok = texture && p_SDL_UpdateTexture(texture, NULL, bytes, (int)width * 4) &&
        p_SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_BLEND) &&
        p_SDL_SetTextureScaleMode(texture, linear ? SDL_SCALEMODE_LINEAR : SDL_SCALEMODE_NEAREST);
    free(bytes);
    if (!ok) { sdl_fail(); if (texture) p_SDL_DestroyTexture(texture); return -1; }
    Texture *t = &textures[slot];
    t->texture = texture; t->owner = handle; t->pixels = (int)(width * height); ++t->generation;
    r->texture_pixels += t->pixels;
    return (xu_int)(t->generation * MAX_TEXTURES + (unsigned)slot + 1);
}
xu_int API(texture_close)(xu_int handle, xu_int texture_handle) {
    if (!library_ready || !main_thread()) return -1;
    if (texture_handle <= 0) return fail("closed texture");
    uint64_t value = (uint64_t)texture_handle - 1;
    Texture *t = &textures[value % MAX_TEXTURES];
    // Renderer teardown already released this generation. Closing its owner is safe.
    if (!t->texture || t->generation != value / MAX_TEXTURES) return 0;
    if (t->owner != handle) return fail("texture belongs to a different renderer");
    Renderer *r = lookup(handle);
    if (!r) return -1;
    r->texture_pixels -= t->pixels;
    p_SDL_DestroyTexture(t->texture); t->texture = NULL;
    return 0;
}
xu_int API(present)(xu_int handle) {
    Renderer *r = lookup(handle);
    if (!r) return -1;
    if (!r->recording) return fail("no GPU frame active");
    if (!p_SDL_RenderPresent(r->renderer)) return sdl_fail();
    r->recording = false;
    return 0;
}
xu_int API(read_pixel)(xu_int handle, xu_int x, xu_int y) {
    Renderer *r = lookup(handle);
    if (!r) return -1;
    if (!r->recording || x < 0 || x > 16383 || y < 0 || y > 16383) return fail("invalid readback state or pixel");
    SDL_Rect rectangle = {(int)x, (int)y, 1, 1};
    SDL_Surface *surface = p_SDL_RenderReadPixels(r->renderer, &rectangle);
    if (!surface) return sdl_fail();
    Uint8 red, green, blue, alpha;
    bool ok = p_SDL_ReadSurfacePixel(surface, 0, 0, &red, &green, &blue, &alpha);
    p_SDL_DestroySurface(surface);
    if (!ok) return sdl_fail();
    return (xu_int)(((uint32_t)red << 24) | ((uint32_t)green << 16) | ((uint32_t)blue << 8) | alpha);
}
xu_int API(capture)(xu_int handle, const xu_i64_span *path) {
    Renderer *r = lookup(handle);
    char filename[4096];
    if (!r || !copy_text(path, filename, sizeof(filename))) return -1;
    if (!r->recording) return fail("capture must precede present");
    SDL_Surface *surface = p_SDL_RenderReadPixels(r->renderer, NULL);
    if (!surface) return sdl_fail();
    bool ok = p_SDL_SavePNG(surface, filename);
    p_SDL_DestroySurface(surface);
    return ok ? 0 : sdl_fail();
}
// Event output is [kind, code, x, y, repeated]. Only one event drain is supported.
xu_int API(poll)(xu_int handle, const xu_i64_span_mut *output) {
    Renderer *r = lookup(handle);
    if (!r) return -1;
    if (live_renderers != 1) return fail("event polling currently requires one live window");
    if (!output || output->len != 5 || !output->data) return fail("invalid event output span");
    for (int i = 0; i < 5; ++i) output->data[i] = 0;
    SDL_Event event;
    // Bound ignored event work so the caller retains control during event floods.
    for (int count = 0; count < 1024 && p_SDL_PollEvent(&event); ++count) {
        if (event.type == SDL_EVENT_QUIT) { output->data[0] = 1; return 1; }
        if (event.type == SDL_EVENT_WINDOW_CLOSE_REQUESTED && event.window.windowID == p_SDL_GetWindowID(r->window)) {
            output->data[0] = 1; return 1;
        }
        if ((event.type == SDL_EVENT_KEY_DOWN || event.type == SDL_EVENT_KEY_UP) &&
            event.key.windowID == p_SDL_GetWindowID(r->window)) {
            output->data[0] = event.type == SDL_EVENT_KEY_DOWN ? 2 : 3;
            output->data[1] = event.key.scancode; output->data[4] = event.key.repeat; return 1;
        }
        if (event.type == SDL_EVENT_WINDOW_FOCUS_LOST && event.window.windowID == p_SDL_GetWindowID(r->window)) {
            output->data[0] = 4; return 1;
        }
        if ((event.type == SDL_EVENT_MOUSE_BUTTON_DOWN || event.type == SDL_EVENT_MOUSE_BUTTON_UP) &&
            event.button.windowID == p_SDL_GetWindowID(r->window)) {
            output->data[0] = event.type == SDL_EVENT_MOUSE_BUTTON_DOWN ? 5 : 6;
            output->data[1] = event.button.button;
            output->data[2] = (xu_int)event.button.x; output->data[3] = (xu_int)event.button.y; return 1;
        }
        if (event.type == SDL_EVENT_MOUSE_MOTION && event.motion.windowID == p_SDL_GetWindowID(r->window)) {
            output->data[0] = 7; output->data[2] = (xu_int)event.motion.x; output->data[3] = (xu_int)event.motion.y; return 1;
        }
    }
    return 0;
}
