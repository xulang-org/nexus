#ifdef _WIN32
#ifndef _CRT_SECURE_NO_WARNINGS
#define _CRT_SECURE_NO_WARNINGS
#endif
#endif
// CPU PNG transport only. No video/audio initialization, windows or GPU APIs.
#include <SDL3/SDL.h>
#include "xu_native.h"
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif
#define API(name) XU_NATIVE_SYMBOL(xu_nexus_image_native_##name)
#define FUNCTIONS(X) X(SDL_GetError) X(SDL_IOFromConstMem) X(SDL_LoadPNG_IO) X(SDL_ReadSurfacePixel) X(SDL_DestroySurface)
#define DECLARE(name) static __typeof__(name) *p_##name;
FUNCTIONS(DECLARE)
static atomic_flag loading=ATOMIC_FLAG_INIT;
static atomic_bool ready;
static _Thread_local char error_text[1024];
static xu_int fail(const char *message) {snprintf(error_text,sizeof(error_text),"%s",message);return -1;}
static bool load_codec(void) {
    if (atomic_load_explicit(&ready,memory_order_acquire)) return true;
    while (atomic_flag_test_and_set_explicit(&loading,memory_order_acquire)) {}
    if (atomic_load_explicit(&ready,memory_order_relaxed)) {atomic_flag_clear_explicit(&loading,memory_order_release);return true;}
#if defined(XU_PHONE_GAME_LINK)
    void *library=(void *)1;
#define FIND(name) (&name)
#define UNLOAD() ((void)0)
#elif defined(_WIN32)
    DWORD length=GetEnvironmentVariableW(L"XU_SDL_LIBRARY",NULL,0);
    wchar_t *path=length ? calloc(length,sizeof(*path)) : NULL;
    if (length && !path) { fail("PNG library path allocation failed");goto failed; }
    if (path) {
        DWORD actual=GetEnvironmentVariableW(L"XU_SDL_LIBRARY",path,length);
        if (!actual || actual>=length) {free(path);fail("PNG library path changed while loading");goto failed;}
    }
    HMODULE library=LoadLibraryW(path ? path : L"SDL3.dll");free(path);
#define FIND(name) ((void *)GetProcAddress(library,#name))
#define UNLOAD() FreeLibrary(library)
#else
    const char *override=getenv("XU_SDL_LIBRARY");
    void *library=override && *override ? dlopen(override,RTLD_NOW|RTLD_LOCAL) : NULL;
#ifdef __APPLE__
    const char *paths[]={"libSDL3.dylib","/opt/homebrew/lib/libSDL3.dylib","/usr/local/lib/libSDL3.dylib"};
#else
    const char *paths[]={"libSDL3.so.0","libSDL3.so"};
#endif
    if (!override || !*override) for (size_t i=0;!library && i<sizeof(paths)/sizeof(*paths);++i) library=dlopen(paths[i],RTLD_NOW|RTLD_LOCAL);
#define FIND(name) dlsym(library,#name)
#define UNLOAD() dlclose(library)
#endif
    if (!library) {fail("SDL 3.4+ PNG runtime unavailable; set XU_SDL_LIBRARY");goto failed;}
#define LOAD(name) p_##name=(__typeof__(name) *)FIND(name); \
    if (!p_##name) {fail("SDL PNG runtime is missing " #name);UNLOAD();goto failed;}
    FUNCTIONS(LOAD)
    atomic_store_explicit(&ready,true,memory_order_release);
    atomic_flag_clear_explicit(&loading,memory_order_release);return true;
failed:
    atomic_flag_clear_explicit(&loading,memory_order_release);return false;
}
xu_int API(error_len)(void) {return (xu_int)strlen(error_text);}
xu_int API(error_byte)(xu_int index) {return index>=0 && (xu_uint)index<strlen(error_text) ? (unsigned char)error_text[index] : 0;}
static Uint32 word(const unsigned char *p) {return ((Uint32)p[0]<<24)|((Uint32)p[1]<<16)|((Uint32)p[2]<<8)|p[3];}
xu_int API(decode_png)(const xu_u8_span *source,xu_int width,xu_int height,const xu_i64_span_mut *output) {
    if (!source || !source->data || source->len<33 || source->len>32*1024*1024 || width<1 || height<1 ||
        width>4096 || height>4096 || width*height>4194304 || !output || !output->data || output->len!=width*height)
        return fail("invalid PNG input/dimensions/output");
    const unsigned char *data=source->data;
    if (memcmp(data,"\x89PNG\r\n\x1a\n",8) || word(data+8)!=13 || memcmp(data+12,"IHDR",4) ||
        word(data+16)!=(Uint32)width || word(data+20)!=(Uint32)height) return fail("PNG signature/dimensions differ from output");
    if (!load_codec()) return -1;
    SDL_IOStream *memory=p_SDL_IOFromConstMem(data,(size_t)source->len);
    if (!memory) return fail(p_SDL_GetError());
    SDL_Surface *surface=p_SDL_LoadPNG_IO(memory,true);
    if (!surface) return fail(p_SDL_GetError());
    if (surface->w!=(int)width || surface->h!=(int)height) {p_SDL_DestroySurface(surface);return fail("PNG decoded dimensions differ from IHDR");}
    for (int y=0;y<(int)height;++y) for (int x=0;x<(int)width;++x) {
        Uint8 r,g,b,a;
        if (!p_SDL_ReadSurfacePixel(surface,x,y,&r,&g,&b,&a)) {fail(p_SDL_GetError());p_SDL_DestroySurface(surface);return -1;}
        output->data[(size_t)y*(size_t)width+(size_t)x]=(xu_int)(((Uint32)r<<24)|((Uint32)g<<16)|((Uint32)b<<8)|a);
    }
    p_SDL_DestroySurface(surface);return 0;
}
