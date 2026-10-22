// uvm command line: load a class from original Unreal II packages, run an
// event/function in the independent VM, optionally compare Log() output with
// a reference captured from the original engine.
//
//   uvm <SystemDir> <Package.Class> [--func Main] [--parms "..."] [--compare ref.txt] [--quiet] [-v]
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>

#include "uvm.h"

#if defined(_WIN32) && defined(UVM_CRASH_TRACE)
#define NOMINMAX
#include <windows.h>
#include <dbghelp.h>
#pragma comment(lib, "dbghelp.lib")
static LONG WINAPI crashHandler(EXCEPTION_POINTERS* ep) {
    HANDLE proc = GetCurrentProcess();
    SymInitialize(proc, nullptr, TRUE);
    std::fprintf(stderr, "uvm crash: exception 0x%08lx at %p\n", ep->ExceptionRecord->ExceptionCode,
                 ep->ExceptionRecord->ExceptionAddress);
    CONTEXT ctx = *ep->ContextRecord;
    STACKFRAME64 sf{};
    sf.AddrPC.Offset = ctx.Rip; sf.AddrPC.Mode = AddrModeFlat;
    sf.AddrFrame.Offset = ctx.Rbp; sf.AddrFrame.Mode = AddrModeFlat;
    sf.AddrStack.Offset = ctx.Rsp; sf.AddrStack.Mode = AddrModeFlat;
    for (int n = 0; n < 40 && StackWalk64(IMAGE_FILE_MACHINE_AMD64, proc, GetCurrentThread(), &sf, &ctx, nullptr,
                                            SymFunctionTableAccess64, SymGetModuleBase64, nullptr); ++n) {
        char buf[sizeof(SYMBOL_INFO) + 256] = {};
        auto* sym = reinterpret_cast<SYMBOL_INFO*>(buf);
        sym->SizeOfStruct = sizeof(SYMBOL_INFO);
        sym->MaxNameLen = 255;
        DWORD64 disp = 0;
        IMAGEHLP_LINE64 line{};
        line.SizeOfStruct = sizeof line;
        DWORD ldisp = 0;
        bool hasSym = SymFromAddr(proc, sf.AddrPC.Offset, &disp, sym);
        bool hasLine = SymGetLineFromAddr64(proc, sf.AddrPC.Offset, &ldisp, &line);
        std::fprintf(stderr, "  #%d %s %s:%lu\n", n, hasSym ? sym->Name : "?", hasLine ? line.FileName : "?",
                     hasLine ? line.LineNumber : 0);
    }
    return EXCEPTION_EXECUTE_HANDLER;
}
#endif

int main(int argc, char** argv) {
#if defined(_WIN32) && defined(UVM_CRASH_TRACE)
    SetUnhandledExceptionFilter(crashHandler);
#endif
    if (argc < 3) {
        std::fprintf(stderr, "usage: uvm <SystemDir> <Package.Class> [--func F] [--parms P] [--compare ref.txt] [--quiet] [-v]\n");
        return 2;
    }
    std::string sysDir = argv[1], target = argv[2], func = "Main", parms, compare;
    bool quiet = false, verbose = false;
    for (int k = 3; k < argc; ++k) {
        if (!std::strcmp(argv[k], "--func") && k + 1 < argc) func = argv[++k];
        else if (!std::strcmp(argv[k], "--parms") && k + 1 < argc) parms = argv[++k];
        else if (!std::strcmp(argv[k], "--compare") && k + 1 < argc) compare = argv[++k];
        else if (!std::strcmp(argv[k], "--quiet")) quiet = true;
        else if (!std::strcmp(argv[k], "-v")) verbose = true;
    }
    auto dot = target.find('.');
    if (dot == std::string::npos) { std::fprintf(stderr, "target must be Package.Class\n"); return 2; }
    try {
        auto t0 = std::chrono::steady_clock::now();
        uvm::Linker linker;
        linker.systemDir = sysDir;
        linker.verbose = verbose;
        uvm::VM vm(linker);
        vm.echo = !quiet;
        vm.registerCoreNatives();
        vm.registerNativeDecls();
        uvm::Class* cls = linker.findClass(target.substr(0, dot), target.substr(dot + 1));
        if (!cls) { std::fprintf(stderr, "class %s not found\n", target.c_str()); return 1; }
        uvm::Function* fn = cls->findFunction(func);
        if (!fn) { std::fprintf(stderr, "function %s not found\n", func.c_str()); return 1; }
        // UCC creates the commandlet as Transient.<Class>0
        uvm::Object* transient = vm.spawnObject(cls, "Transient");
        transient->cls = nullptr;
        vm.transientPackage = transient;
        uvm::Object* obj = vm.spawnObject(cls, cls->name + "0");
        obj->outer = transient;
        auto t1 = std::chrono::steady_clock::now();
        std::vector<uvm::Value> args;
        args.push_back(uvm::Value::str_(parms));
        uvm::Value ret = vm.call(fn, obj, args);
        auto t2 = std::chrono::steady_clock::now();
        auto ms = [](auto a, auto b) { return std::chrono::duration<double, std::milli>(b - a).count(); };
        std::fprintf(stderr, "[uvm] load+link %.1f ms, run %.3f ms, %llu steps, return %d, %zu packages\n",
                     ms(t0, t1), ms(t1, t2), static_cast<unsigned long long>(vm.stepsExecuted), ret.i,
                     linker.packages.size());
        if (!compare.empty()) {
            // Reference formats: probe files hold bare "T<n>=..." lines; log references hold the
            // original UCC.log "ScriptLog:"/"ScriptWarning:" lines. A leading time stamp
            // ("0.618 ") inside a warning is non-deterministic and is normalised on both sides.
            auto normalise = [](std::string s) {
                auto p = s.find(") ");
                if (p != std::string::npos) {
                    size_t q = p + 2, r = q;
                    while (r < s.size() && (std::isdigit(static_cast<unsigned char>(s[r])) || s[r] == '.')) ++r;
                    if (r > q && r < s.size() && s[r] == ' ' && s.find('.', q) < r) s = s.substr(0, q) + "<t>" + s.substr(r);
                }
                return s;
            };
            std::ifstream f(compare);
            std::vector<std::string> ref;
            bool logStyle = false;
            for (std::string line; std::getline(f, line);) {
                if (!line.empty() && line.back() == '\r') line.pop_back();
                if (line.rfind("Script", 0) == 0) logStyle = true;
                ref.push_back(normalise(line));
            }
            std::vector<std::string> got;
            for (auto& s : vm.output) {
                if (logStyle) { got.push_back(normalise(s)); continue; }
                std::string bare = s.rfind("ScriptLog: ", 0) == 0 ? s.substr(11) : s;
                if (bare.size() > 1 && bare[0] == 'T' && std::isdigit(static_cast<unsigned char>(bare[1]))) got.push_back(bare);
            }
            size_t same = 0, n = std::max(ref.size(), got.size());
            for (size_t k = 0; k < n; ++k) {
                std::string a = k < ref.size() ? ref[k] : "<missing>";
                std::string b = k < got.size() ? got[k] : "<missing>";
                if (a == b) ++same;
                else std::fprintf(stderr, "MISMATCH line %zu\n  original: %s\n  uvm:      %s\n", k + 1, a.c_str(), b.c_str());
            }
            std::fprintf(stderr, "[uvm] compare: %zu/%zu lines identical to the original engine\n", same, n);
            return same == n ? 0 : 1;
        }
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "uvm error: %s\n", e.what());
        return 1;
    }
}
