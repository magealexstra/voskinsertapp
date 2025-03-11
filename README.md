# VOSK Dictation

A standalone dictation tool using VOSK for speech recognition with ydotool integration for text entry. This tool allows you to dictate text and have it inserted at your cursor position in any application.

## Features

- **Text Entry Mode**: Dictated text is inserted at the cursor position without trailing spaces
- **Standard Mode**: Dictated text is appended with trailing spaces
- **Toggle Between Modes**: Easily switch between text entry and standard modes
- **Suspend/Resume**: Temporarily pause dictation when needed
- **Self-Contained**: Runs independently with minimal dependencies
- **Fast Response**: Optimized for speed and responsiveness

## Requirements

- Linux system (for ydotool support)
- Python 3.6 or higher
- ydotool for keyboard simulation (optional but recommended)

## Installation

### Quick Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/magealexstra/voskinsertapp.git
   cd voskinsertapp
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
   git clone https://github.com/magealexstra/voskinsertapp.git
   cd voskinsertapp
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install the package:
   ```bash
   pip install -e .
   ```

## Usage

### Basic Usage

```bash
vosk-dictation --text-entry
```

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

### VOSK Model Not Found

If the VOSK model is not found, the tool will attempt to download it automatically. If this fails, you can manually download a model from [the VOSK website](https://alphacephei.com/vosk/models) and place it in one of these directories:

- `~/.cache/vosk`
- `~/vosk-models`
- `/usr/share/vosk`
- `/usr/local/share/vosk`
- `./models`

## License

MIT License
