/* Included by hle_gui.c: 48-byte guest WNDCLASSEX <-> native structures.
 * Each registration has its own static host thunk. WNDPROC handles returned by
 * Windows (including A/W conversion sentinels) have non-recycled guest IDs.
 * They are accepted ONLY by CallWindowProc/RegisterClassEx, never as guest code. */
typedef struct GuiClass {
    ATOM atom;
    uint32_t owner, proc;
    HINSTANCE host_owner;
    int live;
    int guest_extra,host_extra;
    uint32_t generation;
    int wide;
} GuiClass;
static GuiClass classes[64];
static unsigned class_count;
typedef struct PriorProc {
    WNDPROC host;
    uint32_t id, owner,generation;
    int class_index; /* -1: system class; otherwise registration lifetime */
} PriorProc;
static PriorProc prior_procs[256];
static unsigned prior_count;
/* These measured controls contain one pointer in window-extra storage. The
 * native x86 fixture checks both size and all other scalar class fields. USER32
 * builtins already reserve the same byte count in WOW64 and native USER32. */
static const char* pointer_classes[]={"SysTabControl32","SysListView32","RICHEDIT","tooltips_class32","SysTreeView32","msctls_trackbar32","msctls_progress32"};
typedef struct ClassQueryLayout { uint32_t address,fields[12]; int guest_extra,host_extra; } ClassQueryLayout;
static ClassQueryLayout class_queries[128];
static unsigned class_query_count;
typedef struct ClassModule { uint32_t guest; HMODULE host; } ClassModule;
static ClassModule class_modules[64];
static unsigned class_module_count;
typedef struct GuiBorrow { void* host; uint32_t token; int kind,owned; } GuiBorrow;
static GuiBorrow class_objects[256];
static unsigned class_object_count;
enum { GO_ICON=1, GO_CURSOR, GO_BRUSH, GO_FONT };
static uint32_t known_font_token(HFONT host) {
    unsigned i;
    for(i=0;host && i<class_object_count;i++)
        if(class_objects[i].host==host && class_objects[i].kind==GO_FONT) return class_objects[i].token;
    return 0;
}
static PriorProc* prior_find(CPU* c,uint32_t id);
static uint32_t owner_generation(CPU* c,uint32_t owner) {
    XrtModule* m;
    if(!owner) return 0;
    if(xrt_handle_type(owner)==XH_MODULE) return xrt_system_module_generation(c,owner);
    m=xrt_module_by_addr(owner);
    if(!m || m->base!=owner) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"WNDPROC owner %08x is unloaded",owner);
    return m->generation;
}
static void validate_guest_proc(CPU* c, uint32_t proc) {
    const char* stub = NULL;
    XrtModule* m = xrt_module_by_addr(proc);
    if (!m || m->unloaded || !xrt_lookup(proc, &stub) || stub)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "WNDPROC %08x is not a live translated function", proc);
}
static HINSTANCE class_module(CPU* c, uint32_t guest) {
    unsigned i;
    XrtModule* m;
    if (!guest) return NULL;
    if (xrt_handle_type(guest) == XH_MODULE) return (HINSTANCE)xrt_system_module_host(c, guest);
    m=xrt_module_by_addr(guest);
    if(!m || m->base!=guest || m->unloaded)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"class module %08x is not a live translated image",guest);
    for (i=0; i<class_module_count; i++)
        if (class_modules[i].guest == guest) return class_modules[i].host;
    if (class_module_count == 64) xrt_fatal(c, XRT_EXIT_SETUP, "class module table full");
    class_modules[class_module_count].guest = guest;
    class_modules[class_module_count].host = resource_module(c, guest);
    if (!class_modules[class_module_count].host) xrt_fatal(c, XRT_EXIT_SETUP, "class module mapping failed");
    /* Distinct resource mappings retain HINSTANCE identity without executing PE32. */
    return class_modules[class_module_count++].host;
}
static uint32_t class_owner(CPU* c, HINSTANCE host) {
    unsigned i;
    if (!host) return 0;
    for (i=0; i<class_module_count; i++)
        if (class_modules[i].host == host) return class_modules[i].guest;
    return xrt_system_module_guest(c, host);
}
static uint32_t borrow_class_object(CPU* c, void* host, int kind) {
    unsigned i;
    if (!host) return 0;
    if (kind == GO_BRUSH && (uintptr_t)host <= COLOR_MENUBAR+1) return (uint32_t)(uintptr_t)host;
    for(i=0;i<class_object_count;i++)
        if(class_objects[i].host==host && class_objects[i].kind==kind) return class_objects[i].token;
    if(class_object_count==256) xrt_fatal(c,XRT_EXIT_SETUP,"class object table full");
    i=class_object_count++;
    class_objects[i].host=host; class_objects[i].kind=kind;
    /* Separate namespace, lifetime is the process/system class (borrowed). */
    return class_objects[i].token=kind==GO_FONT ? xrt_handle_new(XH_FONT,host) : 0xfb000000u+16*i;
}
static void* class_object(CPU* c, uint32_t token, int kind) {
    unsigned i;
    if (!token || (kind==GO_BRUSH && token<=COLOR_MENUBAR+1)) return (void*)(uintptr_t)token;
    for(i=0;i<class_object_count;i++)
        if(class_objects[i].token==token && class_objects[i].kind==kind && class_objects[i].host) return class_objects[i].host;
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"unknown class object %08x kind %d",token,kind);
}
/* WM_GETICON returns a borrowed HICON. Reuse the typed class-image namespace:
 * shared LoadIcon handles remain valid across window destruction, and no native
 * handle bits are stored in guest memory or granted destruction ownership. */
