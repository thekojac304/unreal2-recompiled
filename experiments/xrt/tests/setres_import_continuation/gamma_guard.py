"""Exact retained parent-owned desktop gamma restoration guard; no game launcher."""
import ctypes as C
import os
import struct
from common import core
from supervisor import fixture_profiles as F

class DesktopGamma:
    """Parent owns restoration even after child failure, cancellation or watchdog."""
    def __init__(self,out):self.out=out;self.dcs=[]
    def __enter__(self):
        from ctypes import wintypes as W
        g=C.WinDLL('gdi32',use_last_error=True);self.g=g
        g.CreateDCW.argtypes=[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,C.c_void_p];g.CreateDCW.restype=W.HDC
        for name in ('GetDeviceGammaRamp','SetDeviceGammaRamp'):
            f=getattr(g,name);f.argtypes=[W.HDC,C.c_void_p];f.restype=W.BOOL
        g.DeleteDC.argtypes=[W.HDC];g.DeleteDC.restype=W.BOOL
        # The qualified physical snapshot supplies every active source display.
        E,A,collector=F.modules();snap=collector.Collector().snapshot(os.getpid(),self.out/'gamma-owner-before.json')
        A.environment(snap,physical=True)
        try:
            for name in sorted({p['gdi_name'] for p in snap['paths']}):
                dc=g.CreateDCW('DISPLAY',name,None,None);core.require(dc,'gamma display DC unavailable')
                data=C.create_string_buffer(1536)
                if not g.GetDeviceGammaRamp(dc,data):g.DeleteDC(dc);raise RuntimeError('cannot save original desktop gamma')
                raw=data.raw
                self.dcs.append((name,dc,raw))
                words=struct.unpack('<768H',raw)
                core.require(any(words),'original desktop gamma is entirely zero')
                core.require(all(words[c*256]<words[c*256+255] and
                    all(words[c*256+i]<=words[c*256+i+1] for i in range(255)) for c in range(3)),
                    'original desktop gamma failed monotonic/range validation')
                # Repeat acquisition validates that the saved bytes are stable.
                check=C.create_string_buffer(1536)
                if not g.GetDeviceGammaRamp(dc,check) or check.raw!=raw:
                    raise RuntimeError('original desktop gamma unstable')
            core.require(self.dcs,'no active displays to protect')
            core.atomic(self.out/'desktop-gamma-saved.json',dict(displays=[dict(name=n,bytes=b.hex()) for n,d,b in self.dcs]))
        except BaseException:
            for n,d,b in self.dcs:g.DeleteDC(d)
            raise
        return self
    def __exit__(self,*_):
        rows=[]
        for name,dc,raw in self.dcs:
            before=C.create_string_buffer(1536);read=bool(self.g.GetDeviceGammaRamp(dc,before))
            saved=C.create_string_buffer(raw);ok=bool(self.g.SetDeviceGammaRamp(dc,saved))
            after=C.create_string_buffer(1536);got=bool(self.g.GetDeviceGammaRamp(dc,after))
            rows.append(dict(name=name,before_read=read,before=before.raw.hex(),set_original=ok,
                             after_read=got,after=after.raw.hex(),equal=ok and got and after.raw==raw))
            self.g.DeleteDC(dc)
        core.atomic(self.out/'desktop-gamma-restored.json',dict(passed=all(r['equal'] for r in rows),displays=rows))
        if not rows or not all(r['equal'] for r in rows):raise core.IntegrityFailure('desktop gamma restoration unverified')
