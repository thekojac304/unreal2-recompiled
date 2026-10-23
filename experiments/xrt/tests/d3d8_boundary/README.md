# Measured D3D8 boundary

`build.cmd` builds one project-owned PE32 fixture, lifts that exact DLL and compares it on the x64
runtime against the same fixture source compiled natively for x64. It requires the official DXVK 3.1.1
archive extracted under `third_party/graphics/dxvk-v3.1.1/`; hashes and PE architectures are checked.
No game code or downloaded binaries belong in Git.

`native_matrix.py` separately records x86/x64 DXVK, system x86/x64 availability, x86 d3d8to9 and
the retained x86 dgVoodoo reference. It needs those existing official artifacts. Each invocation
uses a new directory; output contains all identifier payload bytes, 53 caps words, HRESULTs, paths,
binary hashes and configs. System/wrapper query failures are measured outcomes, not passing probes.

The game sequence is SDK **120**, Count, identifiers for every adapter with flag **2**, then adapter
**0/HAL** caps. Observed texture queries use `(0,1,22,0,3,DXT1/3/5)`. The 1,068-byte identifier payload
excludes four x64 host tail-padding bytes. Native x86/x64 Driver strings differ legitimately; the
translated/native x64 comparison is byte-identical without normalization.

Six positive probes compare 945 values: queries, COM identity/lifetime, observed formats, invalid-adapter
output behavior, adjacent canaries and outstanding-reference cleanup. Two deliberate translated negatives
exercise stale and unsupported interface calls. They must exit 76 with the named diagnostic.

The implementation intentionally stops before unobserved methods, including CreateDevice. See
[GRAPHICS_STARTUP.md](../../GRAPHICS_STARTUP.md) for the actual client milestone, limits and evidence.
