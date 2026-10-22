"""Check that the constants the harnesses use for the mirrored engine sequences equal the memory operands
the engine actually loads (read from the sandbox Core.dll as data; nothing is executed or copied out).

  FGlobalMath::FGlobalMath  sine table  fmul qword [C]   harness: pi/16384 (double)
  FGlobalMath::FGlobalMath  sqrt table  fmul dword [C]   harness: 2^-14 (float)
  appInit timing loop                   fadd qword [C]   harness: 3.14 (double)

Prints JSON: for each site, the instruction RVA, whether the operand value equals the harness constant,
and the loop bound found next to it.
Usage: python -I check_constants.py <Core.dll>
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "tools", "xrt"))
from discover import Module  # noqa: E402

FGLOBALMATH = "??0FGlobalMath@@QAE@XZ"
APPSIN, APPSQRT = "?appSin@@YANN@Z", "?appSqrt@@YANN@Z"


def main():
    mod = Module(sys.argv[1]).run()
    img, base = mod.img, mod.img.base
    exp = {n: base + r for n, r in img.exports.items()}
    out = {}

    def mem(ins):
        for op in ins.operands:
            if op.type == 3 and op.mem.base == 0 and op.mem.index == 0:
                return op.mem.disp & 0xFFFFFFFF, op.size
        return None, None

    def scan(entry, callee, want, label):
        fn = mod.functions[entry]
        order = sorted(fn.insns)
        for i, va in enumerate(order):
            ins = fn.insns[va]
            if ins.mnemonic == "call" and ins.operands[0].type == 2 and (ins.operands[0].imm & 0xFFFFFFFF) == callee:
                # nearest preceding fmul/fadd with an absolute memory operand
                for j in range(i - 1, max(i - 8, -1), -1):
                    pv = fn.insns[order[j]]
                    a, size = mem(pv)
                    if pv.mnemonic in ("fmul", "fadd") and a is not None:
                        raw = bytes(img.image[a - base:a - base + size])
                        val = struct.unpack("<d" if size == 8 else "<f", raw)[0]
                        bound = None
                        for k in range(i, min(i + 10, len(order))):
                            c = fn.insns[order[k]]
                            if c.mnemonic == "cmp" and c.operands[1].type == 2:
                                bound = c.operands[1].imm
                                break
                        out.setdefault(label, []).append({"call_rva": hex(va - base), "operand_rva": hex(pv.address - base),
                                                          "instruction": pv.mnemonic, "operand_size": size,
                                                          "equals_harness_constant": val == want,
                                                          "loop_bound": bound})
                        break

    scan(exp[FGLOBALMATH], exp[APPSIN], 3.14159265358979323846 / 16384.0, "sine_table_step_pi_over_16384")
    scan(exp[FGLOBALMATH], exp[APPSQRT], struct.unpack("<f", struct.pack("<f", 6.103515625e-05))[0], "sqrt_table_scale_2^-14")
    for e, fn in mod.functions.items():
        for va, ins in fn.insns.items():
            if ins.mnemonic == "call" and ins.operands[0].type == 2 and (ins.operands[0].imm & 0xFFFFFFFF) == exp[APPSQRT]:
                order = sorted(fn.insns)
                i = order.index(va)
                for k in range(i + 1, min(i + 8, len(order))):
                    c = fn.insns[order[k]]
                    a, size = mem(c)
                    if c.mnemonic == "fadd" and a is not None and size == 8:
                        val = struct.unpack("<d", bytes(img.image[a - base:a - base + 8]))[0]
                        if val == 3.14:
                            out.setdefault("timing_loop_3.14", []).append({"function_rva": hex(e - base), "call_rva": hex(va - base),
                                                                           "operand_rva": hex(c.address - base),
                                                                           "equals_harness_constant": True})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
