# Measured msvcr70 `tolower` boundary

The x86 oracle loads **only** the manifest-bound isolated `System/msvcr70.dll`.
The x64 candidate calls `xrt_hle_msvcr70` with actual guest memory and CPU state.
Neither side calls the host C runtime's `tolower`.

Build serially with `build.cmd`, then run `compare.py` from the workspace root.
The comparison writes a fresh evidence directory and verifies all protected
inputs around every process. `build_state.cmd` adds guest TEB/thread-state checks.

The 2026-10-23 run checked all **4,294,967,296** input bit patterns on **each**
side in the C locale: zero return mismatches against the full-int mapping
`65..90 -> input+32`, otherwise the original 32-bit input. This includes EOF,
negative integers and values above 255; inputs are never narrowed to a byte.
This exhaustive sweep checks returns. The separate **397,314-case** state corpus
checks errno, last-error, cdecl stack cleanup and callee-saved registers, including
all bytes, EOF, dense signed boundaries, all high words and seeded random bits.
Its C, C+MBCP932 and C+MBCP1254 outputs are byte-identical to the candidate.

Native first calls on two concurrently alive CRT threads preserve last-error,
start with errno zero, and expose distinct errno locations, also distinct from
the main thread. The candidate checks independent guest-thread errno storage.
The additional guest-state fixture checks the TEB last-error word, host
last-error, errno and thread PRNG state across all state-corpus inputs.

English/1252, Turkish/1254 and Japanese/932 are **measurements, not supported
adapter modes**. Non-ASCII case mappings, out-of-byte-domain returns and some
last-error effects differ from C. Examples: English/1252 `0xc0 -> 0xe0`,
Japanese/932 `0x8260 -> 0x8281`, and English/1252 EOF `-1 -> 0xff`.
The current Windows locale spelling accepted by this old CRT was
`Turkish_Türkiye.1254`; `Turkish_Turkey.1254` and `Turkish.1254` failed.
Those failures and initial attempts remain in the raw evidence.

The translated runtime has no locale-changing adapter: `setlocale` and
`_setmbcp` remain unbound and produce explicit unsupported-import diagnostics.
The host runtime's locale never selects guest `tolower` behavior.

Raw evidence: `experiments/xrt/results/raw/tolower-world-20261023/oracle-final/`.
Expanded CRT's **110 mismatches / 1,796 pending**, the **six ACP 932 differences**,
and x87 sticky-status/tag/large-input/double-rounding limitations remain open.
