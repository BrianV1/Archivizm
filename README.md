# Archivizm
## The swiss army knife for Digital Archivists 

The program is split up into 4 tabs.
1. Monitor, lets you see what storage devices are actively connected to you computer with a brief description.
2. File Scan, lets you observe the contents of any device/directory. File types can be recognized using [Siegfried](https://github.com/richardlehane/siegfried) or a lighterweight method. Provides a graphical view of the contents of the directory. Additionally, you can export meta data from your selected device to a spreadsheet (.csv or .XLSX).
3. Duplicates, sifts through the contents of a selcted directory to find duplicate files. Uses MD5 hashing to check for duplicates.
4. Settings, lets you select a spreadsheet to excel device information to and choose what information to display in the duplicates tab.



# Archivizm - Installation and Usage Guide

## Quick Start
- **Windows**: Double-click `Archivizm.bat`
- **Linux/macOS**: Run `./Archivizm.sh` in terminal

---

## Windows Installation & Usage

### Method 1: Simple Double-Click (Recommended)
1. **Download** the Archivizm folder to your computer
2. **Double-click** `Archivizm.bat`
3. **First time only**: Wait for automatic setup (5-10 minutes)
4. **Application opens automatically**

### Method 2: Command Line
```cmd
# Open Command Prompt in the Archivizm folder
cd path\to\Archivizm

# Run the application
Archivizm.bat
```

### What happens automatically:
- ✅ Virtual environment creation
- ✅ Python package installation
- ✅ spaCy model download
- ✅ Siegfried installation
- ✅ Application launch

---

## Linux/macOS Installation & Usage

```bash
# 1. Open terminal in the Archivizm folder
cd /path/to/Archivizm

# 2. Make the launcher executable (first time only)
chmod +x Archivizm.sh

# 3. Run the application
./Archivizm.sh
```

### What happens during first run:
1. **Creates virtual environment** (isolated Python installation)
2. **Installs dependencies**: pandas, PyQt5, matplotlib, spacy, etc.
3. **Downloads language model** for text processing (200-300MB)
4. **Installs Siegfried** for file format identification
5. **Launches the application**


## Troubleshooting

### Windows Issues:
**If double-click doesn't work:**
1. Right-click `Archivizm.bat`
2. Select "Run as administrator"

**If you see a flash and close:**
1. Open Command Prompt
2. Navigate to Archivizm folder: `cd C:\path\to\Archivizm`
3. Run: `Archivizm.bat`
4. Read the error message

### Linux/macOS Issues:
**"Permission denied" error:**
```bash
chmod +x Archivizm.sh
./Archivizm.sh
```

**"Command not found" error:**
```bash
bash Archivizm.sh
```

**Python not found:**
```bash
# Install Python first (Ubuntu/Debian)
sudo apt update
sudo apt install python3 python3-pip

# macOS with Homebrew
brew install python
```

---

## Manual Setup

### If automatic setup fails:
```bash
# 1. Create virtual environment
python -m venv archivizm_env

# 2. Activate environment
# Windows:
archivizm_env\Scripts\activate
# Linux/macOS:
source archivizm_env/bin/activate

# 3. Install packages
pip install -r requirements.txt

# 4. Download spaCy model
python -m spacy download en_core_web_sm

# 5. Run application
python Archivizm.py
```

---

## System Requirements

### Minimum:
- **OS**: Windows 10, macOS 10.14+, or Ubuntu 18.04+
- **RAM**: 4GB
- **Storage**: 1GB free space
- **Python**: 3.8 or newer (included in setup)

### Recommended:
- **RAM**: 8GB+
- **Storage**: 2GB free space
- **Internet**: For first-time setup

---

## File Structure
```
Archivizm/
├── Archivizm.bat          # ← Windows users: DOUBLE-CLICK THIS
├── Archivizm.sh           # ← Linux/macOS users: RUN THIS
├── setup.bat              # Automatic setup (Windows)
├── setup.sh               # Automatic setup (Linux/macOS)
├── Archivizm.py           # Main application
├── requirements.txt       # Dependencies list
└── Siegfried/             # File identification tool
```

---

## Need Help?
1. Check that Python is installed: `python --version`
2. Ensure you have internet connection for first setup
3. Run the setup manually if automatic setup fails
4. Check the terminal/command prompt for error messages

**Remember**: First run takes longer due to setup. Subsequent runs start instantly!

---

## Summary
### Windows:
```cmd
# Just double-click:
Archivizm.bat
```

### Linux/macOS:
```bash
# One-time setup then run:
chmod +x Archivizm.sh
./Archivizm.sh

# Or combined:
chmod +x Archivizm.sh && ./Archivizm.sh
```

     




