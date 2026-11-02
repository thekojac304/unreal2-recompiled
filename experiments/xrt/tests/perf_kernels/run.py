"""perf_kernels - translation-overhead microbenchmark on owned kernels shaped like the game's hot paths (README.md).

  .venv\\Scripts\\python.exe -I experiments\\xrt\\tests\\perf_kernels\\run.py [--opt LIST] [--cl "FLAGS"]... [--reps N]
                                                                  [--n name=N]... [--export DIR] [--json FILE]

Builds kernels.c as a 32-bit x87 DLL (cl /O2 /arch:IA32, no CRT), runs it natively (native.exe: reference
checksums and native x86 timings), lifts it with tools/xrt/xlift.py (plain, and with every --opt LIST given; the
default list is the game build's), compiles bench.c + the lifted C for x64 with every --cl flag set given (default
"/O2 /fp:strict", the game build's) against out/dev-init/runtime/xrt.h, runs them and prints one table: per kernel
the native time, each variant's time and its ratio to native. Every translated checksum must equal the native one;
the exit status is 1 otherwise. --export DIR copies the lifted C of the last --opt, bench.c, the headers and the
image for a cross build (gcc/clang, Linux x86-64 or AArch64; see README.md): owned code only, no game bytes."""
import json
import os
import shutil
import struct
import subprocess
import sys

import pefile

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT = os.path.join(WS, "experiments", "xrt", "build", "perf_kernels")
RT = os.path.join(WS, "out", "dev-init", "runtime")
VCVARS = r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
GAME_OPT = "base,flags,icall,iflags,pc,regs,sse,x87,x87v,x87w"
REC = struct.Struct("<24s2I2IQ2d")
FIELDS = ("name", "n", "status", "eax", "edx", "h_out", "min_ms", "med_ms")
DEFAULT_N = {"k_bones": 1500, "k_verts": 150, "k_actors": 1500, "k_strings": 600, "k_bsp": 300}
sys.path.insert(0, os.path.join(WS, "tools", "xrt"))


def sh(arch, cmd, cwd=OUT):
    r = subprocess.run(f'call "{VCVARS}" {arch} >nul && {cmd}', shell=True, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"failed: {cmd}\n{r.stdout}{r.stderr}")
    return r.stdout


def records(path):
    with open(path, "rb") as f:
        data = f.read()
    out = []
    for o in range(0, len(data), REC.size):
        d = dict(zip(FIELDS, REC.unpack_from(data, o)))
        d["name"] = d["name"].split(b"\0")[0].decode()
        out.append(d)
    return out


def lift(dst, opt):
    cmd = [sys.executable, "-I", os.path.join(WS, "tools", "xrt", "xlift.py"), os.path.join(OUT, "PerfKernels.dll"),
           "--out", os.path.join(OUT, dst), "--no-marks"]
    if opt:
        cmd += ["--opt", opt]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"xlift failed:\n{r.stdout}{r.stderr}")
    with open(os.path.join(OUT, dst, "PerfKernels_meta.json")) as f:
        return json.load(f)


# a --cl flag set may name its compiler first: "clang-cl: /O2 /fp:strict" (default cl); clang-cl is LLVM's MSVC-compatible driver
COMPILERS = {"cl": "cl", "clang-cl": '"C:/Program Files/LLVM/bin/clang-cl.exe"'}


def build_bench(lifted, exe, flags):
    cc = "cl"
    if ":" in flags and flags.split(":", 1)[0].strip() in COMPILERS:
        cc, flags = flags.split(":", 1)[0].strip(), flags.split(":", 1)[1].strip()
    srcs = " ".join(f'"{os.path.join(OUT, lifted, n)}"' for n in sorted(os.listdir(os.path.join(OUT, lifted))) if n.endswith(".c"))
    objdir = os.path.join(OUT, exe + ".obj")
    os.makedirs(objdir, exist_ok=True)
    quiet = "/W3 /wd4102 /wd4146 /wd4100" if cc == "cl" else "/W0"
    with open(os.path.join(OUT, lifted, "PerfKernels_protos.h")) as f:
        if "XRT_RV_ABI" in f.read():
            flags += " /DXRT_RV_ABI"      # xlift --opt rv: bench.c must use the same lifted-function type
    sh("x64", f'{COMPILERS[cc]} /nologo {flags} {quiet} /D_CRT_SECURE_NO_WARNINGS /I"{RT}" /I"{HERE}" '
              f'/Fo"{objdir}\\\\" /Fe"{os.path.join(OUT, exe + ".exe")}" {srcs} "{os.path.join(HERE, "bench.c")}" /link /STACK:0x1000000')


