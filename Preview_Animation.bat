@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYW="
for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do (
    if not defined PYW set "PYW=%%i"
)
if not defined PYW (
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%d\pythonw.exe" set "PYW=%%d\pythonw.exe"
    )
)
if not defined PYW set "PYW=pythonw.exe"

start "" "%PYW%" "%~dp0launcher.py" --preview
