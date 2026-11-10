/* hle_openal.c - host OpenAL 1.0 adapter for ALAudio.dll, standing in for the game's DefOpenAL32.dll.
 *
 * ALAudio.dll (translated) loads its OpenAL driver with appGetDllHandle("OpenAL32.dll"), which does not exist,
 * then "DefOpenAL32.dll" (Creative's software/DirectSound3D implementation, shipped in System). That DLL is not
 * translated: its own mixer, DirectSound3D/waveOut back ends and timer-callback threads would all run as guest
 * code. Instead LoadLibrary gives the guest a module identity backed by this adapter (hle_kernel32.c): every
 * export name is checked against the game's DefOpenAL32.dll export table, implemented entry points reach the
 * functions below, the others are explicit traps (fatal if called).
 *
 * The OpenAL 1.0 semantics are implemented here on XAudio2 2.9 (the host's mixer and resampler):
 *  - a buffer is an immutable reference-counted PCM block (8/16-bit, mono/stereo); alBufferData replaces the block,
 *    so data XAudio2 may still read is never changed or freed;
 *  - a source plays its buffer queue on an XAudio2 source voice of the buffer format (voices are pooled; a stopped
 *    voice keeps its blocks until XAudio2 reports its queue empty);
 *  - state machine INITIAL/PLAYING/PAUSED/STOPPED, AL_BUFFERS_QUEUED/PROCESSED, queue/unqueue, looping;
 *  - mono sources are spatialised: distance models AL_NONE / AL_INVERSE_DISTANCE / AL_INVERSE_DISTANCE_CLAMPED
 *    (OpenAL 1.0 formula), constant-power stereo pan from the listener frame (AL_SOURCE_RELATIVE: position in
 *    the listener frame), Doppler with a 343.3 m/s speed of sound times AL_DOPPLER_VELOCITY (ALAudio passes
 *    metres: 0.0127 per Unreal unit); stereo sources are not spatialised (gain only, as in Creative's driver);
 *  - parameter changes made while the context is suspended (ALAudio's Update brackets) are committed at
 *    alcProcessContext; play/stop/pause take effect at once.
 * Not modelled (reported once if used): EAX (alIsExtensionPresent("EAX3.0") is AL_FALSE, which ALAudio checks
 * before using it), sound cones, AL_MIN/MAX_DISTANCE effects other than the clamp.
 * Evidence: openal_* events (device, first plays, mix levels from an XAudio2 volume meter on the submix feeding the mastering voice,
 * i.e. what was actually mixed for the output device) and a summary at close. XRT_DEV_SOUND=muted keeps the
 * whole pipeline running but sets the mastering volume to 0 (the meter is on the submix all sources feed). */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <xaudio2.h>
#include <xaudio2fx.h>
#include <math.h>
#include <float.h>
#include <stdlib.h>
#include <string.h>
#include "xrt_internal.h"

#define AL_NONE 0
#define AL_SOURCE_RELATIVE 0x202
#define AL_CONE_INNER_ANGLE 0x1001
#define AL_CONE_OUTER_ANGLE 0x1002
#define AL_PITCH 0x1003
#define AL_POSITION 0x1004
#define AL_DIRECTION 0x1005
#define AL_VELOCITY 0x1006
#define AL_LOOPING 0x1007
#define AL_BUFFER 0x1009
#define AL_GAIN 0x100A
#define AL_MIN_GAIN 0x100D
#define AL_MAX_GAIN 0x100E
#define AL_ORIENTATION 0x100F
#define AL_SOURCE_STATE 0x1010
#define AL_INITIAL 0x1011
#define AL_PLAYING 0x1012
#define AL_PAUSED 0x1013
#define AL_STOPPED 0x1014
#define AL_BUFFERS_QUEUED 0x1015
#define AL_BUFFERS_PROCESSED 0x1016
#define AL_REFERENCE_DISTANCE 0x1020
#define AL_ROLLOFF_FACTOR 0x1021
#define AL_CONE_OUTER_GAIN 0x1022
#define AL_MAX_DISTANCE 0x1023
#define AL_FORMAT_MONO8 0x1100
#define AL_FORMAT_MONO16 0x1101
#define AL_FORMAT_STEREO8 0x1102
#define AL_FORMAT_STEREO16 0x1103
#define AL_FREQUENCY 0x2001
#define AL_BITS 0x2002
#define AL_CHANNELS 0x2003
#define AL_SIZE 0x2004
#define AL_INVALID_NAME 0xA001
#define AL_INVALID_ENUM 0xA002
#define AL_INVALID_VALUE 0xA003
#define AL_INVALID_OPERATION 0xA004
#define AL_OUT_OF_MEMORY 0xA005
#define AL_VENDOR 0xB001
#define AL_VERSION 0xB002
#define AL_RENDERER 0xB003
#define AL_EXTENSIONS 0xB004
#define AL_DOPPLER_FACTOR 0xC000
#define AL_DOPPLER_VELOCITY 0xC001
#define AL_DISTANCE_MODEL 0xD000
#define AL_INVERSE_DISTANCE 0xD001
#define AL_INVERSE_DISTANCE_CLAMPED 0xD002
#define ALC_MAJOR_VERSION 0x1000
#define ALC_MINOR_VERSION 0x1001
#define ALC_DEFAULT_DEVICE_SPECIFIER 0x1004
#define ALC_DEVICE_SPECIFIER 0x1005
#define ALC_EXTENSIONS 0x1006
#define ALC_FREQUENCY 0x1007
#define ALC_INVALID_DEVICE 0xA001
#define ALC_INVALID_CONTEXT 0xA002
#define ALC_INVALID_ENUM 0xA003
#define ALC_INVALID_VALUE 0xA004

#define MAX_SOURCES 256
#define MAX_QUEUE 16
#define MAX_VOICES 160
#define MAX_RATIO 8.0f

typedef struct Pcm { LONG refs; uint32_t size; uint8_t data[1]; } Pcm;
typedef struct Buffer { int live; uint32_t format, freq, channels, bits; Pcm* pcm; int queued; } Buffer;
typedef struct Entry { Pcm* pcm; } Entry;   /* NULL pcm: an empty buffer (complete as soon as it is at the head) */
typedef struct Voice {
    IXAudio2VoiceCallback cb;      /* OnBufferEnd counts finished/flushed submissions (XAudio2 thread) */
    volatile LONG ended;
    int carry;                     /* ended buffers not yet matched to fifo entries */
    IXAudio2SourceVoice* v;
    uint32_t rate, channels, bits;
    int busy;                      /* attached to a source */
    Entry fifo[MAX_QUEUE * 2];     /* submissions XAudio2 may still read, oldest first */
    int nfifo;
} Voice;
typedef struct Source {
    int live, state, relative, looping, dirty;
    float gain, pitch, pos[3], vel[3], dir[3], ref, rolloff, maxd, ming, maxg, cone_in, cone_out, cone_gain;
    uint32_t queue[MAX_QUEUE];
    int nq, processed, submitted;  /* queue entries [0,processed) done, [0,submitted) given to the voice */
    Voice* voice;
} Source;

static CRITICAL_SECTION lock;
static INIT_ONCE lock_once = INIT_ONCE_STATIC_INIT;
static IXAudio2* xa;
static IXAudio2MasteringVoice* master;
static IXAudio2SubmixVoice* mix;        /* every source voice sends here; the meter measures it, before the master volume */
static IUnknown* meter;
static uint32_t master_channels, master_rate;
static uint32_t device_va, context_va, current_va;   /* guest identities (runtime region) */
static uint32_t al_error, alc_error;
static int suspended, listener_dirty;
static float lis_pos[3], lis_vel[3], lis_at[3] = {0, 0, -1}, lis_up[3] = {0, 1, 0}, lis_gain = 1.0f;
static float doppler_factor = 1.0f, doppler_velocity = 1.0f;
static uint32_t distance_model = AL_INVERSE_DISTANCE_CLAMPED;
static Source sources[MAX_SOURCES];
static Buffer* buffers;
static uint32_t nbuffers, cbuffers;
static Voice voices[MAX_VOICES];
static int nvoices;
static uint32_t str_vendor, str_version, str_renderer, str_ext, str_device, str_alc_ext;
static struct { uint64_t plays, buffers, bytes, voices_created, starved, partial, refused, commits; float peak; } st;
static int logged_plays;
static struct { uint32_t site; uint64_t restarts, plays; } play_sites[8];   /* alSourcePlay callers (evidence) */
static struct { uint32_t site; uint64_t stops, playing; } stop_sites[8];   /* alSourceStop callers (evidence) */
static uint64_t natural_ends, natural_loop_ends, plays_ref0;
static void count_stop(uint32_t site, int playing) {
    int i;
    for (i = 0; i < 8 && stop_sites[i].site && stop_sites[i].site != site; i++) ;
    if (i == 8) return;
    stop_sites[i].site = site; stop_sites[i].stops++; stop_sites[i].playing += playing;
}
static void count_site(uint32_t site, int restart) {
    int i;
    for (i = 0; i < 8 && play_sites[i].site && play_sites[i].site != site; i++) ;
    if (i == 8) return;
    play_sites[i].site = site; play_sites[i].plays++; play_sites[i].restarts += restart;
}
static ULONGLONG meter_last;
static float meter_peak[2], meter_rms[2];
static int meter_passes;

