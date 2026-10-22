// Tests UELib (third_party/Unreal-Library) against the installed Unreal II packages.
// Usage: dotnet run -- <dir-or-file> [...] [--decompile]
// Reports, per package: detected build, export count, objects that failed to deserialize,
// objects with trailing (unconsumed) bytes, and optionally UnrealScript decompile failures.
using UELib;
using UELib.Core;
using UELib.Services;

sealed class CountingLog : ILogService
{
    public int Asserts, Exceptions;
    public readonly List<string> Samples = new();
    public void Log(string text) { }
    public void Log(string format, params object[] arg) { }
    public void SilentException(Exception e)
    {
        Exceptions++;
        if (Samples.Count < 12) Samples.Add("EXC " + e.Message.Split('\n')[0]);
    }
    public void SilentAssert(bool ok, string message)
    {
        if (ok) return;
        Asserts++;
        if (Samples.Count < 24) Samples.Add("TRAILING " + message);
    }
}

static class Program
{
    static readonly string[] Exts = { ".u", ".un2", ".utx", ".usx", ".uax", ".ugx", ".unr", ".ukx" };

    static int Main(string[] args)
    {
        bool decompile = args.Contains("--decompile");
        bool force = args.Contains("--force");
        var files = new List<string>();
        foreach (var a in args.Where(a => !a.StartsWith("--")))
        {
            if (Directory.Exists(a))
                files.AddRange(Directory.EnumerateFiles(a, "*.*", SearchOption.AllDirectories)
                    .Where(f => Exts.Contains(Path.GetExtension(f).ToLowerInvariant()) && !f.Contains("\\Save\\")));
            else files.Add(a);
        }
        var log = new CountingLog();
        LibServices.LogService = log;
        int totalExports = 0, totalErr = 0, totalTrailing = 0, pkgFail = 0, decompiled = 0, decompileFail = 0;
        var builds = new Dictionary<string, int>();
        foreach (var path in files.OrderBy(f => f))
        {
            int before = log.Asserts;
            try
            {
                var pkg = UnrealLoader.LoadPackage(path);
                pkg.InitializePackage(UnrealPackage.InitFlags.All);
                int exports = 0, errors = 0;
                foreach (var obj in pkg.Objects.ToList())
                {
                    if (obj.ExportTable == null) continue;
                    exports++;
                    // UELib defers many content objects; --force deserializes every export.
                    if (force && obj.DeserializationState == 0)
                    {
                        try { obj.BeginDeserializing(); }
                        catch (Exception) { errors++; continue; }
                    }
                    if (obj.DeserializationState.HasFlag(UObject.ObjectState.Errorlized)) errors++;
                }
                if (decompile)
                {
                    foreach (var cls in pkg.Objects.OfType<UClass>().Where(c => c.ExportTable != null))
                    {
                        try { cls.Decompile(); decompiled++; }
                        catch (Exception) { decompileFail++; }
                    }
                }
                string build = pkg.Build?.Name.ToString() ?? "?";
                builds[$"{build} v{pkg.Version}/{pkg.LicenseeVersion}"] = builds.GetValueOrDefault($"{build} v{pkg.Version}/{pkg.LicenseeVersion}") + 1;
                int trailing = log.Asserts - before;
                totalExports += exports; totalErr += errors; totalTrailing += trailing;
                if (errors > 0 || trailing > 0)
                    Console.WriteLine($"{Path.GetFileName(path),-28} {build,-12} exports={exports,6} deserialize_errors={errors,5} trailing={trailing,5}");
            }
            catch (Exception e)
            {
                pkgFail++;
                Console.WriteLine($"{Path.GetFileName(path),-28} PACKAGE LOAD FAILED: {e.GetType().Name}: {e.Message.Split('\n')[0]}");
            }
        }
        Console.WriteLine($"packages={files.Count} load_failures={pkgFail} exports={totalExports} deserialize_errors={totalErr} trailing_data={totalTrailing}");
        if (decompile) Console.WriteLine($"classes decompiled={decompiled} decompile_exceptions={decompileFail}");
        Console.WriteLine("detected builds: " + string.Join(", ", builds.Select(kv => $"{kv.Key} x{kv.Value}")));
        foreach (var s in log.Samples) Console.WriteLine("  sample: " + s);
        return 0;
    }
}
