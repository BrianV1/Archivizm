@echo off
echo Creating virtual environment...
python -m venv archivizm_env

echo Activating virtual environment...
call archivizm_env\Scripts\activate.bat

echo Installing Python packages from requirements.txt...
pip install -r requirements.txt

echo Downloading spaCy English model...
python -m spacy download en_core_web_sm

echo Checking Siegfried installation...
if not exist "Siegfried" (
    echo Warning: Siegfried directory not found. Please ensure sf.exe and default.sig are in the Siegfried folder.
) else (
    if exist "Siegfried\sf.exe" (
        echo Siegfried found: Siegfried\sf.exe
    ) else (
        echo Warning: sf.exe not found in Siegfried folder.
    )
    if exist "Siegfried\default.sig" (
        echo Siegfried signature file found: Siegfried\default.sig
    ) else (
        echo Warning: default.sig not found in Siegfried folder.
    )
)

echo.
echo Installation complete!
echo To activate the environment, run: archivizm_env\Scripts\activate
pause