static BOOL CALLBACK init_lock(PINIT_ONCE o, PVOID p, PVOID* q) { (void)o; (void)p; (void)q; InitializeCriticalSection(&lock); return TRUE; }
static void enter(void) { InitOnceExecuteOnce(&lock_once, init_lock, NULL, NULL); EnterCriticalSection(&lock); }
static void leave(void) { LeaveCriticalSection(&lock); }

static void set_error(uint32_t e) { if (!al_error) al_error = e; }
static float farg(CPU* c, int i) { uint32_t u = ARG(i); float f; memcpy(&f, &u, 4); return f; }
static int guest_ok(uint32_t p, uint32_t size) { return p && xrt_is_committed(p, size ? size : 1); }
static void once(int* flag, const char* what) { if (!*flag) { *flag = 1; xrt_log("OpenAL: %s", what); xrt_event("openal_unmodelled", "\"what\": \"%s\"", what); } }

static void pcm_release(Pcm* p) { if (p && !InterlockedDecrement(&p->refs)) free(p); }
static Buffer* buffer_get(uint32_t name) { return name && name <= nbuffers && buffers[name - 1].live ? &buffers[name - 1] : NULL; }
static Source* source_get(uint32_t name) { return name && name <= MAX_SOURCES && sources[name - 1].live ? &sources[name - 1] : NULL; }
static int context_live(void) { return context_va && current_va == context_va && xa; }

/* ---------------------------------------------------------------- voices */
/* Blocks XAudio2 has finished with are released oldest first; empty entries complete once at the head. */
/* Completion comes from XAudio2's OnBufferEnd (also called for flushed buffers), never from GetState: right after
 * SubmitSourceBuffer the voice state does not yet count the new buffer, and a source that had only just been started
 * looked finished (ALAudio then freed and replayed its ambient sounds every frame: launch 5, ~1000 plays/s). */
static void STDMETHODCALLTYPE cb_pass_start(IXAudio2VoiceCallback* t, UINT32 n) { (void)t; (void)n; }
static void STDMETHODCALLTYPE cb_void(IXAudio2VoiceCallback* t) { (void)t; }
static void STDMETHODCALLTYPE cb_ctx(IXAudio2VoiceCallback* t, void* p) { (void)t; (void)p; }
static void STDMETHODCALLTYPE cb_buffer_end(IXAudio2VoiceCallback* t, void* p) {
    (void)p; InterlockedIncrement(&((Voice*)((char*)t - offsetof(Voice, cb)))->ended);
}
static void STDMETHODCALLTYPE cb_error(IXAudio2VoiceCallback* t, void* p, HRESULT e) { (void)t; (void)p; (void)e; }
static const IXAudio2VoiceCallbackVtbl voice_cb_vtbl = {cb_pass_start, cb_void, cb_void, cb_ctx, cb_buffer_end, cb_ctx, cb_error};
static int voice_poll(Voice* v) {
    int done = v->carry + (int)InterlockedExchange(&v->ended, 0), completed = 0;
    while (v->nfifo && (!v->fifo[0].pcm || done > 0)) {
        if (v->fifo[0].pcm) { pcm_release(v->fifo[0].pcm); done--; }
        memmove(v->fifo, v->fifo + 1, (size_t)--v->nfifo * sizeof v->fifo[0]);
        completed++;
    }
    v->carry = v->nfifo ? done : 0;   /* more ends than entries cannot happen; never let them complete later work */
    return completed;
}
static Voice* voice_acquire(uint32_t rate, uint32_t channels, uint32_t bits) {
    WAVEFORMATEX f;
    XAUDIO2_SEND_DESCRIPTOR send = {0, (IXAudio2Voice*)mix};
    XAUDIO2_VOICE_SENDS sends = {1, &send};
    Voice* v = NULL;
    HRESULT hr;
    int i;
    for (i = 0; i < nvoices; i++) {
        Voice* w = &voices[i];
        if (w->busy) continue;
        if (w->nfifo) voice_poll(w);
        if (!w->nfifo && w->rate == rate && w->channels == channels && w->bits == bits) { v = w; break; }
    }
    if (!v) {
        if (nvoices == MAX_VOICES) { st.refused++; return NULL; }
        memset(&f, 0, sizeof f);
        f.wFormatTag = WAVE_FORMAT_PCM; f.nChannels = (WORD)channels; f.nSamplesPerSec = rate;
        f.wBitsPerSample = (WORD)bits; f.nBlockAlign = (WORD)(channels * bits / 8); f.nAvgBytesPerSec = rate * f.nBlockAlign;
        v = &voices[nvoices];
        memset(v, 0, sizeof *v);
        v->cb.lpVtbl = (IXAudio2VoiceCallbackVtbl*)&voice_cb_vtbl;
        hr = IXAudio2_CreateSourceVoice(xa, &v->v, &f, 0, MAX_RATIO, &v->cb, &sends, NULL);
        if (FAILED(hr)) { xrt_log("OpenAL: CreateSourceVoice(%u Hz, %u ch, %u bit) failed %08lx", rate, channels, bits, hr); st.refused++; return NULL; }
        v->rate = rate; v->channels = channels; v->bits = bits;
        nvoices++; st.voices_created++;
    }
    v->busy = 1;
    return v;
}
/* Detach: stop and flush; the blocks stay referenced until a later poll sees the XAudio2 queue empty. */
static void voice_release(Source* s) {
    Voice* v = s->voice;
    if (!v) return;
    IXAudio2SourceVoice_Stop(v->v, 0, XAUDIO2_COMMIT_NOW);
    IXAudio2SourceVoice_FlushSourceBuffers(v->v);
    v->busy = 0;
    s->voice = NULL;
}
static int voice_submit(Source* s, int index) {
    Buffer* b = buffer_get(s->queue[index]);
    Voice* v = s->voice;
    XAUDIO2_BUFFER xb;
    if (v->nfifo == (int)(sizeof v->fifo / sizeof v->fifo[0])) return 0;
    if (!b || !b->pcm || !b->pcm->size) { v->fifo[v->nfifo++].pcm = NULL; return 1; }
    memset(&xb, 0, sizeof xb);
    xb.AudioBytes = b->pcm->size; xb.pAudioData = b->pcm->data;
    if (s->looping && s->nq == 1) xb.LoopCount = XAUDIO2_LOOP_INFINITE;
    if (FAILED(IXAudio2SourceVoice_SubmitSourceBuffer(v->v, &xb, NULL))) { st.refused++; return 0; }
    InterlockedIncrement(&b->pcm->refs);
    v->fifo[v->nfifo++].pcm = b->pcm;
    return 1;
}

