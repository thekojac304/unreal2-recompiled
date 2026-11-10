/* This PE32 fixture alone imports FixtureCreateDevice. */
#include "../d3d8_boundary/probe.c"
int _fltused;
__declspec(dllimport) DWORD WINAPI FixtureOpen(void);
__declspec(dllimport) HRESULT WINAPI FixtureCreateDevice(D8Interface*,UINT,UINT,DWORD,DWORD,D8Present*,void**);
typedef struct FV {HRESULT(WINAPI*qi)(void*,REFIID,void**);ULONG(WINAPI*add)(void*);ULONG(WINAPI*release)(void*);void*unused[3];HRESULT(WINAPI*parent)(void*,D8Interface**);void*unused2[2];HRESULT(WINAPI*creation)(void*,DWORD*);} FV;
typedef struct FO {FV*vt;}FO;
static const GUID device_iid={0x7385e5df,0x8fe8,0x41d5,{0x86,0xb6,0xd7,0xb4,0x85,0x47,0xb6,0xcf}};
static FO*saved_device;
__declspec(dllexport)int probe_device_guard(void){D8Interface*p=Direct3DCreate8(120);D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};D8Device*d=NULL;return p->vt->CreateDevice(p,0,1,NULL,0x42,&pp,&d);}
static FO*make(D8Interface*p,DWORD w,UINT adapter,UINT interval){D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};void*out=(void*)0xa5a5a5a5;HRESULT hr;pp.window=(HWND)(ULONG_PTR)w;pp.interval=interval;SetLastError(18);hr=FixtureCreateDevice(p,adapter,1,w,0x42,&pp,&out);logv(hr);logv(GetLastError());logv(out!=NULL);words(&pp,13);return (FO*)out;}
__declspec(dllexport)int probe_fixture(void){D8Interface*p=Direct3DCreate8(120),*parent;DWORD w=FixtureOpen(),cp[4];FO*d,*q;UINT i;probe_log_n=0;
    for(i=0;i<3;i++){d=make(p,w,0,0);if(!d)return 1;saved_device=d;logv(d->vt->add(d));logv(d->vt->release(d));logv(d->vt->qi(d,&device_iid,(void**)&q));logv(q==d);logv(q->vt->release(q));logv(d->vt->qi(d,&unknown,(void**)&q));logv(q==d);logv(q->vt->release(q));q=(FO*)0xa5a5a5a5;logv(d->vt->qi(d,&missing,(void**)&q));logv(q==NULL);logv(d->vt->creation(d,cp));logv(cp[0]);logv(cp[1]);logv(cp[2]==w);logv(cp[3]);logv(d->vt->parent(d,&parent));logv(parent==p);logv(parent->vt->Release(parent));logv(d->vt->release(d));}
    make(p,w,0xffffffff,0);make(p,w,0,1);logv(p->vt->Release(p));return 0;}
__declspec(dllexport)int probe_fixture_parent_first(void){D8Interface*p=Direct3DCreate8(120),*q=NULL;FO*d;probe_log_n=0;d=make(p,FixtureOpen(),0,0);logv(p->vt->Release(p));logv(d->vt->parent(d,&q));logv(q==p);logv(q->vt->Release(q));logv(d->vt->release(d));return 0;}
__declspec(dllexport)int probe_fixture_stale(void){probe_fixture();return saved_device->vt->add(saved_device);}
__declspec(dllexport)int probe_fixture_clear(void){D8Interface*p=Direct3DCreate8(120);FO*d=make(p,FixtureOpen(),0,0);typedef HRESULT(WINAPI*Fn)(void*,DWORD,void*,DWORD,DWORD,float,DWORD);return ((Fn)(*(void***)d)[36])(d,0,NULL,1,0,1.0f,0);}
__declspec(dllexport)int probe_fixture_present(void){D8Interface*p=Direct3DCreate8(120);FO*d=make(p,FixtureOpen(),0,0);typedef HRESULT(WINAPI*Fn)(void*,void*,void*,DWORD,void*);return ((Fn)(*(void***)d)[15])(d,NULL,NULL,0,NULL);}
__declspec(dllexport)int probe_fixture_leak(void){D8Interface*p=Direct3DCreate8(120);FO*d=make(p,FixtureOpen(),0,0);logv(d->vt->add(d));return 0;}
__declspec(dllexport)int probe_fixture_bad_parameters(void){D8Interface*p=Direct3DCreate8(120);DWORD w=FixtureOpen();void*out;return FixtureCreateDevice(p,0,1,w,0x42,(D8Present*)1,&out);}
__declspec(dllexport)int probe_fixture_bad_output(void){D8Interface*p=Direct3DCreate8(120);DWORD w=FixtureOpen();D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};pp.window=(HWND)(ULONG_PTR)w;return FixtureCreateDevice(p,0,1,w,0x42,&pp,(void**)1);}
