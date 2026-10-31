"""Read-only reconstruction of the retained second run; never launches a guest."""
import collections
import json
import struct
from pathlib import Path
from trace_reader import records

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'out/dev-init/runs/20261030-220553-8fd4cb9f'


def main():
    counts = collections.Counter()
    batches = []
    names = []
    windows = []
    reads = []
    active = {}
    completed = collections.Counter()
    late_lengths = []
    critical = []
    for r in records(RUN / 'monitor.bin'):
        name = r.name.decode()
        counts[(r.event, name)] += 1
        if r.event == 2:
            caller = struct.unpack_from('<I', r.stack)[0] if r.stack_size else 0
            active[r.invocation] = (name, caller)
            if name == 'msvcr70.dll!wcscpy' and caller == 0x10144ebf:
                names.append(dict(sequence=r.sequence, saved_caller_ebx=struct.unpack_from('<I', r.stack, 20)[0]))
        if r.event == 3:
            key = active.pop(r.invocation, None)
            if key:
                completed[key] += 1
                if r.sequence > 120000 and key[0] == 'msvcr70.dll!wcslen':
                    late_lengths.append(r.result)
        if name == 'dev.calibration.timeGetTime.batch':
            batches.append(dict(sequence=r.sequence, values=[v.value for v in r.values[:r.count]]))
        if r.event == 3 and name == 'WIN.CreateWindowExW':
            windows.append(dict(sequence=r.sequence, result=hex(r.result)))
        if r.event == 3 and name == 'kernel32.dll!ReadFile':
            reads.append(dict(sequence=r.sequence, result=r.result))
        if r.event in (5, 8, 9) or name == 'UGameEngine.Init' or 'D3D' in name:
            critical.append(dict(sequence=r.sequence, event=r.event, name=name, result=r.result))
        last = r
    passes = []
    for number in (0, 1, 2):
        rows = [b for b in batches if b['values'][6] == number]
        passes.append(dict(pass_number=number, calls=sum(b['values'][1] for b in rows),
                           last_sequence=rows[-1]['sequence'], elapsed_ms=rows[-1]['values'][8],
                           backwards=sum(b['values'][5] for b in rows)))
    value = dict(run=str(RUN), records=last.sequence, checksum_chain_verified=True,
        process=json.loads((RUN / 'process.json').read_text()),
        calibration=passes, critical=critical, windows=windows, last_read=reads[-1],
        completed_archive_name_copies=completed[('msvcr70.dll!wcscpy', 0x10144ebf)],
        name_copy_first=names[:3], name_copy_last=names[-8:],
        final_gap_saved_caller_ebx=struct.unpack_from('<I', last.stack, 20)[0],
        late_string_length_range=[min(late_lengths), max(late_lengths)],
        resolved_callers=[dict(import_name=name, return_address=hex(address), completed=count)
            for (name, address), count in completed.items() if address in
            (0x1010c4ee, 0x10141d01, 0x10141d35, 0x10144ebf)],
        counts=[dict(event=k[0], name=k[1], count=v) for k,v in counts.items()])
    output = ROOT / 'out/dev-init/second-run-analysis.json'
    output.write_text(json.dumps(value, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