/* ---------------------------------------------------------------- spatial parameters */
static float dot3(const float* a, const float* b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
static void cross3(const float* a, const float* b, float* r) {
    r[0] = a[1] * b[2] - a[2] * b[1]; r[1] = a[2] * b[0] - a[0] * b[2]; r[2] = a[0] * b[1] - a[1] * b[0];
}
static void norm3(float* a) { float l = sqrtf(dot3(a, a)); if (l > 1e-12f) { a[0] /= l; a[1] /= l; a[2] /= l; } }
static void commit(Source* s) {
    Voice* v = s->voice;
    float gain = s->gain, ratio = s->pitch, m[4] = {1, 0, 0, 1};
    s->dirty = 0;
    if (!v) return;
    st.commits++;
    if (v->channels == 1) {
        float rel[3], lx, ly, lz, d, dist_gain = 1.0f, pan, th, right[3], up[3];
        int k;
        for (k = 0; k < 3; k++) rel[k] = s->relative ? s->pos[k] : s->pos[k] - lis_pos[k];
        if (s->relative) { lx = rel[0]; ly = rel[1]; lz = rel[2]; }
        else {
            float at[3] = {lis_at[0], lis_at[1], lis_at[2]};
            norm3(at);
            cross3(at, lis_up, right); norm3(right); cross3(right, at, up);
            lx = dot3(rel, right); ly = dot3(rel, up); lz = -dot3(rel, at);
        }
        d = sqrtf(lx * lx + ly * ly + lz * lz);
        if (distance_model != AL_NONE) {
            float dd = d;
            if (distance_model == AL_INVERSE_DISTANCE_CLAMPED) { if (dd < s->ref) dd = s->ref; if (dd > s->maxd) dd = s->maxd; }
            if (s->ref + s->rolloff * (dd - s->ref) > 0.0f) dist_gain = s->ref / (s->ref + s->rolloff * (dd - s->ref));
        }
        gain *= dist_gain;
        pan = d > 1e-6f ? lx / d : 0.0f;
        if (pan > 1.0f) pan = 1.0f; else if (pan < -1.0f) pan = -1.0f;
        th = (pan + 1.0f) * 0.785398163f;
        m[0] = cosf(th); m[1] = sinf(th);
        if (doppler_factor > 0.0f && d > 1e-6f) {
            float ss = 343.3f * doppler_velocity, sl[3] = {rel[0], rel[1], rel[2]}, vls, vss, lim;
            norm3(sl);
            vls = s->relative ? 0.0f : dot3(lis_vel, sl);
            vss = dot3(s->vel, sl);
            lim = ss / doppler_factor;
            if (vls > lim) vls = lim;
            if (vss > lim) vss = lim;
            if (ss - doppler_factor * vss > 1e-3f) ratio *= (ss - doppler_factor * vls) / (ss - doppler_factor * vss);
        }
    }
    if (gain < s->ming) gain = s->ming;
    if (gain > s->maxg) gain = s->maxg;
    gain *= lis_gain;
    if (ratio < XAUDIO2_MIN_FREQ_RATIO) ratio = XAUDIO2_MIN_FREQ_RATIO;
    if (ratio > MAX_RATIO) ratio = MAX_RATIO;
    IXAudio2SourceVoice_SetVolume(v->v, gain, XAUDIO2_COMMIT_NOW);
    IXAudio2SourceVoice_SetFrequencyRatio(v->v, ratio, XAUDIO2_COMMIT_NOW);
    if (v->channels == 1) {
        float mm[16] = {0};
        mm[0] = m[0]; mm[1] = master_channels > 1 ? m[1] : 0.0f;
        IXAudio2SourceVoice_SetOutputMatrix(v->v, NULL, 1, master_channels, mm, XAUDIO2_COMMIT_NOW);
    }
}
static void maybe_commit(Source* s) { s->dirty = 1; if (!suspended) commit(s); }

/* Poll a playing source: completed submissions become processed entries; a drained queue stops the source. */
static void source_update(Source* s) {
    int done;
    if (s->state != AL_PLAYING || !s->voice) return;
    done = voice_poll(s->voice);
    if (s->looping && s->nq > 1) {
        if (!s->voice->nfifo) {              /* looping queue: every entry is played again, none is processed */
            int i;
            for (i = 0; i < s->nq; i++) voice_submit(s, i);
            s->submitted = s->nq;
        }
        return;
    }
    s->processed += done;
    if (s->processed > s->submitted) s->processed = s->submitted;
    if (!s->voice->nfifo && s->submitted == s->nq) {
        voice_release(s);
        natural_ends++; natural_loop_ends += s->looping;
        s->state = AL_STOPPED;
        s->processed = s->nq;
    } else if (!s->voice->nfifo)
        st.starved++;
}
static void source_play(Source* s) {
    Buffer* first = NULL;
    int i;
    if (s->state == AL_PAUSED && s->voice) {
        IXAudio2SourceVoice_Start(s->voice->v, 0, XAUDIO2_COMMIT_NOW);
        s->state = AL_PLAYING;
        return;
    }
    voice_release(s);
    s->processed = s->submitted = 0;
    for (i = 0; i < s->nq && !first; i++) first = buffer_get(s->queue[i]);
    if (!first || !first->pcm) { s->state = AL_STOPPED; s->processed = s->nq; return; }
    if (!(s->voice = voice_acquire(first->freq, first->channels, first->bits))) {
        set_error(AL_OUT_OF_MEMORY);
        s->state = AL_STOPPED; s->processed = s->nq;
        return;
    }
    commit(s);
    for (i = 0; i < s->nq; i++)
        if (voice_submit(s, i)) s->submitted++;
    IXAudio2SourceVoice_Start(s->voice->v, 0, XAUDIO2_COMMIT_NOW);
    s->state = AL_PLAYING;
    st.plays++;
    {   /* every streamed (queued) play is logged: ALAudio's Ogg voice and music streams */
        static int logged_streams;
        if (s->nq >= 2 && logged_streams < 400) {
            logged_streams++;
            xrt_log("OpenAL: stream play %llu source %d: %d queued buffer(s), %u Hz %u ch, gain %.2f rel %d", st.plays,
                    (int)(s - sources) + 1, s->nq, first->freq, first->channels, s->gain, s->relative);
        }
    }
    if (logged_plays < 256) {
        logged_plays++;
        if (logged_plays <= 64)   /* the event timeline is usually full by now: the log keeps the first plays */
            xrt_log("OpenAL: play %llu source %d: %d buffer(s), %u Hz %u ch, %u bytes (%.2f s), gain %.2f pitch %.2f loop %d rel %d",
                    st.plays, (int)(s - sources) + 1, s->nq, first->freq, first->channels, first->pcm->size,
                    first->pcm->size / (double)(first->freq * first->channels * first->bits / 8), s->gain, s->pitch, s->looping, s->relative);
        xrt_event("openal_play", "\"source\": %d, \"buffers\": %d, \"rate\": %u, \"channels\": %u, \"bytes\": %u, \"seconds\": %.3f, "
                  "\"gain\": %.3f, \"pitch\": %.3f, \"looping\": %d, \"relative\": %d", (int)(s - sources) + 1, s->nq, first->freq,
                  first->channels, first->pcm->size, first->pcm->size / (double)(first->freq * first->channels * first->bits / 8),
                  s->gain, s->pitch, s->looping, s->relative);
    }
}
static void source_stop(Source* s) {
    voice_release(s);
    s->state = AL_STOPPED;
    s->processed = s->submitted = s->nq;
}
static void source_reset(Source* s) {
    memset(s, 0, sizeof *s);
    s->live = 1; s->state = AL_INITIAL; s->gain = s->pitch = 1.0f; s->ref = 1.0f; s->rolloff = 1.0f;
    s->maxd = FLT_MAX; s->maxg = 1.0f; s->cone_in = s->cone_out = 360.0f; s->cone_gain = 1.0f;
}
static void queue_clear(Source* s) {
    int i;
    for (i = 0; i < s->nq; i++) { Buffer* b = buffer_get(s->queue[i]); if (b) b->queued--; }
    s->nq = s->processed = s->submitted = 0;
}

/* ---------------------------------------------------------------- mix meter (evidence) */
static void meter_sample(void) {
    float peak[8] = {0}, rms[8] = {0};
    XAUDIO2FX_VOLUMEMETER_LEVELS lv;
    ULONGLONG now = GetTickCount64();
    uint32_t k, n = master_channels > 8 ? 8 : master_channels;
    if (!meter) return;
    lv.pPeakLevels = peak; lv.pRMSLevels = rms; lv.ChannelCount = master_channels;
    if (SUCCEEDED(IXAudio2Voice_GetEffectParameters((IXAudio2Voice*)mix, 0, &lv, sizeof lv))) {
        for (k = 0; k < n && k < 2; k++) {
            if (peak[k] > meter_peak[k]) meter_peak[k] = peak[k];
            meter_rms[k] += rms[k] * rms[k];
        }
        meter_passes++;
    }
    if (now - meter_last >= 2000) {
        XAUDIO2_PERFORMANCE_DATA pd;
        int i, playing = 0;
        IXAudio2_GetPerformanceData(xa, &pd);
        for (i = 0; i < MAX_SOURCES; i++) playing += sources[i].live && sources[i].state == AL_PLAYING;
        xrt_log("OpenAL mix: peak %.4f/%.4f rms %.4f/%.4f, %d playing, %u active voices of %d, %llu plays, %llu buffers, glitches %u",
                meter_peak[0], meter_peak[1], meter_passes ? sqrtf(meter_rms[0] / meter_passes) : 0.0f,
                meter_passes ? sqrtf(meter_rms[1] / meter_passes) : 0.0f, playing, pd.ActiveSourceVoiceCount, nvoices, st.plays,
                st.buffers, pd.GlitchesSinceEngineStarted);
        {
            int i;
            for (i = 0; i < 8 && play_sites[i].site; i++)
                xrt_log("OpenAL play site %08x: %llu plays, %llu of a playing source", play_sites[i].site, play_sites[i].plays, play_sites[i].restarts);
            for (i = 0; i < 8 && stop_sites[i].site; i++)
                xrt_log("OpenAL stop site %08x: %llu stops, %llu of a playing source", stop_sites[i].site, stop_sites[i].stops, stop_sites[i].playing);
            xrt_log("OpenAL natural ends: %llu (%llu with AL_LOOPING set); plays with AL_REFERENCE_DISTANCE 0 (silent): %llu", natural_ends, natural_loop_ends, plays_ref0);
            {   /* read-only: Core's GAudioMaxRadiusMultiplier (ALAudio stops ambient slots beyond Radius * this) */
                XrtModule* core = xrt_module_by_name("Core.dll");
                uint32_t va = core ? xrt_module_export(core, "?GAudioMaxRadiusMultiplier@@3MA", 0) : 0;
                if (va) { uint32_t u = rd32(va); float f; memcpy(&f, &u, 4); xrt_log("OpenAL: GAudioMaxRadiusMultiplier = %g", f); }
            }
        }
        if (meter_peak[0] > st.peak) st.peak = meter_peak[0];
        if (meter_peak[1] > st.peak) st.peak = meter_peak[1];
        xrt_event("openal_mix", "\"peak\": [%.4f, %.4f], \"rms\": [%.4f, %.4f], \"samples\": %d, \"playing\": %d, \"active_voices\": %u, "
                  "\"voices\": %d, \"glitches\": %u, \"latency_samples\": %u, \"plays\": %llu",
                  meter_peak[0], meter_peak[1], meter_passes ? sqrtf(meter_rms[0] / meter_passes) : 0.0f,
                  meter_passes ? sqrtf(meter_rms[1] / meter_passes) : 0.0f, meter_passes, playing, pd.ActiveSourceVoiceCount,
                  nvoices, pd.GlitchesSinceEngineStarted, pd.CurrentLatencyInSamples, st.plays);
        meter_last = now; meter_peak[0] = meter_peak[1] = meter_rms[0] = meter_rms[1] = 0; meter_passes = 0;
    }
}

/* ---------------------------------------------------------------- ALC */
/* XAudio2Create needs COM on the creating thread. The guest's threads keep their own apartments (the game's COM and
 * DirectMusic use them), so a host keeper thread enters the MTA, creates the engine and mastering voice, and holds
 * the MTA until alcCloseDevice; guest threads use the objects from the implicit MTA. */
static HANDLE keeper, keeper_ready, keeper_stop;
static HRESULT keeper_hr;
static DWORD WINAPI keeper_main(LPVOID p) {
    HRESULT hr = CoInitializeEx(NULL, COINIT_MULTITHREADED);
    (void)p;
    if (SUCCEEDED(hr)) hr = XAudio2Create(&xa, 0, XAUDIO2_DEFAULT_PROCESSOR);
    if (SUCCEEDED(hr)) hr = IXAudio2_CreateMasteringVoice(xa, &master, 2, XAUDIO2_DEFAULT_SAMPLERATE, 0, NULL, NULL, AudioCategory_GameEffects);
    if (SUCCEEDED(hr)) {
        XAUDIO2_VOICE_DETAILS d;
        XAUDIO2_EFFECT_DESCRIPTOR fx;
        XAUDIO2_EFFECT_CHAIN chain;
        IXAudio2MasteringVoice_GetVoiceDetails(master, &d);
        master_rate = d.InputSampleRate;
        master_channels = 2;          /* the submix every source voice sends to */
        chain.EffectCount = 0; chain.pEffectDescriptors = &fx;
        if (SUCCEEDED(XAudio2CreateVolumeMeter(&meter, 0))) {
            fx.pEffect = meter; fx.InitialState = TRUE; fx.OutputChannels = 2;
            chain.EffectCount = 1;
        }
        hr = IXAudio2_CreateSubmixVoice(xa, &mix, 2, master_rate, 0, 0, NULL, chain.EffectCount ? &chain : NULL);
        if (FAILED(hr) && meter) { meter->lpVtbl->Release(meter); meter = NULL; hr = IXAudio2_CreateSubmixVoice(xa, &mix, 2, master_rate, 0, 0, NULL, NULL); }
    }
    if (FAILED(hr) && xa) { IXAudio2_Release(xa); xa = NULL; }
    keeper_hr = hr;
    SetEvent(keeper_ready);
    if (SUCCEEDED(hr)) WaitForSingleObject(keeper_stop, INFINITE);
    CoUninitialize();
    return 0;
}
static HRESULT keeper_start(void) {
    keeper_ready = CreateEventW(NULL, TRUE, FALSE, NULL);
    keeper_stop = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!keeper_ready || !keeper_stop || !(keeper = CreateThread(NULL, 0, keeper_main, NULL, 0, NULL)))
        return HRESULT_FROM_WIN32(GetLastError());
    WaitForSingleObject(keeper_ready, INFINITE);
    if (FAILED(keeper_hr)) { WaitForSingleObject(keeper, INFINITE); CloseHandle(keeper); keeper = NULL; }
    return keeper_hr;
}
static void keeper_end(void) {
    if (!keeper) return;
    SetEvent(keeper_stop);
    WaitForSingleObject(keeper, INFINITE);
    CloseHandle(keeper); CloseHandle(keeper_ready); CloseHandle(keeper_stop);
    keeper = keeper_ready = keeper_stop = NULL;
}
static void hle_alcOpenDevice(CPU* c) {
    const char* want = ARG(0) && guest_ok(ARG(0), 1) ? (const char*)G2H(ARG(0)) : "(default)";
    const char* mode = getenv("XRT_DEV_SOUND");
    HRESULT hr;
    char q[200];
    enter();
    if (device_va) { leave(); xrt_log("OpenAL: second alcOpenDevice refused"); RET_C(0); return; }
    hr = keeper_start();
    if (FAILED(hr)) {
        leave();
        xrt_log("OpenAL: alcOpenDevice(\"%s\"): XAudio2 unavailable (%08lx) -> NULL", want, hr);
        xrt_event("openal_device", "\"requested\": %s, \"ok\": false, \"hr\": \"0x%08lx\"", xrt_jstr(q, sizeof q, want), hr);
        RET_C(0);
        return;
    }
    if (mode && !strcmp(mode, "muted")) IXAudio2MasteringVoice_SetVolume(master, 0.0f, XAUDIO2_COMMIT_NOW);
    device_va = xrt_rt_alloc(16, 16);
    if (!str_vendor) {
        str_vendor = xrt_guest_strdup_a("Unreal II port (XRT)");
        str_version = xrt_guest_strdup_a("1.0");
        str_renderer = xrt_guest_strdup_a("OpenAL 1.0 on XAudio2");
        str_ext = xrt_guest_strdup_a("");
        str_alc_ext = xrt_guest_strdup_a("");
        str_device = xrt_guest_strdup_a("XAudio2");
    }
    leave();
    xrt_log("OpenAL: alcOpenDevice(\"%s\") -> XAudio2 %u ch %u Hz%s, meter %s", want, master_channels, master_rate,
            mode && !strcmp(mode, "muted") ? " (muted)" : "", meter ? "on" : "off");
    xrt_event("openal_device", "\"requested\": %s, \"ok\": true, \"channels\": %u, \"rate\": %u, \"muted\": %s, \"meter\": %s",
              xrt_jstr(q, sizeof q, want), master_channels, master_rate, mode && !strcmp(mode, "muted") ? "true" : "false",
              meter ? "true" : "false");
    RET_C(device_va);
}
static void hle_alcCreateContext(CPU* c) {
    uint32_t attrs = ARG(1), i;
    enter();
    if (!ARG(0) || ARG(0) != device_va) { alc_error = ALC_INVALID_DEVICE; leave(); RET_C(0); return; }
    if (context_va) { alc_error = ALC_INVALID_VALUE; leave(); RET_C(0); return; }
    for (i = 0; attrs && guest_ok(attrs + 8 * i, 8) && rd32(attrs + 8 * i) && i < 16; i++)
        xrt_log("OpenAL: context attribute %04x = %u (%s)", rd32(attrs + 8 * i), rd32(attrs + 8 * i + 4),
                rd32(attrs + 8 * i) == ALC_FREQUENCY ? "the XAudio2 mastering voice keeps the device rate" : "recorded");
    context_va = xrt_rt_alloc(16, 16);
    leave();
    RET_C(context_va);
}
static void hle_alcMakeContextCurrent(CPU* c) {
    enter();
    if (ARG(0) && ARG(0) != context_va) { alc_error = ALC_INVALID_CONTEXT; leave(); RET_C(0); return; }
    current_va = ARG(0);
    leave();
    RET_C(1);
}
static void hle_alcGetCurrentContext(CPU* c) { RET_C(current_va); }
static void hle_alcGetContextsDevice(CPU* c) { RET_C(ARG(0) && ARG(0) == context_va ? device_va : 0); }
static void hle_alcSuspendContext(CPU* c) { enter(); if (ARG(0) == context_va) suspended = 1; leave(); RET_C(ARG(0)); }
static void hle_alcProcessContext(CPU* c) {
    int i;
    enter();
    if (ARG(0) == context_va && xa) {
        suspended = 0;
        for (i = 0; i < MAX_SOURCES; i++) {
            Source* s = &sources[i];
            if (!s->live) continue;
            source_update(s);
            if (s->voice && (s->dirty || listener_dirty)) commit(s);
        }
        listener_dirty = 0;
        meter_sample();
    }
    leave();
    RET_C(ARG(0));
}
static void hle_alcDestroyContext(CPU* c) {
    int i;
    enter();
    if (!ARG(0) || ARG(0) != context_va) { alc_error = ALC_INVALID_CONTEXT; leave(); RET_C(ALC_INVALID_CONTEXT); return; }
    for (i = 0; i < MAX_SOURCES; i++) if (sources[i].live) { voice_release(&sources[i]); queue_clear(&sources[i]); sources[i].live = 0; }
    context_va = 0;
    if (current_va == ARG(0)) current_va = 0;
    leave();
    RET_C(0);
}
static void hle_alcCloseDevice(CPU* c) {
    uint32_t i;
    int k;
    enter();
    if (!ARG(0) || ARG(0) != device_va) { alc_error = ALC_INVALID_DEVICE; leave(); RET_C(0); return; }
    for (k = 0; k < nvoices; k++) IXAudio2SourceVoice_DestroyVoice(voices[k].v);   /* synchronous: XAudio2 is done with the blocks */
    for (k = 0; k < nvoices; k++) { int j; for (j = 0; j < voices[k].nfifo; j++) pcm_release(voices[k].fifo[j].pcm); }
    nvoices = 0;
    for (i = 0; i < nbuffers; i++) if (buffers[i].live) { pcm_release(buffers[i].pcm); buffers[i].live = 0; }
    if (mix) IXAudio2SubmixVoice_DestroyVoice(mix);
    if (master) IXAudio2MasteringVoice_DestroyVoice(master);
    if (meter) meter->lpVtbl->Release(meter);
    IXAudio2_Release(xa);
    keeper_end();
    xa = NULL; master = NULL; mix = NULL; meter = NULL; device_va = 0;
    for (k = 0; k < MAX_SOURCES; k++) sources[k].voice = NULL;
    leave();
    xrt_log("OpenAL: device closed: %llu plays, %llu buffers (%llu bytes), %llu voices, %llu starved polls, %llu refused, peak %.4f",
            st.plays, st.buffers, st.bytes, st.voices_created, st.starved, st.refused, st.peak);
    xrt_event("openal_close", "\"plays\": %llu, \"buffers\": %llu, \"bytes\": %llu, \"voices\": %llu, \"starved\": %llu, \"refused\": %llu, "
              "\"partial_frames\": %llu, \"commits\": %llu, \"peak\": %.4f", st.plays, st.buffers, st.bytes, st.voices_created, st.starved,
              st.refused, st.partial, st.commits, st.peak);
    RET_C(1);
}
static void hle_alcGetError(CPU* c) { uint32_t e = alc_error; alc_error = 0; RET_C(e); }
static void hle_alcGetString(CPU* c) {
    switch (ARG(1)) {
    case 0: RET_C(str_vendor ? str_vendor : 0); return;
    case ALC_DEFAULT_DEVICE_SPECIFIER: case ALC_DEVICE_SPECIFIER: RET_C(str_device); return;
    case ALC_EXTENSIONS: RET_C(str_alc_ext); return;
    }
    alc_error = ALC_INVALID_ENUM;
    RET_C(0);
}
static void hle_alcGetIntegerv(CPU* c) {
    uint32_t p = ARG(3), n = ARG(2);
    if (!n || !guest_ok(p, 4)) { alc_error = 0xA004; RET_C_VOID(); return; }
    switch (ARG(1)) {
    case ALC_MAJOR_VERSION: wr32(p, 1); break;
    case ALC_MINOR_VERSION: wr32(p, 0); break;
    case ALC_FREQUENCY: wr32(p, master_rate); break;
    default: alc_error = ALC_INVALID_ENUM;
    }
    RET_C_VOID();
}

