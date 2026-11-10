"""Reproducible source-level guard inventory with exact expressions and provenance."""
import ast
from collections import Counter
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
SOURCES={
 'd3d8':'https://learn.microsoft.com/en-us/previous-versions/ms889722(v=msdn.10)',
 'stages':'https://learn.microsoft.com/en-us/previous-versions/ms889726(v=msdn.10)',
 'caps':'https://raw.githubusercontent.com/wine-mirror/wine/master/include/d3d8caps.h',
 'backend':'https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/d3d8_device.cpp',
 'move':'https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-movewindow',
 'attach':'https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-attachthreadinput',
 'memory':'https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualquery',
 'abi':'https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention',
 'com':'https://learn.microsoft.com/en-us/windows/win32/api/unknwn/nn-unknwn-iunknown'}

def balanced(text,start):
    depth=0;quote=None;escaped=False
    for pos in range(start,len(text)):
        ch=text[pos]
        if quote:
            if escaped:escaped=False
            elif ch=='\\':escaped=True
            elif ch==quote:quote=None
        elif ch in "\"'":quote=ch
        elif ch=='(':depth+=1
        elif ch==')':
            depth-=1
            if depth==0:return pos+1
    raise ValueError('unbalanced C expression')

def statement_end(text,start):
    """Find a C body terminator without treating strings/comments as syntax."""
    at=start
    while at<len(text) and text[at].isspace():at+=1
    braces=0;parens=0;quote=None;escaped=False;block=False;line=False
    is_block=at<len(text) and text[at]=='{'
    for pos in range(at,len(text)):
        ch=text[pos];nxt=text[pos:pos+2]
        if line:
            if ch=='\n':line=False
            continue
        if block:
            if text[pos-1:pos+1]=='*/':block=False
            continue
        if quote:
            if escaped:escaped=False
            elif ch=='\\':escaped=True
            elif ch==quote:quote=None
            continue
        if nxt=='//':line=True;continue
        if nxt=='/*':block=True;continue
        if ch in "\"'":quote=ch;continue
        if ch=='{':braces+=1
        elif ch=='}':
            braces-=1
            if is_block and braces==0:return pos+1
        elif ch=='(':parens+=1
        elif ch==')':parens-=1
        elif ch==';' and braces==parens==0:return pos+1
    return len(text)

def cguards(path):
    text=path.read_text();funcs=list(re.finditer(r'(?m)^(?:__declspec\(noinline\) )?static [^\n;{}]+?\b(\w+)\([^;\n]*\)\s*\{',text))
    branches=[]
    for m in re.finditer(r'\bif\s*\(',text):
        begin=text.index('(',m.start())
        try:end=balanced(text,begin)
        except ValueError:continue
        finish=statement_end(text,end);branches.append((m.start(),end,finish,text[begin+1:end-1]))
    for match in re.finditer(r'\b(xrt_fatal|d8_domain)\s*\(',text):
        end=balanced(text,text.index('(',match.start()));expression=text[match.start():end]
        fn=next((v[1] for v in reversed(funcs) if v.start()<match.start()),'<file>')
        conditions=[condition for begin,body,finish,condition in branches if body<=match.start()<finish]
        condition=conditions[-1] if conditions else None
        yield dict(line=text.count('\n',0,match.start())+1,function=fn,expression=expression,condition=condition,
            nearest_condition=condition,enclosing_if_conditions=conditions,mechanism=match[1],
            condition_kind='enclosing_if' if conditions else 'unconditional_or_helper_domain; exact predicate is in the call/function control flow')
    if path.name=='semantic_policy.h':
        for match in re.finditer(r'\breturn\b([^;]*);',text):
            fn=next((v[1] for v in reversed(funcs) if v.start()<match.start()),'<file>')
            yield dict(line=text.count('\n',0,match.start())+1,function=fn,expression=match[0],nearest_condition=match[1].strip(),mechanism='scalar_domain_result')

