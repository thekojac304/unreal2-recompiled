def sequence():
    raw=(PRIOR/'runtime/batch_cases.inc').read_text()
    calls=[]
    for line in raw.splitlines():
        if not line.startswith(' {'): continue
        v=[int(t.removesuffix('u'),0) for t in line.strip(' {},\n').split(',')]
        group,slot,a,b,c,site,config=v
        calls.append(dict(group=group,slot=slot,a=a,b=b,c=c,site=site,config=config))
    core.require(len(calls)==238,'238 configured tuples required')
    # The tuple inventory groups cache calls by callsite. The actual original
    # cache loop executes all sampler/texture sites for stage 0, then stage 1.
    # Keep its observed execution order separate from the admitted tuple set.
    cache=calls[42:-1]
    stage=[q for q in cache if q['slot'] in (63,61)]
    ordered=[];emitted=False
    for q in cache:
        if q['slot'] in (63,61):
            if not emitted:
                ordered += sorted(stage,key=lambda v:(v['a'],v['site']))
                emitted=True
        else:ordered.append(q)
    result=[dict(slot=42,site=0x696f31d)] + calls[:42] + [dict(kind='resize',slot=-1)] + ordered + calls[-1:]
    for q in result:
        if q['slot']>0:
            q['method'],q['n']=METHODS[q['slot']]
    returns={}
    for p in (W/'experiments/xrt/gen/d3ddrv').glob('*.c'):
        for ret,site in re.findall(r'ICALL\([^;]*?, (0x[0-9a-f]+)u, (0x[0-9a-f]+)u\);',p.read_text()):returns[int(site,0)]=int(ret,0)
    for q in result:
        if q['slot']>0:q['return_pc']=returns[q['site']]
    return result
