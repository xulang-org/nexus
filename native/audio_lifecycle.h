/* SDL platform lifecycle transport. Never invokes Xu or retains its samples.
 * Event watches run under SDL's watcher lock and may be on another thread;
 * they must never wait on a lock held by an audio open/close operation. */
#ifdef XU_PHONE_GAME_LINK
#include <stdatomic.h>
static atomic_bool audio_background, audio_dispatch_pending;
static atomic_uint_fast64_t audio_generation;
static uint_fast64_t audio_applied_generation;
static bool audio_busy;
static void lifecycle_failure(Output *output) {
    if (!output->failed) {
        snprintf(output->failure,sizeof(output->failure),"audio lifecycle: %s",p_SDL_GetError());
        output->failed=true;
    }
}
static void apply_audio_lifecycle(void) {
    uint_fast64_t generation=atomic_load(&audio_generation);
    if (generation==audio_applied_generation) return;
    bool background=atomic_load(&audio_background);
    for (int i=0;i<MAX_OUTPUTS;++i) {
        Output *output=&outputs[i];
        if (!output->stream) continue;
        if (!p_SDL_PauseAudioStreamDevice(output->stream)) lifecycle_failure(output);
        // Clear on both sides: a last in-flight Xu frame may submit after the
        // background notification, before its cooperative frame boundary.
        if (!p_SDL_ClearAudioStream(output->stream)) lifecycle_failure(output);
        if (!background && !output->desired_paused && !output->failed &&
            !p_SDL_ResumeAudioStreamDevice(output->stream)) lifecycle_failure(output);
    }
    audio_applied_generation=generation;
}
static void SDLCALL audio_on_owner(void *unused) {
    (void)unused;
    atomic_store(&audio_dispatch_pending,false);
    if (audio_busy) return; // The enclosing operation applies pending state.
    audio_busy=true;
    apply_audio_lifecycle();
    audio_busy=false;
}
static bool SDLCALL audio_lifecycle(void *unused, SDL_Event *event) {
    (void)unused;
    if (event->type!=SDL_EVENT_WILL_ENTER_BACKGROUND && event->type!=SDL_EVENT_DID_ENTER_FOREGROUND &&
        event->type!=SDL_EVENT_TERMINATING) return true;
    atomic_store(&audio_background,event->type!=SDL_EVENT_DID_ENTER_FOREGROUND);
    atomic_fetch_add(&audio_generation,1);
    if (SDL_IsMainThread()) {
        if (!audio_busy) audio_on_owner(NULL);
    } else if (!atomic_exchange(&audio_dispatch_pending,true)) {
        if (!p_SDL_RunOnMainThread(audio_on_owner,NULL,false)) {
            atomic_store(&audio_dispatch_pending,false);
            fprintf(stderr,"game audio lifecycle dispatch: %s\n",p_SDL_GetError());
        }
    }
    return true;
}
static bool audio_enter(void) {
    if (!SDL_IsMainThread()) { fail("audio calls require the SDL owner thread"); return false; }
    if (audio_busy) { fail("audio calls cannot reenter the transport"); return false; }
    audio_busy=true;
    if (ready) apply_audio_lifecycle();
    return true;
}
static void audio_leave(void) {
    if (ready) apply_audio_lifecycle();
    audio_busy=false;
}
static bool is_audio_background(void) { return atomic_load(&audio_background); }
static bool configure_audio_lifecycle(void) {
    // Respect an explicit SDL category. The game default mixes with other apps
    // and follows the silent switch. Playback only: no microphone permission.
    if (!p_SDL_GetHint(SDL_HINT_AUDIO_CATEGORY)) p_SDL_SetHint(SDL_HINT_AUDIO_CATEGORY,"ambient");
    if (!p_SDL_AddEventWatch(audio_lifecycle,NULL)) { sdl_fail(); return false; }
    // One stable watch until SDL shutdown; closing an output releases no
    // callback-owned pointer, and the watch never reads slots off the owner.
    return true;
}
#else
static bool audio_enter(void) { return true; }
static void audio_leave(void) {}
static bool is_audio_background(void) { return false; }
static bool configure_audio_lifecycle(void) { return true; }
#endif
