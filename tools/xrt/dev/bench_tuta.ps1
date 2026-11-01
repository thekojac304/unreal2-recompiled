# TutA gameplay benchmark launch (one genuine developer run; owner-authorized batches only).
# Normal New Game path, then after the opening cutscene (control by ~216 s after Init):
#   window A 220000..230000 ms  standing at the spawn view
#   window B 230000..245500 ms  fixed walk / turn / walk / strafe / turn sequence
# Analyse: .venv/Scripts/python.exe -B -I tools/xrt/dev/perf_report.py RUN --window 220000:230000 --window 230000:245500
# -TimingProbe appends a frame-rate correctness probe after window B (same benchmark before it):
#   247.0 s standing jump (Space), shots +0.25/+0.5/+0.75/+1.5 s; 249.0 s running jump (W held 2.5 s, Space at
#   249.5 s), shots 249.8/250.1/251.5 s; 252.5 s walk forward 6 s into the scenery (collision), shot at 258.5 s.
#   Compare the shots of two builds at different frame rates; the run then stops at 260 s instead of 247 s.
# -PauseProbe (not with -TimingProbe): Escape at 247 s opens the in-game menu; CPU snapshots at 248.5/256.5 s bound the
#   paused window, shot at 256.6 s; the run stops at 258 s.
# -FpsCap N: dev.py --fps-cap N (development frame limiter; 0 = uncapped).
# -Monitor: typeperf (RAPL package power, CPU utility, 1 s) and nvidia-smi (GPU utilization/power, 0.5 s) run alongside;
#   their CSVs land in the run directory as power.csv / gpu.csv (local wall-clock time; threads.csv has init_filetime).
param([Parameter(Mandatory)][string]$Question, [Parameter(Mandatory)][string]$Change,
      [string]$Profile = 'development', [int]$SampleHz = 250, [switch]$TimingProbe, [string]$Res = '', [int]$Delay = 0, [switch]$NoCapture, [string]$Staging = 'strict',
      [int]$FpsCap = 0, [switch]$PauseProbe, [switch]$Monitor, [int]$NativeVerify = 0)
if ($TimingProbe -and $PauseProbe) { throw '-TimingProbe and -PauseProbe both use the time after 247 s' }
# Menu cursor: 1.5 px per DirectInput unit ([WinDrv.WindowsClient] MouseSpeed) from the top-left slam. The menus keep
# their pixel size at every resolution (button pitch 46 px at 1540x945 and at 3840x2160) and are centred, so the
# 1540x945 targets NEW GAME 507,233 / NORMAL 520,310 are fixed pixel offsets from the screen centre.
$ng = '507:233'; $nm = '520:310'
if ($Res) {
    $w, $h = $Res.ToLower().Split('x') | ForEach-Object { [double]$_ }
    $ng = '{0}:{1}' -f [math]::Round(($w / 2 - 9.5) / 1.5), [math]::Round(($h / 2 - 122.5) / 1.5)
    $nm = '{0}:{1}' -f [math]::Round(($w / 2 + 10) / 1.5), [math]::Round(($h / 2 - 7.5) / 1.5)
}
$menu = "10000:key:27;13000:move:-3000:-3000:300;14000:move:${ng}:400;15000:shot;15500:click;" +
        "17500:move:-3000:-3000:300;18500:move:${nm}:400;19500:shot;20000:click;60000:shot;120000:shot;180000:shot;200000:shot"
$bench = '220000:shot;230000:shot;230000:key:87:4000;234500:move:-600:0:1500;236500:key:87:4000;' +
         '241000:key:65:2000;243500:move:600:0:1500;245500:shot'
