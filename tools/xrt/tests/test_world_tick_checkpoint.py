"""Prevent entry events, Entry-world actors and unpaired returns becoming milestones."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import world_tick_checkpoint as W


class WorldCheckpointTests(unittest.TestCase):
    def records(self):
        calls, returns = [], []
        for i, stage in enumerate(W.STAGES):
            c = dict(seq=3+i*2, thread=0, this=100, world=200, stage=stage, esp=1000, **{'return': 3000})
            r = dict(c, seq=c['seq']+1, esp_before=1000, esp_after=1004, actual_return=3000)
            calls.append(c)
            returns.append(r)
        return calls, returns

    def test_all_stages_need_returns_and_same_actor_set(self):
        calls, returns = self.records()
        self.assertTrue(W.lifecycle_complete(calls, returns)[0])
        self.assertFalse(W.lifecycle_complete(calls, returns[:-1])[0])
        calls[-1]['this'] = returns[-1]['this'] = 101
        self.assertFalse(W.lifecycle_complete(calls, returns)[0])

    def test_wrong_caller_or_stack_is_not_a_return(self):
        calls, returns = self.records()
        returns[0]['actual_return'] += 1
        self.assertFalse(W.lifecycle_complete(calls, returns)[0])
        returns[0]['actual_return'] -= 1
        returns[0]['esp_after'] += 4
        self.assertFalse(W.lifecycle_complete(calls, returns)[0])

    def test_one_return_cannot_complete_two_calls(self):
        calls, returns = self.records()
        second = dict(calls[0], seq=calls[0]['seq']+0.5)
        pairs = W.paired([calls[0],second],returns[:1],4)
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0][0],second)

    def test_engine_tick_requires_exact_thiscall_stack_cleanup(self):
        call=dict(seq=1,thread=0,this=100,world=0,stage='',esp=1000,**{'return':3000})
        ret=dict(call,seq=2,esp_before=1000,esp_after=1008,actual_return=3000)
        self.assertEqual(len(W.paired([call],[ret],8)),1)
        self.assertEqual(W.paired([call],[dict(ret,esp_after=1012)],8),[])

    def test_entry_world_actors_and_tick_entry_cannot_prove_completion(self):
        calls, returns = self.records()
        for e in calls:
            e['kind'] = 'actor_lifecycle_call'
        for e in returns:
            e['kind'] = 'actor_lifecycle_return'
        events = [dict(kind='engine_loadmap_call', seq=1, thread=0, this=10, esp=5000, **{'return': 6000}),
                  dict(kind='file_open', seq=2, thread=0, path='../Maps/CS_Intro.un2', ok=True),
                  *calls, *returns,
                  dict(kind='engine_loadmap_return', seq=20, thread=0, this=10, esp_before=5000,
                       esp_after=5020, actual_return=6000, result=999, **{'return': 6000}),
                  dict(kind='level_tick_call', seq=21, thread=0, this=999, esp=7000, **{'return': 8000})]
        r = W.candidate(dict(id='fresh'), dict(run_id='fresh', events_dropped=0, events=events))
        self.assertTrue(r['milestones']['T1'])
        self.assertFalse(r['milestones']['T2'])
        self.assertTrue(r['milestones']['T4'])
        self.assertFalse(r['milestones']['T5'])
