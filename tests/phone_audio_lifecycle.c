#define XU_PHONE_GAME_LINK 1
#include "../native/audio.c"
#include <assert.h>
#include <pthread.h>

static void *post(void *kind) {
    SDL_Event event={0}; event.type=(Uint32)(uintptr_t)kind;
    assert(SDL_PushEvent(&event));
    return NULL;
}
static void transition(Uint32 kind) {
    pthread_t thread;
    assert(!pthread_create(&thread,NULL,post,(void *)(uintptr_t)kind));
    assert(!pthread_join(thread,NULL));
    SDL_PumpEvents(); // Deliver nonblocking owner-thread lifecycle work.
}
static void *flood(void *unused) {
    (void)unused;
    for (int i=0;i<200;++i) {
        SDL_Event event={0};
        event.type=i%2 ? SDL_EVENT_DID_ENTER_FOREGROUND : SDL_EVENT_WILL_ENTER_BACKGROUND;
        assert(SDL_PushEvent(&event));
    }
    return NULL;
}
int main(void) {
    SDL_SetMainReady();
    assert(SDL_Init(SDL_INIT_VIDEO));
    xu_int first=API(open)(48000), second=API(open)(48000);
    assert(first>0 && second>0);
    Output *a=lookup(first,false), *b=lookup(second,false);
    assert(a && b && SDL_AudioStreamDevicePaused(a->stream));
    xu_int values[2048]={0}; xu_i64_span samples={2048,values};
    assert(API(submit)(first,&samples)==1024);
    assert(API(submit)(second,&samples)==1024);
    assert(API(pause)(first,0)==0);
    transition(SDL_EVENT_WILL_ENTER_BACKGROUND);
    assert(is_audio_background());
    assert(SDL_AudioStreamDevicePaused(a->stream) && SDL_AudioStreamDevicePaused(b->stream));
    assert(API(queued)(first)==0 && API(queued)(second)==0);
    // A final in-flight frame may enqueue while suspended. It must not play
    // in the background or survive the foreground transition.
    assert(API(submit)(first,&samples)==1024);
    SDL_Delay(40);
    assert(API(queued)(first)==1024);
    transition(SDL_EVENT_DID_ENTER_FOREGROUND);
    assert(!is_audio_background() && API(queued)(first)==0);
    assert(!SDL_AudioStreamDevicePaused(a->stream));
    assert(SDL_AudioStreamDevicePaused(b->stream)); // User pause is preserved.
    assert(API(submit)(first,&samples)==1024);
    bool consumed=false;
    for (int i=0;i<50;++i) { SDL_Delay(10); if(API(queued)(first)<1024) { consumed=true; break; } }
    assert(consumed);
    // Concurrent lifecycle delivery must not deadlock an open/close operation.
    pthread_t thread;
    assert(!pthread_create(&thread,NULL,flood,NULL));
    for (int i=0;i<25;++i) { xu_int extra=API(open)(48000); assert(extra>0); assert(API(close)(extra)==0); }
    assert(!pthread_join(thread,NULL));
    transition(SDL_EVENT_DID_ENTER_FOREGROUND);
    assert(API(close)(first)==0 && API(close)(second)==0);
    assert(live_outputs==0);
    SDL_Quit();
    puts("phone audio: owner dispatch, background clear, desired pause, resume consumption and concurrent lifetime PASS");
}