/* ---------------------------------------------------------------- AL state */
static void hle_alGetError(CPU* c) { uint32_t e; enter(); e = al_error; al_error = 0; leave(); RET_C(e); }
static void hle_alGetString(CPU* c) {
    switch (ARG(0)) {
    case AL_VENDOR: RET_C(str_vendor); return;
    case AL_VERSION: RET_C(str_version); return;
    case AL_RENDERER: RET_C(str_renderer); return;
    case AL_EXTENSIONS: RET_C(str_ext); return;
    }
    set_error(AL_INVALID_ENUM);
    RET_C(0);
}
static void hle_alIsExtensionPresent(CPU* c) {
    char q[100];
    const char* name = guest_ok(ARG(0), 1) ? (const char*)G2H(ARG(0)) : "";
    xrt_event("openal_extension", "\"name\": %s, \"present\": false", xrt_jstr(q, sizeof q, name));
    RET_C(0);
}
static void hle_alGetProcAddress(CPU* c) {
    char q[100];
    const char* name = guest_ok(ARG(0), 1) ? (const char*)G2H(ARG(0)) : "";
    uint32_t r = name[0] == 'a' && name[1] == 'l' ? xrt_hle_proc("defopenal32.dll", name) : 0;
    xrt_event("openal_proc", "\"name\": %s, \"result\": \"0x%08x\"", xrt_jstr(q, sizeof q, name), r);
    RET_C(r);
}
static void hle_alGetEnumValue(CPU* c) { RET_C(0); }
static void hle_alEnable(CPU* c) { set_error(AL_INVALID_ENUM); RET_C_VOID(); }   /* no AL capabilities in 1.0 */
static void hle_alDisable(CPU* c) { set_error(AL_INVALID_ENUM); RET_C_VOID(); }
static void hle_alIsEnabled(CPU* c) { set_error(AL_INVALID_ENUM); RET_C(0); }
static void hle_alDistanceModel(CPU* c) {
    enter();
    if (ARG(0) == AL_NONE || ARG(0) == AL_INVERSE_DISTANCE || ARG(0) == AL_INVERSE_DISTANCE_CLAMPED) { distance_model = ARG(0); listener_dirty = 1; }
    else set_error(AL_INVALID_VALUE);
    leave();
    RET_C_VOID();
}
static void hle_alDopplerFactor(CPU* c) {
    float f = farg(c, 0);
    enter();
    if (f >= 0.0f) { doppler_factor = f; listener_dirty = 1; } else set_error(AL_INVALID_VALUE);
    leave();
    RET_C_VOID();
}
static void hle_alDopplerVelocity(CPU* c) {
    float f = farg(c, 0);
    enter();
    if (f > 0.0f) { doppler_velocity = f; listener_dirty = 1; } else set_error(AL_INVALID_VALUE);
    leave();
    RET_C_VOID();
}
static void hle_alGetInteger(CPU* c) {
    if (ARG(0) == AL_DISTANCE_MODEL) { RET_C(distance_model); return; }
    set_error(AL_INVALID_ENUM);
    RET_C(0);
}
static void hle_alGetIntegerv(CPU* c) {
    if (ARG(0) == AL_DISTANCE_MODEL && guest_ok(ARG(1), 4)) wr32(ARG(1), distance_model);
    else set_error(AL_INVALID_ENUM);
    RET_C_VOID();
}

