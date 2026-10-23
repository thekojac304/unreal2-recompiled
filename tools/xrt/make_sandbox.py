"""Copy manifest-verified, independent snapshot System inputs into a writable run tree.

Usage: python -I tools/xrt/make_sandbox.py <dest-root> [--probe]
XRT_ASSET_MANIFEST selects a verified snapshot manifest; there is no installation fallback.
Destinations must be below workspace sandbox* directories. Previous sandbox_cmp outputs
are archived intact. --probe adds the manifest-bound preserved VMProbe package/config.
Both sides of staging verify all protected inputs. Stdout retains the hash-pair format
used by the commandlet and compiler evidence drivers.
"""
import hashlib
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asset_boundary as A

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IDENTITY_FILES = ("UCC.exe", "Core.dll", "Core.u", "Engine.dll", "Engine.u", "GlmLib.dll", "msvcr70.dll")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def check_destination(dest):
    relp = os.path.relpath(dest, WS)
    first = relp.replace("\\", "/").split("/", 1)[0]
    if relp.startswith("..") or os.path.isabs(relp) or first != 'sandbox_cmp' or relp == first:
        sys.exit(f"refusing: destination must be a directory below {WS}\\sandbox*\\ (got {dest})")
    A.check_writable(dest)


def remove_tree(path, attempts=40):
    if Path(path).absolute().is_relative_to(Path(WS) / 'sandbox_cmp'):
        A.archive(path)
        return
    for k in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            if k == attempts - 1:
                raise
            time.sleep(0.25)


def main():
    A.verify(system_only=True)
    dest = os.path.abspath(sys.argv[1])
    check_destination(dest)
    sysdir = os.path.join(dest, "System")
    if os.path.exists(sysdir):
        remove_tree(sysdir)
    shutil.copytree(A.source() / 'System', sysdir)
    if "--probe" in sys.argv:
        for f in ("VMProbe.u", "VMProbe.ini"):
            shutil.copy2(Path(A.manifest()['probe_root']) / f, os.path.join(sysdir, f))
    for f in IDENTITY_FILES + (("VMProbe.u", "VMProbe.ini") if "--probe" in sys.argv else ()):
        if os.path.exists(os.path.join(sysdir, f)):
            print(f"{f} {sha(os.path.join(sysdir, f))}")
    A.verify(system_only=True)


if __name__ == "__main__":
    main()
