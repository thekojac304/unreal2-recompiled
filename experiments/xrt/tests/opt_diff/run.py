"""Function-level differential test of xlift --opt (flag liveness, pc-store elision); see README.md.

  .venv\\Scripts\\python.exe -I experiments\\xrt\\tests\\opt_diff\\run.py [--vectors N] [--mutations]

Builds the owned test DLL (cases.c, x86), lifts it twice (plain, --opt flags,pc), runs native / plain / opt from the
same vectors and compares: plain vs opt the complete state after every return (status, all GPRs, CF PF ZF SF OF DF,
c->pc, x87 TOP/FCW/FSW/ST(0..7) bits, in/out/stack memory hashes); native vs plain the return value and the in/out
buffers. --mutations re-lifts with deliberately broken liveness rules, each of which must produce a difference.
Exit 0 when everything agrees (and every mutation is detected)."""
import json
import os
import struct
import subprocess
import sys

import pefile

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT = os.path.join(WS, "experiments", "xrt", "build", "opt_diff")
RT = os.path.join(WS, "out", "dev-init", "runtime")        # the runtime headers the game build uses
VCVARS = r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
OPT = "flags,pc,base"                                      # xlift --opt under test (--opt LIST overrides)
DEFINES = []                                               # --define NAME: /DNAME for the x86 test DLL (CFLAGS_CLEAN)
REC = struct.Struct("<3I2II2Q8I2I2HI8QQ")
FIELDS = ("fn", "vec", "status", "eax", "edx", "pc", "h_in", "h_out", *[f"r{i}" for i in range(8)], "flags", "top",
          "fcw", "fsw", "pad", *[f"st{i}" for i in range(8)], "h_stack")
sys.path.insert(0, os.path.join(WS, "tools", "xrt"))


def sh(arch, cmd):
    r = subprocess.run(f'call "{VCVARS}" {arch} >nul && {cmd}', shell=True, cwd=OUT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"failed: {cmd}\n{r.stdout}{r.stderr}")


def lift(dst, opt, mutate=None):
    """Lift OptCases.dll in-process (so a mutation can patch the Lifter) into OUT/dst."""
    import importlib
    import xlift
    importlib.reload(xlift)
    if mutate:
        MUTATIONS[mutate](xlift)
    argv = sys.argv
    sys.argv = ["xlift", os.path.join(OUT, "OptCases.dll"), "--out", os.path.join(OUT, dst), "--no-marks"]
    if opt:
        sys.argv += ["--opt", OPT]
    try:
        xlift.main()
    finally:
        sys.argv = argv
    with open(os.path.join(OUT, dst, "OptCases_meta.json")) as f:
        return json.load(f)


def build_lifted(dst):
    srcs = " ".join(f'"{os.path.join(OUT, dst, n)}"' for n in sorted(os.listdir(os.path.join(OUT, dst))) if n.endswith(".c"))
    sh("x64", f'cl /nologo /O2 /fp:strict /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS /I"{RT}" /I"{HERE}" '
              f'/FIsse_mutants.h /Fo"{os.path.join(OUT, dst)}\\\\" /Fe"{os.path.join(OUT, dst + ".exe")}" {srcs} "{os.path.join(HERE, "lifted.c")}"')


def records(path):
    with open(path, "rb") as f:
        data = f.read()
    return [dict(zip(FIELDS, REC.unpack_from(data, o))) for o in range(0, len(data), REC.size)]


def compare(a, b, keys):
    bad = []
    for x, y in zip(a, b):
        d = [k for k in keys if x[k] != y[k]]
        if d:
            bad.append((x["fn"], x["vec"], d))
    return bad


def mut_jcc_reads_nothing(x):
    orig = x.Lifter.flag_effect
    x.Lifter.flag_effect = lambda self, ins: ((frozenset(), frozenset()) if ins.mnemonic in x.JCC else orig(self, ins))


def not_a_boundary(mnemonics):
    """Mutation: these instructions neither read nor write flags and are no boundary."""
    def patch(x):
        boundary, effect = x.Lifter.flag_boundary, x.Lifter.flag_effect
        x.Lifter.flag_boundary = lambda self, ins: ins.mnemonic not in mnemonics and boundary(self, ins)
        x.Lifter.flag_effect = lambda self, ins: ((frozenset(), frozenset()) if ins.mnemonic in mnemonics
                                                  else effect(self, ins))
    return patch


def mut_cl_shift_kills(x):
    orig = x.Lifter.flag_effect

    def eff(self, ins):
        if ins.mnemonic in ("shl", "shr", "sar") and len(ins.operands) == 2 and ins.operands[1].type != x.X.X86_OP_IMM:
            return frozenset(), x.FLAGS
        return orig(self, ins)
    x.Lifter.flag_effect = eff


