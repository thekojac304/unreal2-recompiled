# D3D8 scalar initialization — integrity stop

Fully validated new tuples: `(48,0)` and `(35,3)`. Together with the prior
five tuples, these have independent native x86/x64 and translated comparisons,
fresh affected/full acceptance and paired actual native/guest returns in exactly
two bounded genuine client sessions. Actual calls use pinned DXVK; unmeasured
tuples and production GetRenderState remain unsupported in the accepted code.

Provisional `(136,1)` passed fixtures, serial build and all regressions. Its
pre-launch gate failed on the cursor clipping baseline, so no third client ran.
That candidate and its working-tree source remain preserved and uncommitted.
The accepted executable still stops at `(136,1)`, slot 50,
`D3DDrv.dll+0xf28c`.

Accepted executable: `build/d3d8-scalar-init-20261025-02/xrt_ucc.exe`

EXE SHA-256: `d67dab4cf6caf71aa981d3af689c8d93c4a30358ea042ac31dfffa8f16e85e52`

PDB SHA-256: `bf88c95bdb7688b8161ce3f0b3e710ac206cd694a8874f6ff2db10ea03d13b1a`

Provisional executable: `build/d3d8-scalar-init-20261025-03/xrt_ucc.exe`

EXE SHA-256: `254c5a923e7c66e0017018f123c8f96ccdb47f00073cfb7f75151b4e7840ba90`

PDB SHA-256: `467d11094cb0fc01316cb326602ee94b80445cba55b778b24a2aa6feddac1499`

All three revisions passed 33 regression stages and 158 Python tests, zero skips.
Every build was serial with verified inputs and isolated outputs. Each genuine
run passed full post-run integrity and cleanup. Final protected assets, binaries,
DXVK/helper/toolchain and historical preservation checks passed. The later
cursor baseline mismatch remains unresolved; no cursor/display/window state was
changed to force continuation.

Highest world milestone remains T2. No engine/world tick completed; OpenWindow
and Engine Init have no paired return. Both live viewports reported valid,
visible, uncloaked HWNDs and 1540×945 clients, with normal placement and recorded
styles/ownership. Their thread active/focus HWND was the viewport; foreground
HWND was NULL. Read-only desktop BitBlt failed with access denied; no screenshot
or rendered game frame is verified.

Existing CRT 110 mismatches / 1,796 pending cases, six ACP 932 differences, locale/setlocale/_setmbcp gaps, and x87 sticky-status/tag/large-input/80-bit-range/double-rounding limitations remain. The previously measured x86 first-Present x87 PE effect is retained.

Next milestone: Review and re-establish the cursor clipping baseline within the owner-approved scope. Then validate the preserved (136,1) candidate in a separately authorized bounded genuine session before adding another tuple. No hardware or display investigation was performed.

[Full stop report](../../out/recovery/d3d8-scalar-init-20261025-01/REPORT.txt)
and [exact identities and observations](../../out/recovery/d3d8-scalar-init-20261025-01/summary.json).
Earlier checkpoints and all pending work remain preserved.
