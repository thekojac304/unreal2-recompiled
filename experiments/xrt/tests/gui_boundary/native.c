#define main probe_host_main
#include "../../../../tools/xrt/tests/ehprobe/native_host.c"
#undef main
#include "keyboard_setup.h"
int main(int argc,char**argv) {if(!keyboard_setup())return 3;return probe_host_main(argc,argv);}
