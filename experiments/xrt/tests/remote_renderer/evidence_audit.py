"""Replay retained material fixture audits on new copies. No graphics execution."""
import shutil,sys
sys.dont_write_bytecode=True
import phase as P
def main():
    dest=P.O/'retained-material-recheck';dest.mkdir()
    for folder,name in [('fixtures','native-results.json'),('fixtures-v4','translated-results.json')]:
        d=dest/folder;d.mkdir();shutil.copy2(P.OLD/folder/name,d/name)
    shutil.copy2(P.OLD/'guest-disassembly.json',dest/'guest-disassembly.json')
    oldphase=P.load('remote_retained_native_audit',P.H.parent/'d3d8_material/phase.py')
    oldphase.O=dest;oldphase.native_audit()
    # The imported translated auditor uses this thread's phase module; bind only
    # its input/output directory while keeping all retained source trees read-only.
    old=P.O;P.O=dest
    try:
        t=P.load('remote_retained_translated_audit',P.H.parent/'d3d8_material/translated.py')
        t.B=dest/'fixtures-v4';t.RT=P.RT;t.audit()
    finally:P.O=old
    P.save('retained-audit.json',dict(passed=True,retained_evidence_only=True,
        fresh_graphics_tests=False,native=P.read(dest/'native-audit.json'),
        translated=P.read(dest/'translated-audit.json'),
        preserved_source_identical=P.core.tree(P.RT)==P.read(P.OLD/'build.json')['runtime'],genuine_launches=0))
if __name__=='__main__':main()