/* ---------------------------------------------------------------- listener */
static void listener_fv(uint32_t param, const float* v, int n) {
    int k;
    switch (param) {
    case AL_POSITION: if (n >= 3) for (k = 0; k < 3; k++) lis_pos[k] = v[k]; break;
    case AL_VELOCITY: if (n >= 3) for (k = 0; k < 3; k++) lis_vel[k] = v[k]; break;
    case AL_ORIENTATION: if (n >= 6) for (k = 0; k < 3; k++) { lis_at[k] = v[k]; lis_up[k] = v[k + 3]; } break;
    case AL_GAIN: if (n >= 1 && v[0] >= 0.0f) lis_gain = v[0]; else set_error(AL_INVALID_VALUE); break;
    default: set_error(AL_INVALID_ENUM); return;
    }
    listener_dirty = 1;
    if (!suspended) { int i; for (i = 0; i < MAX_SOURCES; i++) if (sources[i].live && sources[i].voice) commit(&sources[i]); listener_dirty = 0; }
}
static void hle_alListenerfv(CPU* c) {
    float v[6];
    uint32_t p = ARG(1), n = ARG(0) == AL_ORIENTATION ? 6 : ARG(0) == AL_GAIN ? 1 : 3;
    if (!guest_ok(p, 4 * n)) { set_error(AL_INVALID_VALUE); RET_C_VOID(); return; }
    memcpy(v, G2H(p), 4 * n);
    enter(); listener_fv(ARG(0), v, (int)n); leave();
    RET_C_VOID();
}
static void hle_alListenerf(CPU* c) { float v = farg(c, 1); enter(); if (ARG(0) == AL_GAIN) listener_fv(ARG(0), &v, 1); else set_error(AL_INVALID_ENUM); leave(); RET_C_VOID(); }
static void hle_alListener3f(CPU* c) {
    float v[3] = {farg(c, 1), farg(c, 2), farg(c, 3)};
    enter(); if (ARG(0) == AL_POSITION || ARG(0) == AL_VELOCITY) listener_fv(ARG(0), v, 3); else set_error(AL_INVALID_ENUM); leave();
    RET_C_VOID();
}
static void hle_alGetListenerfv(CPU* c) {
    uint32_t p = ARG(1);
    const float* v = ARG(0) == AL_POSITION ? lis_pos : ARG(0) == AL_VELOCITY ? lis_vel : ARG(0) == AL_GAIN ? &lis_gain : NULL;
    if (ARG(0) == AL_ORIENTATION && guest_ok(p, 24)) { memcpy(G2H(p), lis_at, 12); memcpy(G2H(p + 12), lis_up, 12); }
    else if (v && guest_ok(p, ARG(0) == AL_GAIN ? 4 : 12)) memcpy(G2H(p), v, ARG(0) == AL_GAIN ? 4 : 12);
    else set_error(v ? AL_INVALID_VALUE : AL_INVALID_ENUM);
    RET_C_VOID();
}

