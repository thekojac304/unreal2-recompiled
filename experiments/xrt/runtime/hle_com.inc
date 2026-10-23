/* Shared guest COM primitives. Each interface retains its own typed host
 * ownership table; only guest memory/vtable allocation is common. */
static const GUID com_iunknown={0,0,0,{0xc0,0,0,0,0,0,0,0x46}};
static void com_memory(CPU*c,uint32_t p,uint32_t size,const char*interface_name) {
    if(!p || !xrt_is_committed(p,size))
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"%s: invalid guest range %08x size %u",interface_name,p,size);
}
static uint32_t com_vtable(const char*const*names,unsigned count) {
    unsigned i;
    uint32_t table=xrt_rt_alloc(count*4,4);
    for(i=0;i<count;i++) wr32(table+4*i,xrt_hle_proc("xrt.com",names[i]));
    return table;
}
