// ehprobe.cpp - controlled C++ exception scenarios: native x86 execution (the game's msvcr70.dll __CxxFrameHandler)
// versus the translated runtime's dispatcher (experiments/xrt/runtime/xrt_eh.c) on the same binary, lifted.
// Each probe logs constructor/destructor/catch events into probe_log; the harnesses print the logs, compare.py
// compares them. Built by build_and_run.cmd (x86, /EHsc, no CRT; the EH tables are patched to the VC7 format and
// bound to msvcr70.dll by patch_probe.py).

extern "C" {
__declspec(dllexport) int probe_log[256];
__declspec(dllexport) int probe_log_n;
}

static void note(int v) {
    if (probe_log_n < 256)
        probe_log[probe_log_n++] = v;
}

struct Obj {
    int id;
    __declspec(noinline) Obj(int i) : id(i) { note(100 + id); }
    __declspec(noinline) ~Obj() { note(200 + id); }
};

struct Ex {
    int code;
    __declspec(noinline) Ex(int c) : code(c) { note(300 + c); }
    __declspec(noinline) Ex(const Ex& o) : code(o.code) { note(400 + o.code); }
    __declspec(noinline) ~Ex() { note(500 + code); }
};

static volatile int zero = 0;
static const char msg[] = "probe";

// ---- 1. cleanup: destructors in the frames between throw and catch, then local unwind of the catching try
static __declspec(noinline) void thrower(int v) {
    Obj a(1);
    if (zero == 0)
        throw v;
    note(-1);
}
static __declspec(noinline) void middle(int v) {
    Obj b(2);
    {
        Obj c(3);
        thrower(v);
    }
    note(-2);
}
extern "C" __declspec(dllexport) int __cdecl probe_cleanup(void) {
    probe_log_n = 0;
    {
        Obj outer(4);
        try {
            Obj inner(5);
            middle(7);
            note(-3);
        } catch (int e) {
            note(600 + e);
        }
        note(700);
    }
    note(799);
    return probe_log_n;
}

// ---- 2. rethrow out of a catch(...) block; exception object of class type caught by reference, destroyed once
static __declspec(noinline) void rethrower(int v) {
    Obj d(6);
    try {
        Obj e(7);
        throw Ex(v);
    } catch (...) {
        note(800);
        throw;
    }
}
extern "C" __declspec(dllexport) int __cdecl probe_rethrow(void) {
    probe_log_n = 0;
    try {
        rethrower(9);
    } catch (const Ex& x) {
        note(900 + x.code);
    }
    note(950);
    return probe_log_n;
}

// ---- 3. a try/catch nested inside a catch block: the continuation lies inside the outer catch block
extern "C" __declspec(dllexport) int __cdecl probe_nested(void) {
    probe_log_n = 0;
    try {
        if (zero == 0)
            throw 1;
    } catch (int a) {
        note(1000 + a);
        try {
            Obj f(8);
            if (zero == 0)
                throw 2;
        } catch (int b) {
            note(1100 + b);
        }
        note(1200);
    }
    note(1300);
    return probe_log_n;
}

// ---- 4. a new throw from a catch block, caught by an enclosing try of the same function; const pointer matching
extern "C" __declspec(dllexport) int __cdecl probe_enclosing(void) {
    probe_log_n = 0;
    try {
        try {
            if (zero == 0)
                throw (char*)msg;
        } catch (char* s) {
            note(1400 + (s == msg));
            throw 5;
        }
        note(-4);
    } catch (int v) {
        note(1500 + v);
    }
    try {
        if (zero == 0)
            throw (const char*)msg;
    } catch (char*) {
        note(-5);                                   // a const char* must not match catch(char*)
    } catch (const char*) {
        note(1600);
    }
    try {
        if (zero == 0)
            throw 3.5;
    } catch (int) {
        note(-6);
    } catch (...) {
        note(1700);
    }
    return probe_log_n;
}

// ---- 5. the same frame catches repeatedly (the landing pad is reused)
extern "C" __declspec(dllexport) int __cdecl probe_loop(void) {
    probe_log_n = 0;
    for (int i = 0; i < 3; i++) {
        try {
            if (i != 1)
                throw i;
            note(1800 + i);
        } catch (int v) {
            note(1900 + v);
        }
    }
    return probe_log_n;
}

