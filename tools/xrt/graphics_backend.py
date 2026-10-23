"""Pinned official DXVK pair and reproducible, local-only probe environment."""
from pathlib import Path
import hashlib
WS=Path(__file__).resolve().parents[2]
HASHES={
    'x86':{'d3d8.dll':'9152ba43386e756790a66f61cdcee01b3287d156d4161c7456d816faa82fc364',
           'd3d9.dll':'265888c31ca78dffa290c39cb7e50bfb02762590e41927906e46fb32f01497fa'},
    'x64':{'d3d8.dll':'bd65cebf8ece6f80a841a16d98bdf5b76894c172b7ba344180baa17a4d00680c',
           'd3d9.dll':'c126316f7478eaff1ad8087702eda5930f2400187b9c8b3592219c34f6632780'}}
def verified_pair(arch):
    import pefile
    root=WS/'third_party/graphics/dxvk-v3.1.1/dxvk-3.1.1'/('x32' if arch=='x86' else arch)
    for name,digest in HASHES[arch].items():
        p=root/name
        if hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise RuntimeError('DXVK binary hash mismatch: '+str(p))
        pe=pefile.PE(str(p),fast_load=True)
        if pe.FILE_HEADER.Machine!=({'x86':0x14c,'x64':0x8664}[arch]):raise RuntimeError('DXVK architecture mismatch')
    return root
def environment(env,out):
    for key in list(env):
        if key.startswith('DXVK_'):del env[key]
    (out/'dxvk.conf').write_text('')
    env.update(DXVK_CONFIG='',DXVK_CONFIG_FILE=str(out/'dxvk.conf'),DXVK_LOG_PATH=str(out),DXVK_SHADER_CACHE='0')
    return {k:v for k,v in env.items() if k.startswith('DXVK_')}