static uint32_t borrowed_icon_token(CPU* c,HICON host) {
    return borrow_class_object(c,host,GO_ICON);
}
static HICON guest_icon(CPU* c,uint32_t token) {
    return (HICON)class_object(c,token,GO_ICON);
}
static BOOL delete_class_object(uint32_t token,int* handled) {
    unsigned i;
    for(i=0;i<class_object_count;i++) if(class_objects[i].token==token) {
        BOOL ok;
        *handled=1;
        if(!class_objects[i].owned) { *handled=2; return DeleteObject(class_objects[i].host); }
        ok=DeleteObject(class_objects[i].host);
        if(ok) { class_objects[i].host=NULL; class_objects[i].owned=0; }
        return ok;
    }
    return FALSE;
}
static void hle_CreateSolidBrush(CPU* c) {
    HBRUSH brush; uint32_t token; unsigned i;
    begin(c); brush=CreateSolidBrush(ARG(0)); end(c);
    token=borrow_class_object(c,brush,GO_BRUSH);
    if(brush) for(i=0;i<class_object_count;i++) if(class_objects[i].token==token) class_objects[i].owned=1;
    xrt_event("gui_create_brush","\"color\": %u, \"handle\": %u",ARG(0),token);
    RET_STD(1,token);
}
static void hle_GetStockObject(CPU* c) {
    HGDIOBJ obj; DWORD type; uint32_t token=0;
    begin(c); obj=GetStockObject((int)ARG(0)); end(c);
    if(obj) {
        type=GetObjectType(obj);
        if(type!=OBJ_BRUSH && type!=OBJ_FONT)
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"GetStockObject type %lu requires typed handle mapping",type);
        token=borrow_class_object(c,obj,type==OBJ_FONT?GO_FONT:GO_BRUSH);
    }
    xrt_event("gui_stock_object","\"index\": %u, \"handle\": %u",ARG(0),token);
    RET_STD(1,token);
}
static void hle_CreatePatternBrush(CPU* c) {
    HBRUSH brush; uint32_t token; unsigned i;
    HBITMAP bitmap=xrt_handle_get(ARG(0),XH_BITMAP);
    begin(c); brush=CreatePatternBrush(bitmap); end(c);
    token=borrow_class_object(c,brush,GO_BRUSH);
    if(brush) for(i=0;i<class_object_count;i++) if(class_objects[i].token==token) class_objects[i].owned=1;
    RET_STD(1,token);
}
static LRESULT class_dispatch(unsigned i, HWND h, UINT msg, WPARAM wp, LPARAM lp) {
    PriorProc* prior;
    if (i>=class_count || !classes[i].live)
        xrt_fatal(callback_cpu,XRT_EXIT_UNSUPPORTED,"callback for unregistered guest class");
    if(classes[i].generation!=owner_generation(callback_cpu,classes[i].owner))
        xrt_fatal(callback_cpu,XRT_EXIT_UNSUPPORTED,"class belongs to an earlier module mapping");
    prior=prior_find(callback_cpu,classes[i].proc);
    if(prior) return classes[i].wide?CallWindowProcW(prior->host,h,msg,wp,lp):CallWindowProcA(prior->host,h,msg,wp,lp);
    validate_guest_proc(callback_cpu,classes[i].proc);
    return invoke_gui_proc(h,msg,wp,lp,classes[i].proc);
}
#define CLASS_THUNK(n) static LRESULT CALLBACK class_thunk_##n(HWND h,UINT m,WPARAM w,LPARAM l){return class_dispatch(n,h,m,w,l);}
/* Explicit indices keep callback code static: no writable/executable trampolines. */
CLASS_THUNK(0) CLASS_THUNK(1) CLASS_THUNK(2) CLASS_THUNK(3) CLASS_THUNK(4) CLASS_THUNK(5) CLASS_THUNK(6) CLASS_THUNK(7)
CLASS_THUNK(8) CLASS_THUNK(9) CLASS_THUNK(10) CLASS_THUNK(11) CLASS_THUNK(12) CLASS_THUNK(13) CLASS_THUNK(14) CLASS_THUNK(15)
CLASS_THUNK(16) CLASS_THUNK(17) CLASS_THUNK(18) CLASS_THUNK(19) CLASS_THUNK(20) CLASS_THUNK(21) CLASS_THUNK(22) CLASS_THUNK(23)
CLASS_THUNK(24) CLASS_THUNK(25) CLASS_THUNK(26) CLASS_THUNK(27) CLASS_THUNK(28) CLASS_THUNK(29) CLASS_THUNK(30) CLASS_THUNK(31)
CLASS_THUNK(32) CLASS_THUNK(33) CLASS_THUNK(34) CLASS_THUNK(35) CLASS_THUNK(36) CLASS_THUNK(37) CLASS_THUNK(38) CLASS_THUNK(39)
CLASS_THUNK(40) CLASS_THUNK(41) CLASS_THUNK(42) CLASS_THUNK(43) CLASS_THUNK(44) CLASS_THUNK(45) CLASS_THUNK(46) CLASS_THUNK(47)
CLASS_THUNK(48) CLASS_THUNK(49) CLASS_THUNK(50) CLASS_THUNK(51) CLASS_THUNK(52) CLASS_THUNK(53) CLASS_THUNK(54) CLASS_THUNK(55)
CLASS_THUNK(56) CLASS_THUNK(57) CLASS_THUNK(58) CLASS_THUNK(59) CLASS_THUNK(60) CLASS_THUNK(61) CLASS_THUNK(62) CLASS_THUNK(63)
#define CT(n) class_thunk_##n,
static WNDPROC class_thunks[]={
CT(0) CT(1) CT(2) CT(3) CT(4) CT(5) CT(6) CT(7) CT(8) CT(9) CT(10) CT(11) CT(12) CT(13) CT(14) CT(15)
CT(16) CT(17) CT(18) CT(19) CT(20) CT(21) CT(22) CT(23) CT(24) CT(25) CT(26) CT(27) CT(28) CT(29) CT(30) CT(31)
CT(32) CT(33) CT(34) CT(35) CT(36) CT(37) CT(38) CT(39) CT(40) CT(41) CT(42) CT(43) CT(44) CT(45) CT(46) CT(47)
CT(48) CT(49) CT(50) CT(51) CT(52) CT(53) CT(54) CT(55) CT(56) CT(57) CT(58) CT(59) CT(60) CT(61) CT(62) CT(63)};
#undef CT
#undef CLASS_THUNK
/* Only the actual Unicode class registration admits the measured window
 * protocol. Arbitrary explicit CallWindowProc targets do not inherit it. */
