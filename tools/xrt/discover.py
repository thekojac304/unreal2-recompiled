"""Static function discovery for MSVC-compiled PE32 modules (recursive descent).

Seeds: entry point, exports in code, relocation-referenced code addresses (vtables,
function-pointer tables, EH funclets, jump-table targets), and direct call targets
found while decoding. Jump tables follow the MSVC patterns
    [cmp r, N; ja dflt;] [movzx r, byte [r + btab];] jmp dword [r*4 + tab]
and are bounded by the cmp/ja guard when present, else by the run of relocated slots.

Everything that cannot be resolved statically (indirect calls, unrecognised indirect
jumps) is recorded so the lifter can route it through the runtime dispatcher, and the
runtime can fail with a precise diagnostic when a target is unknown.

Usage: python -I tools/xrt/discover.py <module> [--base 0x...] [--entries out.txt] [--json out.json]
"""
import collections
import json
import sys

from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from capstone import x86 as X

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from peimage import PEImage  # noqa: E402

JCC = {"je", "jne", "jl", "jge", "jle", "jg", "jb", "jae", "jbe", "ja", "js", "jns", "jp", "jnp", "jo", "jno"}
NORETURN_IMPORTS = {"_CxxThrowException", "exit", "_exit", "abort", "ExitProcess", "_amsg_exit", "?terminate@@YAXXZ",
                    "RaiseException", "_invalid_parameter_noinfo_noreturn", "longjmp"}


class Function:
    __slots__ = ("entry", "insns", "labels", "jumptables", "calls", "icalls", "ijmps", "tails", "problems", "fallthrough_into")

    def __init__(self, entry):
        self.entry = entry
        self.insns = {}          # va -> capstone insn
        self.labels = set()      # branch targets inside the function
        self.jumptables = {}     # jmp insn va -> list of target vas
        self.calls = set()       # direct call targets
        self.icalls = []         # va of indirect calls (via dispatcher)
        self.ijmps = []          # va of indirect jumps that are not jump tables (tail dispatch)
        self.tails = set()       # direct tail-jump targets (other functions)
        self.problems = []       # (va, text) - lifted as runtime traps
        self.fallthrough_into = []