def main():
    args = sys.argv[1:]
    opts = [args[i + 1] for i, a in enumerate(args) if a == "--opt"] or [GAME_OPT]
    cls = [args[i + 1] for i, a in enumerate(args) if a == "--cl"] or ["/O2 /fp:strict"]
    reps = int(args[args.index("--reps") + 1]) if "--reps" in args else 7
    ns = dict(DEFAULT_N)
    for i, a in enumerate(args):
        if a == "--n":
            k, v = args[i + 1].split("=")
            ns[k] = int(v)
    os.makedirs(OUT, exist_ok=True)
    sh("x86", f'cl /nologo /O2 /arch:IA32 /GS- /Zl /W3 /LD "{os.path.join(HERE, "kernels.c")}" /Fo"{OUT}\\\\" '
              f'/link /NOENTRY /NODEFAULTLIB /BASE:0x5B000000 /DYNAMICBASE:NO /OUT:PerfKernels.dll')
    sh("x86", f'cl /nologo /O2 /W3 /I"{HERE}" "{os.path.join(HERE, "native.c")}" /Fo"{OUT}\\\\" /Fenative.exe')
    pe = pefile.PE(os.path.join(OUT, "PerfKernels.dll"))
    base = pe.OPTIONAL_HEADER.ImageBase
    with open(os.path.join(OUT, "image.bin"), "wb") as f:
        f.write(pe.get_memory_mapped_image())
    kernels = sorted((s.name.decode(), base + s.address) for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name.startswith(b"k_"))
    native_args = [f"{n}:{ns.get(n, 100)}" for n, _ in kernels]
    print(subprocess.run([os.path.join(OUT, "native.exe"), os.path.join(OUT, "PerfKernels.dll"), os.path.join(OUT, "native.bin"),
                          str(reps), *native_args], check=True, capture_output=True, text=True).stdout, end="")
    nat = {r["name"]: r for r in records(os.path.join(OUT, "native.bin"))}
    variants = []            # (label, lifted dir, exe, cl flags)
    metas = {}
    for oi, opt in enumerate([""] + opts):
        dst = "plain" if not opt else f"opt{oi}"
        metas[dst] = lift(dst, opt)
        for ci, fl in enumerate(cls):
            exe = f"{dst}_cl{ci}"
            build_bench(dst, exe, fl)
            variants.append((("plain" if not opt else opt) + ((" | " + fl) if len(cls) > 1 else ""), dst, exe, fl))
    results = {}
    ok = True
    for label, dst, exe, fl in variants:
        bench_args = [f"{n}={va:#x}:{ns.get(n, 100)}" for n, va in kernels]
        r = subprocess.run([os.path.join(OUT, exe + ".exe"), os.path.join(OUT, "image.bin"), hex(base),
                            os.path.join(OUT, exe + ".bin"), str(reps), *bench_args], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"{exe} exited {r.returncode:#x}\n{r.stdout}{r.stderr}")
        results[label] = {x["name"]: x for x in records(os.path.join(OUT, exe + ".bin"))}
        for n, x in results[label].items():
            ref = nat[n]
            if x["status"] or (x["eax"], x["edx"], x["h_out"]) != (ref["eax"], ref["edx"], ref["h_out"]):
                ok = False
                print(f"MISMATCH {label} {n}: status {x['status']} checksum {x['edx']:08x}{x['eax']:08x} vs native "
                      f"{ref['edx']:08x}{ref['eax']:08x}, out hash {x['h_out']:016x} vs {ref['h_out']:016x}")
    width = max(len(l) for l, _, _, _ in variants)
    print(f"\n{'kernel':10} {'native':>9}  " + "  ".join(f"{l:>{max(width, 14)}}" for l, _, _, _ in variants))
    print(f"{'':10} {'ms':>9}  " + "  ".join(f"{'ms (x native)':>{max(width, 14)}}" for _ in variants))
    geo = {l: [] for l, _, _, _ in variants}
    for n, _ in kernels:
        row = f"{n:10} {nat[n]['med_ms']:9.2f}  "
        for l, _, _, _ in variants:
            x = results[l][n]
            ratio = x["med_ms"] / nat[n]["med_ms"] if nat[n]["med_ms"] else 0
            geo[l].append(ratio)
            row += f"{x['med_ms']:>{max(width, 14) - 8}.2f} ({ratio:4.1f}x)  "
        print(row)
    import math
    print(f"{'geomean':10} {'':>9}  " + "  ".join(f"{'':>{max(width, 14) - 8}} ({math.exp(sum(math.log(v) for v in geo[l]) / len(geo[l])):4.1f}x)  "
                                                   for l, _, _, _ in variants))
    if "--json" in args:
        with open(args[args.index("--json") + 1], "w", encoding="utf-8") as f:
            json.dump({"native": nat, "variants": {l: {"cl": fl, "lifted": dst, "kernels": results[l]} for l, dst, _, fl in variants},
                       "n": ns, "reps": reps, "lift_meta": {k: v.get("optimizations") for k, v in metas.items()}}, f, indent=1, default=str)
    if "--export" in args:
        d = args[args.index("--export") + 1]
        last = variants[-1][1]
        os.makedirs(os.path.join(d, "lifted"), exist_ok=True)
        for n in os.listdir(os.path.join(OUT, last)):
            shutil.copy(os.path.join(OUT, last, n), os.path.join(d, "lifted", n))
        for n in ("bench.c", "kernels.h"):
            shutil.copy(os.path.join(HERE, n), d)
        shutil.copy(os.path.join(RT, "xrt.h"), d)
        shutil.copy(os.path.join(OUT, "image.bin"), d)
        with open(os.path.join(d, "reference.json"), "w") as f:
            json.dump({"base": hex(base), "kernels": [(n, hex(va), ns.get(n, 100)) for n, va in kernels],
                       "native": {n: {"checksum": f"{r['edx']:08x}{r['eax']:08x}", "h_out": f"{r['h_out']:016x}", "med_ms": r["med_ms"]} for n, r in nat.items()}}, f, indent=1)
        print("exported to", d)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