/* ---------------------------------------------------------------- sources */
static void hle_alGenSources(CPU* c) {
    int32_t n = (int32_t)ARG(0);
    uint32_t p = ARG(1), got = 0, names[MAX_SOURCES];
    int i;
    enter();
    if (n < 0 || !guest_ok(p, 4 * (uint32_t)(n ? n : 1)) || !context_live()) { set_error(n < 0 || context_live() ? AL_INVALID_VALUE : AL_INVALID_OPERATION); leave(); RET_C_VOID(); return; }
    for (i = 0; i < MAX_SOURCES && (int32_t)got < n; i++) if (!sources[i].live) names[got++] = (uint32_t)i + 1;
    if ((int32_t)got < n) set_error(AL_OUT_OF_MEMORY);     /* nothing is generated when not all fit */
    else for (i = 0; i < n; i++) { source_reset(&sources[names[i] - 1]); wr32(p + 4 * i, names[i]); }
    leave();
    RET_C_VOID();
}
static void hle_alDeleteSources(CPU* c) {
    int32_t n = (int32_t)ARG(0), i;
    uint32_t p = ARG(1);
    enter();
    if (n < 0 || (n && !guest_ok(p, 4 * (uint32_t)n))) { set_error(AL_INVALID_VALUE); leave(); RET_C_VOID(); return; }
    for (i = 0; i < n; i++) if (!source_get(rd32(p + 4 * i))) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
    for (i = 0; i < n; i++) { Source* s = source_get(rd32(p + 4 * i)); if (s) { voice_release(s); queue_clear(s); s->live = 0; } }
    leave();
    RET_C_VOID();
}
static void hle_alIsSource(CPU* c) { int r; enter(); r = source_get(ARG(0)) != NULL; leave(); RET_C(r); }
static void source_f(Source* s, uint32_t param, float f) {
    switch (param) {
    case AL_GAIN: if (f < 0.0f) { set_error(AL_INVALID_VALUE); return; } s->gain = f; break;
    case AL_PITCH: if (f <= 0.0f) { set_error(AL_INVALID_VALUE); return; } s->pitch = f; break;
    case AL_REFERENCE_DISTANCE: if (f < 0.0f) { set_error(AL_INVALID_VALUE); return; } s->ref = f; break;
    case AL_ROLLOFF_FACTOR: if (f < 0.0f) { set_error(AL_INVALID_VALUE); return; } s->rolloff = f; break;
    case AL_MAX_DISTANCE: if (f < 0.0f) { set_error(AL_INVALID_VALUE); return; } s->maxd = f; break;
    case AL_MIN_GAIN: if (f < 0.0f || f > 1.0f) { set_error(AL_INVALID_VALUE); return; } s->ming = f; break;
    case AL_MAX_GAIN: if (f < 0.0f || f > 1.0f) { set_error(AL_INVALID_VALUE); return; } s->maxg = f; break;
    case AL_CONE_INNER_ANGLE: { static int f1; s->cone_in = f; if (f < 360.0f) once(&f1, "sound cones (inner angle < 360)"); return; }
    case AL_CONE_OUTER_ANGLE: { static int f2; s->cone_out = f; if (f < 360.0f) once(&f2, "sound cones (outer angle < 360)"); return; }
    case AL_CONE_OUTER_GAIN: s->cone_gain = f; return;
    default: set_error(AL_INVALID_ENUM); return;
    }
    maybe_commit(s);
}
static void source_fv(Source* s, uint32_t param, const float* v) {
    float* d = param == AL_POSITION ? s->pos : param == AL_VELOCITY ? s->vel : param == AL_DIRECTION ? s->dir : NULL;
    if (!d) { source_f(s, param, v[0]); return; }
    d[0] = v[0]; d[1] = v[1]; d[2] = v[2];
    if (param != AL_DIRECTION) maybe_commit(s);
}
static void hle_alSourcef(CPU* c) {
    Source* s;
    float f = farg(c, 2);
    enter();
    if (!(s = source_get(ARG(0)))) set_error(AL_INVALID_NAME); else source_f(s, ARG(1), f);
    leave();
    RET_C_VOID();
}
static void hle_alSourcefv(CPU* c) {
    Source* s;
    float v[3];
    uint32_t n = ARG(1) == AL_POSITION || ARG(1) == AL_VELOCITY || ARG(1) == AL_DIRECTION ? 3 : 1;
    enter();
    if (!(s = source_get(ARG(0)))) set_error(AL_INVALID_NAME);
    else if (!guest_ok(ARG(2), 4 * n)) set_error(AL_INVALID_VALUE);
    else { memcpy(v, G2H(ARG(2)), 4 * n); source_fv(s, ARG(1), v); }
    leave();
    RET_C_VOID();
}
static void hle_alSource3f(CPU* c) {
    Source* s;
    float v[3] = {farg(c, 2), farg(c, 3), farg(c, 4)};
    enter();
    if (!(s = source_get(ARG(0)))) set_error(AL_INVALID_NAME);
    else if (ARG(1) != AL_POSITION && ARG(1) != AL_VELOCITY && ARG(1) != AL_DIRECTION) set_error(AL_INVALID_ENUM);
    else source_fv(s, ARG(1), v);
    leave();
    RET_C_VOID();
}
static void hle_alSourcei(CPU* c) {
    Source* s;
    uint32_t param = ARG(1), value = ARG(2);
    enter();
    if (!(s = source_get(ARG(0)))) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
    switch (param) {
    case AL_BUFFER: {
        Buffer* b = value ? buffer_get(value) : NULL;
        if (value && !b) { set_error(AL_INVALID_VALUE); break; }
        if (s->state == AL_PLAYING || s->state == AL_PAUSED) { set_error(AL_INVALID_OPERATION); break; }
        voice_release(s);
        queue_clear(s);
        if (b) { s->queue[s->nq++] = value; b->queued++; }
        break;
    }
    case AL_LOOPING:
        if (value > 1) { set_error(AL_INVALID_VALUE); break; }
        if (s->looping && !value && s->voice) IXAudio2SourceVoice_ExitLoop(s->voice->v, XAUDIO2_COMMIT_NOW);
        if (!s->looping && value && s->voice && s->state == AL_PLAYING && s->nq == 1) {
            s->looping = 1;                 /* the playing pass ends, then the buffer repeats */
            if (voice_submit(s, 0)) s->submitted++;
        }
        s->looping = (int)value;
        break;
    case AL_SOURCE_RELATIVE:
        if (value > 1) { set_error(AL_INVALID_VALUE); break; }
        s->relative = (int)value; maybe_commit(s);
        break;
    case AL_CONE_INNER_ANGLE: case AL_CONE_OUTER_ANGLE: source_f(s, param, (float)(int32_t)value); break;
    default: set_error(AL_INVALID_ENUM);
    }
    leave();
    RET_C_VOID();
}
static void hle_alGetSourcei(CPU* c) {
    Source* s;
    uint32_t p = ARG(2), r = 0;
    enter();
    if (!(s = source_get(ARG(0)))) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
    if (!guest_ok(p, 4)) { set_error(AL_INVALID_VALUE); leave(); RET_C_VOID(); return; }
    source_update(s);
    switch (ARG(1)) {
    case AL_SOURCE_STATE: r = (uint32_t)s->state; break;
    case AL_BUFFERS_QUEUED: r = (uint32_t)s->nq; break;
    case AL_BUFFERS_PROCESSED: r = s->looping && s->state == AL_PLAYING ? 0 : (uint32_t)s->processed; break;
    case AL_BUFFER: r = s->nq ? s->queue[s->nq - 1] : 0; break;
    case AL_LOOPING: r = (uint32_t)s->looping; break;
    case AL_SOURCE_RELATIVE: r = (uint32_t)s->relative; break;
    default: set_error(AL_INVALID_ENUM); leave(); RET_C_VOID(); return;
    }
    wr32(p, r);
    leave();
    RET_C_VOID();
}
static void hle_alGetSourcef(CPU* c) {
    Source* s;
    uint32_t p = ARG(2);
    float r;
    enter();
    if (!(s = source_get(ARG(0)))) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
    switch (ARG(1)) {
    case AL_GAIN: r = s->gain; break;
    case AL_PITCH: r = s->pitch; break;
    case AL_REFERENCE_DISTANCE: r = s->ref; break;
    case AL_ROLLOFF_FACTOR: r = s->rolloff; break;
    case AL_MAX_DISTANCE: r = s->maxd; break;
    case AL_MIN_GAIN: r = s->ming; break;
    case AL_MAX_GAIN: r = s->maxg; break;
    default: set_error(AL_INVALID_ENUM); leave(); RET_C_VOID(); return;
    }
    if (guest_ok(p, 4)) memcpy(G2H(p), &r, 4); else set_error(AL_INVALID_VALUE);
    leave();
    RET_C_VOID();
}
static void hle_alGetSourcefv(CPU* c) {
    Source* s;
    uint32_t p = ARG(2);
    const float* v;
    enter();
    if (!(s = source_get(ARG(0)))) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
    v = ARG(1) == AL_POSITION ? s->pos : ARG(1) == AL_VELOCITY ? s->vel : ARG(1) == AL_DIRECTION ? s->dir : NULL;
    if (!v) { leave(); hle_alGetSourcef(c); return; }
    if (guest_ok(p, 12)) memcpy(G2H(p), v, 12); else set_error(AL_INVALID_VALUE);
    leave();
    RET_C_VOID();
}
typedef void (*SourceOp)(Source*);
static void source_op(CPU* c, SourceOp op, int vector) {
    uint32_t n = vector ? ARG(0) : 1, p = vector ? ARG(1) : 0, i;
    enter();
    if (vector && ((int32_t)n < 0 || (n && !guest_ok(p, 4 * n)))) { set_error(AL_INVALID_VALUE); leave(); RET_C_VOID(); return; }
    for (i = 0; i < n; i++) if (!source_get(vector ? rd32(p + 4 * i) : ARG(0))) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
    for (i = 0; i < n; i++) { Source* s = source_get(vector ? rd32(p + 4 * i) : ARG(0)); source_update(s); op(s); }
    leave();
    RET_C_VOID();
}
static void op_pause(Source* s) { if (s->state == AL_PLAYING) { if (s->voice) IXAudio2SourceVoice_Stop(s->voice->v, 0, XAUDIO2_COMMIT_NOW); s->state = AL_PAUSED; } }
static void op_rewind(Source* s) { voice_release(s); s->state = AL_INITIAL; s->processed = s->submitted = 0; }
static void hle_alSourcePlay(CPU* c) {
    Source* s;
    enter(); s = source_get(ARG(0)); if (s) { source_update(s); count_site(rd32(c->r[ESP]), s->state == AL_PLAYING); plays_ref0 += s->ref == 0.0f; } leave();
    source_op(c, source_play, 0);
}
static void hle_alSourceStop(CPU* c) {
    Source* s;
    static int traced;
    enter(); s = source_get(ARG(0)); if (s) { source_update(s); count_stop(rd32(c->r[ESP]), s->state == AL_PLAYING); } leave();
    if (s && s->state == AL_PLAYING && st.plays > 2000 && traced < 6) {   /* diagnostic: who stops playing sources */
        char d[8][96];
        int k;
        traced++;
        for (k = 0; k < 8; k++) xrt_describe(d[k], sizeof d[k], c->hist[(c->hpos - 1 - k) & (XRT_HIST - 1)]);
        xrt_log("OpenAL stop of playing source %u, recent guest function entries: %s < %s < %s < %s < %s < %s < %s < %s",
                ARG(0), d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7]);
        {   /* return addresses on the guest stack (values that fall inside lifted code), innermost first */
            char line[1400], one[100];
            int n = 0, len = 0;
            line[0] = 0;
            for (k = 0; k < 96 && n < 8 && xrt_is_committed(c->r[ESP] + 4 * k, 4); k++) {
                uint32_t v = rd32(c->r[ESP] + 4 * k);
                if (v >= 0x10000000u && v < 0x11200000u && xrt_lookup_containing(v)) {
                    xrt_describe(one, sizeof one, v);
                    len += snprintf(line + len, sizeof line - (size_t)len, "%s[%d] %s", n ? " < " : "", k, one);
                    n++;
                }
            }
            xrt_log("OpenAL stop of playing source %u, stack: %s", ARG(0), line);
        }
    }
    source_op(c, source_stop, 0);
}
static void hle_alSourcePause(CPU* c) { source_op(c, op_pause, 0); }
static void hle_alSourceRewind(CPU* c) { source_op(c, op_rewind, 0); }
static void hle_alSourcePlayv(CPU* c) { source_op(c, source_play, 1); }
static void hle_alSourceStopv(CPU* c) { source_op(c, source_stop, 1); }
static void hle_alSourcePausev(CPU* c) { source_op(c, op_pause, 1); }
static void hle_alSourceRewindv(CPU* c) { source_op(c, op_rewind, 1); }
static void hle_alSourceQueueBuffers(CPU* c) {
    Source* s;
    int32_t n = (int32_t)ARG(1), i;
    uint32_t p = ARG(2);
    Buffer* ref = NULL;
    enter();
    if (!(s = source_get(ARG(0)))) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
    if (n < 0 || (n && !guest_ok(p, 4 * (uint32_t)n)) || s->nq + n > MAX_QUEUE) { set_error(n < 0 || s->nq + n <= MAX_QUEUE ? AL_INVALID_VALUE : AL_OUT_OF_MEMORY); leave(); RET_C_VOID(); return; }
    for (i = 0; i < s->nq && !ref; i++) ref = buffer_get(s->queue[i]);
    for (i = 0; i < n; i++) {
        Buffer* b = buffer_get(rd32(p + 4 * i));
        if (rd32(p + 4 * i) && !b) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
        if (b && ref && (b->freq != ref->freq || b->channels != ref->channels || b->bits != ref->bits)) { set_error(AL_INVALID_OPERATION); leave(); RET_C_VOID(); return; }
        if (b && !ref) ref = b;
    }
    source_update(s);
    for (i = 0; i < n; i++) {
        Buffer* b = buffer_get(rd32(p + 4 * i));
        s->queue[s->nq++] = rd32(p + 4 * i);
        if (b) b->queued++;
        if (s->state == AL_PLAYING && s->voice && s->submitted == s->nq - 1 && voice_submit(s, s->nq - 1)) s->submitted++;
    }
    leave();
    RET_C_VOID();
}
static void hle_alSourceUnqueueBuffers(CPU* c) {
    Source* s;
    int32_t n = (int32_t)ARG(1), i;
    uint32_t p = ARG(2);
    enter();
    if (!(s = source_get(ARG(0)))) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
    source_update(s);
    if (n < 0 || n > s->processed || (s->looping && s->state == AL_PLAYING && n) || (n && !guest_ok(p, 4 * (uint32_t)n))) { set_error(AL_INVALID_VALUE); leave(); RET_C_VOID(); return; }
    for (i = 0; i < n; i++) { Buffer* b = buffer_get(s->queue[i]); wr32(p + 4 * i, s->queue[i]); if (b) b->queued--; }
    memmove(s->queue, s->queue + n, (size_t)(s->nq - n) * sizeof s->queue[0]);
    s->nq -= n; s->processed -= n; s->submitted -= n;
    if (s->submitted < 0) s->submitted = 0;
    leave();
    RET_C_VOID();
}

