"""Create a fresh, isolated copy of the game's singleplayer/System folder for one run.

Usage: python -I tools/xrt/make_sandbox.py <dest-root> [--probe]
  <dest-root>/System receives a copy of <install>/singleplayer/System (read-only source). <dest-root> must be a
  directory below the workspace whose first path component starts with "sandbox" (e.g. sandbox_cmp/<case>).
  --probe also adds VMProbe.u and VMProbe.ini (built in Phase 0 by the original compiler)
  from the Phase 0 sandbox.
Prints the SHA-256 of the copied engine binaries and packages the runs use, so runs can be tied to inputs.
An existing <dest-root>/System is removed first; a file still held open by a process that is exiting is retried
for a few seconds before giving up.
"""
import hashlib
import os
import shutil
import sys
import time

INSTALL = r"E:\Launchbox\Games\PC Games\Unreal 2 - The Awakening\singleplayer\System"
WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IDENTITY_FILES = ("UCC.exe", "Core.dll", "Core.u", "Engine.dll", "Engine.u", "msvcr70.dll")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def check_destination(dest):
    relp = os.path.relpath(dest, WS)
    first = relp.replace("\\", "/").split("/", 1)[0]
    if relp.startswith("..") or os.path.isabs(relp) or not first.startswith("sandbox") or relp == first:
        sys.exit(f"refusing: destination must be a directory below {WS}\\sandbox*\\ (got {dest})")
    if os.path.normcase(dest).startswith(os.path.normcase(os.path.dirname(INSTALL))):
        sys.exit("refusing: destination inside the game installation")


def remove_tree(path, attempts=40):
    for k in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            if k == attempts - 1:
                raise
            time.sleep(0.25)


def main():
    dest = os.path.abspath(sys.argv[1])
    check_destination(dest)
    sysdir = os.path.join(dest, "System")
    if os.path.exists(sysdir):
        remove_tree(sysdir)
    shutil.copytree(INSTALL, sysdir)
    if "--probe" in sys.argv:
        for f in ("VMProbe.u", "VMProbe.ini"):
            shutil.copy2(os.path.join(WS, "sandbox", "System", f), os.path.join(sysdir, f))
    for f in IDENTITY_FILES + (("VMProbe.u", "VMProbe.ini") if "--probe" in sys.argv else ()):
        if os.path.exists(os.path.join(sysdir, f)):
            print(f"{f} {sha(os.path.join(sysdir, f))}")


if __name__ == "__main__":
    main()
