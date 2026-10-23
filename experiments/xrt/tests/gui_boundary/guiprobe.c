/* Same project-owned x86 fixture runs natively and through the actual lifter/runtime. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commctrl.h>
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllexport) int probe_log[128], probe_log_n;
static HWND dialog;
static int init_ok, pos_ok, nested_ok, failures;
static void expect(int actual, int wanted)
{
    probe_log[probe_log_n++] = actual;
    if (actual != wanted)
        failures++;
}
static INT_PTR CALLBACK callback(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    (void)wp;
    if (msg == WM_INITDIALOG)
    {
        dialog = h;
        init_ok = lp == 0x12345678;
        nested_ok = SetWindowPos(h, HWND_TOP, 10, 20, 80, 60, SWP_NOACTIVATE | SWP_NOZORDER);
    }
    if (msg == WM_WINDOWPOSCHANGING)
    {
        WINDOWPOS *p = (WINDOWPOS *)lp;
        if (p->hwnd == h && p->cx == 80 && p->cy == 60)
        {
            pos_ok = 1;
            p->cx = 81;
        }
    }
    return FALSE;
}
__declspec(dllexport) int probe_gui(void)
{
    HDC dc;
    HBITMAP bitmap;
    BITMAPINFO bmi;
    unsigned i;
    BYTE output[16];
    BYTE pixels[16] = {0, 0, 255, 0, 255, 0, 0, 0, 255, 0, 0, 255, 255, 255, 0, 0};
    HWND child;
    RECT rect;
    int wide;
    probe_log_n = failures = 0;
    InitCommonControls();
    for (i = 0; i < sizeof bmi; i++)
        ((volatile BYTE *)&bmi)[i] = 0;
    bmi.bmiHeader.biSize = 40;
    bmi.bmiHeader.biWidth = 2;
    bmi.bmiHeader.biHeight = 2;
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 24;
    dc = GetDC(NULL);
    expect(dc != NULL, 1);
    bitmap = CreateDIBitmap(dc, &bmi.bmiHeader, CBM_INIT, pixels, &bmi, DIB_RGB_COLORS);
    expect(bitmap != NULL, 1);
    expect(GetDIBits(dc, bitmap, 0, 2, output, &bmi, DIB_RGB_COLORS), 2);
    for (i = 0; i < 16; i++)
        if (i % 8 < 6)
            expect(output[i], pixels[i]); /* padding is unspecified */
    expect(ReleaseDC(NULL, dc), 1);
    expect(ReleaseDC(NULL, dc), 0);
    for (wide = 0; wide < 2; wide++)
    {
        init_ok = pos_ok = nested_ok = 0;
        dialog =
            wide ? CreateDialogParamW((HMODULE)&__ImageBase, MAKEINTRESOURCEW(119), NULL, callback, 0x12345678)
                 : CreateDialogParamA((HMODULE)&__ImageBase, MAKEINTRESOURCEA(119), NULL, callback, 0x12345678);
        expect(dialog != NULL, 1);
        expect(init_ok, 1);
        expect(nested_ok, 1);
        expect(pos_ok, 1);
        child = GetDlgItem(dialog, 1024);
        expect(child != NULL, 1);
        expect(GetDlgItem(dialog, 9999) == NULL, 1);
        expect(GetSystemMetrics(SM_CXSCREEN) > 0, 1);
        expect(SetWindowPos(dialog, HWND_TOP, 10, 20, 80, 60, SWP_NOACTIVATE | SWP_NOZORDER), 1);
        expect(pos_ok, 1);
        expect(GetWindowRect(dialog, &rect), 1);
        expect(rect.right - rect.left, 81); /* guest callback mutated the host WINDOWPOS */
        expect((int)(wide ? SendMessageW(child, STM_SETIMAGE, IMAGE_BITMAP, (LPARAM)bitmap)
                          : SendMessageA(child, STM_SETIMAGE, IMAGE_BITMAP, (LPARAM)bitmap)),
               0);
        expect(UpdateWindow(dialog), 1);
        expect(DestroyWindow(dialog), 1);
        expect(DestroyWindow(dialog), 0);
        SetLastError(0x5555);
        expect((wide
                    ? CreateDialogParamW((HMODULE)&__ImageBase, MAKEINTRESOURCEW(999), NULL, callback, 0)
                    : CreateDialogParamA((HMODULE)&__ImageBase, MAKEINTRESOURCEA(999), NULL, callback, 0)) == NULL,
               1);
        expect((int)GetLastError(), 1814);
    }
    expect(DeleteObject(bitmap), 1);
    expect(DeleteObject(bitmap), 0);
    return failures;
}
