# One owner action, non-game only. Does not alter the genuine supervisor.
$ErrorActionPreference = 'Stop'
$reviewPython = 'E:\Unreal2-Port-Investigation\.venv\Scripts\python.exe'
$reviewScript = 'E:\Unreal2-Port-Investigation\experiments\xrt\tests\final_init_review\review.py'
& $reviewPython -B -I $reviewScript environment
if ($LASTEXITCODE -ne 0) { throw 'Physical owner desktop prerequisite failed; nothing was launched.' }
$fixtureStatus = Get-Content -LiteralPath 'E:\Unreal2-Port-Investigation\out\desktop-fixtures\status.json' -Raw | ConvertFrom-Json
if (Get-Process -Id $fixtureStatus.pid -ErrorAction SilentlyContinue) {
    if ($fixtureStatus.state -ne 'waiting') { throw 'Disposable fixture work is active; leave it intact and review before this action.' }
    & $reviewPython -B -I 'E:\Unreal2-Port-Investigation\tools\xrt\desktop_supervisor.py' stop-fixtures
    if ($LASTEXITCODE -ne 0) { throw 'Disposable fixture service did not accept its stop request.' }
    $reviewDeadline = [DateTime]::UtcNow.AddSeconds(5)
    while ((Get-Process -Id $fixtureStatus.pid -ErrorAction SilentlyContinue) -and [DateTime]::UtcNow -lt $reviewDeadline) {
        Start-Sleep -Milliseconds 100
    }
    if (Get-Process -Id $fixtureStatus.pid -ErrorAction SilentlyContinue) { throw 'Disposable fixture service has not stopped; no qualification launch.' }
}
& $reviewPython -B -I $reviewScript physical
if ($LASTEXITCODE -ne 0) { throw 'Owned graphics qualification failed. Preserve evidence; no automatic retry.' }
