@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 函数白板 · Function Board
cd /d "%~dp0"

rem ---------------------------------------------------------------- 找 Python
rem 1) 官方启动器 py -3   2) PATH 里的 python   3) 常见安装位置
set "PY="
for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
for %%V in (313 312 311 310) do if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if not defined PY if exist "%%D\python.exe" set "PY=%%D\python.exe"
if not defined PY for /d %%D in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do if not defined PY if exist "%%D\python.exe" set "PY=%%D\python.exe"
if not defined PY for /d %%D in ("C:/Python3*") do if not defined PY if exist "%%D\python.exe" set "PY=%%D\python.exe"
if not defined PY for /d %%D in ("%ProgramFiles%\Python3*") do if not defined PY if exist "%%D\python.exe" set "PY=%%D\python.exe"

if not defined PY (
  echo.
  echo   [!] 找不到 Python 3。
  echo.
  echo       这个白板需要一个本地 Python 来读写画布、驱动 GHCi。
  echo       装一个： https://www.python.org/downloads/  安装时勾选 "Add python.exe to PATH"。
  echo       已经装了但没进 PATH：把下面这行的路径填成本机的 python.exe，并删掉开头的 rem。
  echo.
  echo         rem set "PY=C:/Users/你的名字/AppData/Local/Programs/Python/Python313/python.exe"
  echo.
  pause
  exit /b 1
)

rem ---------------------------------------------------------------- 找 GHC
set "GHC="
for /f "delims=" %%P in ('where ghc 2^>nul') do if not defined GHC set "GHC=%%P"
if not defined GHC if exist "C:/ghcup/bin/ghc.exe" set "GHC=C:/ghcup/bin/ghc.exe"
if not defined GHC if exist "%USERPROFILE%\ghcup\bin\ghc.exe" set "GHC=%USERPROFILE%\ghcup\bin\ghc.exe"
if not defined GHC if exist "%LOCALAPPDATA%\Programs\ghcup\bin\ghc.exe" set "GHC=%LOCALAPPDATA%\Programs\ghcup\bin\ghc.exe"
if defined GHC set "BOARD_GHC=%GHC%"

"%PY%" server.py --doctor %*
echo %*|findstr /i /c:"--doctor" >nul
if not errorlevel 1 exit /b 0

echo.
echo   浏览器窗口马上打开；关掉这个黑窗口即停止引擎。
echo.
"%PY%" server.py --app %*
if errorlevel 1 pause
