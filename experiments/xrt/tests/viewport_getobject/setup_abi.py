"""Adapt retained project-owned instrumentation to the four-argument USER32 ABI."""
from pathlib import Path
H=Path(__file__).resolve().parent
for arch in ['32','64']:
    text=(H/('../d3d8_device/abi'+arch+'.asm')).read_text().replace('device_abi','window_abi')
    if arch=='32':
        old='    push DWORD PTR [eax+28]\n    push DWORD PTR [eax+24]\n    push DWORD PTR [eax+20]\n'
        assert text.count(old)==1;text=text.replace(old,'')
    else:
        start=text.index('    mov r8d,[r10+20]');end=text.index('    call QWORD PTR [r10]',start)
        text=text[:start]+'    mov r8,[r10+24]\n    mov r9,[r10+32]\n'+text[end:]
    (H/('abi'+arch+'.asm')).open('x').write(text)
