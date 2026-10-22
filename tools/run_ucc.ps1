# Run the ORIGINAL Unreal II UCC.exe from the sandbox copy (never from the game install).
# Usage: .\run_ucc.ps1 <ucc arguments...>
# Prints stdout and the matching UCC.log; returns UCC's exit code.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$UccArgs)
$sb = Join-Path $PSScriptRoot "..\sandbox\System" | Resolve-Path
$out = Join-Path $sb "..\ucc_last.out"
$err = Join-Path $sb "..\ucc_last.err"
Push-Location $sb
try {
    $p = Start-Process -FilePath (Join-Path $sb "UCC.exe") -ArgumentList ($UccArgs -join ' ') -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $out -RedirectStandardError $err
} finally { Pop-Location }
Get-Content $out
$e = Get-Content $err
if ($e) { "---- stderr"; $e }
"---- exit=$($p.ExitCode)"
exit $p.ExitCode