/* ---------------------------------------------------------------- buffers */
static void hle_alGenBuffers(CPU* c) {
    int32_t n = (int32_t)ARG(0), i;
    uint32_t p = ARG(1);
    enter();
    if (n < 0 || (n && !guest_ok(p, 4 * (uint32_t)n))) { set_error(AL_INVALID_VALUE); leave(); RET_C_VOID(); return; }
    if (nbuffers + (uint32_t)n > cbuffers) {
        uint32_t want = cbuffers ? cbuffers * 2 : 1024;
        Buffer* nb;
        while (want < nbuffers + (uint32_t)n) want *= 2;
        if (!(nb = (Buffer*)realloc(buffers, want * sizeof *buffers))) { set_error(AL_OUT_OF_MEMORY); leave(); RET_C_VOID(); return; }
        buffers = nb; cbuffers = want;
    }
    for (i = 0; i < n; i++) {   /* names are never reused: a stale name stays AL_INVALID_NAME */
        memset(&buffers[nbuffers], 0, sizeof buffers[0]);
        buffers[nbuffers].live = 1;
        wr32(p + 4 * i, ++nbuffers);
    }
    leave();
    RET_C_VOID();
}
static void hle_alDeleteBuffers(CPU* c) {
    int32_t n = (int32_t)ARG(0), i;
    uint32_t p = ARG(1);
    enter();
    if (n < 0 || (n && !guest_ok(p, 4 * (uint32_t)n))) { set_error(AL_INVALID_VALUE); leave(); RET_C_VOID(); return; }
    for (i = 0; i < n; i++) {
        uint32_t name = rd32(p + 4 * i);
        Buffer* b = buffer_get(name);
        if (name && !b) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
        if (b && b->queued) { set_error(AL_INVALID_OPERATION); leave(); RET_C_VOID(); return; }
    }
    for (i = 0; i < n; i++) { Buffer* b = buffer_get(rd32(p + 4 * i)); if (b) { pcm_release(b->pcm); b->pcm = NULL; b->live = 0; } }
    leave();
    RET_C_VOID();
}
static void hle_alIsBuffer(CPU* c) { int r; enter(); r = !ARG(0) || buffer_get(ARG(0)) != NULL; leave(); RET_C(r); }
static void hle_alBufferData(CPU* c) {
    uint32_t name = ARG(0), format = ARG(1), data = ARG(2), size = ARG(3), freq = ARG(4), ch, bits, frame;
    Buffer* b;
    Pcm* pcm;
    enter();
    if (!(b = buffer_get(name))) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
    switch (format) {
    case AL_FORMAT_MONO8: ch = 1; bits = 8; break;
    case AL_FORMAT_MONO16: ch = 1; bits = 16; break;
    case AL_FORMAT_STEREO8: ch = 2; bits = 8; break;
    case AL_FORMAT_STEREO16: ch = 2; bits = 16; break;
    default: set_error(AL_INVALID_ENUM); leave(); RET_C_VOID(); return;
    }
    if (b->queued) { set_error(AL_INVALID_OPERATION); leave(); RET_C_VOID(); return; }
    if (freq < 1000 || freq > 200000 || size > 0x10000000u || (size && !guest_ok(data, size))) { set_error(AL_INVALID_VALUE); leave(); RET_C_VOID(); return; }
    frame = ch * bits / 8;
    if (size % frame) { st.partial++; size -= size % frame; }   /* a trailing partial frame cannot be played */
    if (!(pcm = (Pcm*)malloc(sizeof *pcm + size))) { set_error(AL_OUT_OF_MEMORY); leave(); RET_C_VOID(); return; }
    pcm->refs = 1; pcm->size = size;
    if (size) memcpy(pcm->data, G2H(data), size);
    pcm_release(b->pcm);
    b->pcm = pcm; b->format = format; b->freq = freq; b->channels = ch; b->bits = bits;
    st.buffers++; st.bytes += size;
    leave();
    RET_C_VOID();
}
static void hle_alGetBufferi(CPU* c) {
    Buffer* b;
    uint32_t p = ARG(2), r;
    enter();
    if (!(b = buffer_get(ARG(0)))) { set_error(AL_INVALID_NAME); leave(); RET_C_VOID(); return; }
    switch (ARG(1)) {
    case AL_FREQUENCY: r = b->freq; break;
    case AL_BITS: r = b->bits; break;
    case AL_CHANNELS: r = b->channels; break;
    case AL_SIZE: r = b->pcm ? b->pcm->size : 0; break;
    default: set_error(AL_INVALID_ENUM); leave(); RET_C_VOID(); return;
    }
    if (guest_ok(p, 4)) wr32(p, r); else set_error(AL_INVALID_VALUE);
    leave();
    RET_C_VOID();
}