def mut_inc_kills_cf(x):
    orig = x.Lifter.flag_effect
    x.Lifter.flag_effect = lambda self, ins: (frozenset(), x.FLAGS) if ins.mnemonic in ("inc", "dec") else orig(self, ins)


def mut_no_reload_after_call(x):
    x.RELOAD_CALLS = x.RELOAD_CALLS - {"CALL"}


def mut_no_spill_before_icall(x):
    x.NO_SPILL_CALLS = x.NO_SPILL_CALLS | {"ICALL"}


def mut_no_spill_before_return(x):
    orig = x.Lifter.promote

    def promote(self, stmts):
        out = orig(self, stmts)
        leaves = out and ("return;" in out[-1] or "RET(" in out[-1])
        return out[1:] if leaves and out[0] == x.SPILL else out
    x.Lifter.promote = promote


MUTATIONS = {"jcc-reads-nothing": mut_jcc_reads_nothing, "call-not-a-boundary": not_a_boundary({"call"}),
             "cl-shift-always-writes": mut_cl_shift_kills, "inc-dec-overwrite-cf": mut_inc_kills_cf,
             "return-not-a-boundary": not_a_boundary({"ret", "retn"})}
def mut_written_set_misses_esp(x):
    import re
    x.REG_WRITE = re.compile(x.REG_WRITE.pattern.replace("[0-7]", "[0-35-7]"))


# --opt regs only
REG_MUTATIONS = {"regs-written-set-misses-esp": mut_written_set_misses_esp,"regs-no-reload-after-call": mut_no_reload_after_call,
                 "regs-no-spill-before-icall": mut_no_spill_before_icall,
                 "regs-no-spill-before-return": mut_no_spill_before_return}


def mut_x87_no_spill(x):
    x.X87_SPILL = "/* mutated: x87 locals not stored */"


def mut_x87_no_reload(x):
    x.X87_RELOAD = "/* mutated: x87 locals not reloaded */"


def mut_x87_helper_no_reload(x):
    orig = x.Lifter.x87_local

    def x87_local(self, stmts):
        out = orig(self, stmts)
        return out[:-1] if out and out[-1] == x.X87_RELOAD else out
    x.Lifter.x87_local = x87_local


# --opt x87 only
X87_MUTATIONS = {"x87-no-spill": mut_x87_no_spill, "x87-no-reload": mut_x87_no_reload,
                 "x87-helper-no-reload": mut_x87_helper_no_reload}


def mut_x87v_label_keeps_values(x):
    orig = x.Lifter.x87_values
    x.Lifter.x87_values = lambda self, body, labels: orig(self, body, set())


def mut_x87v_call_keeps_values(x):
    x.Lifter.x87v_ends = staticmethod(lambda s: False)


def mut_iflags_reads_nothing(x):
    orig = x.Lifter.iflag_solve
    x.Lifter.iflag_solve = lambda self, *a: (lambda r: (r[0], frozenset(), r[2], r[3]))(orig(self, *a))


def mut_iflags_preserves_nothing(x):
    orig = x.Lifter.iflag_solve
    x.Lifter.iflag_solve = lambda self, *a: (lambda r: (r[0], r[1], frozenset(), r[3]))(orig(self, *a))


def mut_iflags_returns_read_nothing(x):
    orig = x.Lifter.iflag_solve
    x.Lifter.iflag_solve = lambda self, *a: (lambda r: (r[0], r[1], r[2], {}))(orig(self, *a))


def mut_iflags_tail_is_return(x):
    orig = x.Lifter.iflag_nodes

    def nodes(self, fn):
        out = orig(self, fn)
        return {va: (n[:4] + ((("ret",),) if n[4] and n[4][0] == "exit" else (n[4],)) + n[5:]) for va, n in out.items()}
    x.Lifter.iflag_nodes = nodes


def mut_iflags_address_taken_known(x):
    orig = x.Lifter.iflag_analysis

    def analysis(self):
        r = self.img.reloc_targets_in_text
        self.img.reloc_targets_in_text = lambda: set()
        try:
            return orig(self)
        finally:
            self.img.reloc_targets_in_text = r
    x.Lifter.iflag_analysis = analysis


def mut_iflags_indirect_reads_nothing(x):
    orig = x.Lifter.iflag_nodes

    def nodes(self, fn):
        out = orig(self, fn)
        for va, n in out.items():
            ins = fn.insns[va]
            if ins.mnemonic == "call" and n[4] is None and ins.operands[0].type != x.X.X86_OP_IMM:
                out[va] = (frozenset(), frozenset()) + n[2:5] + (False, False)
        return out
    x.Lifter.iflag_nodes = nodes


def mut_cflags_no_audit(x):
    x.Lifter.cflags_audit = False


