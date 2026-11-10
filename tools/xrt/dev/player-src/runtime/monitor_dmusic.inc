typedef char xm_dm_slot_QueryInterface[offsetof(DmLoader8Vtbl,QueryInterface)==0*sizeof(void*)?1:-1];
static HRESULT xm_dm_QueryInterface(CPU*c,DmLoader8* a0,REFIID a1,void** a2){
 XmRequest q={0};HRESULT ret;q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="DmLoader8.QueryInterface";
 q.slot=0;q.interface_id=5;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_blob(c,"DmLoader8.QueryInterface.iid",a1,16);
 ret=a0->lpVtbl->QueryInterface(a0,a1,a2);
 if(a2)xm_blob(c,"DmLoader8.QueryInterface.output",a2,sizeof *a2);
 q.event=XM_END;q.result=(uint32_t)ret;xm_probe(c,&q);return ret;}
typedef char xm_dm_slot_AddRef[offsetof(DmLoader8Vtbl,AddRef)==1*sizeof(void*)?1:-1];
static ULONG xm_dm_AddRef(CPU*c,DmLoader8* a0){
 XmRequest q={0};ULONG ret;q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="DmLoader8.AddRef";
 q.slot=1;q.interface_id=5;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->lpVtbl->AddRef(a0);
 q.event=XM_END;q.result=(uint32_t)ret;xm_probe(c,&q);return ret;}
typedef char xm_dm_slot_Release[offsetof(DmLoader8Vtbl,Release)==2*sizeof(void*)?1:-1];
static ULONG xm_dm_Release(CPU*c,DmLoader8* a0){
 XmRequest q={0};ULONG ret;q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="DmLoader8.Release";
 q.slot=2;q.interface_id=5;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->lpVtbl->Release(a0);
 q.event=XM_END;q.result=(uint32_t)ret;xm_probe(c,&q);return ret;}
