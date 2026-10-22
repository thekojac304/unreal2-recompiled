"""Create a fresh, isolated copy of the game's singleplayer/System folder for one run.

Usage: python -I tools/xrt/make_sandbox.py <dest-root> [--probe]
  <dest-root>/System receives a copy of <install>/singleplayer/System (read-only source).
  --probe also adds VMProbe.u and VMProbe.ini (built in Phase 0 by the original compiler)
  from the Phase 0 sandbox.
Prints the SHA-256 of the copied engine binaries and Core.u so runs can be tied to inputs.
"""
import hashlib
import os
import shutil
import sys

INSTALL = r"E:\Launchbox\Games\PC Games\Unreal 2 - The Awakening\singleplayer\System"
WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    dest = os.path.abspath(sys.argv[1])
    if not os.path.basename(dest).startswith("sandbox") and "sandbox" not in dest:
        sys.exit("refusing: destination must be a sandbox directory")
    sysdir = os.path.join(dest, "System")
    if os.path.exists(sysdir):
        shutil.rmtree(sysdir)
    shutil.copytree(INSTALL, sysdir)
    if "--probe" in sys.argv:
        for f in ("VMProbe.u", "VMProbe.ini"):
            shutil.copy2(os.path.join(WS, "sandbox", "System", f), os.path.join(sysdir, f))
    for f in ("UCC.exe", "Core.dll", "Core.u") + (("VMProbe.u",) if "--probe" in sys.argv else ()):
        print(f"{f} {sha(os.path.join(sysdir, f))}")


if __name__ == "__main__":
    main()
