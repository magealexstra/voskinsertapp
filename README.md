# VOSK Dictation

A standalone dictation tool using VOSK for speech recognition with ydotool integration for text entry. This tool allows you to dictate text and have it inserted at your cursor position in any application.

## Features

- **Text Entry Mode**: Dictated text is inserted at the cursor position without trailing spaces
- **Standard Mode**: Dictated text is appended with trailing spaces
- **Toggle Between Modes**: Easily switch between text entry and standard modes
- **Suspend/Resume**: Temporarily pause dictation when needed
- **Self-Contained**: Runs independently with minimal dependencies
- **Fast Response**: Optimized for speed and responsiveness
- **Automatic Model Setup**: Downloads and configures VOSK speech recognition models as needed
- **Modern GUI**: Cross-platform graphical interface with dark theme for easy control

## Requirements

- Linux system (for ydotool support)
- Python 3.6 or higher
- ydotool for keyboard simulation (optional but recommended)

## Installation

### Quick Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/magealexstra/vosk-dictation.git
   cd vosk-dictation
   ```

2. Set up the virtual environment and install dependencies:
   ```bash
   python -m vosk_dictation.dictation --setup
   ```

3. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```

### Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/magealexstra/vosk-dictation.git
   cd vosk-dictation
   ```

2. Run the installation script:
   ```bash
   ./install.sh
   ```
   
   The installation script will:
   - Install all required dependencies
   - Check for ydotool (required for text entry mode)
   - Set up the command-line tool and GUI

3. Alternatively, install manually:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

## Usage

### Basic Usage (Command Line)

```bash
vosk-dictation --text-entry
```

### Graphical User Interface

A modern cross-platform GUI is available for easier control of the dictation tool:

```bash
vosk-dictation-gui
```

Or run directly from the Python module:

```bash
python -m vosk_dictation.gui
```

The GUI provides:
- Start/Stop buttons for dictation control
- Toggle button to switch between text entry and standard modes
- History panel showing the last 3-4 dictation entries
- Copy functionality for each dictation entry
- Modern dark theme for reduced eye strain

The GUI will automatically install PyQt5 if it's not already installed on your system.

### Command Line Options

- `--model-dir MODEL_DIR`: Path to the VOSK model directory
- `--config-dir CONFIG_DIR`: Path to a custom config directory
- `--language LANGUAGE`: Language code to use (default: en-US)
- `--setup-ydotool`: Set up ydotool permissions
- `--no-ydotool`: Disable ydotool for input simulation
- `--text-entry`: Run in text entry mode (insert at cursor position)
- `--setup`: Set up virtual environment and install dependencies
- `--debug`: Enable debug logging

### Available Commands

While the dictation tool is running, you can use the following commands:

- `suspend` or `pause`: Temporarily stop listening
- `resume` or `continue`: Resume listening after suspension
- `restart`: Restart the listener
- `status`: Check the listener status and current mode
- `toggle-mode`: Switch between text entry and standard modes
- `exit` or `quit`: Exit the program
- `help`: Show the help message

## Setting Up ydotool

For the best experience, you should set up ydotool with the proper permissions:

```bash
vosk-dictation --setup-ydotool
```

This will:
1. Create a udev rule for ydotool
2. Add your user to the input group
3. Reload udev rules

You'll need to log out and log back in for the changes to take effect.

## Troubleshooting

### ydotool Not Working

If ydotool is not working properly, make sure:

1. The ydotool daemon is running:
   ```bash
   sudo ydotoold
   ```

2. Your user has the proper permissions:
   ```bash
   sudo usermod -aG input $USER
   ```

3. The udev rules are set up correctly:
   ```bash
   sudo bash -c 'echo "KERNEL==\"uinput\", GROUP=\"input\", MODE=\"0660\", OPTIONS+=\"static_node=uinput\"" > /etc/udev/rules.d/60-ydotool.rules'
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

### VOSK Model Management

The tool now automatically downloads and sets up the VOSK model when needed. If no model is found, it will:

1. Create the necessary directory structure in `~/.cache/vosk`
2. Download an appropriate English model
3. Extract and prepare the model for use

If automatic download fails, you can manually download a model from [the VOSK website](https://alphacephei.com/vosk/models) and place it in one of these directories:

- `~/.cache/vosk` (recommended)
- `~/vosk-models`
- `/usr/share/vosk`
- `/usr/local/share/vosk`
- `./models`

## License

MIT License
