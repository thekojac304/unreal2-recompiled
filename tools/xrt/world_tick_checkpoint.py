"""Independent T1..T6 evidence from genuine client calls and paired caller returns."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from world_evidence import summarize

STAGES = ('PreBeginPlay', 'BeginPlay', 'PostBeginPlay')


def paired(calls, returns, popped):
    matches = []
    used = set()
    for ret in sorted(returns, key=lambda e:e['seq']):
        for call in sorted(calls, key=lambda e:e['seq'], reverse=True):
            if call['seq'] in used:
                continue
            if (ret['seq'] > call['seq'] and ret.get('thread') == call.get('thread')
                    and all(ret.get(k) == call.get(k) for k in ('this', 'world', 'stage', 'return'))
                    and ret.get('esp_before') == call['esp']
                    and ret.get('esp_after') == call['esp'] + popped
                    and ret.get('actual_return') == call['return']):
                matches.append((call, ret))
                used.add(call['seq'])
                break
    return sorted(matches, key=lambda pair:pair[0]['seq'])


def lifecycle_complete(calls, returns):
    pairs = paired(calls, returns, 4)
    actors = [{c['this'] for c, r in pairs if c['stage'] == stage} for stage in STAGES]
    return bool(calls and len(pairs) == len(calls) and actors[0] and all(a == actors[0] for a in actors)), pairs


def candidate(meta, report):
    events = report.get('events', [])
    valid = report.get('events_dropped') == 0 and report.get('run_id') == meta.get('id')
    selected = None
    for call, ret in paired([e for e in events if e['kind'] == 'engine_loadmap_call'],
                            [e for e in events if e['kind'] == 'engine_loadmap_return'], 20):
        opened = any(e['kind'] == 'file_open' and e.get('ok') and
                     e.get('path', '').replace('\\', '/').lower().endswith('/cs_intro.un2') and
                     call['seq'] < e['seq'] < ret['seq'] for e in events)
        if opened and ret.get('result'):
            selected = dict(world=ret['result'], entry_seq=call['seq'], return_seq=ret['seq'])
    calls, returns = [], []
    if selected:
        calls = [e for e in events if e['kind'] == 'actor_lifecycle_call' and
                 e['world'] == selected['world'] and selected['entry_seq'] < e['seq'] < selected['return_seq']]
        returns = [e for e in events if e['kind'] == 'actor_lifecycle_return' and e['seq'] < selected['return_seq']]
    lifecycle, pairs = lifecycle_complete(calls, returns)
    init = paired([e for e in events if e['kind'] == 'engine_init_call'],
                  [e for e in events if e['kind'] == 'engine_init_return'], 4)
    engine_ticks = [e for e in events if e['kind'] == 'engine_tick_call']
    engine_returns = paired(engine_ticks, [e for e in events if e['kind'] == 'engine_tick_return'], 8)
    ticks = [e for e in events if e['kind'] == 'level_tick_call' and selected and
             e['this'] == selected['world'] and e['seq'] > selected['return_seq']]
    tick_returns = paired(ticks, [e for e in events if e['kind'] == 'level_tick_return'], 12)
    return dict(observer_valid=valid, selected_map=selected,
                lifecycle_calls=dict(Counter(e['stage'] for e in calls)),
                lifecycle_returns=dict(Counter(c['stage'] for c, r in pairs)),
                lifecycle_actor_count=len({c['this'] for c, r in pairs}),
                milestones=dict(T1=bool(valid and selected), T2=bool(valid and selected and lifecycle),
                                T3=bool(valid and init), T4=bool(valid and ticks),
                                T5=bool(valid and tick_returns), T6=bool(valid and len(tick_returns) >= 3)),
                completed_selected_world_ticks=[dict(entry=c['seq'], returned=r['seq']) for c, r in tick_returns],
                engine_tick_entries=len(engine_ticks),
                completed_engine_ticks=[dict(entry=c['seq'],returned=r['seq']) for c,r in engine_returns],
                first_fatal=next((e for e in events if e['kind'] == 'fatal'), None),
                input_events=[e for e in events if e['kind'].startswith('dinput')])


def reference(root):
    trace = json.loads((root / 'trace.json').read_text())
    result = summarize(trace)
    selected = result['selected_map']
    rows = [json.loads(s) for s in (root / 'input.jsonl').read_text().splitlines()]
    calls, returns = [], []
    if selected:
        for row in rows:
            if (not row['label'].startswith('AActor.event') or not row.get('actor_world_readable') or
                    int(row['actor_world'], 16) != int(selected['world'], 16) or
                    not selected['entry_seq'] < row['seq'] < selected['return_seq']):
                continue
            stage = row['label'].removeprefix('AActor.event').removesuffix('.exit')
            e = dict(seq=row['seq'], thread=row['thread'], stage=stage, world=int(row['actor_world'], 16),
                     this=int(row['ecx']['address'], 16), **{'return': int(row['stack'][0], 16)})
            if row['label'].endswith('.exit'):
                e.update(esp_after=int(row['esp'], 16), esp_before=int(row['esp'], 16)-4,
                         actual_return=int(row['eip'], 16))
                returns.append(e)
            else:
                e['esp'] = int(row['esp'], 16)
                calls.append(e)
    complete, pairs = lifecycle_complete(calls, returns)
    result.update(lifecycle_returns_paired=complete,
                  lifecycle_returns=dict(Counter(c['stage'] for c, r in pairs)),
                  lifecycle_actor_count=len({c['this'] for c, r in pairs}))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference', type=Path, required=True)
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    c = candidate(json.loads((a.candidate / 'meta.json').read_text()),
                  json.loads((a.candidate / 'report.json').read_text()))
    r = reference(a.reference)
    result = dict(reference_path=str(a.reference), candidate_path=str(a.candidate), reference=r, candidate=c,
                  actor_counts_match=r['lifecycle_returns'] == c['lifecycle_returns'],
                  unique_actor_counts_match=r['lifecycle_actor_count'] == c['lifecycle_actor_count'])
    a.out.write_text(json.dumps(result, indent=2))
    print(a.out, c['milestones'], flush=True)


if __name__ == '__main__':
    main()