class Module:
    def __init__(self, path, base=None):
        self.img = PEImage(path, base)
        self.md = Cs(CS_ARCH_X86, CS_MODE_32)
        self.md.detail = True
        self.relocs = self.img.reloc_vas()
        self._cache = {}
        self.entries = set()
        self.seed_kind = collections.defaultdict(set)
        self.functions = {}
        self.owner = {}          # insn va -> set of function entries
        self.data_in_text = []   # (start, end) of byte-index tables found next to jump tables
        self.data_refs = set()   # code-section addresses used as absolute memory operands

    def decode(self, va):
        ins = self._cache.get(va)
        if ins is None:
            if not self.img.in_text(va):
                return None
            code = self.img.bytes_at(va, 16)
            got = list(self.md.disasm(code, va, 1))
            ins = got[0] if got else None
            self._cache[va] = ins
        return ins

    def is_iat(self, op):
        return op.type == X.X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0 and op.mem.segment == 0 \
            and (op.mem.disp & 0xFFFFFFFF) in self.img.iat

    def seeds(self):
        img = self.img
        if img.entry_rva:
            self.add_seed(img.base + img.entry_rva, "entry")
        for name, rva in img.exports.items():
            if img.in_text(img.base + rva):
                self.add_seed(img.base + rva, "export")
        for t in img.reloc_targets_in_text():
            self.add_seed(t, "reloc")
        if not img.relocs:
            # EXE without .reloc: code pointers in data must be found by scanning aligned dwords.
            for s in img.sections:
                if s["flags"] & 0x20000000:
                    continue
                for off in range(0, s["vsize"] - 3, 4):
                    v = img.u32(img.base + s["rva"] + off)
                    if img.in_text(v) and self.plausible_entry(v):
                        self.add_seed(v, "datascan")

    def plausible_entry(self, va):
        ins = self.decode(va)
        if ins is None or ins.mnemonic in ("int3", "hlt") or ins.bytes[:2] == b"\0\0":
            return False
        return True

    def add_seed(self, va, kind):
        self.seed_kind[va].add(kind)
        self.entries.add(va)

    def is_boundary(self, va):
        """A seed that marks a real function start (not merely a relocated label inside a function)."""
        kinds = self.seed_kind.get(va)
        return bool(kinds) and bool(kinds - {"reloc", "datascan", "imm"})

    def noreturn_target(self, t):
        ins = self.decode(t)
        if ins is not None and ins.mnemonic == "jmp" and self.is_iat(ins.operands[0]):
            return self.img.iat[ins.operands[0].mem.disp & 0xFFFFFFFF][1] in NORETURN_IMPORTS
        return t in self.noreturn_funcs

    noreturn_funcs = frozenset()

    # ---------------------------------------------------------------- jump tables
    def jump_table(self, fn, ins, block_insns):
        op = ins.operands[0]
        mm = op.mem
        if not (op.type == X.X86_OP_MEM and mm.index != 0 and mm.scale == 4 and mm.base == 0 and mm.segment == 0):
            return None
        tab = mm.disp & 0xFFFFFFFF
        idx_reg = mm.index
        bound = None
        btab = None
        # walk back within the block for movzx idx, byte [idx + btab] and cmp idx, N / ja
        for prev in reversed(block_insns[-6:]):
            m = prev.mnemonic
            ops = prev.operands
            if m == "movzx" and len(ops) == 2 and ops[0].type == X.X86_OP_REG and ops[1].type == X.X86_OP_MEM and ops[1].size == 1 \
                    and ops[1].mem.disp and btab is None:
                btab = (ops[1].mem.disp & 0xFFFFFFFF)
            if m == "cmp" and len(ops) == 2 and ops[1].type == X.X86_OP_IMM and ops[0].type == X.X86_OP_REG:
                bound = ops[1].imm & 0xFFFFFFFF
                break
        count = None
        if btab is not None and bound is not None and self.img.in_image(btab):
            count = max(self.img.u8(btab + k) for k in range(bound + 1)) + 1
            self.data_in_text.append((btab, btab + bound + 1))
        elif btab is None and bound is not None:
            count = bound + 1
        targets = []
        k = 0
        while True:
            slot = tab + 4 * k
            if count is not None and k >= count:
                break
            if count is None and slot not in self.relocs:
                break
            if not self.img.in_image(slot):
                return None
            t = self.img.u32(slot)
            if not self.img.in_text(t):
                if count is None:
                    break
                return None
            targets.append(t)
            k += 1
            if k > 4096:
                return None
        return targets or None

    # ---------------------------------------------------------------- per-function descent
    def explore(self, entry):
        fn = Function(entry)
        todo = [entry]
        while todo:
            va = todo.pop()
            block = []
            while va not in fn.insns:
                if va != entry and self.is_boundary(va) and va not in fn.labels:
                    # fell into another function (e.g. after a noreturn call that we did not know)
                    fn.fallthrough_into.append(va)
                    break
                ins = self.decode(va)
                if ins is None:
                    fn.problems.append((va, "undecodable or outside code"))
                    break
                fn.insns[va] = ins
                block.append(ins)
                m = ins.mnemonic
                ops = ins.operands
                nxt = va + ins.size
                if m in JCC or m in ("jecxz", "loop", "loope", "loopne"):
                    t = ops[0].imm & 0xFFFFFFFF
                    fn.labels.add(t)
                    fn.labels.add(nxt)
                    todo.append(t)
                elif m == "jmp":
                    if ops[0].type == X.X86_OP_IMM:
                        t = ops[0].imm & 0xFFFFFFFF
                        if self.is_boundary(t) and t != entry:
                            fn.tails.add(t)
                        else:
                            fn.labels.add(t)
                            todo.append(t)
                    elif self.is_iat(ops[0]):
                        pass
                    else:
                        tg = self.jump_table(fn, ins, block)
                        if tg is not None:
                            fn.jumptables[va] = tg
                            for t in tg:
                                fn.labels.add(t)
                                todo.append(t)
                        else:
                            fn.ijmps.append(va)
                    break
                elif m in ("ret", "retn", "iret", "iretd"):
                    break
                elif m == "call":
                    if ops[0].type == X.X86_OP_IMM:
                        t = ops[0].imm & 0xFFFFFFFF
                        fn.calls.add(t)
                        self.add_seed(t, "call")
                        if self.noreturn_target(t):
                            break
                    elif self.is_iat(ops[0]):
                        name = self.img.iat[ops[0].mem.disp & 0xFFFFFFFF][1]
                        if name in NORETURN_IMPORTS:
                            break
                    else:
                        fn.icalls.append(va)
                elif m in ("int3", "hlt", "ud2"):
                    fn.problems.append((va, f"{m} reached by static flow"))
                    break
                for op in ops:
                    if op.type == X.X86_OP_MEM and op.mem.segment == 0:
                        d = op.mem.disp & 0xFFFFFFFF
                        if self.img.in_text(d):        # code-section address used as data operand
                            self.data_refs.add(d)
                if not self.img.relocs:
                    for op in ops:
                        if op.type == X.X86_OP_IMM and self.img.in_text(op.imm & 0xFFFFFFFF) and m in ("push", "mov"):
                            t = op.imm & 0xFFFFFFFF
                            if t not in self.entries and self.plausible_entry(t):
                                self.add_seed(t, "imm")
                va = nxt
                if va in fn.labels and va in fn.insns:
                    break
        return fn

    def _explore_all(self, max_rounds=50):
        self.functions = {}
        for _ in range(max_rounds):
            pending = [e for e in self.entries if e not in self.functions]
            if not pending:
                break
            for e in sorted(pending):
                self.functions[e] = self.explore(e)

    def run(self):
        self.seeds()
        self._explore_all()
        # Pass 2: relocated addresses that are jump-table data or jump-table case labels are not
        # function entries; drop them (unless also exported/called) and rediscover.
        data_ranges, case_labels = [], set()
        for fn in self.functions.values():
            for jva, targets in fn.jumptables.items():
                tab = fn.insns[jva].operands[0].mem.disp & 0xFFFFFFFF
                data_ranges.append((tab, tab + 4 * len(targets)))
                case_labels.update(targets)
        data_ranges = data_ranges + self.data_in_text
        self.table_data = data_ranges
        drop = set()
        for va in list(self.entries):
            if self.is_boundary(va):
                continue
            if va in case_labels or va in self.data_refs or any(a <= va < b for a, b in data_ranges):
                drop.add(va)
        if drop:
            self.entries -= drop
            for va in drop:
                self.seed_kind.pop(va, None)
            self._explore_all()
        # Pass 3 (modules without relocations): heuristic data/immediate seeds that start inside an
        # instruction of a real function are false positives.
        if not self.img.relocs:
            bad = {va for va in self.conflicting() if va in self.entries and not self.is_boundary(va)}
            if bad:
                self.entries -= bad
                for va in bad:
                    self.seed_kind.pop(va, None)
                self._explore_all()
        for e, fn in self.functions.items():
            for va in fn.insns:
                self.owner.setdefault(va, set()).add(e)
        return self

    # ---------------------------------------------------------------- safety for breakpoints
    def instruction_starts(self):
        starts = {}
        for fn in self.functions.values():
            for va, ins in fn.insns.items():
                starts[va] = ins.size
        return starts

    def conflicting(self):
        """Instruction starts that lie inside another decoded instruction (decoding disagreement)."""
        starts = self.instruction_starts()
        covered = {}
        for va, sz in starts.items():
            for k in range(1, sz):
                covered[va + k] = va
        return {va for va in starts if va in covered}

    def summary(self):
        fns = self.functions.values()
        return {
            "module": self.img.name, "base": hex(self.img.base), "functions": len(self.functions),
            "instructions": sum(len(f.insns) for f in fns),
            "jump_tables": sum(len(f.jumptables) for f in fns),
            "indirect_calls": sum(len(f.icalls) for f in fns),
            "indirect_jumps_unresolved": sum(len(f.ijmps) for f in fns),
            "fallthrough_into_other_function": sum(len(f.fallthrough_into) for f in fns),
            "static_problems": sum(len(f.problems) for f in fns),
            "decode_conflicts": len(self.conflicting()),
            "seed_kinds": dict(collections.Counter(k for ks in self.seed_kind.values() for k in ks)),
        }


def main():
    args = sys.argv[1:]
    base = int(args[args.index("--base") + 1], 16) if "--base" in args else None
    mod = Module(args[0], base).run()
    s = mod.summary()
    print(json.dumps(s, indent=1))
    if "--entries" in args:
        bad = mod.conflicting()
        with open(args[args.index("--entries") + 1], "w") as f:
            for e in sorted(mod.functions):
                if e not in bad and mod.decode(e) is not None:
                    f.write(f"{e - mod.img.base:x}\n")
    if "--json" in args:
        out = {"summary": s, "functions": {hex(e): {"n": len(f.insns), "calls": sorted(hex(c) for c in f.calls),
                                                    "icalls": len(f.icalls), "ijmps": [hex(v) for v in f.ijmps],
                                                    "problems": [(hex(v), t) for v, t in f.problems]}
                                           for e, f in sorted(mod.functions.items())}}
        with open(args[args.index("--json") + 1], "w") as f:
            json.dump(out, f)


if __name__ == "__main__":
    main()
