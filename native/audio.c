// Audio device transport only. Mixing, resampling and playback state live in Xu.
#define SDL_MAIN_HANDLED
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include "xu_native.h"
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
#define API(name) XU_NATIVE_SYMBOL(xu_nexus_audio_native_##name)
#define FUNCTIONS(X) \
    X(SDL_SetMainReady) X(SDL_IsMainThread) X(SDL_InitSubSystem) X(SDL_QuitSubSystem) X(SDL_GetError) \
    X(SDL_OpenAudioDeviceStream) X(SDL_DestroyAudioStream) X(SDL_PauseAudioStreamDevice) \
    X(SDL_ResumeAudioStreamDevice) X(SDL_GetAudioStreamQueued) X(SDL_PutAudioStreamData) \
    X(SDL_ClearAudioStream) X(SDL_GetCurrentAudioDriver) X(SDL_AddEventWatch) X(SDL_GetHint) X(SDL_SetHint) X(SDL_RunOnMainThread)
#define DECLARE(name) static __typeof__(name) *p_##name;
FUNCTIONS(DECLARE)
enum { MAX_OUTPUTS = 8, MAX_BLOCK = 4096, MAX_QUEUED = 24000 };
typedef struct { SDL_AudioStream *stream; uint64_t generation; int rate;
    bool desired_paused, failed; char failure[256]; } Output;
static Output outputs[MAX_OUTPUTS];
static int live_outputs;
static bool ready;
static _Thread_local char last_error[1024];
static xu_int fail(const char *message) { snprintf(last_error, sizeof(last_error), "%s", message ? message : "unknown audio error"); return -1; }
static xu_int sdl_fail(void) { return fail(p_SDL_GetError()); }
#include "audio_lifecycle.h"
static bool load_sdl(void) {
    if (ready) return true;
#if defined(XU_PHONE_GAME_LINK)
    if (!SDL_IsMainThread()) { fail("open audio on the SDL owner thread"); return false; }
#elif defined(__APPLE__)
    if (!pthread_main_np()) { fail("open audio on the owner main thread"); return false; }
#endif
#if defined(XU_PHONE_GAME_LINK)
    void *library = (void *)1;
#define FIND(name) (&name)
#define UNLOAD() ((void)0)
#else
    const char *override = getenv("XU_NEXUS_SDL_AUDIO_LIBRARY");
#ifdef _WIN32
    HMODULE library = LoadLibraryA(override && *override ? override : "SDL3.dll");
#define FIND(name) ((void *)GetProcAddress(library, #name))
#define UNLOAD() FreeLibrary(library)
#else
    void *library = NULL;
    if (override && *override) library = dlopen(override, RTLD_NOW | RTLD_LOCAL);
#ifdef __APPLE__
    const char *candidates[] = {"libSDL3.dylib", "/opt/homebrew/lib/libSDL3.dylib", "/usr/local/lib/libSDL3.dylib"};
#else
    const char *candidates[] = {"libSDL3.so.0", "libSDL3.so"};
#endif
    if (!override || !*override) {
        for (size_t i = 0; !library && i < sizeof(candidates) / sizeof(candidates[0]); ++i) library = dlopen(candidates[i], RTLD_NOW | RTLD_LOCAL);
    }
#define FIND(name) dlsym(library, #name)
#define UNLOAD() dlclose(library)
#endif
#endif
    if (!library) { fail("SDL audio runtime not found; set XU_NEXUS_SDL_AUDIO_LIBRARY"); return false; }
#define LOAD(name) p_##name = (__typeof__(name) *)FIND(name); \
    if (!p_##name) { fail("SDL audio is missing " #name); UNLOAD(); return false; }
    FUNCTIONS(LOAD)
#ifndef XU_PHONE_GAME_LINK
    p_SDL_SetMainReady();
#endif
    if (!configure_audio_lifecycle()) return false;
    ready = true; return true;
}
static Output *lookup(xu_int handle, bool allow_failed) {
    if (!ready || !p_SDL_IsMainThread()) { fail("audio calls require the owner main thread"); return NULL; }
    if (handle <= 0) { fail("closed audio output"); return NULL; }
    uint64_t value = (uint64_t)handle - 1;
    Output *output = &outputs[value % MAX_OUTPUTS];
    if (!output->stream || output->generation != value / MAX_OUTPUTS) { fail("stale audio output"); return NULL; }
    if (output->failed && !allow_failed) { fail(output->failure); return NULL; }
    return output;
}
xu_int API(error_len)(void) { return (xu_int)strlen(last_error); }
xu_int API(error_byte)(xu_int index) { return index >= 0 && (uint64_t)index < strlen(last_error) ? (unsigned char)last_error[index] : 0; }
static xu_int operation_open(xu_int rate) {
    if (!load_sdl()) return -1;
    if (!p_SDL_IsMainThread()) return fail("open audio on the owner main thread");
    if (rate < 8000 || rate > 192000) return fail("invalid audio sample rate");
    int slot = -1;
    for (int i = 0; i < MAX_OUTPUTS; ++i) if (!outputs[i].stream) { slot = i; break; }
    if (slot < 0) return fail("audio output capacity exceeded");
    if (!live_outputs && !p_SDL_InitSubSystem(SDL_INIT_AUDIO)) return sdl_fail();
    SDL_AudioSpec spec = {.format = SDL_AUDIO_S16, .channels = 2, .freq = (int)rate};
    SDL_AudioStream *stream = p_SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, NULL, NULL);
    if (!stream) { sdl_fail(); if (!live_outputs) p_SDL_QuitSubSystem(SDL_INIT_AUDIO); return -1; }
    Output *output = &outputs[slot];
    output->stream = stream; output->rate = (int)rate;
    output->desired_paused = true; output->failed = false; output->failure[0] = 0; ++output->generation; ++live_outputs;
    return (xu_int)(output->generation * MAX_OUTPUTS + (unsigned)slot + 1);
}
static xu_int operation_close(xu_int handle) {
    Output *output = lookup(handle, true);
    if (!output) return -1;
    p_SDL_DestroyAudioStream(output->stream); output->stream = NULL;
    if (--live_outputs == 0) p_SDL_QuitSubSystem(SDL_INIT_AUDIO);
    return 0;
}
static xu_int operation_pause(xu_int handle, xu_int paused) {
    Output *output = lookup(handle, false);
    if (!output) return -1;
    if (paused != 0 && paused != 1) return fail("invalid audio pause flag");
    bool ok = paused || is_audio_background() ? p_SDL_PauseAudioStreamDevice(output->stream) : p_SDL_ResumeAudioStreamDevice(output->stream);
    if (!ok) return sdl_fail();
    output->desired_paused = paused != 0;
    return 0;
}
static xu_int operation_queued(xu_int handle) {
    Output *output = lookup(handle, false);
    if (!output) return -1;
    int bytes = p_SDL_GetAudioStreamQueued(output->stream);
    return bytes < 0 ? sdl_fail() : bytes / 4;
}
static xu_int operation_submit(xu_int handle, const xu_i64_span *samples) {
    Output *output = lookup(handle, false);
    if (!output) return -1;
    if (!samples || !samples->data || samples->len < 2 || samples->len % 2 || samples->len > MAX_BLOCK * 2)
        return fail("invalid interleaved audio sample span");
    int queued = p_SDL_GetAudioStreamQueued(output->stream);
    if (queued < 0) return sdl_fail();
    if (queued / 4 > MAX_QUEUED - samples->len / 2) return fail("audio queue frame budget exceeded");
    int16_t staging[MAX_BLOCK * 2];
    for (xu_int i = 0; i < samples->len; ++i) {
        if (samples->data[i] < -32768 || samples->data[i] > 32767) return fail("sample outside signed PCM16");
        staging[i] = (int16_t)samples->data[i];
    }
    // SDL copies synchronously. No callbacks, Xu references or staging are retained.
    return p_SDL_PutAudioStreamData(output->stream, staging, (int)(samples->len * 2)) ? samples->len / 2 : sdl_fail();
}
static xu_int operation_clear(xu_int handle) { Output *output = lookup(handle, false);
    return !output ? -1 : p_SDL_ClearAudioStream(output->stream) ? 0 : sdl_fail(); }
