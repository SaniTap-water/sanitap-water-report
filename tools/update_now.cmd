@echo off
rem What the desktop shortcut "Update water report now" runs.
rem Asks for one on-demand rebuild, starts the scheduled task, waits for it,
rem and leaves the result on screen. The build itself is tools/weekly_build.sh;
rem this only starts it. See CONTRIBUTING.md, "Updating mid-week".
title Update water report now
cd /d "%USERPROFILE%"
set TASK=SaniTapWeeklyPublish
rem The build has its own clone; it resets itself to origin/main every run.
set REPO=/home/bushp/sanitap-water-report-build

schtasks /query /tn %TASK% /fo LIST | findstr /c:"Status:" | findstr /c:"Running" >nul
if not errorlevel 1 (
  echo The report is already being built. Watching the running build instead.
  goto wait
)

rem Tell the build this run was asked for, so it rebuilds even if an edition
rem already went out today. The build deletes the file when it reads it.
wsl.exe -d Ubuntu -- touch %REPO%/logs/update_requested
echo Starting %TASK% ...
schtasks /run /tn %TASK%
if errorlevel 1 (
  echo.
  echo Could not start the task. Nothing was built.
  goto end
)

:wait
echo.
echo Building from live mWater and running every gate. This takes about
echo twenty minutes. You can close this window; the build carries on.
timeout /t 20 /nobreak >nul
:poll
schtasks /query /tn %TASK% /fo LIST | findstr /c:"Status:" | findstr /c:"Running" >nul
if not errorlevel 1 (
  echo   %TIME%  still running ...
  timeout /t 60 /nobreak >nul
  goto poll
)

echo.
echo ===== finished =====
schtasks /query /tn %TASK% /v /fo LIST | findstr /c:"Last Run Time:" /c:"Last Result:"
echo.
echo Last lines of the publisher log:
wsl.exe -d Ubuntu -- tail -n 12 %REPO%/logs/publisher.log
echo.
echo "Last Result: 0" and a PUBLISHED line above mean the new edition is live.
:end
