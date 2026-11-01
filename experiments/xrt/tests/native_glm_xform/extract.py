"""Copy the translated GlmLib f_2fd7d20 from the developer generated unit into OUT as f_2fd7d20_translated (the
reference for test.c). Usage: extract.py GENERATED_DIR OUT_C"""
import re
import sys
from pathlib import Path

gen, out = Path(sys.argv[1]), Path(sys.argv[2])
text = (gen / 'GlmLib_008.c').read_text()
m = re.search(r'^void f_2fd7d20\(CPU\* c\) \{\n.*?^\}\n', text, re.M | re.S)
if not m:
    raise SystemExit('f_2fd7d20 not found in GlmLib_008.c')
body = m.group(0).replace('void f_2fd7d20(CPU* c)', 'void f_2fd7d20_translated(CPU* c)', 1)
out.write_text('/* extracted by extract.py from ' + str(gen / 'GlmLib_008.c') + ' - do not distribute */\n'
               '#include "xrt.h"\nextern uint8_t xrt_hits_GlmLib[];\n' + body)
print('extracted', len(body.splitlines()), 'lines')
