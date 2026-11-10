"""Conservative constant propagation through native x64 control flow."""
def propagate(ins,md):
    import capstone as CS
    by={v.address:v for v in ins};states={ins[0].address:{'rcx':'cpu'}};todo=[ins[0].address]
    aliases={}
    for family in ('ax','bx','cx','dx','si','di','bp','sp'):
        aliases['r'+family]='r'+family;aliases['e'+family]='r'+family
    for i in range(8,16):aliases['r'+str(i)]=aliases['r'+str(i)+'d']='r'+str(i)
    def reg(i):return aliases.get(md.reg_name(i),md.reg_name(i))
    def merge(address,state):
        if address not in by:return
        if address not in states:states[address]=state.copy();todo.append(address);return
        old=states[address];meet={k:v for k,v in old.items() if k in state and state[k]==v}
        if meet!=old:states[address]=meet;todo.append(address)
    while todo:
        address=todo.pop();x=by[address];s=states[address].copy();ops=x.operands
        def val(o):
            if o.type==CS.x86_const.X86_OP_IMM:return o.imm
            if o.type==CS.x86_const.X86_OP_REG:return s.get(reg(o.reg))
            if o.type==CS.x86_const.X86_OP_MEM and md.reg_name(o.mem.base) in ('rbp','rsp') and not o.mem.index:
                return s.get('stack_'+md.reg_name(o.mem.base)+'_'+str(o.mem.disp))
        dst=reg(ops[0].reg) if ops and ops[0].type==CS.x86_const.X86_OP_REG else None
        result=None;handled=False
        if x.mnemonic=='mov' and dst:
            result=val(ops[1]);handled=True
        elif x.mnemonic=='lea' and dst:
            m=ops[1].mem;b=s.get(reg(m.base)) if m.base else 0;i=s.get(reg(m.index)) if m.index else 0
            if isinstance(b,int) and isinstance(i,int):result=(b+i*m.scale+m.disp)&0xffffffff
            elif b=='cpu' and not m.disp and not m.index:result='cpu'
            handled=True
        elif x.mnemonic in ('add','sub') and dst:
            a=s.get(dst);b=val(ops[1]);handled=True
            if isinstance(a,int) and isinstance(b,int):result=(a+b if x.mnemonic=='add' else a-b)&0xffffffff
        elif x.mnemonic=='xor' and dst and ops[1].type==CS.x86_const.X86_OP_REG and reg(ops[1].reg)==dst:
            result=0;handled=True
        if x.mnemonic=='mov' and ops[0].type==CS.x86_const.X86_OP_MEM:
            m=ops[0].mem
            if md.reg_name(m.base) in ('rbp','rsp') and not m.index:
                key='stack_'+md.reg_name(m.base)+'_'+str(m.disp);v=val(ops[1]);s.pop(key,None)
                if v is not None:s[key]=v
            if s.get(reg(m.base))=='cpu' and m.disp==0x44:
                v=val(ops[1])
                if v is None:s.pop('guest_pc',None)
                else:s['guest_pc']=v
        if handled:
            s.pop(dst,None)
            if result is not None:s[dst]=result
        else:
            try:_,writes=x.regs_access()
            except CS.CsError:writes=[]
            for r in writes:s.pop(reg(r),None)
        if x.mnemonic=='call':
            for r in ('rax','rcx','rdx','r8','r9','r10','r11'):s.pop(r,None)
        if x.mnemonic in ('ret','int3','ud2'):continue
        target=ops[0].imm if ops and ops[0].type==CS.x86_const.X86_OP_IMM else None
        if x.mnemonic=='jmp':
            if target is not None:merge(target,s)
            continue
        if x.mnemonic.startswith('j') and target is not None:merge(target,s)
        merge(address+x.size,s)
    return states