def pyguards(path):
    text=path.read_text();tree=ast.parse(text)
    functions=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    for node in ast.walk(tree):
        call=isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='require'
        if not isinstance(node,ast.Assert) and not call:continue
        condition=node.test if isinstance(node,ast.Assert) else node.args[0] if node.args else None
        fn=next((n.name for n in sorted(functions,key=lambda f:f.lineno,reverse=True) if n.lineno<=node.lineno<=n.end_lineno),'<module>')
        yield dict(line=node.lineno,function=fn,expression=ast.get_source_segment(text,node),condition=ast.get_source_segment(text,condition) if condition else None,nearest_condition=ast.get_source_segment(text,condition) if condition else None,mechanism='assert' if isinstance(node,ast.Assert) else 'require')

def classify(path,row):
    t=(row['expression']+' '+(row['nearest_condition'] or '')).lower();name=path.name;fn=row['function']
    category='SAFETY_CRITICAL';action='retained';exact=False
    reason='Guest memory, identity, ownership, reentrancy, ABI, containment, or enforcement invariant; never bypassed.'
    api=SOURCES['abi'];original='Runtime 32-bit guest ABI and typed host boundary; see source expression.'
    # Classify known guards by their concrete purpose, not their exit number.
    if 'unsupported slot' in t or 'requires marshalling' in t or 'pointer message' in t or 'unknown guest font' in t:
        category='SAFETY_CRITICAL';reason='Unsupported pointer/resource operation cannot be forwarded without a typed ownership/marshalling implementation.'
    elif 'renderer identity changed' in t or 'renderer device identity mismatch' in t:
        action='replaced_by_typed_COM_identity_and_scoped_renderer_binding'
        reason='The API validates the live device token and ownership. The proposed SetRes observer checks renderer/viewport binding at entry and return; arbitrary render-callsite stack reconstruction is removed.'
    elif any(x in t for x in ('tuple','profile field','unmeasured/reduced capability','editor profile','configured tuple','len(self.profile)','len(self.completed)','material bytes','input bytes changed','transform/gamma argument','configured sequence','unmeasured callsite','unmeasured dpi','unmeasured style/menu','unmeasured geometry','unsupported state=','failed actual hresult','unclassified native last-error','resizeviewport flags/dimensions','resizeviewport unqualified client','return_value=cs','initial setres entry:')):
        category='SEMANTIC_COMPATIBILITY';exact=True;action='generalized_in_integrated_runtime_and_observer'
        reason='Historical profile or fixture value is not an API contract; use scalar domains/live caps/typed input and transfer checks.';api=SOURCES['d3d8']
    elif name=='integrated_renderer.inc' and any(x in t for x in ('batch','found','q->','d8_experimental')):
        category='SEMANTIC_COMPATIBILITY';exact=True;action='removed_profile_admission';reason='Call order, callsite and fixture configuration are observations, not API argument domains.';api=SOURCES['d3d8']
    elif name=='observer.py' and any(x in t for x in ('mxcsr','a[:5]','a[32:160]','x87','fsw')) and not any(x in t for x in ('nonvolatile xmm','suspended','callback','unsafe','errors')):
        category='STRICT_DIFFERENTIAL';action='recorded_separately_in_new_observer';reason='Native-x86/FPU equivalence remains a strict finding. New unsafe ABI/control corruption is still fatal.'
    elif any(x in t for x in ('only four null','only four null arguments','four null arguments','unmeasured point count','non-null rect is unmeasured','unmeasured selector/dpi','0xae: unmeasured','theme destruction','outside measured range')):
        category='SEMANTIC_COMPATIBILITY';exact=True;action='retained_compatibility_limitation'
        reason='Broader domain requires an additional typed or documented-message implementation; no invented success or unknown scalar forwarding.'
    elif 'unsupported captured tuple' in t:
        category='SEMANTIC_COMPATIBILITY';exact=True;action='dimensions_generalized_other_presentation_scope_retained'
        reason='Backend/format/windowed behavior scope retained; dimensions are no longer a particular screen size.'
        action='replaced_by_live_creation_domains_and_device_format_queries'
        reason='Windowed HAL scope and safe FPU behavior remain explicit. Counts, RGB/depth formats, BOOLs, dimensions and supported multisampling use typed domains and actual query results.'
    elif 'unmeasured sdk version' in t:
        category='SEMANTIC_COMPATIBILITY';exact=True;action='known_UINT_factory_native_result';reason='Direct3DCreate8 is a known UINT API; preserve actual native pointer/NULL instead of a fixture literal.'
    elif 'unsupported rendering window tuple' in t:
        category='SEMANTIC_COMPATIBILITY';exact=True;action='generalized_to_two_owned_live_windows';reason='D3D focus and presentation HWNDs may differ; each still requires same-process/thread ownership.'
    elif name=='observer.py' and ('failed/incorrect guest return' in t or 'resizeviewport failed return/ret12' in t or 'renderer site/return/device argument' in t or 'nested resizeviewport callback' in t):
        category='SEMANTIC_COMPATIBILITY';exact=True;action='split_compatibility_policy_from_safety_checks';reason='Exact success/callsite/single callback depth is not the contract. Preserve actual HRESULT/nonzero UBOOL and callback nesting; retain return/identity/stack/suspended CPU checks individually.'
    elif 'unsupported rectangle bounds' in t or 'unsupported argument combination' in t:
        category='SEMANTIC_COMPATIBILITY';exact=True;action='generalized_clear_contract';reason='Clear accepts copied rectangle arrays, target/depth/stencil flags and valid depth; fixed color/depth/size assumptions removed.'
    elif row['mechanism']=='d8_domain' or name=='semantic_policy.h':
        category='SEMANTIC_COMPATIBILITY';action='semantic_validation';reason='Documented enumeration/range/bitmask and live capability validation; actual backend results are propagated.';api=SOURCES['d3d8']
    if 'memory' in fn or any(x in t for x in ('page_guard','page_noaccess','guest range','readable','writable','pointer','output','overlap')) and category=='SAFETY_CRITICAL':api=SOURCES['memory']
    if 'MoveWindow' in fn:api=SOURCES['move'];original='WinDrv ResizeViewport 11104F20; Window MoveWindow import at 110018E2; signed geometry and BOOL repaint.'
    elif 'AttachThreadInput' in fn:api=SOURCES['attach'];original='WinDrv TryRenderDevice 11104A48; real self-thread FALSE/error87 and keyboard effects retained.'
    elif 'TextureStage' in fn:api=SOURCES['stages'];original='D3DDrv 0696F3AC..0696F42E and state-cache 06977800..069783FE; DWORD state payloads.'
    elif any(x in fn for x in ('SetRender','SetMaterial','SetTransform','SetTexture','SetVertex','SetStream','SetIndices','Gamma','Clear')):
        original='Original D3DDrv SetRes 0696E890..0696F4E9 / cache 06977800..069783FE; original instruction correspondence retained in original-provenance.json.'
    elif any(x in fn for x in ('QueryInterface','AddRef','Release','object','cleanup')):api=SOURCES['com'];original='IUnknown identity/reference ownership; guest tokens never become native pointers.'
    if path.is_relative_to(RT):action='current_'+action if action!='retained' else 'retained_in_integrated_candidate'
    components=[]
    if 'nonvolatile' in t and any(x in t for x in ('x87','a[:5]','a[32:160]')):
        components=[dict(category='SAFETY_CRITICAL',predicate='nonvolatile GPR/XMM and x87/MXCSR control/ABI preservation',action='retain individually'),
                    dict(category='STRICT_DIFFERENTIAL',predicate='x87 status/register exact native-x86 equivalence',action='retain historical verdict; record separately')]
    return dict(category=category,action=action,components=components,exact_representation_required=exact and category=='SAFETY_CRITICAL',historical_exact_policy=exact,
                necessary_for_safe_execution=category=='SAFETY_CRITICAL',can_use_semantic_validation=category=='SEMANTIC_COMPATIBILITY',reason=reason,api_contract=api,original_basis=original)