# --opt iflags only
IFLAG_MUTATIONS = {"iflags-callee-reads-nothing": mut_iflags_reads_nothing,
                   "iflags-callee-preserves-nothing": mut_iflags_preserves_nothing,
                   "iflags-returns-read-nothing": mut_iflags_returns_read_nothing,
                   "iflags-tail-is-return": mut_iflags_tail_is_return,
                   "iflags-address-taken-known": mut_iflags_address_taken_known,
                   "iflags-indirect-reads-nothing": mut_iflags_indirect_reads_nothing}


# --opt x87v only
X87V_MUTATIONS = {"x87v-label-keeps-values": mut_x87v_label_keeps_values,
                  "x87v-call-keeps-values": mut_x87v_call_keeps_values}


def mut_x87w_exit_not_stored(x):
    x.Lifter.x87w_exits = staticmethod(lambda s: False)


X87W_STORE = r"^c->st\[\(ft_ \+ (\d)u\) & 7u\] = fc(\d)_;$"


def x87w_rewritten(edit):
    """Mutation (--opt x87w): the deferred stores x87_values emitted (standalone statements) edited after the pass."""
    def patch(x):
        import re
        orig = x.Lifter.x87_values

        def values(self, body, labels):
            out, used = orig(self, body, labels)
            return edit(re, out, labels), used
        x.Lifter.x87_values = values
    return patch


def label_not_stored(re, out, labels):
    res = []
    for i, (va, st) in enumerate(out):
        if i + 1 < len(out) and out[i + 1][0] in labels:
            while st and re.match(X87W_STORE, st[-1]):
                st = st[:-1]
        res.append((va, st))
    return res


def wrong_slot(re, out, labels):
    return [(va, [re.sub(X87W_STORE, lambda m: f"c->st[(ft_ + {int(m.group(1)) + 1}u) & 7u] = fc{m.group(2)}_;", s)
                  for s in st]) for va, st in out]


# --opt x87w only
X87W_MUTATIONS = {"x87w-exit-not-stored": mut_x87w_exit_not_stored,
                  "x87w-label-not-stored": x87w_rewritten(label_not_stored),
                  "x87w-wrong-slot": x87w_rewritten(wrong_slot)}

def sse_renamed(renames):
    """Mutation (--opt sse): some final forms replaced by the broken variants of sse_mutants.h."""
    def patch(x):
        x.SSE_FORMS = tuple((old, renames.get(new, new)) for old, new in x.SSE_FORMS)
    return patch


# --opt sse only
SSE_MUTATIONS = {"sse-float-store-wide": sse_renamed({"wrf32s(": "wrf32s_mut_wide("}),
                 "sse-double-store-narrow": sse_renamed({"wrf64s(": "wrf64s_mut_narrow("}),
                 "sse-compare-no-unordered": sse_renamed({"XFCOMPAREO(": "XFCOMPAREO_mut_nan(",
                                                          "fcompareo(c, ": "fcompareo_mut_nan(c, "}),
                 "sse-compare-equal-as-less": sse_renamed({"XFCOMPAREO(": "XFCOMPAREO_mut_le(",
                                                           "fcompareo(c, ": "fcompareo_mut_le(c, "})}