$seconds = 247
if ($TimingProbe) {
    $bench += ';247000:key:32:100;247250:shot;247500:shot;247750:shot;248500:shot;' +
              '249000:key:87:2500;249500:key:32:100;249800:shot;250100:shot;251500:shot;' +
              '252500:key:87:6000;258500:shot'
    $seconds = 260
}
if ($PauseProbe) {
    $bench += ';247000:key:27;248500:cpu;256500:cpu;256600:shot'
    $seconds = 258
}
# -Delay S shifts the whole script (Escape included) by S seconds: CS_Intro is measured 0..10+S s after Init and
# every later window moves by S (cutscene 150+S.., spawn 220+S.., movement 230+S..245.5+S).
# -NoCapture: no periodic captures (dev.py --capture shots) and no shot inside a timed window (the cutscene shots go,
# 220/230 s become 215 s, 245.5 s becomes 246 s); the menu, 60 s and probe shots stay. Capture-free "cpu" steps
# (threads.csv) bound the timed windows instead: main menu 11-15 s, cutscene 96/150/158/177/210 s, spawn 220-230 s,
# movement 230-245.5 s, and with -Delay >= 50 CS_Intro 30-59.9 s after Init.
if ($NoCapture) {
    $menu = $menu.Replace(';120000:shot;180000:shot;200000:shot', '').Replace('13000:move', '11000:cpu;13000:move').Replace(
        '20000:click;60000:shot', '20000:click;60000:shot;96000:cpu;150000:cpu;158000:cpu;177000:cpu;210000:cpu')
    $bench = $bench.Replace('220000:shot;230000:shot;', '215000:shot;220000:cpu;230000:cpu;').Replace(
        '243500:move:600:0:1500;245500:shot', '243500:move:600:0:1500;245500:cpu;246000:shot')
}
$script = "$menu;$bench"
if ($Delay) {
    $script = ($script -split ';' | ForEach-Object { $t, $r = $_ -split ':', 2; '{0}:{1}' -f ([int]$t + 1000 * $Delay), $r }) -join ';'
    $seconds += $Delay
}
if ($NoCapture -and $Delay -ge 50) { $script = "30000:cpu;59900:cpu;$script" }
$timeout = [math]::Min(360, $seconds + 83)
$extra = @(); if ($Res) { $extra = '--windowed-res', $Res }
if ($NoCapture) { $extra += '--capture', 'shots' }
if ($FpsCap) { $extra += '--fps-cap', $FpsCap }
if ($NativeVerify) { $extra += '--native-verify', $NativeVerify }   # needs a dev.py build --native executable
$extra += '--staging', $Staging   # strict (default) or reuse: see dev.py --staging   # e.g. 3840x2160; empty = the snapshot's 1540x945
$maps = 'CS_Titles.un2','Atlantis.un2','m01a.un2','TutA.un2','TutB.un2','Entry.un2' | ForEach-Object { '--allow-map', $_ }
Set-Location (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$runs = 'out/dev-init/runs'; $before = @(Get-ChildItem $runs -Directory | ForEach-Object Name)
$mon = @()
if ($Monitor) {
    $tmp = New-Item -ItemType Directory -Force "out/dev-init/monitor-$(Get-Date -Format yyyyMMdd-HHmmss)"
    $mon += Start-Process typeperf -PassThru -WindowStyle Hidden -ArgumentList ('"\Energy Meter(RAPL_Package0_PKG)\Power" ' +
        '"\Processor Information(_Total)\% Processor Utility" "\Processor Information(_Total)\% Processor Time" ' +
        "-si 1 -f CSV -y -o `"$tmp\power.csv`"")
    $mon += Start-Process nvidia-smi -PassThru -WindowStyle Hidden -ArgumentList ('--query-gpu=timestamp,utilization.gpu,power.draw,' +
        "clocks.gr,clocks.mem --format=csv -lms 500 -f `"$tmp\gpu.csv`"")
}
try {
    & .venv/Scripts/python.exe -B -I tools/xrt/dev/dev.py run --authorize-init --authorize-first-scene `
        --first-scene 100000 --scene-seconds $seconds --timeout $timeout --campaign-assets --music-script-track @maps `
        --input $script --trace-profile $Profile --sample-hz $SampleHz @extra --question $Question --change $Change
    $code = $LASTEXITCODE
} finally {
    $mon | ForEach-Object { if (-not $_.HasExited) { Stop-Process -Id $_.Id -Force } }
    if ($Monitor) {
        $run = Get-ChildItem $runs -Directory | Where-Object { $before -notcontains $_.Name } | Sort-Object Name | Select-Object -Last 1
        if ($run) { Get-ChildItem $tmp -File | Move-Item -Destination $run.FullName; Remove-Item $tmp }
    }
}
exit $code
