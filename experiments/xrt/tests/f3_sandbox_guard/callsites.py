"""F3 validation helper: list call sites of the sandbox-guarded KERNEL32 imports in the guest modules,
search for "\\?\\" (long-path prefix) strings, and list the path-related imports.

Usage: python -I callsites.py <module.dll|exe> [...]   (reads the sandbox copy; prints addresses only)"""
import sys

sys.path.insert(0, r"E:\Unreal2-Port-Investigation\tools\xrt")
from discover import Module  # noqa: E402

GUARDED = {"CreateFileW", "CreateFileA", "SetFileAttributesW", "DeleteFileW", "SetCurrentDirectoryW"}
PATHY = ("File", "Directory", "Path", "Find")


def main():
    for path in sys.argv[1:]:
        m = Module(path)
        img = m.img
        print(f"== {img.name} base {img.base:#x}")
        imps = sorted({nm for _, dll, nm in img.imports if dll.lower() == "kernel32.dll" and any(p in nm for p in PATHY)})
        print("  kernel32 path-related imports:", ", ".join(imps))
        m.run()
        iat = {va: nm for va, (dll, nm) in img.iat.items() if dll.lower() == "kernel32.dll" and nm in GUARDED}
        sites = {}
        for fe, fn in m.functions.items():
            for va, ins in fn.insns.items():
                if ins.mnemonic not in ("call", "jmp"):
                    continue
                for op in ins.operands:
                    if op.type == 3 and op.mem.base == 0 and op.mem.index == 0 and (op.mem.disp & 0xFFFFFFFF) in iat:
                        sites.setdefault(iat[op.mem.disp & 0xFFFFFFFF], []).append((va, fe))
        for nm in sorted(sites):
            print(f"  {nm}: {len(sites[nm])} site(s): " + ", ".join(f"{va:#x} (fn {fe:#x})" for va, fe in sorted(sites[nm])))
        data = bytes(img.image)
        bs = chr(0x5C)
        for prefix in (bs + bs + "?" + bs, bs + bs + "." + bs, "?" + bs):
            for kind, pat in (("ansi", prefix.encode("ascii")), ("wide", prefix.encode("utf-16-le"))):
                hits = [i for i in range(len(data)) if data.startswith(pat, i)]
                print(f"  {kind} {prefix!r} occurrences: {len(hits)}" + (" at rva " + ", ".join(f"{h:#x}" for h in hits[:8]) if hits else ""))


if __name__ == "__main__":
    main()
