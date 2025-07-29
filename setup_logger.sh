#!/bin/bash

echo "Setting up GEARS Data Logger environment..."

# 1. System update
#sudo apt update && sudo apt upgrade -y

# 2. Install Python and required packages
echo "Installing Python packages..."
sudo apt install -y python3 python3-pip python3-tk git unzip

# 3. Install the LabJack LJM driver for Raspberry Pi
echo "Installing LabJack LJM driver..."

wget https://files.labjack.com/installers/LJM/Linux/AArch64/release/LabJack-LJM_2025-05-07.zip -O /tmp/LJMInstaller.zip
unzip -o /tmp/LJMInstaller.zip -d /tmp/LJMInstall
cd /tmp/LJMInstall
sudo ./labjack_ljm_installer.run

# 4. Install Python wrapper for LabJack
echo "Installing labjack Python wrapper..."
sudo pip3 install labjack-ljm --break-system-packages
sudo pip3 install requests --break-system-packages

# 5. Create desktop launcher
APP_PATH="$HOME/GEARS_Datalogger_Code/app.py"
DESKTOP_ENTRY="$HOME/Desktop/DataLogger.desktop"

if [ -f "$APP_PATH" ]; then
    echo "Creating desktop launcher..."
    cat <<EOF > "$DESKTOP_ENTRY"
[Desktop Entry]
Name=GEARS Data Logger
Comment=Start the LabJack logging app
Exec=python3 $APP_PATH
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=false
EOF

    chmod +x "$DESKTOP_ENTRY"
else
    echo "Skipping launcher: $APP_PATH not found."
fi

echo "Setup complete. You can now launch the logger from the desktop."

cd "$HOME"
