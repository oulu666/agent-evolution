param([switch]$Worker, [switch]$Smoke)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$outputRoot = Join-Path $projectRoot 'runs_overnight_diagnosis_20261110'
if ($Smoke) { $outputRoot += '_smoke_v2' }
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

if (-not $Worker) {
    $workerCommand = "& '" + $PSCommandPath.Replace("'", "''") + "' -Worker"
    if ($Smoke) { $workerCommand += ' -Smoke' }
    $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($workerCommand))
    $process = Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -PassThru -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encodedCommand
    )
    Write-Output "Background launcher started (PID $($process.Id))."
    Write-Output "Progress: $outputRoot\status.json"
    Write-Output "Results:  $outputRoot\report.md"
    Write-Output 'The worker keeps Windows awake while running and releases this request when it exits.'
    Write-Output 'Keep the computer powered on. The queue resumes completed units if launched again.'
    exit 0
}

$mutex = New-Object System.Threading.Mutex($false, 'Local\TinyAgentOvernightDiagnosis20261110')
try {
    $acquired = $mutex.WaitOne(0)
} catch [System.Threading.AbandonedMutexException] {
    $acquired = $true
}
if (-not $acquired) {
    $mutex.Dispose()
    exit 0
}
$launcherStatusPath = Join-Path $outputRoot 'launcher_status.json'
$logPath = Join-Path $outputRoot ('run_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')
$awakeSet = $false
try {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class TinyAgentAwake {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint state);
}
'@
    $awakeResult = [TinyAgentAwake]::SetThreadExecutionState([uint32]2147483649)
    if ($awakeResult -eq 0) { throw 'Could not request Windows to remain awake.' }
    $awakeSet = $true
    $wslRoot = (& wsl.exe -d Ubuntu -- wslpath -u $projectRoot).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $wslRoot) { throw 'Could not locate the project inside Ubuntu.' }
    $wslOutput = "$wslRoot/" + (Split-Path -Leaf $outputRoot)
    $pythonArgs = @('--output-root', $wslOutput,
                    '--profile', 'full', '--pairs', '96')
    if ($Smoke) { $pythonArgs += '--smoke' }
    $wslLog = "$wslOutput/" + (Split-Path -Leaf $logPath)
    @{ status = 'running'; windows_pid = $PID; log = $logPath; started_at = (Get-Date).ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $launcherStatusPath -Encoding UTF8
    # Redirect inside Ubuntu so normal progress stays UTF-8 without PowerShell error formatting.
    & wsl.exe -d Ubuntu --cd $wslRoot -- bash setup/run_overnight_diagnosis.sh $wslLog @pythonArgs
    $workerExitCode = $LASTEXITCODE
    @{ status = $(if ($workerExitCode -eq 0) { 'completed' } else { 'failed' });
       exit_code = $workerExitCode; log = $logPath; finished_at = (Get-Date).ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $launcherStatusPath -Encoding UTF8
} catch {
    @{ status = 'failed'; error = $_.Exception.Message; log = $logPath; finished_at = (Get-Date).ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $launcherStatusPath -Encoding UTF8
    $_ | Out-String | Add-Content -LiteralPath $logPath -Encoding UTF8
    exit 1
} finally {
    if ($awakeSet) { [TinyAgentAwake]::SetThreadExecutionState([uint32]2147483648) | Out-Null }
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
exit $workerExitCode
