/* Actual game CreateVertexShader path: bounded declaration, NULL function.
 * Shader DWORDs are typed opaque guest handles, never forwarded unchecked.
 * Programmable code, tessellation and embedded constants remain explicit traps.
 */
typedef struct D8Declaration {DWORD guest,host;unsigned live,bytes[16];} D8Declaration;
static D8Declaration d8_declarations[2048];
static unsigned d8_declaration_used;
static D8Declaration*d8_decl_guest(CPU*c,DWORD handle) {
 unsigned i;for(i=0;i<d8_declaration_used;i++)if(d8_declarations[i].guest==handle&&d8_declarations[i].live)return &d8_declarations[i];
 xrt_fatal(c,76,"D3D8 declaration: stale or unknown handle");
}
static D8Declaration*d8_decl_native(DWORD handle) {
 unsigned i;for(i=0;i<d8_declaration_used;i++)if(d8_declarations[i].host==handle&&d8_declarations[i].live)return &d8_declarations[i];return NULL;
}
static void d8_declaration_device_dead(void){unsigned i;for(i=0;i<d8_declaration_used;i++)d8_declarations[i].live=0;}
static unsigned d8_copy_declaration(CPU*c,uint32_t address,DWORD words[256],unsigned sizes[16],const DWORD*caps) {
 unsigned i,stream=0,offset=0,registers=0,seen_streams=0,elements=0;DWORD token;
 memset(sizes,0,16*sizeof *sizes);
 for(i=0;i<256;i++) {
  uint64_t p=(uint64_t)address+4*i;unsigned kind,type,reg,amount;
  if(p>UINT32_MAX)xrt_fatal(c,76,"D3D8 declaration: address overflow");
  d8_device_memory(c,(uint32_t)p,4,0);token=rd32((uint32_t)p);words[i]=token;
  if(token==0xffffffffu){if(!elements)xrt_fatal(c,76,"D3D8 declaration: no vertex elements");return i+1;}
  kind=token>>29;
  if(token==0)continue;
  if(kind==1){
   if(token&~0x2000000fu)xrt_fatal(c,76,"D3D8 declaration: tessellation/reserved stream bits");
   stream=token&15;if(stream>=caps[47]||(seen_streams&(1u<<stream)))xrt_fatal(c,76,"D3D8 declaration: duplicate/out-of-capacity stream");
   seen_streams|=1u<<stream;offset=0;continue;
  }
  if(kind!=2)xrt_fatal(c,76,"D3D8 declaration: unsupported token class");
  seen_streams|=1u<<stream;
  if(token&0x10000000u){
   if(token&~0x500f0000u)xrt_fatal(c,76,"D3D8 declaration: reserved skip token bits");
   amount=4*((token>>16)&15u);
  } else {
   static const unsigned widths[]={4,8,12,16,4,4,4,8};
   if(token&~0x4007001fu)xrt_fatal(c,76,"D3D8 declaration: reserved element bits");
   reg=token&31;type=(token>>16)&7;
   if(reg>=17||(registers&(1u<<reg)))xrt_fatal(c,76,"D3D8 declaration: invalid/duplicate register");
   registers|=1u<<reg;amount=widths[type];elements++;
   /* Native decides semantic combinations, e.g. a non-FLOAT3 normal. */
  }
  offset+=amount;if(offset>caps[48]||offset>65535)xrt_fatal(c,76,"D3D8 declaration: stream extent exceeds caps");
  if(!(token&0x10000000u))sizes[stream]=offset;
 }
 xrt_fatal(c,76,"D3D8 declaration: END absent within 256 DWORD capacity");
}
static void d8_device_CreateVertexShader(CPU*c) {
 LONG id=d8_api_entry(c,75,5);D8DeviceObject*o=d8_semantic_frame(c);DWORD words[256],native;unsigned sizes[16],n;uint32_t out=ARG(3);CPU*prev;HRESULT hr;DWORD error;
 if(ARG(2))xrt_fatal(c,76,"CreateVertexShader: programmable shader code unsupported");
 if(ARG(4)&~0x10u)xrt_fatal(c,76,"CreateVertexShader: unknown usage flags");
 if(d8_declaration_used==2048)xrt_fatal(c,76,"CreateVertexShader: typed handle capacity");
 d8_device_memory(c,out,4,1);native=rd32(out);n=d8_copy_declaration(c,ARG(1),words,sizes,o->caps.words);
 prev=d8_native_enter(c,75,words,n*4);hr=XM_CreateVertexShader(c,o->host,words,NULL,&native,ARG(4));error=GetLastError();
 if(SUCCEEDED(hr)) {
  D8Declaration*d;
  if(!native||d8_decl_native(native)){d8_native_failed=1;xrt_fatal(c,76,"CreateVertexShader: invalid native identity");}
  d=&d8_declarations[d8_declaration_used];d->guest=0xf1000001u+2*d8_declaration_used++;d->host=native;d->live=1;memcpy(d->bytes,sizes,sizeof sizes);
  d8_device_memory(c,out,4,1);wr32(out,d->guest);
 } else {d8_device_memory(c,out,4,1);wr32(out,native);}
 d8_semantic_return(c,prev,id,5,hr,error);
}
static void d8_device_SetVertexShader(CPU*c) {
 LONG id=d8_api_entry(c,76,2);D8DeviceObject*o=d8_semantic_frame(c);DWORD value=ARG(1);CPU*prev;HRESULT hr;DWORD error;
 if((value&0xfffff001u)==0xf1000001u)value=d8_decl_guest(c,value)->host;
 else {
  d8_domain(c,d8_fvf_domain(value),"SetVertexShader FVF/owned declaration");
  d8_domain(c,((value>>8)&15u)<=(o->caps.words[35]&0xffffu)?D8_VALID:D8_CAPABILITY,"SetVertexShader texture coordinate capability");
  d8_domain(c,!(value&0x20u)||(o->caps.words[35]&0x100000u)?D8_VALID:D8_CAPABILITY,"SetVertexShader point size capability");
 }
 prev=d8_native_enter(c,76,NULL,0);hr=XM_SetVertexShader(c,o->host,value);error=GetLastError();d8_dev_shader=value;d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_device_GetVertexShader(CPU*c) {
 LONG id=d8_api_entry(c,77,2);D8DeviceObject*o=d8_semantic_frame(c);DWORD value,error;CPU*prev;HRESULT hr;uint32_t out=ARG(1);D8Declaration*d;
 d8_device_memory(c,out,4,1);value=rd32(out);prev=d8_native_enter(c,77,NULL,0);hr=XM_GetVertexShader(c,o->host,&value);error=GetLastError();
 if(SUCCEEDED(hr)){d=d8_decl_native(value);if(d)value=d->guest;else if(value)d8_domain(c,d8_fvf_domain(value),"GetVertexShader native ownership");}
 d8_device_memory(c,out,4,1);wr32(out,value);d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_device_DeleteVertexShader(CPU*c) {
 LONG id=d8_api_entry(c,78,2);D8DeviceObject*o=d8_semantic_frame(c);D8Declaration*d=d8_decl_guest(c,ARG(1));CPU*prev;HRESULT hr;DWORD error;
 prev=d8_native_enter(c,78,NULL,0);hr=XM_DeleteVertexShader(c,o->host,d->host);error=GetLastError();if(SUCCEEDED(hr))d->live=0;d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_layout_requirements(CPU*c,D8DeviceObject*o,unsigned primitives,unsigned bytes[16]) {
 DWORD value=0,error=GetLastError();HRESULT hr;CPU*prev;D8Declaration*d;
 if(primitives>o->caps.words[45])xrt_fatal(c,76,"D3D8 draw: primitive count exceeds caps");
 prev=xrt_gui_callback_enter(c);d8_rendering=1;hr=XM_GetVertexShader(c,o->host,&value);d8_rendering=0;xrt_gui_callback_leave(prev);SetLastError(error);
 if(FAILED(hr))xrt_fatal(c,76,"D3D8 draw: cannot resolve native layout");
 d=d8_decl_native(value);if(d)memcpy(bytes,d->bytes,sizeof d->bytes);else{memset(bytes,0,16*sizeof *bytes);bytes[0]=d8_fvf_bytes(c,value);}
}
