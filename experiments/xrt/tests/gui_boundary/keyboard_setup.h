/* Only this fixture thread's key-state table changes; no input is sent. */
static int keyboard_setup(void) {
    BYTE state[256];unsigned i;
    for(i=0;i<256;i++)state[i]=(BYTE)(((i&2)?0x80:0)|(i&1));
    return SetKeyboardState(state)!=0;
}
