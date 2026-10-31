"""Passive reconstruction of the third retained developer run; never launches."""
import collections
import json
import struct
from pathlib import Path
from trace_reader import records, snapshot, context

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'out/dev-init/runs/20261030-221937-21570264'


def main():
    counts = collections.Counter()
    windows, exceptional, reads = [], [], []
    for r in records(RUN / 'monitor.bin'):
        name = r.name.decode()
        counts[name] += 1
        if r.event == 3 and 'CreateWindowEx' in name:
            windows.append(context(r))
        if r.event == 3 and name == 'kernel32.dll!ReadFile':
            reads.append(context(r))
        if r.event in (5, 8, 9, 10) or name == 'UGameEngine.Init' or 'D3D' in name or name.startswith('D8'):
            exceptional.append(context(r))
        last = r
    side = snapshot(str(RUN / 'monitor.bin') + '.routine')
    samples = []
    for s in side.imports:
        if not s.begins:
            continue
        samples.append(dict(name=s.name.decode(), begins=s.begins, ends=s.ends,
                            last_begin=context(s.last_begin), last_end=context(s.last_end),
                            last_begin_stack=[hex(v) for v in struct.unpack('<32I', bytes(s.last_begin.stack))]))
    value = dict(run=str(RUN), checksum_chain_verified=True, records=last.sequence,
                 observed=side.observed, aggregated=side.routine_events,
                 process=json.loads((RUN / 'process.json').read_text()),
                 top_record_producers=counts.most_common(25), windows=windows,
                 exceptional=exceptional, last_reads=reads[-8:], routine_samples=samples)
    output = ROOT / 'out/dev-init/third-run-analysis.json'
    output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({k:v for k,v in value.items() if k!='routine_samples'}, indent=2))


if __name__ == '__main__':
    main()
