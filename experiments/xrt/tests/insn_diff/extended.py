"""Extended forms for the differential instruction test: forms outside the Core.dll/UCC.exe census that
tools/xrt/xlift.py implements (or is meant to), for the modules that come next (Engine.dll, ...).

Each entry is one example encoding (hand-assembled here, verified by disassembly); gen.py derives the
form and encoding class from it exactly as census.py does and then synthesizes snippets the same way.
Memory examples use [ebx+0x10]; gen.py re-encodes the addressing. Results are reported separately
from the census forms (results.json: "in_census": false).
"""
EXAMPLES = """
c1c005 d1c0 d3c0 d2c0 c0c003 66c1c005 66d3c0 d1c8 c1c805 d3c8 d2c8 66d3c8 c0c803 d34310 d14b10
d2e0 d2e8 d2f8 66d3e0 66d3e8 66d3f8 c0e003 c0f803 66c1e805 d0f8 c16b1005 d07b10 d36310
0fa4c805 0facc805 0fa54b10 0fad4b10
d1d0 d1d8 c1d805 d3d8 d1d1 d1d9 c0d003 66d1d8 66d3d0 d15b10 d35310
0f40c1 0f41c1 0f42c1 0f43c1 0f44c1 0f45c1 0f46c1 0f47c1 0f48c1 0f49c1 0f4ac1 0f4bc1 0f4cc1 0f4dc1 0f4ec1 0f4fc1
0f444310 660f44c1
0fc8 0fcb 0fce
f6e1 f66310 f6e9 660fafc1 666bc105 6669c13412
6698 98 6699
ac 66ad ad ae 66af af a6 66a7 a7 a4 66a5 a5 ab f366a5 f2ae f3ae f2af f2a6 f3a7 f3ab
fd f9 f8 f5
874310 86c1 91 87c0 6687c1
66f7d8 66f7d0 f75b10 f65b10 f75310
6640 66ff4b10 fe4b10
12c1 661bc1 83531005 805b1005 1b4310 194310 1405 1c05
6601c8 6629c8 6621c8 6609c8 6631c8 6685c8 66a93412 66854310 668143103412 6683e805 6683c8ff
004310 284310 324310 0a4310 80731005 3405 2c05 0c05
0fbec1 0fbfc1 0fbe4310 0fb6c4
0f944310 0f9f4310
8f4310 54 5c
8a6310 886310 8ac4 a000810020
f0014310 f0ff4310 f0ff4b10 f0294310 f0214310 f0094310 f0314310 f0f75b10 f0f75310 f0114310 f0194310
d9e1 d9e4 d9ee d9eb d9ec d9e9 dde1 dde9 dae9 ded9 d8d2 d8da
df4310 df5310 df5b10 db5310 db5b10 da4310 de4b10 da6310 da6b10 de7b10 da5310 de5b10
dee1 dcc1 dce9 dce1 dcf9 dcf1 dcc9 d8e9 d8f9 ddd1
dd7b10 d97b10 d96b10 dbe2 dbe3 9b
"""

# Forms the lifter deliberately leaves as traps (listed so the report shows them as known, not tested).
UNSUPPORTED_EXAMPLES = """
d9e5 d9f8 d9f5 d9f7 d9f6 ddc1 dac1 dbe9 dfe9 df6310 df7310 db6b10 db7b10 d96310 d97310 dd6310 dd7310
d9f4 d9fb d9f9 66f7e1 66f7e9 f6f1 66f7f1 0fa3c8 0fbcc1 0fbdc1 0fc14310 0fb14b10 9e 9f 9c 9d 60 61 d7
"""


def examples():
    return [bytes.fromhex(h) for h in EXAMPLES.split()]


def unsupported_examples():
    return [bytes.fromhex(h) for h in UNSUPPORTED_EXAMPLES.split()]
