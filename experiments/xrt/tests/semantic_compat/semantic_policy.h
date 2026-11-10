/* D3D8 scalar domains, independent of historical fixture tuples.
 * Return codes classify validation; they are NEVER API results.
 * DWORD payloads are forwarded unchanged, including noncanonical BOOLs.
 * Capability words use the statically checked, 212-byte D3DCAPS8 layout.
 */
#ifndef XRT_SEMANTIC_POLICY_H
#define XRT_SEMANTIC_POLICY_H
enum { D8_VALID, D8_INVALID, D8_UNIMPLEMENTED, D8_CAPABILITY };
static int d8_finite(unsigned v) { return (v & 0x7f800000u) != 0x7f800000u; }
static int d8_float_nonnegative(unsigned v) { return d8_finite(v) && (!(v>>31) || !(v&0x7fffffffu)); }
static int d8_enum(unsigned v,unsigned lo,unsigned hi) { return v>=lo && v<=hi; }
static int d8_cap_enum(unsigned v,unsigned lo,unsigned hi,unsigned caps) {
    if(!d8_enum(v,lo,hi))return D8_INVALID;
    return (caps & (1u<<(v-1))) ? D8_VALID : D8_CAPABILITY;
}
__declspec(noinline) static int d8_render_domain(unsigned s,unsigned v,const DWORD *caps) {
    if(s>=128 && s<=135)return v&~15u ? D8_INVALID : D8_VALID;
    switch(s) {
    /* Win32 BOOL: zero/nonzero; do not rewrite the original DWORD. */
    case 14:case 15:case 16:case 27:case 28:case 29:
    case 136:case 137:case 141:case 142:case 143:case 153:
    case 156:case 157:case 161: return D8_VALID;
    case 26:return !v || (caps[9]&1u)?D8_VALID:D8_CAPABILITY;
    case 48: return !v || (caps[9]&0x10000u) ? D8_VALID:D8_CAPABILITY;
    case 52: return !v || caps[34] ? D8_VALID:D8_CAPABILITY;
    case 7: return v<=2 ? (v!=2 || (caps[9]&0x40000u) ? D8_VALID:D8_CAPABILITY) : D8_INVALID;
    case 8:return d8_enum(v,1,3)?D8_VALID:D8_INVALID;
    case 9:return v==3?D8_UNIMPLEMENTED:d8_enum(v,1,2)?D8_VALID:D8_INVALID;
    case 22:return !d8_enum(v,1,3)?D8_INVALID:(caps[8]&(1u<<(v+3)))?D8_VALID:D8_CAPABILITY;
    case 19:return d8_cap_enum(v,1,13,caps[11]);
    case 20:return d8_cap_enum(v,1,11,caps[12]);
    case 23:return d8_cap_enum(v,1,8,caps[10]);
    case 25:return d8_cap_enum(v,1,8,caps[13]);
    case 56:return d8_enum(v,1,8)?D8_VALID:D8_INVALID;
    case 24:return v<=255?D8_VALID:D8_INVALID;
    case 34:case 57:case 58:case 59:case 60:case 139:case 162:return D8_VALID;
    case 35:return v<=3 ? (!v || (caps[9]&0x100u) ? D8_VALID:D8_CAPABILITY):D8_INVALID;
    case 140:return v<=3 ? (!v || (caps[9]&0x80u) ? D8_VALID:D8_CAPABILITY):D8_INVALID;
    case 36:case 37:case 38:case 158:case 159:case 160:case 170:
        return d8_finite(v)?D8_VALID:D8_INVALID;
    case 47:return v<=16?D8_VALID:D8_INVALID;
    case 53:case 54:case 55:return d8_cap_enum(v,1,8,caps[34]);
    case 145:case 146:case 147:case 148:return v<=2?D8_VALID:D8_INVALID;
    case 152:return (v & ~(caps[41]>=32?~0u:((1u<<caps[41])-1)))?D8_CAPABILITY:D8_VALID;
    case 154:case 155:case 166:return d8_float_nonnegative(v)?D8_VALID:D8_INVALID;
    case 168:return v&~15u?D8_INVALID:D8_VALID;
    case 171:return d8_enum(v,1,5)?(v==1 || (caps[8]&0x800u)?D8_VALID:D8_CAPABILITY):D8_INVALID;
    /* Known but not characterized features, including backend no-op cases. */
    case 10:case 30:case 40:case 151:case 163:case 164:case 165:
    case 167:case 172:case 173:return D8_UNIMPLEMENTED;
    default:return D8_INVALID;
    }
}
__declspec(noinline) static int d8_stage_domain(unsigned stage,unsigned s,unsigned v,const DWORD*caps) {
    unsigned mask;
    if(stage>=8)return D8_INVALID;
    switch(s) {
    case 1:case 4:return v==1?D8_VALID:d8_cap_enum(v,1,26,caps[36]);
    case 2:case 3:case 5:case 6:case 26:case 27:
        if((v&~0x3fu) || (v&15u)>5)return D8_INVALID;
        return (v&15u)!=5 || (caps[8]&0x400u)?D8_VALID:D8_CAPABILITY;
    case 7:case 8:case 9:case 10:case 19:case 22:case 23:return d8_finite(v)?D8_VALID:D8_INVALID;
    case 11:return (v&0xffffu)<8 && (v>>16)<=3?D8_VALID:D8_INVALID;
    case 13:case 14:case 25:
        if(!d8_enum(v,1,5))return D8_INVALID;
        return caps[19]&(v==5?0x20u:1u<<(v-1))?D8_VALID:D8_CAPABILITY;
    case 15:case 20:return D8_VALID;
    case 16:case 17:
        if(!d8_enum(v,1,3))return D8_INVALID;
        mask=1u<<((s==16?24:8)+v-1);
        return caps[16]&mask?D8_VALID:D8_CAPABILITY;
    case 18:
        if(v>2)return D8_INVALID;
        return !v || (caps[16]&(1u<<(15+v)))?D8_VALID:D8_CAPABILITY;
    case 21:return v>=1 && v<=caps[27]?D8_VALID:D8_CAPABILITY;
    case 24:return !(v&~0x107u) && (v&7)<=4 && (!(v&0x100u)||(v&7))?D8_VALID:D8_INVALID;
    case 28:return v==1?D8_VALID:v==5?(caps[8]&0x400u?D8_VALID:D8_CAPABILITY):D8_INVALID;
    default:return D8_INVALID;
    }
}
static int d8_transform_domain(unsigned s) {
    return s==2 || s==3 || (s>=16&&s<=23) || (s>=256&&s<=511);
}
static int d8_fvf_domain(unsigned v) {
    unsigned p=v&14u,n=(v>>8)&15u,i,used=0xffffu;
    /* Bit zero marks D3D8 programmable handles, whose ownership is unimplemented. */
    if(v&1u)return D8_UNIMPLEMENTED;
    if(!p || n>8 || (v&0x6000u) || ((v&0x9000u)==0x9000u))return D8_INVALID;
    if(p==4 && (v&(0x10u|0x9000u)))return D8_INVALID;
    if((v&0x9000u) && p<6)return D8_INVALID;
    for(i=0;i<n;i++)used|=3u<<(16+2*i);
    return v&~used?D8_INVALID:D8_VALID;
}
#endif
