#!/bin/bash
# Installation script for VOSK Dictation with GUI

echo "Installing VOSK Dictation with GUI..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3 and try again."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is required but not installed. Please install pip3 and try again."
    exit 1
fi

# Install the package in development mode
echo "Installing package dependencies..."
pip3 install -e .

# Check if ydotool is installed
if ! command -v ydotool &> /dev/null; then
    echo "Warning: ydotool is not installed. Text entry mode will not work without it."
    echo "Please install ydotool for full functionality."
fi

echo "Installation complete!"
echo ""
echo "You can now run the VOSK Dictation tool with:"
echo "  vosk-dictation --text-entry"
echo ""
echo "Or run the GUI with:"
echo "  vosk-dictation-gui"
echo ""
echo "The first run will download the speech recognition model (about 50MB)."
