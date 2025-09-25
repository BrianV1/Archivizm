#!/bin/bash
echo "Creating virtual environment..."
python -m venv archivizm_env

echo "Activating virtual environment..."
source archivizm_env/bin/activate

echo "Installing Python packages from requirements.txt..."
pip install -r requirements.txt

echo "Downloading spaCy English model..."
python -m spacy download en_core_web_sm

echo "Checking Siegfried installation..."
if [ -d "Siegfried" ]; then
    if [ -f "Siegfried/sf.exe" ]; then
        echo "Siegfried found: Siegfried/sf.exe"
    else
        echo "Warning: sf.exe not found in Siegfried folder."
    fi
    if [ -f "Siegfried/default.sig" ]; then
        echo "Siegfried signature file found: Siegfried/default.sig"
    else
        echo "Warning: default.sig not found in Siegfried folder."
    fi
else
    echo "Warning: Siegfried directory not found. Please ensure sf.exe and default.sig are in the Siegfried folder."
fi

echo
echo "Installation complete!"
echo "To activate the environment, run: source archivizm_env/bin/activate"