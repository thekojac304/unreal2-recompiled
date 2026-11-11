# Licensing

## Covered by the MIT License

Everything in this repository that was written for the project, in every branch and commit, is MIT-licensed
([LICENSE](LICENSE)):

- the static translator (`tools/xrt/xlift.py` and related tools), the runtime and the player (`tools/xrt/`,
  `experiments/xrt/runtime/`, `tools/xrt/dev/player-src/`);
- the setup and release tooling (`tools/xrt/setup/`, `tools/xrt/dev/dev.py`, `tools/xrt/dev/port.py`), the `U2Port`
  settings package source
  (`tools/xrt/dev/port/`);
- tests, fixtures, experiments, analysis scripts, measurement results, patches to our own runtime;
- documentation and reports.

## Not covered

| Material | Where | Status |
|---|---|---|
| Screenshots of the game | `docs/images/*.jpg` | Frames rendered by our player from the original game's content. The pictured artwork belongs to the game's rights holders. Included only to illustrate the project |
| Captured output of the original game's own tools | `experiments/xrt/references/*.stdout` | Short console transcripts from the game's `ucc.exe` (including its "Copyright 2001 Epic Games Inc" banner), kept as test oracles |
| Third-party license texts and notices | `tools/xrt/dev/player/DXVK-LICENSE.txt`, `tools/xrt/setup/THIRD-PARTY-NOTICES.txt` | Belong to their projects |
| Facts about the game's program files | Function addresses (for example `f_1090ad20`), file sizes and hashes, structure layouts, in code, tests and reports | No rights are claimed in these facts, and the MIT License grants none in the game |

## Never in this repository

- Unreal II: The Awakening's files, extracted UnrealScript or other game content.
- Program code translated from the game's executables. The tools produce it on the user's own computer from the
  user's own installation, and that output is not covered by this repository's license.

## Third-party software used by the project

| Component | License | Use |
|---|---|---|
| DXVK 3.1.1 | zlib/libpng | Downloaded at build time (SHA-256 pinned); unmodified binaries in the release |
| LLVM 23.1.4 `clang-cl`, `lld-link` | Apache-2.0 with LLVM exceptions | Bundled unmodified in the release to compile the locally prepared code |
| Python, PyInstaller bootloader | PSF; GPL-2.0 with bootloader exception | Runtime of the bundled `u2gen.exe` |
| Capstone | BSD-3-Clause | Disassembler used by the translator |
| pefile | MIT | PE parser used by the translator |
| UELib | MIT | Used during the feasibility study (not shipped) |

The release download carries these components' license texts in `LICENSES\`, `dxvk\LICENSE.txt` and
`toolchain\LICENSE-LLVM.txt`.

*Unreal II: The Awakening* and *Unreal* are trademarks of their owners. This project is not affiliated with or
endorsed by Epic Games or Legend Entertainment.
