$ErrorActionPreference = 'Stop'
$root = 'C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent'
$run = Join-Path $root 'runs_ext_p13_phase0b'
$active = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $run 'manual_resume_active_receipt.json') | ConvertFrom-Json
$receiptDir = Join-Path $root $active.receipt_dir
$authorization = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $receiptDir 'authorization_before_archive.json') | ConvertFrom-Json
if ($authorization.authorization_quote -ne '允许归档并解除本次游戏触发的STOP，继续完成同一轮测评。') { throw 'Manual authorization mismatch' }
$stop = Join-Path $run 'logs\STOP'
if (Test-Path -LiteralPath $stop) { throw 'New STOP present; do not rotate or resume anything' }
$stopArchive = Join-Path $root $active.archive_path
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $stopArchive).Hash.ToLower() -ne $authorization.original_STOP_sha256) { throw 'Original STOP archive changed' }
$source = Join-Path $run 'logs\guard.jsonl'
$lines = [System.IO.File]::ReadAllLines($source)
$bad = @($lines | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object { -not $_.safe })
if ($bad.Count -ne 1 -or $bad[0].time -ne '2026-11-18 22:58:34 +0800' -or $bad[0].all_apex_process_count -ne 1) { throw 'Unrecognized unsafe history; do not rotate' }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$destination = Join-Path $run ('logs\guard.before_manual_resume_' + $stamp + '.jsonl')
if (Test-Path -LiteralPath $destination) { throw 'Archive already exists; no overwrite' }
$before = Join-Path $receiptDir 'guard_session_rotation_before.json'
if (Test-Path -LiteralPath $before) { throw 'Rotation already attempted; no retry' }
$note = [ordered]@{time_Beijing=(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'); operation='Full journal volume rotation, not row filtering; historical Apex stop retained'; reason='Frozen analyzer checks current guard-session safety. Previous authorized interruption is preserved as a complete separately hashed volume, with explicit full-history post-resume audit.'; original_guard_path='runs_ext_p13_phase0b/logs/guard.jsonl'; historical_unsafe_records=1; known_stop_time='2026-11-18 22:58:34 +0800'; archive_path=$destination; authorization_receipt=(Join-Path $receiptDir 'authorization_before_archive.json'); experimental_protocol_data_gates_unchanged=$true; future_stop_authorization=$false}
[System.IO.File]::WriteAllText($before, ($note | ConvertTo-Json -Depth 10), [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::Move($source, $destination)
$stream = [System.IO.File]::Open($source, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite)
$stream.Close()
$after = [ordered]@{time_Beijing=(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'); archive_path=$destination; archive_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLower(); original_row_count=$lines.Count; historical_unsafe_record_preserved=$true; fresh_session_path=$source; no_guard_disabled=$true; no_STOP_cleared_by_this_operation=$true}
$out = Join-Path $receiptDir 'guard_session_rotation_receipt.json'
[System.IO.File]::WriteAllText($out, ($after | ConvertTo-Json -Depth 10), [System.Text.UTF8Encoding]::new($false))
$after | ConvertTo-Json -Depth 10
