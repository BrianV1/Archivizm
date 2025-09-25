@echo off
cd /d "%~dp0"

echo Starting Archivizm...
if not exist "archivizm_env" (
    echo Virtual environment not found. Running setup...
    call setup.bat
)

if exist "archivizm_env\Scripts\activate.bat" (
    call archivizm_env\Scripts\activate.bat
    python Archivizm.py
    pause
) else (
    echo Error: Virtual environment setup failed.
    pause
)