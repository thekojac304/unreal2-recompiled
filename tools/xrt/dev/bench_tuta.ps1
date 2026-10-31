# TutA gameplay benchmark launch (one genuine developer run; owner-authorized batches only).
# Normal New Game path, then after the opening cutscene (control by ~216 s after Init):
#   window A 220000..230000 ms  standing at the spawn view
#   window B 230000..245500 ms  fixed walk / turn / walk / strafe / turn sequence
# Analyse: .venv/Scripts/python.exe -B -I tools/xrt/dev/perf_report.py RUN --window 220000:230000 --window 230000:245500
param([Parameter(Mandatory)][string]$Question, [Parameter(Mandatory)][string]$Change,
      [string]$Profile = 'development', [int]$SampleHz = 250)
$menu = '10000:key:27;13000:move:-3000:-3000:300;14000:move:507:233:400;15000:shot;15500:click;' +
        '17500:move:-3000:-3000:300;18500:move:520:310:400;19500:shot;20000:click;60000:shot;120000:shot;180000:shot;200000:shot'
$bench = '220000:shot;230000:shot;230000:key:87:4000;234500:move:-600:0:1500;236500:key:87:4000;' +
         '241000:key:65:2000;243500:move:600:0:1500;245500:shot'
$maps = 'CS_Titles.un2','Atlantis.un2','m01a.un2','TutA.un2','TutB.un2','Entry.un2' | ForEach-Object { '--allow-map', $_ }
Set-Location (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
& .venv/Scripts/python.exe -B -I tools/xrt/dev/dev.py run --authorize-init --authorize-first-scene `
    --first-scene 100000 --scene-seconds 247 --timeout 330 --campaign-assets --music-script-track @maps `
    --input "$menu;$bench" --trace-profile $Profile --sample-hz $SampleHz --question $Question --change $Change
exit $LASTEXITCODE
