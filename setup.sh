#!/bin/bash

# Function to check and install python3-venv on Linux
install_venv_package() {
    if command -v apt-get > /dev/null 2>&1; then
        # Debian/Ubuntu based systems
        echo "Checking for python3-venv package..."
        if ! dpkg -l | grep -q python3-venv; then
            echo "Installing python3-venv package..."
            sudo apt-get update
            sudo apt-get install -y python3-venv
        fi
    elif command -v yum > /dev/null 2>&1; then
        # RedHat/CentOS based systems
        echo "Checking for python3-venv package..."
        if ! rpm -qa | grep -q python3-venv; then
            echo "Installing python3-venv package..."
            sudo yum install -y python3-venv
        fi
    elif command -v dnf > /dev/null 2>&1; then
        # Fedora systems
        echo "Checking for python3-venv package..."
        if ! dnf list installed | grep -q python3-venv; then
            echo "Installing python3-venv package..."
            sudo dnf install -y python3-venv
        fi
    elif command -v pacman > /dev/null 2>&1; then
        # Arch Linux systems
        echo "Checking for python3-venv package..."
        if ! pacman -Q python-venv > /dev/null 2>&1; then
            echo "Installing python-venv package..."
            sudo pacman -S --noconfirm python-venv
        fi
    else
        echo "Note: Cannot automatically install venv on this system."
        echo "If virtual environment creation fails, please install python3-venv manually."
    fi
}

# Function to detect Python command
get_python_command() {
    if command -v python3 > /dev/null 2>&1; then
        echo "python3"
    elif command -v python > /dev/null 2>&1; then
        # Check if python points to python3
        if python --version 2>&1 | grep -q "Python 3"; then
            echo "python"
        else
            echo "UNSUPPORTED"
        fi
    else
        echo "NOT_FOUND"
    fi
}

# Function to detect operating system
get_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macOS" ;;
        Linux*)     echo "Linux" ;;
        CYGWIN*|MINGW*|MSYS*) echo "Windows" ;;
        *)          echo "Unknown" ;;
    esac
}

# Function to download and install Siegfried
install_siegfried() {
    local OS=$1
    echo "Downloading Siegfried for $OS..."
    
    case $OS in
        "Linux")
            wget -O siegfried.tar.gz https://github.com/richardlehane/siegfried/releases/download/v1.10.0/sf-v1.10.0-linux-64bit.tar.gz
            tar -xzf siegfried.tar.gz
            mv sf-1.10.0/sf Siegfried/
            mv sf-1.10.0/default.sig Siegfried/
            rm -rf sf-1.10.0 siegfried.tar.gz
            ;;
        "macOS")
            wget -O siegfried.tar.gz https://github.com/richardlehane/siegfried/releases/download/v1.10.0/sf-v1.10.0-mac-64bit.tar.gz
            tar -xzf siegfried.tar.gz
            mv sf-1.10.0/sf Siegfried/
            mv sf-1.10.0/default.sig Siegfried/
            rm -rf sf-1.10.0 siegfried.tar.gz
            ;;
        "Windows")
            wget -O siegfried.zip https://github.com/richardlehane/siegfried/releases/download/v1.10.0/sf-v1.10.0-windows-64bit.zip
            unzip -q siegfried.zip
            mv sf-1.10.0/sf.exe Siegfried/
            mv sf-1.10.0/default.sig Siegfried/
            rm -rf sf-1.10.0 siegfried.zip
            ;;
        *)
            echo "Unsupported OS for automatic Siegfried installation"
            return 1
            ;;
    esac
}

echo "================================"
echo "    Archivizm Setup Script"
echo "================================"
echo

# Check if Python is available
PYTHON_CMD=$(get_python_command)

if [ "$PYTHON_CMD" = "NOT_FOUND" ]; then
    echo "❌ Error: Python 3 is not installed!"
    echo "Please install Python 3.8 or newer from: https://python.org"
    exit 1
elif [ "$PYTHON_CMD" = "UNSUPPORTED" ]; then
    echo "❌ Error: Python 2 is not supported!"
    echo "Please install Python 3.8 or newer from: https://python.org"
    exit 1
fi

# Check Python version
echo "Using Python: $($PYTHON_CMD --version 2>&1)"

# Check if Python version is sufficient
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info[0])")

if [ $PYTHON_MAJOR -lt 3 ]; then
    echo "❌ Error: Python 3 is required!"
    exit 1
fi

# Install venv package if on Linux
OS=$(get_os)
if [ "$OS" = "Linux" ]; then
    install_venv_package
fi

echo "Creating virtual environment..."
$PYTHON_CMD -m venv archivizm_env

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to create virtual environment!"
    echo "On Ubuntu/Debian, try: sudo apt-get install python3-venv"
    echo "On CentOS/RHEL, try: sudo yum install python3-venv"
    exit 1
fi

echo "Activating virtual environment..."
source archivizm_env/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing Python packages from requirements.txt..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to install requirements!"
        exit 1
    fi
else
    echo "❌ Error: requirements.txt not found!"
    exit 1
fi

echo "Downloading spaCy English model..."
python -m spacy download en_core_web_sm

if [ $? -ne 0 ]; then
    echo "⚠ Warning: Failed to download spaCy model"
    echo "You can try manually: python -m spacy download en_core_web_sm"
fi

echo "Checking Siegfried installation..."
if [ ! -d "Siegfried" ]; then
    echo "Creating Siegfried directory..."
    mkdir -p Siegfried
fi

# Check if sf executable exists (handle different OS naming)
SF_EXECUTABLE="Siegfried/sf"
if [ "$OS" = "Windows" ]; then
    SF_EXECUTABLE="Siegfried/sf.exe"
fi

if [ ! -f "$SF_EXECUTABLE" ] || [ ! -f "Siegfried/default.sig" ]; then
    echo "Siegfried not found or incomplete. Installing..."
    
    if install_siegfried "$OS"; then
        # Make executable if on Unix-like system
        if [ "$OS" != "Windows" ] && [ -f "$SF_EXECUTABLE" ]; then
            chmod +x "$SF_EXECUTABLE"
        fi
        
        if [ -f "$SF_EXECUTABLE" ] && [ -f "Siegfried/default.sig" ]; then
            echo "✅ Siegfried installed successfully!"
        else
            echo "⚠ Warning: Siegfried installation may have failed"
        fi
    else
        echo "⚠ Warning: Could not install Siegfried automatically"
        echo "Please download manually from: https://github.com/richardlehane/siegfried/releases"
    fi
else
    echo "✅ Siegfried found: $SF_EXECUTABLE"
    echo "✅ Siegfried signature file found: Siegfried/default.sig"
fi

echo "Creating launcher script..."
cat > Archivizm.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d "archivizm_env" ]; then
    echo "Virtual environment not found. Running setup..."
    chmod +x setup.sh
    ./setup.sh
fi

echo "Starting Archivizm..."
source archivizm_env/bin/activate
python Archivizm.py
EOF

chmod +x Archivizm.sh

echo
echo "✅ Setup complete!"
echo
echo "To run Archivizm, use:"
echo "   ./Archivizm.sh"
echo
echo "Or double-click the Archivizm.sh file (if your file manager supports it)"
