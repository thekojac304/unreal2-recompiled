r"""F2 driver: real msvcr70 __getmainargs (system ACP and per-process ACP 932) vs the runtime adapter.

Run after build.cmd:  .venv\Scripts\python -I experiments\xrt\tests\f2_mbcs_argv\run_f2.py
For every case the reference harness is started with CreateProcessW and the given wide command line; the
candidate harness parses the exact bytes the reference saw (msvcr70's _acmdln), so only the parsers differ.
Also prints, per DBCS code page, which ASCII bytes are valid trail bytes on this host (MultiByteToWideChar).
"""
import ctypes
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
OUT = os.path.join(ROOT, "experiments", "xrt", "build", "f2_mbcs_argv")
DLL = os.path.join(ROOT, "sandbox_ref", "hellofull", "System", "msvcr70.dll")

# the part after the program name; the program name is always the quoted harness path
BS = chr(0x5C)
CASES = [
    "Core.HelloWorldCommandlet a b c",
    'x=1 -flag "two words" back' + BS + 'slash',
    '"表" a b',                         # U+8868 = 95 5C in CP932
    '"ソ" a b',                         # U+30BD = 83 5C
    '"能"x y',                          # U+80FD = 94 5C
    "表" + BS + '"x y',                 # U+8868 then backslash-quote: trail 5C + 5C + 22
    "ソフト a",                 # 5C trail not followed by a quote
    '"C:' + BS + 'ダメ文字ソ" next',
    'Core.HelloWorldCommandlet "C:' + BS + 'ソ" b',   # divergence only after argv[1]
    '"日本" a',                     # no 5C trail
]


def parse(text):
    r = {"argv": []}
    for line in text.splitlines():
        k, _, v = line.partition(" ")
        if k == "argv":
            r["argv"].append(v)
        else:
            r[k] = v
    return r


def run_ref(exe, tail):
    cmdline = '"%s" %s' % (exe, tail)
    env = dict(os.environ, F2_MSVCR70=DLL)
    p = subprocess.run(cmdline, env=env, capture_output=True, text=True)   # str -> CreateProcessW as-is
    if p.returncode:
        raise SystemExit("%s failed %d: %s" % (exe, p.returncode, p.stderr))
    return parse(p.stdout)


def run_cand(cmdhex):
    p = subprocess.run([os.path.join(OUT, "cand_argv.exe"), cmdhex], capture_output=True, text=True)
    if p.returncode:
        raise SystemExit("cand failed %d: %s %s" % (p.returncode, p.stdout, p.stderr))
    return parse(p.stdout)


def show(argv):
    out = []
    for h in argv[1:]:
        out.append("-" if h == "-" else h)
    return " | ".join(out)


def trail_census():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.MultiByteToWideChar.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_char_p, ctypes.c_int, ctypes.c_wchar_p, ctypes.c_int]
    k32.IsDBCSLeadByteEx.argtypes = [ctypes.c_uint, ctypes.c_ubyte]
    buf = ctypes.create_unicode_buffer(8)
    for cp in (932, 936, 949, 950):
        leads = [b for b in range(256) if k32.IsDBCSLeadByteEx(cp, b)]
        trails = set()
        for lb in leads:
            for tb in range(256):
                if k32.MultiByteToWideChar(cp, 8, bytes([lb, tb]), 2, buf, 8) == 1:   # MB_ERR_INVALID_CHARS
                    trails.add(tb)
        special = {hex(b): (b in trails) for b in (0x00, 0x09, 0x20, 0x22, 0x5C)}
        print("CP%d: %d lead bytes, min trail %#x; trail in {NUL,TAB,SP,DQ,BSL}: %s" % (cp, len(leads), min(trails), special))


def main():
    diffs = 0
    for exe_name in ("ref_argv.exe", "ref_argv_acp932.exe"):
        exe = os.path.join(OUT, exe_name)
        print("== %s" % exe_name)
        for tail in CASES:
            ref = run_ref(exe, tail)
            cand = run_cand(ref["cmd"])
            same = ref["argc"] == cand["argc"] and ref["argv"] == cand["argv"]
            same1 = ref["argv"][:2] == cand["argv"][:2]
            print("ACP %s mbcp %s  case %s" % (ref["ACP"], ref["mbcp"], ascii(tail)))
            print("   bytes after argv0: %s" % ref["cmd"][ref["cmd"].find("2220") + 4:])
            print("   msvcr70 argc %s: %s" % (ref["argc"], show(ref["argv"])))
            print("   adapter argc %s: %s" % (cand["argc"], show(cand["argv"])))
            print("   %s%s" % ("SAME" if same else "DIFFERENT", "" if same else (" (argv[1] same)" if same1 else " (argv[1] differs)")))
            diffs += not same
    trail_census()
    print("differences: %d" % diffs)
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
