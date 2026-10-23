/* Bounded read-only COM observer. It hooks only interfaces actually returned to
 * the game, plus their returned AudioPath/Graph and same-vtable QI aliases.
 * Slot numbers remain explicit; no assumed success or calls are injected. */
typedef struct {DWORD self,vt;unsigned slots;char name[32];} MusicObject;
static MusicObject music_objects[1024];static int music_nobjects;
typedef struct {int used,thread;DWORD ret,esp,ecx,stack[16];char label[96];} MusicPending;
static MusicPending music_pending[2048];
static void music_hook(DWORD addr) {
    int bi=bp_find(addr);
    if(bi<0)bi=bp_add(addr,4,mod_of(addr),-1);
    if(bi<0){fputs("music hook failed\n",stderr);exit(5);}
    bps[bi].music=1;
}
static void music_track(DWORD self,const char*name,unsigned slots) {
    DWORD vt=0,methods[64];
    if(!self)return;
    for(int i=0;i<music_nobjects;i++)if(music_objects[i].self==self)return;
    if(music_nobjects==1024 || slots>64 || !rd(self,&vt,4) || !rd(vt,methods,slots*4)) {
        fputs("music object census incomplete\n",stderr);exit(5);
    }
    MusicObject*o=&music_objects[music_nobjects++];
    o->self=self;o->vt=vt;o->slots=slots;strcpy(o->name,name);
    for(unsigned i=0;i<slots;i++)music_hook(methods[i]);
}
static void music_output(DWORD p,const char*name,unsigned slots) {
    DWORD self=0;if(p && rd(p,&self,4))music_track(self,name,slots);
}
static void music_by_iid(DWORD iid_address,DWORD output) {
    /* Public Windows SDK interface identities; only these exact ABI sizes are hooked. */
    static const GUID enumerator={0xa95664d2,0x9614,0x4f35,{0xa7,0x46,0xde,0x8d,0xb6,0x36,0x17,0xe6}};
    static const GUID client={0x1cb9ad4c,0xdbfa,0x4c32,{0xb1,0x78,0xc2,0xf5,0x68,0xa7,3,0xb2}};
    static const GUID client2={0x726778cd,0xf60a,0x4eda,{0x82,0xde,0xe4,0x76,0x10,0xcd,0x78,0xaa}};
    static const GUID client3={0x7ed4ee07,0x8e67,0x4cd4,{0x8c,0x1a,0x2b,0x7a,0x59,0x87,0xad,0x42}};
    static const GUID render={0xf294acfc,0x3146,0x4483,{0xa7,0xbf,0xad,0xdc,0xa7,0xc2,0x60,0xe2}};
    GUID iid;if(!rd(iid_address,&iid,sizeof iid))return;
    if(IsEqualGUID(&iid,&enumerator))music_output(output,"MMDeviceEnumerator",8);
    else if(IsEqualGUID(&iid,&client))music_output(output,"AudioClient",15);
    else if(IsEqualGUID(&iid,&client2))music_output(output,"AudioClient",18);
    else if(IsEqualGUID(&iid,&client3))music_output(output,"AudioClient",21);
    else if(IsEqualGUID(&iid,&render))music_output(output,"AudioRenderClient",5);
}
static void music_discover(const char*label,const DWORD*s,DWORD result,int entry) {
    if((LONG)result<0)return;
    /* entry snapshots include [esp]=return, instruction call sites do not. */
    const DWORD*a=s+entry;
    if(!strcmp(label,"DirectInput.Factory"))music_output(a[3],"DI8W",11);
    else if(!strcmp(label,"DirectInput.DI8W.slot3"))music_output(a[2],"DID8W",32);
    else if(!strcmp(label,"DirectMusic.Loader8"))music_output(a[4],"Loader8",15);
    else if(!strcmp(label,"DirectMusic.Performance8"))music_output(a[4],"Performance8",53);
    else if(!strcmp(label,"DirectMusic.Performance.InitAudio"))music_output(a[2],"DirectSound",11);
    else if(!strcmp(label,"DirectMusic.Performance.GetDefaultAudioPath"))music_output(a[1],"AudioPath",7);
    else if(!strcmp(label,"DirectMusic.AudioPath.GetObjectInPath"))music_output(a[7],"Graph",7);
    else if(!strcmp(label,"DirectMusic.Loader.GetObject"))music_output(a[3],"Script",13);
    else if(!strcmp(label,"DirectMusic.API.DirectSoundCreate8"))music_output(a[1],"DirectSound",12);
    else if(!strcmp(label,"DirectMusic.API.DirectSoundCreate"))music_output(a[1],"DirectSound",11);
    else if(!strcmp(label,"DirectMusic.DirectSound.slot3"))music_output(a[2],"SoundBuffer",21);
    else if(!strcmp(label,"DirectMusic.API.CoCreateInstance"))music_by_iid(a[3],a[4]);
    else if(!strcmp(label,"DirectMusic.MMDeviceEnumerator.slot4"))music_output(a[3],"MMDevice",7);
    else if(!strcmp(label,"DirectMusic.MMDeviceEnumerator.slot5"))music_output(a[2],"MMDevice",7);
    else if(!strcmp(label,"DirectMusic.MMDeviceEnumerator.slot3"))music_output(a[3],"MMDeviceCollection",5);
    else if(!strcmp(label,"DirectMusic.MMDeviceCollection.slot4"))music_output(a[2],"MMDevice",7);
    else if(!strcmp(label,"DirectMusic.MMDevice.slot3"))music_by_iid(a[1],a[4]);
    else if(!strcmp(label,"DirectMusic.AudioClient.slot14"))music_by_iid(a[1],a[2]);
    /* QI may return a tear-off with a shorter vtable. Only identical-vtable aliases
     * are enrolled; all requested IIDs and output bytes are still logged. */
    else if(strstr(label,".slot0")) {
        DWORD self=0,vt=0;
        music_by_iid(a[1],a[2]);
        if(rd(a[2],&self,4) && self && rd(self,&vt,4))
            for(int i=0;i<music_nobjects;i++)if(music_objects[i].vt==vt) {
                music_track(self,music_objects[i].name,music_objects[i].slots);break;
            }
    }
}
static MusicPending* music_save(const char*label,int thread,const CONTEXT*ctx,int entry) {
    for(int i=0;i<2048;i++)if(!music_pending[i].used) {
        MusicPending*p=&music_pending[i];memset(p,0,sizeof*p);p->used=1;p->thread=thread;p->esp=ctx->Esp;
        p->ecx=ctx->Ecx;
        strncpy(p->label,label,95);rd(ctx->Esp,p->stack,sizeof p->stack);
        if(entry){p->ret=p->stack[0];music_hook(p->ret);}
        return p;
    }
    fputs("music pending calls exhausted\n",stderr);exit(5);
}
static void music_observe(int point,int seq,int thread,const CONTEXT*ctx) {
    char stem[96],label[128];size_t n;
    if(!getenv("UCTRACE_MUSIC_LOG") || point<0 ||
       (strncmp(evp[point].label,"DirectMusic.",12) && strncmp(evp[point].label,"DirectInput.",12) &&
        strncmp(evp[point].label,"AActor.event",12)))return;
    music_write(evp[point].label,seq,thread,ctx,NULL);
    strcpy(stem,evp[point].label);n=strlen(stem);
    if(!strncmp(stem,"AActor.event",12)) {
        music_save(stem,thread,ctx,1);
    } else if(n>5 && !strcmp(stem+n-5,".call")) {
        stem[n-5]=0;music_save(stem,thread,ctx,0);
    } else if(n>6 && !strcmp(stem+n-6,".entry")) {
        stem[n-6]=0;music_save(stem,thread,ctx,1);
    } else if(n>7 && !strcmp(stem+n-7,".return")) {
        stem[n-7]=0;
        for(int i=2047;i>=0;i--) {
            MusicPending*p=&music_pending[i];
            if(p->used && !p->ret && p->thread==thread && !strcmp(p->label,stem)) {
                snprintf(label,sizeof label,"%s.outputs",stem);music_write(label,++ev_seq,thread,ctx,p->stack);
                music_discover(stem,p->stack,ctx->Eax,0);p->used=0;break;
            }
        }
    }
}
static void music_break(const CONTEXT*ctx,int thread) {
    DWORD stack[16]={0};char label[128];
    if(!getenv("UCTRACE_MUSIC_LOG"))return;
    /* Latest nested call with this return address and a popped frame. */
    int match=-1;DWORD best=0;
    for(int i=0;i<2048;i++) {
        MusicPending*p=&music_pending[i];
        if(p->used && p->ret==ctx->Eip && p->thread==thread && ctx->Esp>p->esp &&
           (match<0 || p->esp<best)){match=i;best=p->esp;}
    }
    if(match>=0) {
        MusicPending*p=&music_pending[match];
        CONTEXT observed=*ctx;
        if(!strncmp(p->label,"AActor.event",12))observed.Ecx=p->ecx;
        snprintf(label,sizeof label,"%s.exit",p->label);music_write(label,++ev_seq,thread,&observed,p->stack);
        music_discover(p->label,p->stack,ctx->Eax,1);
        size_t label_len=strlen(p->label);
        if(!ctx->Eax && label_len>=6 && !strcmp(p->label+label_len-6,".slot2")) {
            for(int i=0;i<music_nobjects;i++)if(music_objects[i].self==p->stack[1])music_objects[i].self=0;
        }
        p->used=0;
    }
    rd(ctx->Esp,stack,sizeof stack);
    for(int i=0;i<music_nobjects;i++)if(stack[1] && music_objects[i].self==stack[1]) {
        MusicObject*o=&music_objects[i];DWORD methods[64];
        if(!rd(o->vt,methods,o->slots*4))break;
        for(unsigned k=0;k<o->slots;k++)if(methods[k]==ctx->Eip) {
            snprintf(label,sizeof label,"%s.%s.slot%u",!strncmp(o->name,"DI",2)?"DirectInput":"DirectMusic",o->name,k);
            music_write(label,++ev_seq,thread,ctx,NULL);music_save(label,thread,ctx,1);break;
        }
        break;
    }
}
