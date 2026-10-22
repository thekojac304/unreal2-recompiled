# Compile VMProbe with the ORIGINAL Unreal II compiler (UCC make) inside the sandbox,
# then run it in the original engine and save the reference output.
# Usage: .\build_probe.ps1 [-Package VMProbe] [-Deps Core]
param([string]$Package = "VMProbe", [string[]]$Deps = @("Core"))
$ErrorActionPreference = "Stop"
$ws = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$sb = Join-Path $ws "sandbox"
$sys = Join-Path $sb "System"

# 1. stage sources where UCC expects them: <root>\<Package>\Classes\*.uc
$srcDir = Join-Path $PSScriptRoot "$Package\Classes"
$dstDir = Join-Path $sb "$Package\Classes"
New-Item -ItemType Directory -Force $dstDir | Out-Null
Copy-Item "$srcDir\*.uc" $dstDir -Force

# 2. a make ini derived from the sandbox Unreal2.ini with a minimal EditPackages list
$ini = Get-Content (Join-Path $sys "Unreal2.ini")
$out = New-Object System.Collections.Generic.List[string]
$inEditor = $false
foreach ($line in $ini) {
    if ($line -match '^\[') {
        if ($inEditor) { foreach ($d in $Deps + $Package) { $out.Add("EditPackages=$d") } }
        $inEditor = ($line -eq '[Editor.EditorEngine]')
    }
    if ($inEditor -and $line -match '^EditPackages=') { continue }
    $out.Add($line)
}
Set-Content -Path (Join-Path $sys "$Package.ini") -Value $out

# 3. remove any previous build so make recompiles it
Remove-Item (Join-Path $sys "$Package.u") -ErrorAction SilentlyContinue

# 4. compile and run
& (Join-Path $ws "tools\run_ucc.ps1") make "-ini=$Package.ini"
if (-not (Test-Path (Join-Path $sys "$Package.u"))) { throw "compile failed" }
Copy-Item (Join-Path $sys "$Package.u") (Join-Path $PSScriptRoot "$Package.u") -Force
& (Join-Path $ws "tools\run_ucc.ps1") "$Package.$Package" "-ini=$Package.ini" | Tee-Object -Variable runOut | Out-Null
$runOut | Where-Object { $_ -match '^T\d+=' } | Set-Content (Join-Path $PSScriptRoot "$Package.reference.txt")
$runOut