def main():
    runtime_names=['hle_d3d8.inc','hle_d3d8_device.inc','d3d8_device_slots.inc','integrated_renderer.inc','hle_gui.c','hle_gui_classes.inc','hle_gui_diag.inc','hle_misc.c','xrt_loader.c']
    paths=[root/name for root in (PRIOR/'runtime',RT) for name in runtime_names if (root/name).exists()]
    paths += list(RT.glob('semantic*'))
    paths += [H.parent/'renderer_config_diagnosis'/n for n in ('observer.py','evidence.py','profile_gate.py','attach_audit.py')]
    paths += [H/'observer.py']
    paths += [W/'tools/xrt/supervisor'/n for n in ('observer.py','plan.py','policy.py','service.py','windows.py') if (W/'tools/xrt/supervisor'/n).exists()]
    rows=[]
    for p in paths:
        for row in (pyguards(p) if p.suffix=='.py' else cguards(p)):
            row.update(source=str(p),source_sha256=core.sha(p),**classify(p,row));row['id']='G'+str(len(rows)+1).zfill(4);rows.append(row)
    # Make every old field and all 53 exact caps predicates independently searchable.
    fields=read(PRIOR/'field-sources.json')['fields']
    expanded=[]
    for offset,field in fields.items():
        expanded.append(dict(offset=offset,field=field,old_expected=read(PRIOR/'configuration-profile.json')['fields'][offset],
            action='remove_fixture_equality; original code computes nonzero/bitmask/clamp without host normalization',
            replacement='validate resulting D3D state and live host caps, retain guest bytes unchanged'))
    provenance={}
    for p in [W/'out/recovery/d3d8-remote-20261029-01/initialization-plan.json',PRIOR/'original-pe-analysis.json',PRIOR/'field-sources.json',
              W/'out/recovery/renderer-prerequisites-20261029-01/extended-contracts.json']:
        if p.exists():provenance[str(p)]=dict(sha256=core.sha(p),evidence=read(p))
    save(O/'original-provenance.json',provenance)
    result=dict(version=1,scope='C fatal/domain sites and Python assertion sites in complete renderer/GUI/import/observer/containment source closure; old and new sites counted separately',
        sources={str(p):core.sha(p) for p in paths},total_guard_sites=len(rows),categories=dict(Counter(r['category'] for r in rows)),
        actions=dict(Counter(r['action'] for r in rows)),guards=rows,renderer_fields=expanded,
        capability_equality_predicates_removed=53,strict_failures_changed=False,supervisor_policy_changed=False,
        condition_note='expression and enclosing if/assert condition text are exact source. Unconditional traps and helper-domain calls retain their exact call expression and function; no invented inverse CFG predicate. Loop-expanded capability comparisons are counted as one source site plus 53 explicit predicates. API provenance is by typed boundary; original instruction references are retained in original-provenance.json.',
        documentation=SOURCES)
    result['source_groups']=dict(Counter('legacy_runtime' if Path(r['source']).is_relative_to(PRIOR/'runtime') else 'integrated_runtime' if Path(r['source']).is_relative_to(RT) else 'legacy_observer' if 'renderer_config_diagnosis' in r['source'] else 'semantic_observer' if Path(r['source'])==H/'observer.py' else 'unchanged_supervisor' for r in rows))
    result['documentation']['icon_dpi']='https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-geticon'
    result['documentation']['pinned_shader_handle_and_present_mapping']='https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/d3d8_util.h'
    save(O/'guard-inventory.json',result)
    print('Guard inventory:',len(rows),result['categories'],flush=True)
if __name__=='__main__':main()