static int registered_getobject_proc(HWND h, uint32_t proc) {
    DWORD error=GetLastError();
    WNDPROC host=(WNDPROC)GetClassLongPtrW(h,GCLP_WNDPROC);
    unsigned i;int match=0;
    for(i=0;i<class_count;i++)
        if(host==class_thunks[i] && classes[i].live && classes[i].wide && classes[i].proc==proc) {
            match=classes[i].generation==owner_generation(callback_cpu,classes[i].owner);
            break;
        }
    SetLastError(error);return match;
}
static PriorProc* prior_find(CPU* c,uint32_t id) {
    unsigned i;
    for(i=0;i<prior_count;i++) if(prior_procs[i].id==id) {
        PriorProc* p=&prior_procs[i];
        if(p->class_index>=0 && !classes[p->class_index].live)
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"prior WNDPROC belongs to an unregistered class");
        if(p->generation!=owner_generation(c,p->owner))
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"prior WNDPROC belongs to an earlier module mapping");
        return p;
    }
    return NULL;
}
static uint32_t proc_identity(CPU* c,WNDPROC host,uint32_t owner,int ci) {
    unsigned i;
    for(i=0;i<class_count;i++) if(host==class_thunks[i] && classes[i].live) return classes[i].proc;
    for(i=0;i<prior_count;i++)
        if(prior_procs[i].host==host && prior_procs[i].owner==owner && prior_procs[i].generation==owner_generation(c,owner) && prior_procs[i].class_index==ci) return prior_procs[i].id;
    if(prior_count==256) xrt_fatal(c,XRT_EXIT_SETUP,"prior WNDPROC table full");
    i=prior_count++;
    prior_procs[i].host=host; prior_procs[i].owner=owner; prior_procs[i].class_index=ci;
    prior_procs[i].generation=owner_generation(c,owner);
    return prior_procs[i].id=0xfc000000u+16*i;
}
static const void* class_string(uint32_t guest) { return guest<0x10000 ? (void*)(uintptr_t)guest : G2H(guest); }
static uint32_t copy_class_string(const void* p,int wide) {
    uint32_t g; size_t n;
    if((uintptr_t)p<0x10000) return (uint32_t)(uintptr_t)p;
    if(!wide) return xrt_guest_strdup_a((const char*)p);
    n=(wcslen((const WCHAR*)p)+1)*2;
    g=xrt_heap_alloc((uint32_t)n); memcpy(G2H(g),p,n); return g;
}
static void get_class_info(CPU* c,int wide) {
    WNDCLASSEXW w; WNDCLASSEXA a;
    HINSTANCE owner=class_module(c,ARG(0));
    uint32_t p=ARG(2),go,provider=0,identity; int r,ci=-1,extra; unsigned i;
    char name[256],quoted[1024];
    if(ARG(1)<0x10000) snprintf(name,sizeof name,"#%u",ARG(1));
    else if(wide) {
        if(!WideCharToMultiByte(CP_ACP,0,G2H(ARG(1)),-1,name,sizeof name,NULL,NULL))
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"class name exceeds measured encoding/length");
    }
    else snprintf(name,sizeof name,"%s",(char*)G2H(ARG(1)));
    memset(&w,0,sizeof w); memset(&a,0,sizeof a);
    w.cbSize=sizeof w; a.cbSize=sizeof a;
    begin(c);
    r=wide ? GetClassInfoExW(owner,class_string(ARG(1)),p?&w:NULL) : GetClassInfoExA(owner,class_string(ARG(1)),p?&a:NULL);
    end(c);
    if(r && p) {
        /* The two native layouts have identical non-string members. */
        if(!wide) memcpy(&w,&a,sizeof w);
        go=class_owner(c,w.hInstance);
        for(i=0;i<class_count;i++) if(classes[i].live && classes[i].atom==(ATOM)r && classes[i].host_owner==w.hInstance) ci=(int)i;
        extra=w.cbWndExtra;
        if(ci>=0) extra=classes[ci].guest_extra;
        else for(i=0;i<sizeof pointer_classes/sizeof pointer_classes[0];i++) {
            WNDCLASSEXA layout={sizeof layout};
            if(GetClassInfoExA(NULL,pointer_classes[i],&layout)==r) {
                if(w.cbWndExtra!=8 || w.cbClsExtra!=0)
                    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"system class pointer layout changed: %s",pointer_classes[i]);
                extra=4;
                provider=xrt_system_gui_owner(c,i==2?"riched32.dll":"comctl32.dll");
                break;
            }
        }
        if(ci<0 && !provider) {
            static const char* builtin[]={"BUTTON","EDIT","STATIC","LISTBOX","COMBOBOX","SCROLLBAR"};
            for(i=0;i<6;i++) {
                WNDCLASSEXA known={sizeof known};
                if(GetClassInfoExA(NULL,builtin[i],&known)==r) {
                    if(w.cbClsExtra!=0 || w.cbWndExtra!=(i==5?80:8))
                        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"USER32 class layout changed: %s",builtin[i]);
                    provider=xrt_system_gui_owner(c,"user32.dll");break;
                }
            }
            if(!provider) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"system class %s has no measured x86 layout/owner",name);
        }
        identity=proc_identity(c,w.lpfnWndProc,provider?provider:go,ci);
        /* GetClassInfoEx leaves the caller's cbSize unchanged, even if it is 4. */
        wr32(p+4,w.style); wr32(p+8,identity);
        wr32(p+12,w.cbClsExtra); wr32(p+16,extra); wr32(p+20,go);
        wr32(p+24,borrow_class_object(c,w.hIcon,GO_ICON)); wr32(p+28,borrow_class_object(c,w.hCursor,GO_CURSOR));
        wr32(p+32,borrow_class_object(c,w.hbrBackground,GO_BRUSH));
        wr32(p+36,copy_class_string(w.lpszMenuName,wide)); wr32(p+40,copy_class_string(w.lpszClassName,wide));
        wr32(p+44,borrow_class_object(c,w.hIconSm,GO_ICON));
        /* Provenance survives the engine replacing lpfnWndProc/name/owner in
         * this structure to superclass a real control. No host offset is exposed. */
        for(i=0;i<class_query_count;i++) if(class_queries[i].address==p) break;
        if(i==class_query_count) {
            if(i==128) xrt_fatal(c,XRT_EXIT_SETUP,"class query layout table full");
            class_query_count++;
        }
        class_queries[i].address=p; memcpy(class_queries[i].fields,G2H(p),48);
        class_queries[i].guest_extra=extra; class_queries[i].host_extra=w.cbWndExtra;
    }
    xrt_event("gui_class_query","\"wide\": %d, \"name\": %s, \"owner\": %u, \"atom\": %d, \"extra\": %d, \"error\": %u",wide,xrt_jstr(quoted,sizeof quoted,name),ARG(0),r,w.cbWndExtra,xrt_get_last_error(c));
    RET_STD(3,r);
}
static void register_class(CPU* c,int wide) {
    WNDCLASSEXW w; uint32_t p=ARG(0),proc,owner; ATOM atom;
    unsigned i=class_count,k; PriorProc* prior;
    if(!p || rd32(p)!=48) { xrt_set_last_error(c,ERROR_INVALID_PARAMETER); RET_STD(1,0); return; }
    if(i==64) xrt_fatal(c,XRT_EXIT_SETUP,"class registration table full");
    memset(&w,0,sizeof w); w.cbSize=sizeof w;
    proc=rd32(p+8); owner=rd32(p+20); prior=prior_find(c,proc);
    if(!prior) validate_guest_proc(c,proc);
    w.style=rd32(p+4); w.lpfnWndProc=class_thunks[i];
    w.cbClsExtra=rd32(p+12); w.cbWndExtra=rd32(p+16); w.hInstance=class_module(c,owner);
    for(k=0;k<class_query_count;k++) if(class_queries[k].address==p && class_queries[k].guest_extra==(int)rd32(p+16)) {
        unsigned f; int matches=1;
        for(f=0;f<12;f++) if(f!=2 && f!=5 && f!=10 && rd32(p+4*f)!=class_queries[k].fields[f]) matches=0;
        if(matches) w.cbWndExtra=class_queries[k].host_extra;
        break;
    }
    w.hIcon=class_object(c,rd32(p+24),GO_ICON); w.hCursor=class_object(c,rd32(p+28),GO_CURSOR);
    w.hbrBackground=class_object(c,rd32(p+32),GO_BRUSH);
    w.lpszMenuName=class_string(rd32(p+36)); w.lpszClassName=class_string(rd32(p+40));
    w.hIconSm=class_object(c,rd32(p+44),GO_ICON);
    begin(c); atom=wide ? RegisterClassExW(&w) : RegisterClassExA((WNDCLASSEXA*)&w); end(c);
    if(atom) { classes[i].atom=atom; classes[i].owner=owner; classes[i].host_owner=w.hInstance; classes[i].proc=proc; classes[i].live=1; classes[i].guest_extra=rd32(p+16); classes[i].host_extra=w.cbWndExtra; classes[i].generation=owner_generation(c,owner); classes[i].wide=wide; class_count++; }
    xrt_event("gui_class_register","\"wide\": %d, \"owner\": %u, \"proc\": %u, \"atom\": %u, \"error\": %u",wide,owner,proc,atom,xrt_get_last_error(c));
    RET_STD(1,atom);
}
static void unregister_class(CPU* c,int wide) {
    HINSTANCE owner=class_module(c,ARG(1)); WNDCLASSEXW w={sizeof w};
    int atom,ok; unsigned i;
    atom=wide ? GetClassInfoExW(owner,class_string(ARG(0)),&w) : GetClassInfoExA(owner,class_string(ARG(0)),(WNDCLASSEXA*)&w);
    begin(c); ok=wide ? UnregisterClassW(class_string(ARG(0)),owner) : UnregisterClassA(class_string(ARG(0)),owner); end(c);
    if(ok) for(i=0;i<class_count;i++) if(classes[i].live && classes[i].atom==(ATOM)atom && classes[i].host_owner==owner) classes[i].live=0;
    xrt_event("gui_class_unregister","\"result\": %d, \"error\": %u",ok,xrt_get_last_error(c));
    RET_STD(2,ok);
}
static LPARAM forward_message(CPU* c,HWND h,UINT msg,uint32_t wp,uint32_t lp,WPARAM* host_wp);
static void refresh_forwarded_message(UINT msg,uint32_t wp,uint32_t lp,LPARAM host_lp);
static void call_window_proc(CPU* c,int wide) {
    uint32_t proc=ARG(0),msg=ARG(2); PriorProc* prior=prior_find(c,proc);
    CPU* previous=callback_cpu; LRESULT result; HWND h=window_host(ARG(1)); WPARAM wp; LPARAM lp;
    if(msg==WM_GETICON)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"CallWindowProc WM_GETICON result path is unmeasured");
    if(ARG(1) && !h) { xrt_set_last_error(c,ERROR_INVALID_WINDOW_HANDLE); RET_STD(5,0); return; }
    lp=forward_message(c,h,msg,ARG(3),ARG(4),&wp);
    if(!prior) validate_guest_proc(c,proc);
    callback_cpu=c; begin(c);
    if(prior) result=wide ? CallWindowProcW(prior->host,h,msg,wp,lp) : CallWindowProcA(prior->host,h,msg,wp,lp);
    else result=invoke_gui_proc(h,msg,wp,lp,proc);
    end(c); callback_cpu=previous;
    refresh_forwarded_message(msg,ARG(3),ARG(4),lp);
    xrt_event("gui_call_window_proc","\"proc\": %u, \"message\": %u, \"result\": %d",proc,msg,(int)result);
    RET_STD(5,(uint32_t)result);
}
/* Reuse the active message's host layout after validating identity. The host
 * pointer never leaves this frame. Writable pointer-free structures are synced
 * before forwarding so guest edits affect the real default/prior procedure. */
