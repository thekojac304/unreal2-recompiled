"""Independent bounded RIFF/script name oracle. It cannot initialize or execute music.

Only missing-name failure is implemented. Present routines are explicit unsupported
operations; no return value stands in for native Script.Init or script execution.
"""
import re,struct,hashlib
DMUS_E_SCRIPT_ROUTINE_NOT_FOUND=0x8878121b

class UnsupportedScript(RuntimeError):pass

def scripts(data):
    found=[]
    def walk(lo,hi,parent=None):
        while lo<hi:
            if lo+8>hi:raise ValueError('truncated RIFF chunk header')
            tag,size=struct.unpack_from('<4sI',data,lo);body=lo+8;end=body+size
            if end>hi:raise ValueError('RIFF chunk exceeds parent')
            if tag in [b'RIFF',b'LIST']:
                if size<4:raise ValueError('missing RIFF form')
                if tag==b'RIFF' and data[body:body+4]==b'DMSC':
                    item={'language':None,'source':None,'name':None};walk(body+4,end,item)
                    if item['language']!='VBScript' or item['source'] is None:raise UnsupportedScript('unsupported script language/source')
                    item['routines']=re.findall(r'^\s*sub\s+([a-z_][a-z0-9_]*)\s*(?:\(\s*\))?\s*$',item['source'],re.I|re.M)
                    item['source_sha256']=hashlib.sha256(item.pop('source').encode('utf-16le')).hexdigest();found.append(item)
                else:walk(body+4,end,parent if data[body:body+4]==b'UNFO' else None)
            elif parent is not None and tag in [b'scla',b'scsr',b'UNAM']:
                if size%2:raise ValueError('odd UTF-16 script chunk')
                text=data[body:end].decode('utf-16le').rstrip('\0')
                parent[{b'scla':'language',b'scsr':'source',b'UNAM':'name'}[tag]]=text
            lo=end+(size&1)
        if lo!=hi:raise ValueError('missing RIFF alignment byte')
    walk(0,len(data));return found

def call_missing(script,name):
    if name.casefold() in {r.casefold() for r in script['routines']}:
        raise UnsupportedScript(f'present routine {name}: execution, state and scheduling unsupported')
    if name and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name):raise UnsupportedScript('unmeasured routine-name syntax')
    return DMUS_E_SCRIPT_ROUTINE_NOT_FOUND
