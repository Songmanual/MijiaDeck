@echo off
:: ============================================
:: MiHome-Windows one-click build entry (double-click friendly)
:: All build logic lives in build.ps1 to keep Nuitka
:: arguments in a single place.
:: ============================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
pause
