# Function-level differential test of `xlift --opt` (`opt_diff`)

Checks the translator optimizations of `tools/xrt/xlift.py --opt` (flag liveness, pc-store elision, local
guest-memory base, guest registers in locals) on whole functions, where the per-instruction test
(`../insn_diff`, which also has a `--live-random` mode for the reduced flag updates) cannot see control flow.

```bat
.venv\Scripts\python.exe -I experiments\xrt\tests\opt_diff\run.py --mutations --vectors 3000
.venv\Scripts\python.exe -I experiments\xrt\tests\opt_diff\run.py --opt flags,pc --mutations
```

1. `cases.c` (owned code, no game bytes) is built as a 32-bit DLL with `cl /O2 /arch:IA32` and no CRT: compare
   chains, 64-bit arithmetic and compares (adc/sbb/shld/shrd), a jump table, setcc, x87 compares through
   `fnstsw ax / test ah / jp` on arbitrary float bit patterns, byte/word arithmetic, direct, recursive and
   indirect calls, `rep movsb/stosd`, shifts by `cl`, division; plus hand-written `__asm` functions that keep flags
   alive where compilers never do: across a shift by `cl` = 0, `inc`/`dec` (CF), labels, backward edges,
   `loop/loopne/jecxz`, a call to a flag-preserving function, a callee that reads the caller's CF, and the return.
2. It is lifted twice (plain and `--opt`, default `flags,pc,base`) into `experiments/xrt/build/opt_diff/` and
   compiled for x64 with the game build's flags (`/O2 /fp:strict`) against `out/dev-init/runtime/xrt.h`.
3. `native.exe` (x86) calls every export on the CPU; `plain.exe` and `opt.exe` run the lifted code from the same
   vectors (`opt_diff.h`: in/out buffers at fixed addresses, arguments, random initial registers and flags).
4. Compared: plain vs opt the complete state after every return (status, all GPRs, CF PF ZF SF OF DF, `c->pc`,
   x87 TOP/FCW/FSW and ST(0..7) bit patterns, in/out/stack memory hashes); native vs plain the return value and
   the in/out buffers.
5. `--mutations` re-lifts with deliberately broken rules (jcc reads nothing; call / return not a boundary; shift
   by `cl` always overwrites; inc/dec overwrite CF; with `regs`: no reload after a call, no spill before an
   indirect call or a return). Each must change some result. Exit 0 only if everything agrees and every
   mutation is detected. `results.json` records the last run.
