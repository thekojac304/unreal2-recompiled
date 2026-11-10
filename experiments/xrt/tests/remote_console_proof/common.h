#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <sddl.h>
#include <bcrypt.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>
#include <io.h>
#include "config.h"
typedef struct Identity { wchar_t sid[192]; LUID auth; DWORD session,elevated,restricted; } Identity;
static int identity(HANDLE process, DWORD pid, Identity *v) {
 HANDLE t=NULL; BYTE user[1024]; DWORD n=0; TOKEN_STATISTICS stats; TOKEN_ELEVATION elevation; LPWSTR sid=NULL; int ok=0;
 ZeroMemory(v,sizeof *v);
 if(!OpenProcessToken(process,TOKEN_QUERY,&t))return 0;
 if(!GetTokenInformation(t,TokenUser,user,sizeof user,&n)||!ConvertSidToStringSidW(((TOKEN_USER*)user)->User.Sid,&sid))goto end;
 if(wcsncpy_s(v->sid,192,sid,_TRUNCATE))goto end;
 if(!GetTokenInformation(t,TokenStatistics,&stats,sizeof stats,&n)||!GetTokenInformation(t,TokenElevation,&elevation,sizeof elevation,&n)||!ProcessIdToSessionId(pid,&v->session))goto end;
 v->auth=stats.AuthenticationId;v->elevated=elevation.TokenIsElevated;v->restricted=IsTokenRestricted(t)?1u:0u;ok=1;
end:if(sid)LocalFree(sid);CloseHandle(t);return ok;
}
static int owner(const Identity *v) {
 return !wcscmp(v->sid,OWNER_SID)&&v->auth.LowPart==OWNER_AUTH_LO&&(DWORD)v->auth.HighPart==OWNER_AUTH_HI&&
        v->session==OWNER_SESSION&&v->session==WTSGetActiveConsoleSessionId()&&!v->elevated&&!v->restricted;
}
static void emit_identity(FILE*f,const Identity*v) {
 fprintf(f,"\"sid\":\"%ls\",\"authentication_id\":\"%08lx:%08lx\",\"session\":%lu,\"elevated\":%lu,\"restricted\":%lu",v->sid,(DWORD)v->auth.HighPart,v->auth.LowPart,v->session,v->elevated,v->restricted);
}
static FILE* output(const wchar_t *path) { FILE*f=NULL;if(_wfopen_s(&f,path,L"wx"))return NULL;return f; }
static int object_name(HANDLE h,wchar_t *buf,DWORD bytes) {DWORD n=0;return GetUserObjectInformationW(h,UOI_NAME,buf,bytes,&n)!=0;}
static HANDLE pin(const wchar_t*path,const char*expected) {
 HANDLE f=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 BCRYPT_ALG_HANDLE alg=NULL;BCRYPT_HASH_HANDLE hash=NULL;BYTE block[65536],digest[32];DWORD n=0;char hex[65];int ok=0;unsigned i;
 if(f==INVALID_HANDLE_VALUE)return NULL;
 if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,NULL,0)<0||BCryptCreateHash(alg,&hash,NULL,0,NULL,0,0)<0)goto end;
 for(;;){if(!ReadFile(f,block,sizeof block,&n,NULL))goto end;if(!n)break;if(BCryptHashData(hash,block,n,0)<0)goto end;}
 if(BCryptFinishHash(hash,digest,sizeof digest,0)<0)goto end;
 for(i=0;i<32;i++)sprintf_s(hex+2*i,3,"%02x",digest[i]);ok=!strcmp(hex,expected);
end:if(hash)BCryptDestroyHash(hash);if(alg)BCryptCloseAlgorithmProvider(alg,0);if(!ok){CloseHandle(f);return NULL;}return f;
}
