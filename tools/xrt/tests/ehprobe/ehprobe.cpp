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