static xu_int operation_driver_len(xu_int handle) {
    if (!lookup(handle, false)) return -1;
    const char *name = p_SDL_GetCurrentAudioDriver();
    return name ? (xu_int)strlen(name) : fail("audio driver unavailable");
}
static xu_int operation_driver_byte(xu_int handle, xu_int index) {
    if (!lookup(handle, false)) return -1;
    const char *name = p_SDL_GetCurrentAudioDriver();
    if (!name || index < 0 || (uint64_t)index >= strlen(name)) return fail("invalid audio driver byte");
    return (unsigned char)name[index];
}

// All output state is owner-thread-only, including deferred lifecycle work.
#define WRAP0(name) xu_int API(name)(xu_int handle) { if (!audio_enter()) return -1; xu_int result=operation_##name(handle); audio_leave(); return result; }
WRAP0(close)
WRAP0(queued)
WRAP0(clear)
WRAP0(driver_len)
xu_int API(open)(xu_int rate) { if (!audio_enter()) return -1; xu_int result=operation_open(rate); audio_leave(); return result; }
xu_int API(pause)(xu_int handle,xu_int paused) { if (!audio_enter()) return -1; xu_int result=operation_pause(handle,paused); audio_leave(); return result; }
xu_int API(submit)(xu_int handle,const xu_i64_span *samples) { if (!audio_enter()) return -1; xu_int result=operation_submit(handle,samples); audio_leave(); return result; }
xu_int API(driver_byte)(xu_int handle,xu_int index) { if (!audio_enter()) return -1; xu_int result=operation_driver_byte(handle,index); audio_leave(); return result; }