static LPARAM forward_message(CPU* c,HWND h,UINT msg,uint32_t wp,uint32_t lp,WPARAM* host_wp) {
    GuiCallbackFrame* f=callback_frame;
    *host_wp=wp;
    if(f && f->window==h && f->message==msg && f->guest_wp==wp && f->guest_lp==lp) {
        *host_wp=f->host_wp;
        switch(msg) {
        case WM_WINDOWPOSCHANGING: case WM_WINDOWPOSCHANGED:
            unpack_windowpos((WINDOWPOS*)f->host_lp,lp);break;
        case WM_GETMINMAXINFO: memcpy((void*)f->host_lp,G2H(lp),40);break;
        case WM_NCCALCSIZE:
            if(wp) {
                NCCALCSIZE_PARAMS* n=(NCCALCSIZE_PARAMS*)f->host_lp;
                if(rd32(lp+48)!=lp+52) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"NCCALCSIZE changed embedded pointer");
                memcpy(n->rgrc,G2H(lp),48);unpack_windowpos(n->lppos,lp+52);
            } else memcpy((void*)f->host_lp,G2H(lp),16);
            break;
        case WM_CREATE: case WM_NCCREATE: /* Read-only creation input. */
            if(!f->create_words || memcmp(f->create_words,G2H(lp),48))
                xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"CREATESTRUCT field mutation requires marshalling");
            break;
        }
        return f->host_lp;
    }
    if(msg==WM_NULL || msg==WM_USER+77) return (LPARAM)(int32_t)lp;
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"window procedure message 0x%x has no validated callback frame",msg);
}
static void refresh_forwarded_message(UINT msg,uint32_t wp,uint32_t lp,LPARAM host_lp) {
    switch(msg) {
    case WM_WINDOWPOSCHANGING: case WM_WINDOWPOSCHANGED: pack_windowpos(lp,(WINDOWPOS*)host_lp);break;
    case WM_GETMINMAXINFO: memcpy(G2H(lp),(void*)host_lp,40);break;
    case WM_NCCALCSIZE:
        if(wp) { NCCALCSIZE_PARAMS* n=(NCCALCSIZE_PARAMS*)host_lp;memcpy(G2H(lp),n->rgrc,48);pack_windowpos(lp+52,n->lppos); }
        else memcpy(G2H(lp),(void*)host_lp,16);
        break;
    }
}
static void def_window_proc(CPU* c,int wide) {
    HWND h=window_host(ARG(0)); WPARAM wp; LPARAM lp;
    CPU* prev=callback_cpu; LRESULT result;
    lp=forward_message(c,h,ARG(1),ARG(2),ARG(3),&wp);
    begin(c);callback_cpu=c;
    result=wide?DefWindowProcW(h,ARG(1),wp,lp):DefWindowProcA(h,ARG(1),wp,lp);
    end(c);callback_cpu=prev;
    refresh_forwarded_message(ARG(1),ARG(2),ARG(3),lp);
    if(ARG(1)==WM_GETICON)result=borrowed_icon_token(c,(HICON)result);
    RET_STD(4,(uint32_t)result);
}
static void create_window(CPU* c,int wide) {
    HINSTANCE instance=class_module(c,ARG(10)); HWND parent=window_host(ARG(8)),h;
    CPU* previous=callback_cpu; uint32_t token=0;
    uint32_t esp=c->r[ESP],caller=rd32(esp);
    if(ARG(8) && !parent) {xrt_set_last_error(c,ERROR_INVALID_WINDOW_HANDLE);RET_STD(12,0);return;}
    if(ARG(9) && !(ARG(3)&WS_CHILD)) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"CreateWindowEx menu requires typed mapping");
    xrt_event("gui_create_window_call","\"wide\":%d,\"style\":%u,\"esp\":%u,\"return\":%u",wide,ARG(3),esp,caller);
    begin(c);callback_cpu=c;
    h=wide?CreateWindowExW(ARG(0),class_string(ARG(1)),class_string(ARG(2)),ARG(3),(int)ARG(4),(int)ARG(5),(int)ARG(6),(int)ARG(7),parent,(HMENU)(uintptr_t)ARG(9),instance,(void*)(uintptr_t)ARG(11)):
        CreateWindowExA(ARG(0),class_string(ARG(1)),class_string(ARG(2)),ARG(3),(int)ARG(4),(int)ARG(5),(int)ARG(6),(int)ARG(7),parent,(HMENU)(uintptr_t)ARG(9),instance,(void*)(uintptr_t)ARG(11));
    end(c); if(h) token=window_token(h);callback_cpu=previous;forget_dead_windows();
    xrt_event("gui_create_window","\"handle\": %u, \"wide\": %d, \"error\": %u",token,wide,xrt_get_last_error(c));
    RET_STD(12,token);
    xrt_event("gui_create_window_return","\"handle\":%u,\"wide\":%d,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",token,wide,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
static void get_window_long(CPU* c,int wide) {
    LONG result; int index=(int)ARG(1);
    if(index!=GWL_STYLE && index!=GWL_EXSTYLE && index!=GWL_ID)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"GetWindowLong index %d requires typed layout",index);
    begin(c);result=wide?GetWindowLongW(window_host(ARG(0)),index):GetWindowLongA(window_host(ARG(0)),index);end(c);
    RET_STD(2,(uint32_t)result);
}
static void hle_CreateWindowExW(CPU* c){create_window(c,1);}
static void hle_CreateWindowExA(CPU* c){create_window(c,0);}
static void hle_DefWindowProcW(CPU* c){def_window_proc(c,1);}
static void hle_DefWindowProcA(CPU* c){def_window_proc(c,0);}
static void hle_GetWindowLongW(CPU* c){get_window_long(c,1);}
static void hle_GetWindowLongA(CPU* c){get_window_long(c,0);}
/* Property values are opaque guest data, represented by owned host boxes.
 * Reading an unrelated native property never truncates a host HANDLE/pointer. */
