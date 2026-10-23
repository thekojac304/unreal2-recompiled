# Unexplained Ogg byte differences — read-only findings, 2026-10-23

## Required stop during the approved IPC phase

Pre-development census `results/raw/dmusic-ipc-install-before.json` exactly matches the preceding
`directmusic-install-final.json`: 4,757 files and Save metadata, with the known two-byte discrepancy.
Later census `dmusic-ipc-install-mid.json` detects another differing read of the same installed file.
All further experiment execution was stopped and the regression sweep interrupted, as the owner required.

Three repeated reads now give installed SHA-256
`7ab03f8502a91390cb54c94ed345b16ce21eae484e0b082394e9b3f6f81cff8d`. New offset **487591** is
snapshot **96**, installed **d6**; the two earlier differences remain. Size 3,677,906 and recorded mtime
1511068956 are unchanged. Page 115 now fails CRC: stored `9c2729c1`, computed `0eca77c8`; page 116
retains the prior `375940cb` versus stored `6b159d5a` failure. No new decode/listening claim is made.

The other **4,756 installed files and Save entry metadata match**. The preserved sandbox Ogg remains
`b6261e7e09ca82b48361702d09ea6d24c7d24a85b4073dd1ff1920f1317318bb`. Current observed bytes are
preserved at `results/raw/dmusic-ipc-ogg-at-stop.ogg`; offsets, repeated hashes and page records are in
`results/raw/dmusic-ipc-ogg-escalation.json`. Neither input was repaired or overwritten.

Timing and cause remain unestablished. Cached read differences alone do not prove a physical disk write
or identify an actor. The helper's own source-installation open was explicitly denied by its file guard;
accepted game asset opens used the isolated sandbox. This does not establish the cause of this separate
finding. See the [stopped phase handoff](DIRECTMUSIC_IPC.md). Further execution needs an owner decision.

The earlier two-byte and one-byte observations follow as history.

## Additional read-only observation during the DirectMusic phase

The current installed hash is now `413bccc0468b2fa9716e927037646e4c7fc29c699395495d95780a0d3bfce2b4`.
Three independent reads reproduce two differences from the preserved snapshot: the previously recorded
offset **489527**, `6e → 2e`, and newly observed offset **489791**, `6a → 2a`. Size and recorded mtime are
unchanged. The timing and cause of the additional difference are unknown; it is not attributed to this
project. All operations in this phase used read-only access to the installed tree, and neither copy was repaired.

Both differences lie in the same page 116. Its computed CRC is now `375940cb`, against the unchanged
stored `6b159d5a`; the preserved snapshot still passes all CRCs. The same read-only FFmpeg comparison
retains the prior differing PCM results below (the damaged page is rejected): installed PCM SHA-256
`cc60533c15cef5465c5d69fbd694a9603db29f9dc8e54996b42e8972126a07fa`, 21,378,624 bytes, versus snapshot
`bf11c32443208022d30f32d94dff650231f863312e3bceb5f3fc05da7fa6e16e`, 21,403,200 bytes. Decoder exit 0
does not validate the input. `sources_unchanged` is true across this probe.

The other **4,756** installed files and Save junction metadata match `floor-install-after.json`. Raw
evidence: `results/raw/directmusic-install-after.json`, `directmusic-ogg-repeat.json` and
`directmusic-ogg-integrity/report.json`. The earlier one-byte finding follows unchanged as history.

## Prior one-byte observation

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
