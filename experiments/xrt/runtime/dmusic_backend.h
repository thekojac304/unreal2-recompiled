/* Backend-neutral measured DirectMusic operations. No guest addresses, native
 * pointers, size_t or compiler-dependent structures cross this boundary.
 * All integers are little endian; text is bounded UTF-16LE. Version 1. */
#ifndef XRT_DMUSIC_BACKEND_H
#define XRT_DMUSIC_BACKEND_H
#include <stdint.h>
#define DMB_MAGIC 0x31424d44u
#define DMB_VERSION 1u
#define DMB_LIMIT 2000u
enum {DMB_REQUEST=1,DMB_REPLY,DMB_CALLBACK,DMB_CALLBACK_REPLY};
enum {DMB_OK=0,DMB_BAD_FRAME=1,DMB_BAD_HANDLE,DMB_UNSUPPORTED,DMB_SANDBOX,DMB_CALLBACK_FAILED};
enum {DMB_HELLO=1,DMB_CREATE,DMB_QI,DMB_ADDREF,DMB_RELEASE,DMB_INIT_AUDIO,
 DMB_SEARCH,DMB_PATH,DMB_GRAPH,DMB_INSERT,DMB_LOAD,DMB_SCRIPT,DMB_SCRIPT_INIT,
 DMB_VOLUME,DMB_ROUTINE,DMB_ENUM,DMB_RELEASE_OBJECT,DMB_STOP,DMB_CLOSE,DMB_SHUTDOWN,
 DMB_TEST_CRASH=100,DMB_TEST_STALL,DMB_TEST_OPEN,DMB_TEST_PROCESS,DMB_TEST_CALLBACK};
enum {DMB_LOADER=1,DMB_PERFORMANCE,DMB_SOUND,DMB_AUDIOPATH,DMB_TOOLGRAPH,DMB_CONTAINER,DMB_SCRIPT_OBJECT};
typedef struct {
 uint32_t magic,version,bytes,sequence,kind,op,object,status;
 uint32_t v[16];
 uint8_t guid[2][16];
 uint16_t text[512];
 uint8_t data[848];
} DmbMessage;
typedef char DmbSizeCheck[sizeof(DmbMessage)==DMB_LIMIT?1:-1];
static void dmb_message(DmbMessage*m,uint32_t op,uint32_t object) {
 memset(m,0,sizeof *m);m->magic=DMB_MAGIC;m->version=DMB_VERSION;
 m->bytes=sizeof *m;m->kind=DMB_REQUEST;m->op=op;m->object=object;
}
#endif