def main():
    global OPT
    args = sys.argv[1:]
    nvec = int(args[args.index("--vectors") + 1]) if "--vectors" in args else 2000
    OPT = args[args.index("--opt") + 1] if "--opt" in args else OPT
    DEFINES.extend(args[i + 1] for i, a in enumerate(args) if a == "--define")
    os.makedirs(OUT, exist_ok=True)
    defs = "".join(f"/D{d} " for d in DEFINES)
    sh("x86", f'cl /nologo /O2 /arch:IA32 /GS- /Zl /W3 /LD {defs}"{os.path.join(HERE, "cases.c")}" /Fo"{OUT}\\\\" '
              f'/link /NOENTRY /NODEFAULTLIB /BASE:0x5A000000 /DYNAMICBASE:NO /OUT:OptCases.dll')
    sh("x86", f'cl /nologo /O2 /W3 /I"{HERE}" "{os.path.join(HERE, "native.c")}" /Fo"{OUT}\\\\" /Fenative.exe')
    pe = pefile.PE(os.path.join(OUT, "OptCases.dll"))
    base = pe.OPTIONAL_HEADER.ImageBase
    with open(os.path.join(OUT, "image.bin"), "wb") as f:
        f.write(pe.get_memory_mapped_image())
    tests = sorted((s.name.decode(), base + s.address) for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name.startswith(b"t_"))
    names = [n for n, _ in tests]
    vas = [hex(v) for _, v in tests]
    native = os.path.join(OUT, "native.bin")
    subprocess.run([os.path.join(OUT, "native.exe"), os.path.join(OUT, "OptCases.dll"), native, str(nvec), *names], check=True)
    nat = records(native)

    def lifted_run(dst, opt, mutate=None):
        meta = lift(dst, opt, mutate)
        build_lifted(dst)
        path = os.path.join(OUT, dst + ".bin")
        cmd = [os.path.join(OUT, dst + ".exe"), os.path.join(OUT, "image.bin"), hex(base), path, str(nvec), *vas]
        try:
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL, timeout=300)
        except subprocess.TimeoutExpired:
            if mutate:
                return meta, None                   # a broken translation that no longer terminates
            raise
        if r.returncode:
            if mutate:
                return meta, None
            sys.exit(f"{dst}.exe exited {r.returncode:#x}")
        return meta, records(path)

    pmeta, plain = lifted_run("plain", False)
    ometa, opt = lifted_run("opt", True)
    full = [k for k in FIELDS if k not in ("fn", "vec", "pad")]
    if "cflags" in OPT.split(","):
        # cflags: the flags after a return are dead by definition (this harness is a caller reading them); every case
        # still folds the flags it computes into eax/edx/out, which stay compared
        full.remove("flags")
    if "lazypc" in OPT.split(","):
        full.remove("pc")      # lazypc: c->pc after the return is the last call/trap site, a diagnostic value
    vs_native = compare(nat, plain, ("eax", "edx", "h_in", "h_out"))
    not_ok = [(r["fn"], r["vec"], r["status"]) for r in plain + opt if r["status"]]
    vs_opt = compare(plain, opt, full)
    per_fn = {n: {"cases": nvec, "native_vs_plain": sum(1 for f, _, _ in vs_native if f == i),
                  "plain_vs_opt": sum(1 for f, _, _ in vs_opt if f == i)} for i, n in enumerate(names)}
    res = {"opt": OPT, "defines": DEFINES, "vectors_per_function": nvec, "functions": len(names), "cases": nvec * len(names),
           "static_traps": pmeta["static_traps"], "nonzero_status": len(not_ok),
           "native_vs_plain_mismatches": len(vs_native), "plain_vs_opt_mismatches": len(vs_opt),
           "optimizations": ometa.get("optimizations"), "per_function": per_fn}
    print(json.dumps({k: v for k, v in res.items() if k != "per_function"}, indent=1))
    for f, k, d in (vs_native[:5] + vs_opt[:5]):
        print(f"  mismatch {names[f]} vector {k}: {d}")
    # static traps: only the default branch of the switch's jump table (never taken: status stays 0)
    ok = not vs_native and not vs_opt and not not_ok
    if "--mutations" in args:
        res["mutations"] = {}
        if "regs" in OPT.split(","):
            MUTATIONS.update(REG_MUTATIONS)
        if "x87" in OPT.split(","):
            MUTATIONS.update(X87_MUTATIONS)
        if "x87v" in OPT.split(","):
            MUTATIONS.update(X87V_MUTATIONS)
        if "sse" in OPT.split(","):
            MUTATIONS.update(SSE_MUTATIONS)
        if "x87w" in OPT.split(","):
            MUTATIONS.update(X87W_MUTATIONS)
        if "iflags" in OPT.split(","):
            # iflags replaces the local "every call/return reads all flags" rule these two break; its own mutations
            # break the call-side summary, the return side, tail jumps, address-taken detection and indirect calls
            for name in ("call-not-a-boundary", "return-not-a-boundary"):
                MUTATIONS.pop(name, None)
            MUTATIONS.update(IFLAG_MUTATIONS)
        if "cflags" in OPT.split(","):
            # cflags replaces the "indirect calls read everything" rule and the address-taken return rule by its audit;
            # the audit is tested by lifting the violating DLL (no --define CFLAGS_CLEAN) with the audit disabled
            for name in ("iflags-indirect-reads-nothing", "iflags-address-taken-known"):
                MUTATIONS.pop(name, None)
            if "CFLAGS_CLEAN" not in DEFINES:
                MUTATIONS["cflags-no-audit"] = mut_cflags_no_audit
        for name in MUTATIONS:
            _, mut = lifted_run("mut", True, name)
            if mut is None:
                res["mutations"][name] = {"detected": True, "differing_cases": None, "functions": ["harness did not finish"]}
                print(f"mutation {name}: DETECTED (lifted run did not complete)")
                continue
            diff = compare(plain, mut, full)
            fns = sorted({names[f] for f, _, _ in diff})
            res["mutations"][name] = {"detected": bool(diff), "differing_cases": len(diff), "functions": fns}
            print(f"mutation {name}: {'DETECTED' if diff else 'NOT DETECTED'} ({len(diff)} cases; {', '.join(fns)})")
            ok = ok and bool(diff)
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, indent=1)
        f.write("\n")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
