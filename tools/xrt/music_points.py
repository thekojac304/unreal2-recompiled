"""Measured game-side DirectMusic boundaries (instruction RVAs, not replacements)."""

PAIRS = [
    (0x180c7a, 0x180c7d, "AudioPath.GetObjectInPath"),
    (0x180cb7, 0x180cba, "Graph.InsertTool"),
    (0x180ccb, 0x180cce, "Graph.Release"),
    (0x18177f, 0x181785, "CoInitialize"),
    (0x18182c, 0x18182e, "Loader8"),
    (0x181845, 0x181847, "Performance8"),
    (0x181869, 0x18186f, "Performance.InitAudio"),
    (0x1818d8, 0x1818db, "Loader.SetSearchDirectory"),
    (0x18190e, 0x181914, "Performance.SetGlobalParam"),
    (0x18193e, 0x181944, "Performance.GetGlobalParam"),
    (0x18196a, 0x181970, "Performance.GetDefaultAudioPath"),
    (0x181c0f, 0x181c12, "Loader.LoadObjectFromFile"),
    (0x181c91, 0x181c94, "Loader.GetObject"),
    (0x181caa, 0x181cad, "Script.Init"),
    (0x1819aa, 0x1819ad, "Script.CallRoutine"),
    (0x181d49, 0x181d4c, "Loader.ReleaseObjectByUnknown.container"),
    (0x181d57, 0x181d5a, "Container.Release"),
    (0x181db7, 0x181dba, "Loader.ReleaseObjectByUnknown.script"),
    (0x181dcb, 0x181dce, "Script.Release"),
    (0x1817b5, 0x1817b8, "Performance.Stop"),
    (0x1817be, 0x1817c4, "Performance.CloseDown"),
    (0x1817ce, 0x1817d1, "Performance.Release"),
    (0x1817e2, 0x1817e5, "DirectSound.Release"),
    (0x1817f6, 0x1817f9, "Loader.Release"),
]
POINTS = [("Engine.dll", rva, "DirectMusic." + name + "." + suffix)
          for call, ret, name in PAIRS for rva, suffix in [(call, "call"), (ret, "return")]]
POINTS += [("Engine.dll", rva, "DirectMusic." + name) for rva, name in [
    (0x181440, "DMCallRoutine"), (0x1815d0, "execCallRoutine"),
    (0x181503, "DMCallRoutine.return"), (0x180e20, "shutdown"),
    (0x1819c0, "Tool.QueryInterface.entry"), (0x181a20, "Tool.AddRef.entry"),
    (0x181e00, "Tool.Release.entry"), (0x181aa0, "Tool.ProcessPMsg.entry"),
    (0x181a40, "Tool.Init.entry"), (0x181a50, "Tool.GetMsgDeliveryType.entry"),
    (0x181a60, "Tool.GetMediaTypeArraySize.entry"), (0x181a70, "Tool.GetMediaTypes.entry"),
    (0x181af0, "Tool.Flush.entry")]]
