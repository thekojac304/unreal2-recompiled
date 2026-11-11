Minimal C headers for compiling the translated game code (XRT_GAME_DLL) with the bundled clang-cl and no Windows SDK
or Visual Studio. They declare only what xrt.h and the generated units use, with the same types and calling
conventions as Microsoft's C runtime; the functions themselves are imported from the player executable, which links
the real C runtime. clang's own resource headers (stdint.h, stddef.h, intrin.h, emmintrin.h) are used as they are.
Written for this project (no Microsoft header text).