// ---- 6. rethrow from a function called by a catch block
static __declspec(noinline) void rethrow_now() {
    note(2000);
    throw;
}
extern "C" __declspec(dllexport) int __cdecl probe_rethrow_callee(void) {
    probe_log_n = 0;
    try {
        try {
            throw Ex(4);
        } catch (const Ex& e) {
            note(2100 + e.code);
            rethrow_now();
        }
    } catch (Ex& e2) {
        note(2200 + e2.code);
    }
    note(2300);
    return probe_log_n;
}

// ---- 7. (round 4) a catch six guarded frames above the throw: every frame in between has a destructor (an EH frame
// of its own, abandoned by the catch), and the catching function's result is computed after the catch
static __declspec(noinline) int level(int n, int v) {
    Obj o(30 + n);
    if (n == 0) {
        if (zero == 0)
            throw v;
        return -1;
    }
    return level(n - 1, v) + 1;                     // never returns normally
}
extern "C" __declspec(dllexport) int __cdecl probe_deep(void) {
    int r = 0;
    probe_log_n = 0;
    for (int k = 0; k < 2; k++) {
        try {
            r += level(5, 40 + k);
        } catch (int e) {
            note(2500 + e);
            r += e;
        }
    }
    note(r);
    return r * 100 + probe_log_n;
}

// ---- 8. (round 4) the caller's state across a callee that catches internally: the caller keeps accumulators in
// callee-saved registers (ebx/esi/edi) over many calls, each of which throws and catches in the callee's own frame,
// so the caller's state (guest registers, and the host registers of its translated frame) must survive every resumption
static __declspec(noinline) int catcher(int i) {
    Obj t(60);
    try {
        if (zero == 0)
            throw i * 3;
    } catch (int e) {
        return e + 1;                               // result produced by the continuation
    }
    return -1000;
}
extern "C" __declspec(dllexport) int __cdecl probe_caller_state(void) {
    unsigned a = 7, b = 11, s = 0;
    probe_log_n = 0;
    for (int i = 0; i < 200; i++) {
        int v = catcher(i);
        a = a * 33 + (unsigned)v;
        b ^= a + (unsigned)i;
        s += (unsigned)v;
        if (i % 50 == 0)
            probe_log_n = 0;                        // keep the log short: one Obj ctor/dtor pair per call
    }
    note((int)(a & 0x7fff));
    note((int)(b & 0x7fff));
    note((int)s);
    return (int)((a ^ b ^ s) & 0x7fffffff);
}

// ---- 9. (round 4) the normal path only: a small function with an EH frame (a local with a destructor), called many
// times without any exception - what Unreal's guard/unguard frames cost per call (time it with the hosts)
struct Quiet {
    int v;
    __declspec(noinline) Quiet(int i) : v(i) {}
    __declspec(noinline) ~Quiet() { if (v == -12345) note(-7); }
};
static __declspec(noinline) void touch_nothing(int) {}
static void (*volatile touch)(int) = touch_nothing;   // opaque call: may throw as far as the compiler knows
static __declspec(noinline) int guarded_small(int i) {
    Quiet q(i);
    touch(i);                                          // q is live across a call that may throw: an EH frame
    return q.v * 3 + 1;
}
extern "C" __declspec(dllexport) int __cdecl probe_guard_calls(void) {
    unsigned s = 0;
    probe_log_n = 0;
    for (int i = 0; i < 2000000; i++)
        s = s * 31 + (unsigned)guarded_small(i);
    note((int)(s & 0x7fffffff));
    return (int)(s & 0x7fffffff);
}

// ---- negative probes: behaviour the translated runtime does not support must stop it with a diagnostic
extern "C" __declspec(dllexport) int __cdecl probe_neg_unhandled(void) {
    probe_log_n = 0;
    Obj g(9);
    if (zero == 0)
        throw 11;                                   // no handler: the original terminates
    return probe_log_n;
}
extern "C" __declspec(dllexport) int __cdecl probe_neg_catch_by_value(void) {
    probe_log_n = 0;
    try {
        throw Ex(6);
    } catch (Ex e) {                                // needs the copy constructor (not implemented by the dispatcher)
        note(2400 + e.code);
    }
    return probe_log_n;
}
