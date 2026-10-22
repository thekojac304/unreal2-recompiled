#!/bin/sh
# Build uvm with g++ inside a Linux container and run the differential tests.
# Expects the workspace mounted at /work. Usage: run_linux_tests.sh <build-dir-name>
set -e
OUT=/work/experiments/uvm/build/$1
mkdir -p "$OUT"
cd /work/experiments/uvm
g++ -std=c++17 -O2 -Wall -Wextra -o "$OUT/uvm" src/package.cpp src/vm.cpp src/natives_core.cpp src/main.cpp
echo "arch: $(uname -m)  compiler: $(g++ --version | head -n1)"
SYS=/work/sandbox/System
REF=/work/experiments/vmprobe
status=0
for c in HelloWorldCommandlet SimpleCommandlet ArrayTest; do
  echo "== Core.$c"
  "$OUT/uvm" "$SYS" "Core.$c" --parms "a b c" --quiet --compare "$REF/Core.$c.reference.txt" || status=1
done
echo "== VMProbe"
"$OUT/uvm" "$SYS" VMProbe.VMProbe --quiet --compare "$REF/VMProbe.reference.txt" || status=1
exit $status
