#!/bin/sh
# Build the lifted Core.dll routines with gcc on Linux (x86-64 or ARM64) and compare with the
# original-DLL reference produced on Windows x86 (build/original_x86.txt).
set -e
cd /work/experiments/lift
tr -d '\r' < build/original_x86.txt > /tmp/original_x86.lf
OUT=build/$1
mkdir -p "$OUT"
echo "arch: $(uname -m)  $(gcc --version | head -n1)"
for mode in strict contract; do
  if [ $mode = strict ]; then FLAGS="-ffp-contract=off"; else FLAGS="-ffp-contract=fast"; fi
  gcc -std=c99 -O2 $FLAGS -Wno-unused-label -o "$OUT/harness_$mode" harness_lifted.c lifted_core.c -lm
  "$OUT/harness_$mode" /work/sandbox/System/Core.dll > "$OUT/lifted_$mode.txt"
  if cmp -s /tmp/original_x86.lf "$OUT/lifted_$mode.txt"; then
    echo "[$mode $FLAGS] IDENTICAL to original x86 ($(wc -l < "$OUT/lifted_$mode.txt") lines)"
  else
    echo "[$mode $FLAGS] DIFFERENT: $(diff /tmp/original_x86.lf "$OUT/lifted_$mode.txt" | grep -c '^<') differing lines"
    diff /tmp/original_x86.lf "$OUT/lifted_$mode.txt" | head -n 6
  fi
done
