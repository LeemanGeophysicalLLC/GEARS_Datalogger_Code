#!/bin/bash

echo "Setting up GEARS Data Logger environment..."

# Detect actual user (the one who ran the script, not root)
REAL_USER=$(logname)
REAL_HOME=$(eval echo "~$REAL_USER")

# 1. System update (optional)
# sudo apt update && sudo apt upgrade -y

# 2. Install Python and required packages
echo "Installing Python packages..."
sudo apt install -y python3 python3-pip python3-tk git unzip

# 3. Install the LabJack LJM driver
echo "Installing LabJack LJM driver..."
wget https://files.labjack.com/installers/LJM/Linux/AArch64/release/LabJack-LJM_2025-05-07.zip -O /tmp/LJMInstaller.zip
unzip -o /tmp/LJMInstaller.zip -d /tmp/LJMInstall
cd /tmp/LJMInstall
sudo ./labjack_ljm_installer.run

# 4. Install Python packages
echo "Installing Python libraries..."
sudo pip3 install labjack-ljm requests --break-system-packages

# 5. Create Desktop launcher for the correct user
APP_PATH="$REAL_HOME/GEARS_Datalogger_Code/app.py"
DESKTOP_ENTRY="$REAL_HOME/Desktop/DataLogger.desktop"

if [ -f "$APP_PATH" ]; then
    echo "Creating desktop launcher at $DESKTOP_ENTRY..."
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
    chown "$REAL_USER":"$REAL_USER" "$DESKTOP_ENTRY"
else
    echo "Skipping launcher: $APP_PATH not found."
fi

echo "Setup complete. You can now launch the logger from the desktop."
