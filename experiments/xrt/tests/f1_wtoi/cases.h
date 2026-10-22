/* cases.h - _wtoi inputs for the F1 check (19-character cap in hle_wtoi). Shared by ref_wtoi.c and cand_wtoi.c. */
static const wchar_t* const cases[] = {
    L"0000000000000000007",            /* 19 chars: 18 zeros + '7' (control, inside the cap) */
    L"00000000000000000007",           /* 20 chars: 19 zeros + '7' (the claimed failure scenario) */
    L"000000000000000000000000000042", /* 30 chars */
    L"-00000000000000000007",          /* sign + 19 zeros + '7' */
    L"                  5",            /* 18 spaces + '5' (control) */
    L"                   5",           /* 19 spaces + '5' */
    L"\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t123",  /* 20 tabs + "123" */
    L"1234567890123456789",            /* 19 digits (control) */
    L"12345678901234567890",           /* 20 digits: the 20th digit changes the mod-2^32 result */
    L"99999999999999999999999",        /* 23 digits */
    L"-12345678901234567890",          /* sign + 20 digits */
    L"1234567890123456789X",           /* 19 digits then a non-digit (control) */
    L"42",                             /* short control */
    L"-2147483648",                    /* short control */
    /* outside F1 (no 19-character issue): Unicode whitespace and digits, which msvcr70 classifies with
     * iswctype(_SPACE) and _wchartodigit rather than the ANSI/C-locale rules */
    L"\x00A0" L"5",                    /* NO-BREAK SPACE + '5' */
    L"\x3000" L"5",                    /* IDEOGRAPHIC SPACE + '5' */
    L"\x0663",                         /* ARABIC-INDIC DIGIT THREE */
    L"\x0967\x0968",                   /* DEVANAGARI ONE TWO */
    L"\xFF11\xFF12",                   /* FULLWIDTH ONE TWO */
    L"\x00B2",                         /* SUPERSCRIPT TWO */
    L"4\x0E55",                        /* '4' + THAI DIGIT FIVE */
};
#define NCASES ((int)(sizeof cases / sizeof cases[0]))
