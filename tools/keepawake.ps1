# Hold the laptop awake while a build runs (21 Oct 2026).
#
# On 20 Oct 2026 a pre-flight run took 12 hours: Windows Modern Standby
# suspended WSL 6 seconds after a step finished (15:12 UTC), hibernated at
# 21:05, and the run only went on when the lid was opened at 04:01. Nothing in
# the build hung. tools/weekly_build.sh starts this for the length of a run.
#
# ES_CONTINUOUS | ES_SYSTEM_REQUIRED: no idle sleep while this process lives
# (the display may still turn off; closing the lid still sleeps). The request
# is held while the hold file exists, at most -Minutes, then released.
#
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File keepawake.ps1 -HoldFile <path> -Minutes 125
param([Parameter(Mandatory = $true)][string]$HoldFile, [int]$Minutes = 125)
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]"0x80000001") | Out-Null
$end = (Get-Date).AddMinutes($Minutes)
while ((Test-Path -LiteralPath $HoldFile) -and ((Get-Date) -lt $end)) { Start-Sleep -Seconds 15 }
[W.P]::SetThreadExecutionState([uint32]"0x80000000") | Out-Null
