# Unexplained Ogg byte difference — read-only findings, 2026-10-23

This is an **unresolved installation integrity finding**, recorded separately from the porting acceptance tests.
Its timing and cause are unestablished. It is not attributed to this project. Neither input was repaired,
overwritten, normalized or deleted.

The installed `singleplayer/Music/M03_fite_loop2.ogg` differs from the preserved checkpoint copy
`sandbox_cmp/level/Music/M03_fite_loop2.ogg` at exactly one byte: offset **489527**, snapshot `0x6e`,
installed `0x2e` (one changed bit). Both are 3,677,906 bytes. The preceding report also retained identical
recorded mtimes. Repeated reads reproduce the same hashes:

| Input | SHA-256 |
|---|---|
| Preserved snapshot | `b6261e7e09ca82b48361702d09ea6d24c7d24a85b4073dd1ff1920f1317318bb` |
| Installed file | `6518e44f945853bf935bd674dbc84b9d9a8310beea1bb7262cf240dfd10fa2bf` |

The differing byte lies in the **compressed body of Ogg page sequence 116**, at page range
`[488957,493160)`, granule 727488. It is not an unused header/padding byte. Using the
[Xiph Ogg framing checksum definition](https://xiph.org/ogg/doc/framing.html), all snapshot pages pass CRC;
exactly one installed page fails. Its stored CRC is `6b159d5a`; snapshot calculation matches that value,
while the installed bytes calculate to `c5184bda`.

Read-only decoding with the same local FFmpeg build produces:

| Input | Decoder diagnostics | Decoded s16le bytes | PCM SHA-256 |
|---|---|---:|---|
| Snapshot | None | 21,403,200 | `bf11c32443208022d30f32d94dff650231f863312e3bceb5f3fc05da7fa6e16e` |
| Installed | CRC mismatch; Vorbis overread of 5 bits | 21,378,624 | `cc60533c15cef5465c5d69fbd694a9603db29f9dc8e54996b42e8972126a07fa` |

Both FFmpeg processes return 0; that exit code does not make the damaged page valid. The installed decode
is 24,576 bytes shorter and has different PCM content. No listening test or claim about the audible severity
was made. No CRC-rewritten variant or repaired audio file was created.

The preserved copy is a local checkpoint, not a newly authenticated distributor source. It establishes the
measured validity/decode difference, without establishing when or why the installed bit changed.

Evidence: `results/compare/ogg_integrity.json`, with full per-page records, exact decoder identity/commands and
diagnostics in `results/raw/ogg-integrity-reproduced/`. The original exploratory check is also preserved at
`results/raw/ogg-integrity/`. Before/after input hashes agree in each check. A fresh 4,757-file installation
census matches `level-init-install-after.json` with zero additional differences; Save entry names/sizes/mtimes
also match. This preserves the existing unexplained difference rather than reporting a clean-install PASS.

Reproduce into a **new** evidence directory (the script refuses an existing output directory):

```powershell
.venv/Scripts/python -I tools/xrt/ogg_integrity.py --snapshot sandbox_cmp/level/Music/M03_fite_loop2.ogg --installed 'E:\Launchbox\Games\PC Games\Unreal 2 - The Awakening\singleplayer\Music\M03_fite_loop2.ogg' --decoder 'C:\Program Files\Shutter Encoder\Library\ffmpeg.exe' --out experiments/xrt/results/raw/ogg-integrity-new
```