typedef struct GuiProperty { HWND window; uint32_t value; int live; } GuiProperty;
static GuiProperty properties[128];
static void forget_window_properties(HWND host) {
    unsigned i;for(i=0;i<128;i++) if(properties[i].window==host) properties[i].live=0;
}
static GuiProperty* property_box(CPU* c,HWND window,HANDLE value) {
    unsigned i;
    if(!value) return NULL;
    for(i=0;i<128;i++) if(value==&properties[i] && properties[i].live && properties[i].window==window) return &properties[i];
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"native window property has no owned guest value mapping");
}
static void window_property(CPU* c,int wide,int op) {
    HWND h=window_host(ARG(0)); HANDLE value; GuiProperty* old; unsigned i; BOOL ok;
    if(op==0) {
        value=wide?GetPropW(h,class_string(ARG(1))):GetPropA(h,class_string(ARG(1)));
        old=property_box(c,h,value);
        for(i=0;i<128;i++) if(!properties[i].live && &properties[i]!=old) break;
        if(i==128) xrt_fatal(c,XRT_EXIT_SETUP,"window property table full");
        properties[i].window=h;properties[i].value=ARG(2);properties[i].live=1;
        begin(c);ok=wide?SetPropW(h,class_string(ARG(1)),&properties[i]):SetPropA(h,class_string(ARG(1)),&properties[i]);end(c);
        if(!ok) properties[i].live=0;
        else if(old) old->live=0;
        RET_STD(3,ok);return;
    }
    begin(c);
    if(op==1) value=wide?GetPropW(h,class_string(ARG(1))):GetPropA(h,class_string(ARG(1)));
    else value=wide?RemovePropW(h,class_string(ARG(1))):RemovePropA(h,class_string(ARG(1)));
    end(c);old=property_box(c,h,value);
    if(old && op==2) old->live=0;
    RET_STD(2,old?old->value:0);
}
static void hle_SetPropW(CPU* c){window_property(c,1,0);}
static void hle_SetPropA(CPU* c){window_property(c,0,0);}
static void hle_GetPropW(CPU* c){window_property(c,1,1);}
static void hle_GetPropA(CPU* c){window_property(c,0,1);}
static void hle_RemovePropW(CPU* c){window_property(c,1,2);}
static void hle_RemovePropA(CPU* c){window_property(c,0,2);}
static void hle_GetClassInfoExW(CPU* c){get_class_info(c,1);}
static void hle_GetClassInfoExA(CPU* c){get_class_info(c,0);}
static void hle_RegisterClassExW(CPU* c){register_class(c,1);}
static void hle_RegisterClassExA(CPU* c){register_class(c,0);}
static void hle_UnregisterClassW(CPU* c){unregister_class(c,1);}
static void hle_UnregisterClassA(CPU* c){unregister_class(c,0);}
static void hle_CallWindowProcW(CPU* c){call_window_proc(c,1);}
static void hle_CallWindowProcA(CPU* c){call_window_proc(c,0);}
static void load_class_image(CPU* c,int wide,int cursor) {
    HINSTANCE module=class_module(c,ARG(0)); void* image; uint32_t token;
    begin(c);
    if(cursor) image=wide ? (void*)LoadCursorW(module,class_string(ARG(1))) : (void*)LoadCursorA(module,class_string(ARG(1)));
    else image=wide ? (void*)LoadIconW(module,class_string(ARG(1))) : (void*)LoadIconA(module,class_string(ARG(1)));
    end(c);
    token=borrow_class_object(c,image,cursor ? GO_CURSOR : GO_ICON);
    xrt_event("gui_load_class_image","\"cursor\": %d, \"module\": %u, \"resource\": %u, \"handle\": %u, \"error\": %u",cursor,ARG(0),ARG(1),token,xrt_get_last_error(c));
    RET_STD(2,token);
}
static void hle_LoadIconW(CPU* c){load_class_image(c,1,0);}
static void hle_LoadIconA(CPU* c){load_class_image(c,0,0);}
static void hle_LoadCursorW(CPU* c){load_class_image(c,1,1);}
static void hle_LoadCursorA(CPU* c){load_class_image(c,0,1);}
/* Measured current-thread cursor transition. The actual previous HCURSOR may
 * first enter the guest here; borrow its typed identity without taking ownership. */
static void hle_SetCursor(CPU* c) {
    uint32_t token=ARG(0),esp=c->r[ESP],caller=rd32(esp),result;
    HCURSOR cursor,previous;CPU* suspended=callback_cpu;
    xrt_event("gui_set_cursor_call","\"cursor\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",token,esp,caller,xrt_get_last_error(c));
    cursor=(HCURSOR)class_object(c,token,GO_CURSOR);
    callback_cpu=c;begin(c);previous=SetCursor(cursor);end(c);callback_cpu=suspended;
    result=borrow_class_object(c,previous,GO_CURSOR);RET_STD(1,result);
    xrt_event("gui_set_cursor_return","\"cursor\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",token,result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
