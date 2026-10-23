/* One x86 image, executed by Windows and by the actual translated callback bridge. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commctrl.h>
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllexport) int probe_log[512], probe_log_n;
static int failures, calls;
static WNDPROC prior;
static void check(int got, int want) {
    probe_log[probe_log_n++] = got;
    if (got != want) failures++;
}
static LRESULT CALLBACK second(HWND h, UINT m, WPARAM w, LPARAM l) {
    calls++;
    return (LRESULT)(m + w + l + (h == NULL ? 7 : 9));
}
static LRESULT CALLBACK first(HWND h, UINT m, WPARAM w, LPARAM l) {
    calls++;
    return CallWindowProcW(second, h, m, w + 1, l + 2) + 3;
}
static void zero(void *p, unsigned n) {
    unsigned i;
    for (i = 0; i < n; i++) ((volatile BYTE *)p)[i] = 0;
}
__declspec(dllexport) int probe_classes(void) {
    WNDCLASSEXW w, q;
    WNDCLASSEXA a, b;
    HINSTANCE owner = (HINSTANCE)&__ImageBase;
    ATOM atom;
    int wide;
    probe_log_n = failures = calls = 0;
    for (wide = 0; wide < 2; wide++) {
        zero(&q, sizeof q); zero(&b, sizeof b);
        q.cbSize = sizeof q; b.cbSize = sizeof b;
        SetLastError(0x5555);
        check((wide ? GetClassInfoExW(NULL, L"Button", &q) : GetClassInfoExA(NULL, "Button", &b)) != 0, 1);
        check(GetLastError(), 0x5555);
        prior = wide ? q.lpfnWndProc : b.lpfnWndProc;
        check(prior != NULL, 1);
        check(wide ? q.cbSize : b.cbSize, 48);
        check(wide ? q.style : b.style, CS_DBLCLKS | CS_HREDRAW | CS_VREDRAW | CS_PARENTDC);
        check(wide ? q.cbClsExtra : b.cbClsExtra, 0);
        /* cbWndExtra and system pointers vary with host architecture; compare semantic fields separately. */
        check((wide ? q.hInstance : b.hInstance) == NULL, 1);
        check((wide ? q.lpszMenuName : (LPCWSTR)b.lpszMenuName) == NULL, 1);
        check((wide ? q.lpszClassName : (LPCWSTR)b.lpszClassName) != NULL, 1);
        check((int)(wide ? CallWindowProcW(prior, NULL, WM_NULL, 0, 0) : CallWindowProcA(prior, NULL, WM_NULL, 0, 0)), 0);
        SetLastError(0x5555);
        check(wide ? GetClassInfoExW(NULL, L"XrtClassMissing", &q) : GetClassInfoExA(NULL, "XrtClassMissing", &b), 0);
        check(GetLastError(), ERROR_CLASS_DOES_NOT_EXIST);
    }
    for (wide = 0; wide < 2; wide++) {
        zero(&w, sizeof w); zero(&a, sizeof a);
        w.cbSize = sizeof w; a.cbSize = sizeof a;
        w.lpfnWndProc = a.lpfnWndProc = first;
        w.hInstance = a.hInstance = owner;
        w.cbClsExtra = a.cbClsExtra = 12;
        w.cbWndExtra = a.cbWndExtra = 20;
        w.style = a.style = CS_DBLCLKS;
        w.hbrBackground = a.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
        w.hIcon = a.hIcon = wide ? LoadIconW(NULL, MAKEINTRESOURCEW(32512)) : LoadIconA(NULL, IDI_APPLICATION);
        w.hCursor = a.hCursor = wide ? LoadCursorW(NULL, MAKEINTRESOURCEW(32512)) : LoadCursorA(NULL, IDC_ARROW);
        check(w.hIcon != NULL, 1); check(w.hCursor != NULL, 1);
        w.lpszClassName = L"XrtClassOracle"; a.lpszClassName = "XrtClassOracle";
        SetLastError(0x5555);
        atom = wide ? RegisterClassExW(&w) : RegisterClassExA(&a);
        check(atom != 0, 1); check(GetLastError(), 0x5555);
        SetLastError(0x5555);
        check((wide ? RegisterClassExW(&w) : RegisterClassExA(&a)) == 0, 1);
        check(GetLastError(), ERROR_CLASS_ALREADY_EXISTS);
        zero(&q, sizeof q); q.cbSize = sizeof q;
        check(GetClassInfoExW(owner, MAKEINTRESOURCEW(atom), &q) != 0, 1);
        check(q.lpfnWndProc == first, wide);
        check(q.hInstance == owner, 1);
        check(q.cbClsExtra, 12); check(q.cbWndExtra, 20);
        check(q.style, CS_DBLCLKS);
        check(q.hbrBackground == (HBRUSH)(COLOR_WINDOW + 1), 1);
        check(q.hIcon == w.hIcon, 1); check(q.hCursor == w.hCursor, 1);
        check((int)CallWindowProcW(q.lpfnWndProc, NULL, WM_USER + 77, 13, 17), WM_USER + 77 + 13 + 17 + 13);
        check(calls, (wide + 1) * 2);
        /* Local ownership must not collapse different translated module identities. */
        SetLastError(0x5555);
        check(GetClassInfoExW(GetModuleHandleW(L"kernel32.dll"), L"XrtClassOracle", &q), 0);
        check(GetLastError(), ERROR_CLASS_DOES_NOT_EXIST);
        SetLastError(0x5555);
        check(wide ? UnregisterClassW(MAKEINTRESOURCEW(atom), owner) : UnregisterClassA(MAKEINTRESOURCEA(atom), owner), 1);
        check(GetLastError(), 0x5555);
        SetLastError(0x5555);
        check(GetClassInfoExW(owner, L"XrtClassOracle", &q), 0);
        check(GetLastError(), ERROR_CLASS_DOES_NOT_EXIST);
        SetLastError(0x5555);
        check(UnregisterClassW(L"XrtClassOracle", owner), 0);
        check(GetLastError(), ERROR_CLASS_DOES_NOT_EXIST);
    }
    zero(&w,sizeof w); w.cbSize=4; w.lpfnWndProc=first; w.hInstance=owner; w.lpszClassName=L"XrtBadSize";
    SetLastError(0x5555); check(RegisterClassExW(&w),0); check(GetLastError(),ERROR_INVALID_PARAMETER);
    zero(&q,sizeof q); q.cbSize=4;
    check(GetClassInfoExW(NULL,L"BUTTON",&q)!=0,1); check(q.cbSize,4);
    return failures;
}
__declspec(dllexport) int probe_brush(void) {
    HBRUSH brush; HBITMAP bitmap; WORD pixels[8]={0x55,0xaa,0x55,0xaa,0x55,0xaa,0x55,0xaa};
    RECT rect; HWND desktop;
    probe_log_n=failures=0;
    desktop=GetDesktopWindow(); check(desktop!=NULL,1);
    check(GetDesktopWindow()==desktop,1);
    check(GetClientRect(desktop,&rect),1);
    check(rect.right>0 && rect.bottom>0 && rect.left==0 && rect.top==0,1);
    brush=CreateSolidBrush(RGB(12,34,56)); check(brush!=NULL,1);
    check(DeleteObject(brush),1); check(DeleteObject(brush),0);
    check(GetStockObject(DEFAULT_GUI_FONT)!=NULL,1);
    check(GetStockObject(DEFAULT_GUI_FONT)==GetStockObject(DEFAULT_GUI_FONT),1);
    check(DeleteObject(GetStockObject(DEFAULT_GUI_FONT)),1);
    bitmap=CreateBitmap(8,8,1,1,pixels); check(bitmap!=NULL,1);
    brush=CreatePatternBrush(bitmap); check(brush!=NULL,1);
    check(DeleteObject(bitmap),1); /* pattern brush owns a distinct copy */
    check(DeleteObject(brush),1); check(DeleteObject(brush),0);
    return failures;
}
__declspec(dllexport) int probe_mutex(void) {
    HANDLE a,b;WCHAR path[260];char narrow[260];UINT n,i;probe_log_n=failures=0;
    SetLastError(0x5555);a=CreateMutexW(NULL,FALSE,L"Local\\XrtClassBoundaryMutexOracle");
    check(a!=NULL,1);check(GetLastError(),0);
    SetLastError(0x5555);b=CreateMutexA(NULL,FALSE,"Local\\XrtClassBoundaryMutexOracle");
    check(b!=NULL,1);check(GetLastError(),ERROR_ALREADY_EXISTS);
    check(a!=b,1);check(CloseHandle(a),1);check(CloseHandle(b),1);
    check(CloseHandle(b),0);check(GetLastError(),ERROR_INVALID_HANDLE);
    SetLastError(0x5555);n=GetSystemDirectoryW(path,260);check(n>0 && n<260,1);check(GetLastError(),0x5555);
    check(GetSystemDirectoryW(NULL,0),n+1);
    check(GetSystemDirectoryA(narrow,260),n);
    for(i=0;i<n;i++){probe_log[probe_log_n++]=path[i];check(path[i],narrow[i]);}
    check(GetSystemDirectoryW(path,2),n+1);
    SetLastError(0x5555);n=GetWindowsDirectoryW(path,260);check(n>0 && n<260,1);check(GetLastError(),0x5555);
    check(GetWindowsDirectoryW(NULL,0),n+1);check(GetWindowsDirectoryA(narrow,260),n);
    for(i=0;i<n;i++){probe_log[probe_log_n++]=path[i];check(path[i],narrow[i]);}
    check(GetWindowsDirectoryW(path,2),n+1);
    SetLastError(0x5555);n=GetDriveTypeA(NULL);probe_log[probe_log_n++]=n;check(n>=DRIVE_REMOVABLE && n<=DRIVE_RAMDISK,1);probe_log[probe_log_n++]=GetLastError();
    check(GetDriveTypeW(NULL),n);
    SetLastError(0x5555);probe_log[probe_log_n++]=GetDriveTypeA("?:\\");probe_log[probe_log_n++]=GetLastError();
    SetLastError(0x5555);probe_log[probe_log_n++]=GetDriveTypeW(L"?:\\");probe_log[probe_log_n++]=GetLastError();
    return failures;
}
__declspec(dllexport) int probe_atoms(void) {
    ATOM a,b;WCHAR text[128];UINT n,i;probe_log_n=failures=0;
    a=GlobalAddAtomW(L"Xrt_ClassOracle_01a166e7");b=GlobalAddAtomA("xrt_classoracle_01a166e7");
    check(a>=0xc000,1);check(a==b,1);n=GlobalGetAtomNameW(a,text,128);check(n,24);
    for(i=0;i<n;i++)probe_log[probe_log_n++]=text[i];
    check(GlobalDeleteAtom(a),0);check(GlobalGetAtomNameW(b,text,128),n);
    check(GlobalDeleteAtom(b),0);check(GlobalGetAtomNameW(b,text,128),0);check(GetLastError(),ERROR_INVALID_HANDLE);
    check(GlobalAddAtomW(MAKEINTATOM(123)),123);check(GlobalDeleteAtom(123),0);
    return failures;
}
__declspec(dllexport) int probe_controls(void) {
    const WCHAR* names[]={L"LISTBOX",L"BUTTON",L"SysTabControl32",L"STATIC",L"SysListView32",L"EDIT",L"RICHEDIT",L"COMBOBOX",L"tooltips_class32",L"SCROLLBAR",L"SysTreeView32",L"msctls_trackbar32",L"msctls_progress32"};
    unsigned i; WNDCLASSEXW w,q; HMODULE rich; int expected;
    probe_log_n=failures=0;
    InitCommonControls(); rich=LoadLibraryW(L"RICHED32.dll"); check(rich!=NULL,1);
    for(i=0;i<sizeof names/sizeof names[0];i++) {
        zero(&w,sizeof w); w.cbSize=sizeof w;
        check(GetClassInfoExW(NULL,names[i],&w)!=0,1);
        probe_log[probe_log_n++]=w.style;
        probe_log[probe_log_n++]=w.cbClsExtra;
        probe_log[probe_log_n++]=w.cbWndExtra;
        check(w.hInstance==NULL,1); check(w.lpfnWndProc!=NULL,1);
        check(w.lpszClassName!=NULL,1); check(w.lpszMenuName==NULL,1);
        check((int)CallWindowProcW(w.lpfnWndProc,NULL,WM_NULL,0,0),0);
        expected=w.cbWndExtra;
        w.lpfnWndProc=first; w.hInstance=(HMODULE)&__ImageBase; w.lpszClassName=L"XrtSuperclassOracle";
        check(RegisterClassExW(&w)!=0,1);
        zero(&q,sizeof q);q.cbSize=sizeof q;
        check(GetClassInfoExW((HMODULE)&__ImageBase,L"XrtSuperclassOracle",&q)!=0,1);
        check(q.cbWndExtra,expected); check(q.lpfnWndProc==first,1);
        check(UnregisterClassW(L"XrtSuperclassOracle",(HMODULE)&__ImageBase),1);
    }
    check(FreeLibrary(rich),1);
    return failures;
}
__declspec(dllexport) int probe_bad_proc(void) {
    return (int)CallWindowProcW((WNDPROC)0x12345678, NULL, WM_NULL, 0, 0);
}
static int window_wide,create_ok,nccreate_ok,window_nested,notify_ok;
static HWND notify_child,created_child;
static LRESULT CALLBACK window_proc(HWND h,UINT msg,WPARAM wp,LPARAM lp) {
    if(msg==WM_PARENTNOTIFY && LOWORD(wp)==WM_CREATE) {notify_child=(HWND)lp;notify_ok=HIWORD(wp)==41 && IsWindow(notify_child);}
    if(msg==WM_NCCREATE || msg==WM_CREATE) {
        CREATESTRUCTW* s=(CREATESTRUCTW*)lp;
        int ok=s->lpCreateParams==(void*)0x12345678 && s->hInstance==(HMODULE)&__ImageBase && s->hwndParent==NULL && s->hMenu==NULL && s->cx==96 && s->cy==80;
        if(msg==WM_NCCREATE) nccreate_ok=ok;
        else {
            create_ok=ok;window_nested=SetWindowPos(h,NULL,7,8,97,81,SWP_NOZORDER|SWP_NOACTIVATE);
            created_child=CreateWindowExW(0,L"BUTTON",L"child",WS_CHILD,0,0,10,10,h,(HMENU)41,(HMODULE)&__ImageBase,NULL);
        }
    }
    return window_wide?DefWindowProcW(h,msg,wp,lp):DefWindowProcA(h,msg,wp,lp);
}
__declspec(dllexport) int probe_window(void) {
    WNDCLASSEXW w; WNDCLASSEXA a; HWND h; ATOM atom; RECT rect;
    probe_log_n=failures=0;
    for(window_wide=0;window_wide<2;window_wide++) {
        create_ok=nccreate_ok=window_nested=notify_ok=0;notify_child=created_child=NULL;
        zero(&w,sizeof w);zero(&a,sizeof a);
        w.cbSize=sizeof w;a.cbSize=sizeof a;w.lpfnWndProc=a.lpfnWndProc=window_proc;
        w.hInstance=a.hInstance=(HMODULE)&__ImageBase;w.lpszClassName=L"XrtWindowOracle";a.lpszClassName="XrtWindowOracle";
        atom=window_wide?RegisterClassExW(&w):RegisterClassExA(&a);check(atom!=0,1);
        h=window_wide?CreateWindowExW(0,w.lpszClassName,L"fixture",WS_OVERLAPPED,0,0,96,80,NULL,NULL,w.hInstance,(void*)0x12345678):CreateWindowExA(0,a.lpszClassName,"fixture",WS_OVERLAPPED,0,0,96,80,NULL,NULL,a.hInstance,(void*)0x12345678);
        check(h!=NULL,1);check(IsWindow(h),1);check(nccreate_ok,1);check(create_ok,1);check(window_nested,1);
          { HDC dc=GetDC(h); check(dc!=NULL,1); check(GetDeviceCaps(dc,BITSPIXEL),32); check(ReleaseDC(h,dc),1); check(ReleaseDC(h,dc),0); }
        check(created_child!=NULL,1);check(notify_ok,1);check(notify_child==created_child,1);
        check((int)SendMessageW(created_child,WM_SETFONT,(WPARAM)GetStockObject(DEFAULT_GUI_FONT),FALSE),0);
        check((HFONT)SendMessageW(created_child,WM_GETFONT,0,0)==GetStockObject(DEFAULT_GUI_FONT),1);
        check((int)SendMessageW(created_child,WM_SETTEXT,0,(LPARAM)L"oracle"),1);
        check((int)SendMessageW(created_child,WM_GETTEXTLENGTH,0,0),6);
        check((int)SendMessageA(created_child,WM_SETTEXT,0,(LPARAM)"fixture"),1);
        check((int)SendMessageA(created_child,WM_GETTEXTLENGTH,0,0),7);
        check(ShowWindow(created_child,SW_SHOWNOACTIVATE),0);
        check((GetWindowLongW(created_child,GWL_STYLE)&WS_VISIBLE)!=0,1);
        check(ShowWindow(created_child,SW_HIDE)!=0,1);
        check(SetPropW(h,L"XrtOracle",(HANDLE)0x12345678),1);
        check((int)GetPropA(h,"XrtOracle"),0x12345678);
        check(SetPropA(h,"XrtOracle",(HANDLE)0x87654321),1);
        check((int)GetPropW(h,L"XrtOracle"),0x87654321);
        check((int)RemovePropA(h,"XrtOracle"),0x87654321);
        SetLastError(0x5555);check((int)GetPropW(h,L"XrtOracle"),0);check(GetLastError(),0x5555);
        check(GetWindowRect(h,&rect),1);check(rect.right-rect.left,GetSystemMetrics(SM_CXMIN));check(rect.bottom-rect.top,81);
        check((GetWindowLongW(h,GWL_EXSTYLE)&WS_EX_WINDOWEDGE)!=0,1);
        SetLastError(0x5555);check(UnregisterClassW(MAKEINTRESOURCEW(atom),w.hInstance),0);check(GetLastError(),ERROR_CLASS_HAS_WINDOWS);
        check(DestroyWindow(h),1);check(IsWindow(h),0);check(UnregisterClassW(MAKEINTRESOURCEW(atom),w.hInstance),1);
    }
    return failures;
}
__declspec(dllexport) int probe_pointer_message(void) {
    return (int)CallWindowProcW(first, NULL, WM_COPYDATA, 0, (LPARAM)L"must marshal");
}
__declspec(dllexport) int probe_stale_prior(void) {
    WNDCLASSEXW w;
    InitCommonControls(); LoadLibraryW(L"RICHED32.dll"); zero(&w,sizeof w);w.cbSize=sizeof w;
    GetClassInfoExW(NULL,L"RICHEDIT",&w);
    FreeLibrary(GetModuleHandleW(L"RICHED32.dll"));
    return (int)CallWindowProcW(w.lpfnWndProc,NULL,WM_NULL,0,0);
}
__declspec(dllexport) int probe_reloaded_prior(void) {
    WNDCLASSEXW w; HMODULE rich;
    InitCommonControls();rich=LoadLibraryW(L"RICHED32.dll");zero(&w,sizeof w);w.cbSize=sizeof w;
    GetClassInfoExW(NULL,L"RICHEDIT",&w);
    FreeLibrary(rich);LoadLibraryW(L"RICHED32.dll");
    return (int)CallWindowProcW(w.lpfnWndProc,NULL,WM_NULL,0,0);
}
__declspec(dllexport) int probe_atom_cleanup(void) {
    GlobalAddAtomW(L"Xrt_AbortAtom_01a166e7");
    return (int)CallWindowProcW((WNDPROC)0x12345678,NULL,WM_NULL,0,0);
}
