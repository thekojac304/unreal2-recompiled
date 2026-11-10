"""Default forensic, explicit selection, negative profiles and omission contracts."""
import sys,uuid,ctypes as C,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import decode,Record
from supervisor.windows import FilePins

def main():
    out=O/('profiles-'+str(uuid.uuid4()));out.mkdir()
    exe=Path(read(O/'live.json')['root'])/'monitor-fixture.exe';results=[]
    for name,profile,mode in [('default',None,0),('forensic','forensic',0),('forensic-large-map','forensic',14),('unknown','invalid-profile',0)]:
        d=out/name;d.mkdir();sb=d/'sandbox';sb.mkdir();stream=sb/'trace.bin';env=fixture.environment(sb)
        if profile is None:env.pop('XRT_MONITOR_PROFILE',None)
        else:env['XRT_MONITOR_PROFILE']=profile
        probe=fixture.Probe(d,sb,name)
        # Mode 14's publication break is unnecessary in this forensic negative.
        probe.on_debugbreak=lambda ev:None
        with FilePins() as pins:
            pins.pin(exe,core.sha(exe))
            with (d/'stdout.txt').open('xb') as stdout,(d/'stderr.txt').open('xb') as stderr:
                p=probe.run([str(exe),str(stream),str(mode)],cwd=sb,env=env,stdout=stdout,stderr=stderr,timeout=30)
        core.require(probe.cleanup['passed'],'profile containment')
        valid=None;rejection=None
        try:rows,valid=decode(stream)
        except (ValueError,FileNotFoundError) as e:rejection=str(e)
        if name in ('default','forensic'):
            core.require(p.returncode==0 and valid and rows[0].name==b'xrt.monitor.v3.forensic' and not valid['omitted_events'],'forensic contract changed')
        else:core.require(p.returncode!=0 and rejection,'invalid profile or forensic payload accepted')
        results.append(dict(case=name,exit=p.returncode,integrity=valid,rejection=rejection,cleanup=probe.cleanup))
    # CRC-valid profile/omission substitutions must still be rejected.
    root=Path(read(O/'live.json')['root']);raw=(root/'explicit-omission/sandbox/trace.bin').read_bytes();size=C.sizeof(Record)
    negatives=[]
    for name in ('unknown-omission','wrong-profile','wrong-count'):
        buf=bytearray(raw);chain=0
        for off in range(0,len(buf),size):
            r=Record.from_buffer_copy(buf[off:off+size])
            if name=='wrong-profile' and off==0:r.name=b'xrt.monitor.v3.forensic'
            if r.event==11:
                if name=='unknown-omission':r.name=b'unknown.bulk.category'
                if name=='wrong-count':r.values[0].value+=1
            r.previous_crc=chain;r.crc=zlib.crc32(bytes(r)[:Record.crc.offset]);chain=r.crc;buf[off:off+size]=bytes(r)
        p=out/(name+'.bin');p.write_bytes(buf)
        try:decode(p)
        except ValueError as e:negatives.append(dict(case=name,rejection=str(e)))
        else:raise AssertionError('invalid omission profile accepted')
    save(O/'profiles.json',dict(passed=True,root=str(out),runtime=core.tree(RT),cases=results,negatives=negatives,
        forensic_default=True,omitted_categories=['resource.map.download','resource.map.upload']))
    print('Default forensic / explicit development / unknown profile / strict span / CRC-valid omission negatives PASS',flush=True)

if __name__=='__main__':main()
