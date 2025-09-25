#!/bin/bash
cd "$(dirname "$0")"

echo "Starting Archivizm..."
if [ ! -d "archivizm_env" ]; then
    echo "Virtual environment not found. Running setup..."
    chmod +x setup.sh
    ./setup.sh
fi

if [ -f "archivizm_env/bin/activate" ]; then
    source archivizm_env/bin/activate
    python Archivizm.py
else
    echo "Error: Virtual environment setup failed."
    read -p "Press enter to continue..."
fi