/* Entry points the game's DefOpenAL32.dll exports and this adapter implements. The rest of its export table
 * (alGetBoolean, alGetDouble, alGetFloat, alGet*v, alGetBufferf, EAXSet/EAXGet, ...) are explicit traps. */
const XrtHle xrt_hle_openal[] = {
    {"defopenal32.dll", "alcOpenDevice", hle_alcOpenDevice},
    {"defopenal32.dll", "alcCloseDevice", hle_alcCloseDevice},
    {"defopenal32.dll", "alcCreateContext", hle_alcCreateContext},
    {"defopenal32.dll", "alcMakeContextCurrent", hle_alcMakeContextCurrent},
    {"defopenal32.dll", "alcProcessContext", hle_alcProcessContext},
    {"defopenal32.dll", "alcSuspendContext", hle_alcSuspendContext},
    {"defopenal32.dll", "alcDestroyContext", hle_alcDestroyContext},
    {"defopenal32.dll", "alcGetCurrentContext", hle_alcGetCurrentContext},
    {"defopenal32.dll", "alcGetContextsDevice", hle_alcGetContextsDevice},
    {"defopenal32.dll", "alcGetError", hle_alcGetError},
    {"defopenal32.dll", "alcGetString", hle_alcGetString},
    {"defopenal32.dll", "alcGetIntegerv", hle_alcGetIntegerv},
    {"defopenal32.dll", "alGetError", hle_alGetError},
    {"defopenal32.dll", "alGetString", hle_alGetString},
    {"defopenal32.dll", "alIsExtensionPresent", hle_alIsExtensionPresent},
    {"defopenal32.dll", "alGetProcAddress", hle_alGetProcAddress},
    {"defopenal32.dll", "alGetEnumValue", hle_alGetEnumValue},
    {"defopenal32.dll", "alEnable", hle_alEnable},
    {"defopenal32.dll", "alDisable", hle_alDisable},
    {"defopenal32.dll", "alIsEnabled", hle_alIsEnabled},
    {"defopenal32.dll", "alDistanceModel", hle_alDistanceModel},
    {"defopenal32.dll", "alDopplerFactor", hle_alDopplerFactor},
    {"defopenal32.dll", "alDopplerVelocity", hle_alDopplerVelocity},
    {"defopenal32.dll", "alGetInteger", hle_alGetInteger},
    {"defopenal32.dll", "alGetIntegerv", hle_alGetIntegerv},
    {"defopenal32.dll", "alListenerf", hle_alListenerf},
    {"defopenal32.dll", "alListener3f", hle_alListener3f},
    {"defopenal32.dll", "alListenerfv", hle_alListenerfv},
    {"defopenal32.dll", "alGetListenerfv", hle_alGetListenerfv},
    {"defopenal32.dll", "alGenSources", hle_alGenSources},
    {"defopenal32.dll", "alDeleteSources", hle_alDeleteSources},
    {"defopenal32.dll", "alIsSource", hle_alIsSource},
    {"defopenal32.dll", "alSourcef", hle_alSourcef},
    {"defopenal32.dll", "alSourcefv", hle_alSourcefv},
    {"defopenal32.dll", "alSource3f", hle_alSource3f},
    {"defopenal32.dll", "alSourcei", hle_alSourcei},
    {"defopenal32.dll", "alGetSourcei", hle_alGetSourcei},
    {"defopenal32.dll", "alGetSourcef", hle_alGetSourcef},
    {"defopenal32.dll", "alGetSourcefv", hle_alGetSourcefv},
    {"defopenal32.dll", "alSourcePlay", hle_alSourcePlay},
    {"defopenal32.dll", "alSourceStop", hle_alSourceStop},
    {"defopenal32.dll", "alSourcePause", hle_alSourcePause},
    {"defopenal32.dll", "alSourceRewind", hle_alSourceRewind},
    {"defopenal32.dll", "alSourcePlayv", hle_alSourcePlayv},
    {"defopenal32.dll", "alSourceStopv", hle_alSourceStopv},
    {"defopenal32.dll", "alSourcePausev", hle_alSourcePausev},
    {"defopenal32.dll", "alSourceRewindv", hle_alSourceRewindv},
    {"defopenal32.dll", "alSourceQueueBuffers", hle_alSourceQueueBuffers},
    {"defopenal32.dll", "alSourceUnqueueBuffers", hle_alSourceUnqueueBuffers},
    {"defopenal32.dll", "alGenBuffers", hle_alGenBuffers},
    {"defopenal32.dll", "alDeleteBuffers", hle_alDeleteBuffers},
    {"defopenal32.dll", "alIsBuffer", hle_alIsBuffer},
    {"defopenal32.dll", "alBufferData", hle_alBufferData},
    {"defopenal32.dll", "alGetBufferi", hle_alGetBufferi},
    {0}};
