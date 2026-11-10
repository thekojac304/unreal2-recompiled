"""Actual translated InitAudio through the unchanged guarded x86 helper."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import decode

def main():
    n=load('audio_owned_build',H/'nonlocal.py')
    out=O/('audio-'+str(uuid.uuid4()));out.mkdir();h=helper(out);e32=h.env('x86')
    data=out/'sandbox-data';data.mkdir();(data/'System').mkdir();(data/'Music').mkdir()
    dll=data/'audioprobe.dll'
    import pefile,struct,json,shutil
    image=A.source()/'System/Engine.dll'
    with pefile.PE(str(image)) as pe:
        def guid(rva):
            raw=pe.get_data(rva,16);a,b,c=struct.unpack('<IHH',raw[:8])
            return '{'+f'0x{a:x},0x{b:x},0x{c:x},'+'{'+','.join(f'0x{x:x}' for x in raw[8:])+'}}'
        header='static const GUID graph_guid='+guid(0x23ffc0)+';\nstatic const GUID tool_guid='+guid(0x240030)+';\n'
        for name,rva in [('loader_class',0x240010),('loader_guid',0x23ffb0),('alltypes_guid',0x23ffe0),
            ('container_class',0x23fff0),('container_guid',0x23ff80),('script_guid',0x23ff90)]:
            header+='static const GUID '+name+'='+guid(rva)+';\n'
        descriptor=bytearray(848);struct.pack_into('<II',descriptor,0,848,0x206)
        descriptor[24:40]=pe.get_data(0x240000,16);descriptor[56:72]='Script1\0'.encode('utf-16le')
        header+='static DWORD script_descriptor[212]={'+','.join(hex(x) for x in struct.unpack('<212I',descriptor))+'};\n'
    header+='static WCHAR music_folder[] = L'+json.dumps(str(data/'Music'))+';\n'
    asset=A.source()/'Music/Intro.con';shutil.copy2(asset,data/'Music/Intro.con')
    core.require(core.sha(asset)==core.sha(data/'Music/Intro.con'),'snapshot script asset copy')
    (out/'tool_guids.h').write_text(header)
    h.run(['cl','/nologo','/c','/O2','/GS-',f'/I{out}',f'/Fo{out}/probe.obj',H/'audio_probe.c'],'probe',environment=e32)
    h.run(['link','/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/DYNAMICBASE:NO','/BASE:0x12000000',f'/OUT:{dll}',out/'probe.obj','kernel32.lib','ole32.lib','uuid.lib'],'dll',environment=e32)
    native=out/'native.exe';h.run(['cl','/nologo','/O2',f'/Fo{out}/native.obj',f'/Fe{native}',W/'tools/xrt/tests/ehprobe/native_host.c'],'native-build',environment=e32)
    translated=n.build_host(out,dll,'audioprobe')
    helper_exe=W/'experiments/xrt/build/dmusic-ipc/dmusic_helper.exe'
    d,a,cl=n.run(out,'native',[native,out,dll,'probe_audio'],[dll])
    d,b,cleanup=n.run(out,'translated-run',[translated,dll,out/'report.json','probe_audio'],[helper_exe],trace=True,
        extra_env={'XRT_DMUSIC_BACKEND':'ipc','XRT_DMUSIC_HELPER':str(helper_exe)})
    core.require(a==b and 'probe_audio returned 0 log 0 1 0 1 0' in b,'native/translated InitAudio result/object/CloseDown')
    rows,valid=decode(d/'trace.bin')
    core.require(any(r.name==b'xrt.com!DMI.InitAudio' and r.event==3 and r.result==0 for r in rows),'actual adapter return')
    core.require({r.name for r in rows}>={b'DirectMusic.IPC.request',b'DirectMusic.IPC.response'},'IPC frame evidence')
    _,ta,_=n.run(out,'native-tool',[native,out,dll,'probe_tool'],[dll])
    td,tb,tcl=n.run(out,'translated-tool',[translated,dll,out/'tool-report.json','probe_tool'],[helper_exe],trace=True,
        extra_env={'XRT_DMUSIC_BACKEND':'ipc','XRT_DMUSIC_HELPER':str(helper_exe)})
    core.require(ta==tb and 'probe_tool returned 0 log ' in tb,'native/translated tool callback order/ownership')
    tool_rows,tool_valid=decode(td/'trace.bin')
    callbacks=[r for r in tool_rows if r.event==2 and r.name==b'DirectMusic.IPC.callback']
    core.require(len(callbacks)>=5 and max(r.depth for r in callbacks)>=3,'nested real helper callback evidence')
    # The real native VBScript engine loads this observed Defender AMSI module.
    # Admit only the exact independently signed/pinned dependency, never its
    # containing directory or arbitrary ProgramData modules.
    defender=Path(r'C:\ProgramData\Microsoft\Windows Defender\Platform\4.18.26100.4-0\X86\MpOAV.dll')
    signature=h.run(['C:/Program Files/PowerShell/7/pwsh.exe','-NoProfile','-Command',
        "Get-AuthenticodeSignature -LiteralPath '"+str(defender)+"' | Select-Object Status,@{Name='Signer';Expression={$_.SignerCertificate.Subject}} | ConvertTo-Json"],
        'defender-signature')
    signer=json.loads(signature.stdout)
    core.require(signer['Status']==0 and 'O=Microsoft Corporation' in signer['Signer'],'script dependency signer')
    _,sa,_=n.run(out,'native-script',[native,out,dll,'probe_script'],[dll,defender])
    sd,sb,scl=n.run(out,'translated-script',[translated,dll,out/'script-report.json','probe_script'],[helper_exe],trace=True,
        extra_env={'XRT_DMUSIC_BACKEND':'ipc','XRT_DMUSIC_HELPER':str(helper_exe)})
    core.require(sa==sb and 'probe_script returned 0 log ' in sb,'native/translated Script.Init/empty routine/cleanup')
    sr,sv=decode(sd/'trace.bin')
    core.require(any(r.name==b'xrt.com!DMI.ScriptInit' and r.event==3 and r.result==0 for r in sr),'actual Script.Init missing')
    core.require(any(r.name==b'xrt.com!DMI.Routine' and r.event==3 and r.result==0x8878121b for r in sr),'actual empty routine error missing')
    negatives=[]
    for name in ('probe_bad_audio','probe_audio_unsupported'):
        q,output,cl=n.run(out,name,[translated,dll,out/(name+'.json'),name],[helper_exe],expected=76,trace=True,
            extra_env={'XRT_DMUSIC_BACKEND':'ipc','XRT_DMUSIC_HELPER':str(helper_exe)})
        try:decode(q/'trace.bin')
        except ValueError as e:negatives.append(dict(case=name,rejection=str(e),cleanup=cl))
        else:raise AssertionError('unsafe audio call accepted')
    save(O/'audio.json',dict(passed=True,root=str(out),runtime=core.tree(RT),oracle=a,integrity=valid,cleanup=cleanup,
        negatives=negatives,helper_sha256=core.sha(helper_exe),native_x86=True,translated_actual_adapter=True,
        actual_tuple=dict(path=8,channels=128,flags=63),tool_oracle=ta,tool_integrity=tool_valid,
        tool_callbacks=len(callbacks),tool_cleanup=tcl,tool_callback_qualified=True,script_callback_qualified=True,
        script_oracle=sa,script_integrity=sv,script_cleanup=scl,script_asset_sha256=core.sha(asset),
        script_native_dependency=dict(path=str(defender),sha256=core.sha(defender),signature=signer),
        guid_source=dict(path=str(image),sha256=core.sha(image),header_sha256=core.sha(out/'tool_guids.h'))))
    print('Actual translated InitAudio / native x86 results / guarded helper / unsupported stops PASS',flush=True)

if __name__=='__main__':main()
