"""Conservative DirectMusic/world summary from identified original and translated runs."""
import argparse,collections,hashlib,json,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import world_evidence as W

def read(p):return json.loads(p.read_text())
def identity(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def candidate(p):
    meta=read(p/'meta.json');r=read(p/'report.json')
    if r['run_id']!=meta['id'] or r['events_dropped']:raise ValueError('incomplete candidate')
    modules={m['name']:m for m in r['modules']}
    if 'Unreal2.exe' not in modules or 'UCC.exe' in modules:raise ValueError('wrong client executable')
    for name,m in modules.items():
        path='System/Plugins/UnrImp.gpi' if name=='UnrImp.gpi' else 'System/'+name
        if m['sha256']!=meta['before'].get(path):raise ValueError('candidate input/lift mismatch: '+path)
    events=r['events'];calls=[e for e in events if e['kind']=='engine_loadmap_call']
    returns=[e for e in events if e['kind']=='engine_loadmap_return']
    post=[e for e in events if e['kind']=='level_postload_return']
    if len(calls)!=2 or len(returns)!=1 or len(post)!=2:raise ValueError('profile changed; inspect new world milestone')
    first,second=calls;ret=returns[0]
    if not(ret['result'] and first['seq']<ret['seq']<second['seq'] and ret['esp_before']==first['esp']
           and ret['esp_after']==first['esp']+20 and ret['return']==ret['actual_return']==first['return']):raise ValueError('unpaired Entry return')
    for returned in post:
        entries=[e for e in events if e['kind']=='level_postload_call' and e['seq']<returned['seq'] and e['this']==returned['this']
                 and e['esp']==returned['esp_before'] and e['return']==returned['return']==returned['actual_return']]
        if not entries or returned['esp_after']!=returned['esp_before']+4:raise ValueError('unpaired PostLoad return')
    opened=[e for e in events if e['kind']=='file_open' and e.get('ok') and e.get('path','').replace('\\','/').lower().endswith('cs_intro.un2')]
    if not any(second['seq']<e['seq']<post[-1]['seq'] for e in opened):raise ValueError('selected map not opened in second call')
    if any(int(v,16) in [0xb5be0,0x938f0] for v in modules['Engine.dll']['hit_rvas']):raise ValueError('tick path advanced; inspect completion')
    return {'path':str(p),'outcome':r['outcome'],'exit_code':r['exit_code'],'events':len(events),'events_dropped':r['events_dropped'],
            'entry_loadmap_nonnull_return':ret,'selected_package_postload_return':post[-1],
            'cs_intro_loadmap_return':None,'selected_actor_initialization':'not established','selected_world':None,
            'completed_selected_world_ticks':[],'modules_bound_to_actual_inputs':True}
def original(p):
    meta=read(p/'meta.json');trace=read(p/'trace.json')
    if (trace['run_id']!=meta['id'] or not trace['complete'] or trace['events_dropped'] or trace['exceptions_dropped']
        or trace['termination_reason']!='natural' or trace['exit_code']):raise ValueError('incomplete original session')
    rows=[json.loads(line) for line in (p/'music.jsonl').read_text().splitlines()]
    game=[{'method':r['label'].removeprefix('DirectMusic.').removesuffix('.outputs'),'result':r['eax']}
          for r in rows if r['label'].endswith('.outputs')]
    classes=collections.Counter();queries=collections.Counter()
    for r in rows:
        if r['label']=='DirectMusic.API.CoCreateInstance.entry':
            guid=lambda i:str(uuid.UUID(bytes_le=bytes.fromhex(r['pointers'][i]['bytes'])[:16]))
            classes[(guid(1),guid(4),r['stack'][3])]+=1
        if r['label'].endswith('.slot0') or r['label']=='DirectMusic.Tool.QueryInterface.entry':
            queries[(r['label'],str(uuid.UUID(bytes_le=bytes.fromhex(r['pointers'][2]['bytes'])[:16])))]+=1
    calls=collections.Counter(r['label'] for r in rows if not r['label'].endswith(('.exit','.outputs','.return')))
    exits=collections.defaultdict(collections.Counter)
    for r in rows:
        if r['label'].endswith('.exit'):exits[r['label']][r['eax']]+=1
    audio={name:[r['eax'] for r in rows if r['label']==label] for name,label in [
        ('initialize','DirectMusic.AudioClient.slot3.exit'),('start','DirectMusic.AudioClient.slot10.exit')]}
    init=next(r for r in rows if r['label']=='DirectMusic.Performance.InitAudio.call')
    routine=next(r for r in rows if r['label']=='DirectMusic.Script.CallRoutine.call')
    inputs=meta['before']
    important=['System/Engine.dll','System/Unreal2.exe','System/Unreal2.ini','System/Golem.u','Maps/CS_Intro.un2','Maps/Entry.un2','Music/Intro.con','System/d3d8.dll','System/d3d9.dll']
    return {'path':str(p),'args':meta['args'],'trace':identity(p/'trace.json'),'music':identity(p/'music.jsonl'),
            'observer':meta['tracer'],'input_files':len(inputs),
            'input_manifest_sha256':hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest(),
            'selected_input_hashes':{k:inputs[k] for k in important},'world':W.summarize(trace),'game_calls':game,
            'init_audio':{'directmusic_output_null':int(init['stack'][1],16)==0,'sound_output_requested':bool(int(init['stack'][2],16)),
                          'hwnd':init['stack'][3],'default_path_type':int(init['stack'][4],16),'pchannels':int(init['stack'][5],16),
                          'flags':int(init['stack'][6],16),'params_null':int(init['stack'][7],16)==0},
            'routine_name_empty':bytes.fromhex(routine['pointers'][1]['bytes'])[:2]==b'\0\0',
            'audio_stream':audio,'call_counts':dict(calls),'return_value_histograms':dict(exits),
            'classes':[{'clsid':c,'iid':i,'context':ctx,'count':n} for (c,i,ctx),n in classes.items()],
            'queries':[{'method':m,'iid':i,'count':n} for (m,i),n in queries.items()],
            'apartments':[{'seq':r['seq'],'thread':r['thread'],'method':r['label'],'result':r['eax'],'stack':r['stack'][:4]}
                          for r in rows if r['label'].startswith(('DirectMusic.API.CoInitialize','DirectMusic.API.CoUninitialize'))]}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('nosound',type=Path);ap.add_argument('sound',type=Path)
    ap.add_argument('candidate',type=Path);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--candidate-repeat',type=Path);a=ap.parse_args()
    n,s=original(a.nosound),original(a.sound);c=candidate(a.candidate)
    report=read(a.candidate/'report.json');meta=read(a.candidate/'meta.json')
    if report['run_id']!=meta['id'] or report['events_dropped']:raise ValueError('incomplete candidate')
    com=[e for e in report['events'] if e['kind'].startswith(('com_','dmusic'))]
    result={'schema':1,'scope':'DirectMusic characterization and COM/Loader8 capability checkpoint; translated CS_Intro completion not achieved',
            'original_nosound':n,'original_sound':s,'original_game_calls_identical':n['game_calls']==s['game_calls'],
            'original_init_audio_identical':n['init_audio']==s['init_audio'],'original_input_hashes_identical':n['input_manifest_sha256']==s['input_manifest_sha256'],
            'nosound_starts_real_output_stream': '00000000' in n['audio_stream']['initialize'] and '00000000' in n['audio_stream']['start'],
            'candidate':c,'candidate_com':com,'candidate_identity':meta['candidate'],
            'translated_selected_world_tick_completed':False,'first_blocker':'x64 native Performance8 class unavailable (80040154); explicit capability gate',
            'independent_script_behavior':'missing-name lookup only, validated against native enumeration/failure; present routines explicitly unsupported',
            'architecture_decision_pending':'bounded native x86 helper integration versus an independently implemented script/audio backend'}
    if a.candidate_repeat:
        result['candidate_repeat']=candidate(a.candidate_repeat)
        repeated=read(a.candidate_repeat/'report.json')
        repeated_com=[e for e in repeated['events'] if e['kind'].startswith(('com_','dmusic'))]
        result['candidate_com_reproduced']=com==repeated_com and report['outcome']==repeated['outcome']
    ws=Path(__file__).resolve().parents[2]
    for key,folder,latest in [('com_oracle','directmusic_com','latest.json'),('native_session','directmusic_boundary','session-latest.json')]:
        p=ws/read(ws/'experiments/xrt/build'/folder/latest)['evidence']/'result.json'
        evidence=read(p)
        result[key]={'evidence':identity(p),'pass':evidence['pass']}
        if key=='native_session':
            result[key].update(parent_pointer_bits=evidence['parent_pointer_bits'],routine_count=len(evidence['native_routines']),
                               present_routines_rejected=len(evidence['present_routines_explicitly_unsupported']),
                               missing_results=evidence['independent_missing_results'],scope=evidence['scope'])
    a.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(a.out)
if __name__=='__main__':main()
