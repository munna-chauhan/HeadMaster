@echo off
REM HeadMaster portable shim for Windows. Delegates to pyrun.js via Node.
node "%~dp0..\.claude\hooks\pyrun.js" %*
