#!/usr/bin/env python3
"""
GUI for VOSK Dictation Tool
A simple PyQt5-based GUI for controlling the VOSK dictation tool.
"""

import os
import sys
import threading
import subprocess
import time
from pathlib import Path

# Base directory for the project
base_dir = Path(__file__).resolve().parent.parent

# Check if we're in a virtual environment
def is_in_virtualenv():
    return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

# Import or set up the virtual environment if needed
if not is_in_virtualenv():
    # First, try to import the setup function
    try:
        # Add the parent directory to the path so we can import the dictation module
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
            
        # Import the setup function
        from vosk_dictation.dictation import setup_virtual_env
        
        # Set up the virtual environment
        print("Not running in a virtual environment. Setting up...")
        if setup_virtual_env(base_dir):
            # Activate the virtual environment
            venv_python = base_dir / "venv" / "bin" / "python"
            if sys.platform == "win32":
                venv_python = base_dir / "venv" / "Scripts" / "python.exe"
                
            if venv_python.exists():
                print(f"Restarting with virtual environment: {venv_python}")
                os.execl(str(venv_python), str(venv_python), *sys.argv)
            else:
                print("Virtual environment created but Python executable not found.")
        else:
            print("Failed to set up virtual environment. Continuing with system Python...")
    except Exception as e:
        print(f"Error setting up virtual environment: {e}")
        print("Continuing with system Python...")

# Now try to import PyQt5
try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                QHBoxLayout, QPushButton, QLabel, QScrollArea, 
                                QFrame, QSizePolicy, QDialog, QComboBox, QFormLayout,
                                QDialogButtonBox, QSpinBox, QCheckBox, QTextEdit)
    from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QObject, QEvent
    from PyQt5.QtGui import QFont, QIcon, QPalette, QColor
except ImportError:
    print("PyQt5 is not installed. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PyQt5"], check=True)
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                QHBoxLayout, QPushButton, QLabel, QScrollArea, 
                                QFrame, QSizePolicy, QDialog, QComboBox, QFormLayout,
                                QDialogButtonBox, QSpinBox, QCheckBox, QTextEdit)
    from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QObject, QEvent
    from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

# Add the parent directory to the path so we can import the dictation module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from vosk_dictation.dictation import VoskDictation
from vosk_dictation import audio_utils
from vosk_dictation import text_inserter

class SettingsDialog(QDialog):
    """Dialog for configuring dictation settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dictation Settings")
        self.setMinimumWidth(400)
        self.init_ui()
        
        # Default settings
        self.device = None
        self.sample_rate = 16000
        self.block_size = 8000
        self.insertion_method = None
        
    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Audio device selection
        self.device_combo = QComboBox()
        self.device_combo.addItem("Default Device", None)
        
        # Get available audio devices
        try:
            devices = audio_utils.get_audio_devices()
            for i, device in enumerate(devices):
                name = device['name']
                self.device_combo.addItem(f"{i}: {name}", i)
        except Exception as e:
            print(f"Error getting audio devices: {e}")
        
        # Sample rate selection
        self.sample_rate_spin = QSpinBox()
        self.sample_rate_spin.setRange(8000, 48000)
        self.sample_rate_spin.setSingleStep(1000)
        self.sample_rate_spin.setValue(16000)
        
        # Block size selection
        self.block_size_spin = QSpinBox()
        self.block_size_spin.setRange(1000, 16000)
        self.block_size_spin.setSingleStep(1000)
        self.block_size_spin.setValue(8000)
        
        # Text insertion method selection
        self.insertion_method_combo = QComboBox()
        self.insertion_method_combo.addItem("Auto-detect", None)
        
        # Get available insertion methods
        try:
            methods = text_inserter.detect_available_methods()
            for method in methods:
                self.insertion_method_combo.addItem(method.name.capitalize(), method.name.lower())
        except Exception as e:
            print(f"Error getting insertion methods: {e}")
            # Add default options
            for method in ["ydotool", "xdotool", "wtype", "clipboard", "none"]:
                self.insertion_method_combo.addItem(method.capitalize(), method)
        
        # Add widgets to form layout
        form_layout.addRow("Audio Device:", self.device_combo)
        form_layout.addRow("Sample Rate:", self.sample_rate_spin)
        form_layout.addRow("Block Size:", self.block_size_spin)
        form_layout.addRow("Text Insertion Method:", self.insertion_method_combo)
        
        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Add layouts to main layout
        layout.addLayout(form_layout)
        layout.addWidget(button_box)
        
    def get_settings(self):
        """Get the selected settings."""
        return {
            'device': self.device_combo.currentData(),
            'sample_rate': self.sample_rate_spin.value(),
            'block_size': self.block_size_spin.value(),
            'insertion_method': self.insertion_method_combo.currentData()
        }

class DictationSignals(QObject):
    """Signal class for thread-safe communication with the GUI."""
    text_received = pyqtSignal(str)
    status_update = pyqtSignal(str)

class EntryWidget(QFrame):
    """Widget for displaying a dictation entry with a copy button."""
    
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI."""
        # Set up the frame style
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("""
            EntryWidget {
                background-color: #424242;
                border-radius: 5px;
                margin: 5px;
            }
        """)
        
        # Create layout
        layout = QHBoxLayout()
        
        # Text label
        self.text_label = QLabel(self.text)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("color: white;")
        
        # Copy button
        copy_button = QPushButton("📋")
        copy_button.setToolTip("Copy to clipboard")
        copy_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #BBBBBB;
                border: none;
                font-size: 16px;
                padding: 5px;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        copy_button.setFixedSize(30, 30)
        copy_button.clicked.connect(self.copy_to_clipboard)
        
        # Add widgets to layout
        layout.addWidget(self.text_label, 1)
        layout.addWidget(copy_button, 0)
        
        self.setLayout(layout)
        
    def copy_to_clipboard(self):
        """Copy the text to the clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text)
        
        # Visual feedback (briefly change button color)
        sender = self.sender()
        original_style = sender.styleSheet()
        sender.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #4CAF50;
                border: none;
                font-size: 16px;
                padding: 5px;
            }
        """)
        
        # Reset after a short delay
        def reset_style():
            time.sleep(1)
            sender.setStyleSheet(original_style)
            
        threading.Thread(target=reset_style, daemon=True).start()

class VoskDictationGUI(QMainWindow):
    """Main GUI window for VOSK Dictation."""
    
    def __init__(self):
        super().__init__()
        self.dictation = None
        self.dictation_thread = None
        self.is_listening = False
        self.text_entry_mode = True
        self.recent_entries = []
        self.max_entries = 4
        
        # Initialize tracking variable for last text to prevent duplicates
        self._last_text = ""
        
        # Audio and text insertion settings
        self.device = None
        self.sample_rate = 16000
        self.block_size = 8000
        self.insertion_method = None
        
        # Try to get default device
        try:
            self.device = audio_utils.get_default_device()
            if self.device is not None:
                # Try to get default sample rate for the device
                self.sample_rate = audio_utils.get_device_sample_rate(self.device)
        except Exception as e:
            print(f"Error getting default audio device: {e}")
        
        self.signals = DictationSignals()
        self.signals.text_received.connect(self.add_entry)
        self.signals.status_update.connect(self.update_status)
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI."""
        # Set window properties
        self.setWindowTitle("VOSK Dictation GUI")
        self.setMinimumSize(600, 500)
        self.setStyleSheet("background-color: #2D2D2D;")
        
        # Create central widget and main layout
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Title
        title_label = QLabel("VOSK Dictation")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: white;
            margin-bottom: 15px;
        """)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_button = self.create_button("Start Listening", "#4CAF50")
        self.stop_button = self.create_button("Stop Listening", "#F44336")
        self.toggle_button = self.create_button("Toggle Mode", "#2196F3")
        self.clear_button = self.create_button("Clear Text", "#9C27B0")
        self.settings_button = self.create_button("Settings", "#FF9800")
        # Disable auto-repeat for settings button to prevent accidental triggering
        self.settings_button.setAutoRepeat(False)
        # Set focus policy to prevent accidental activation
        self.settings_button.setFocusPolicy(Qt.NoFocus)
        
        self.stop_button.setEnabled(False)
        self.toggle_button.setEnabled(False)
        
        self.start_button.clicked.connect(self.start_dictation)
        self.stop_button.clicked.connect(self.stop_dictation)
        self.toggle_button.clicked.connect(self.toggle_mode)
        self.clear_button.clicked.connect(self.clear_text)
        self.settings_button.clicked.connect(self.show_settings)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.toggle_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.settings_button)
        
        # Entries container
        entries_container = QWidget()
        self.entries_layout = QVBoxLayout(entries_container)
        self.entries_layout.setContentsMargins(10, 10, 10, 10)
        self.entries_layout.setSpacing(10)
        self.entries_layout.addStretch(1)  # Push entries to the top
        
        entries_container.setStyleSheet("""
            background-color: #383838;
            border-radius: 5px;
        """)
        
        # Text area for displaying recognized text when no insertion point is available
        self.text_area_label = QLabel("Recognized Text:")
        self.text_area_label.setStyleSheet("color: white; font-weight: bold;")
        
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(False)  # Allow editing so users can copy/edit text
        self.text_area.setMinimumHeight(100)
        
        # Connect focus events to enable/disable cursor insertion
        self.text_area.installEventFilter(self)
        self.text_area.setStyleSheet("""
            QTextEdit {
                background-color: #2D2D2D;
                color: white;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        
        # Scroll area for entries
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(entries_container)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #383838;
                border-radius: 5px;
            }
            QScrollBar:vertical {
                border: none;
                background: #424242;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #666666;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Status label
        self.status_label = QLabel("Status: Not listening")
        self.status_label.setStyleSheet("""
            color: #BBBBBB;
            margin-top: 10px;
        """)
        
        # Assemble the UI
        main_layout.addWidget(title_label)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(scroll_area, 1)
        main_layout.addWidget(self.text_area_label)
        main_layout.addWidget(self.text_area)
        main_layout.addWidget(self.status_label)
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
    def create_button(self, text, color):
        """Create a styled button."""
        button = QPushButton(text)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {self.lighter_color(color)};
            }}
            QPushButton:disabled {{
                background-color: #666666;
                color: #AAAAAA;
            }}
        """)
        return button
    
    def lighter_color(self, hex_color):
        """Return a lighter version of the given hex color."""
        # Simple implementation - just make it 20% lighter
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        
        factor = 1.2
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def show_settings(self):
        """Show the settings dialog."""
        # Temporarily disable the settings button to prevent multiple dialogs
        self.settings_button.setEnabled(False)
        dialog = SettingsDialog(self)
        
        # Set the current settings in the dialog
        if self.device is not None:
            index = dialog.device_combo.findData(self.device)
            if index >= 0:
                dialog.device_combo.setCurrentIndex(index)
                
        dialog.sample_rate_spin.setValue(self.sample_rate)
        dialog.block_size_spin.setValue(self.block_size)
        
        if self.insertion_method is not None:
            index = dialog.insertion_method_combo.findData(self.insertion_method)
            if index >= 0:
                dialog.insertion_method_combo.setCurrentIndex(index)
        
        # Show the dialog and get the result
        if dialog.exec_():
            # Get the settings from the dialog
            settings = dialog.get_settings()
            self.device = settings['device']
            self.sample_rate = settings['sample_rate']
            self.block_size = settings['block_size']
            self.insertion_method = settings['insertion_method']
            
            # Update the status to show the new settings
            device_name = "Default" if self.device is None else f"Device {self.device}"
            insertion_method_name = "Auto" if self.insertion_method is None else self.insertion_method.capitalize()
            self.update_status(f"Settings updated: {device_name}, {insertion_method_name}")
        
        # Re-enable the settings button
        self.settings_button.setEnabled(True)
    
    def start_dictation(self):
        """Start the dictation process."""
        if self.is_listening:
            return
        
        try:
            # Store the user's preferred text entry mode setting
            self._previous_text_entry_mode = self.text_entry_mode
            
            # Determine initial text entry mode based on window state
            # If window is active, disable cursor insertion initially
            initial_text_entry_mode = False if self.isActiveWindow() else self.text_entry_mode
            
            # Create the dictation object with our settings
            self.dictation = VoskDictation(
                text_entry_mode=initial_text_entry_mode,
                device=self.device,
                sample_rate=self.sample_rate,
                block_size=self.block_size,
                insertion_method=self.insertion_method,
                silence_timeout=2.0  # Set to 2 seconds (1 second longer than default)
            )
            
            # Log the initial state
            if self.isActiveWindow():
                print("Starting with cursor insertion disabled (window is active)")
                self.update_status("Cursor insertion disabled while app is active")
            else:
                mode_text = "Text Entry Mode" if self.text_entry_mode else "Standard Mode"
                print(f"Starting dictation in {mode_text}")
                self.update_status(f"Starting dictation in {mode_text}")
            
            # Set up callback for recognized text
            self.dictation.callback = self.on_text_recognized
            
            # Flag to indicate a new dictation session is starting
            # This will be used in add_entry to clear previous text
            self.new_dictation_session = True
            
            # Start dictation in a separate thread
            self.dictation_thread = threading.Thread(target=self._dictation_thread)
            self.dictation_thread.daemon = True
            self.dictation_thread.start()
            
            # Update UI
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.toggle_button.setEnabled(True)
            self.update_status("Status: Listening (Text Entry Mode)" if self.text_entry_mode else "Status: Listening (Standard Mode)")
            self.is_listening = True
            
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
    
    def _dictation_thread(self):
        """Thread function for running dictation."""
        try:
            self.dictation.start_listening()
        except Exception as e:
            self.signals.status_update.emit(f"Error: {str(e)}")
        finally:
            self.is_listening = False
            self.signals.status_update.emit("Status: Not listening")
    
    def stop_dictation(self):
        """Stop the dictation process."""
        if not self.is_listening:
            return
        
        try:
            if self.dictation:
                self.dictation.stop_listening()
            
            # Update UI
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.toggle_button.setEnabled(False)
            self.update_status("Status: Not listening")
            self.is_listening = False
            
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
    
    def toggle_mode(self):
        """Toggle between text entry and standard modes."""
        if not self.dictation:
            return
        
        try:
            # Toggle the mode
            self.text_entry_mode = not self.text_entry_mode
            self.dictation.text_entry_mode = self.text_entry_mode
            
            # Update UI
            if self.text_entry_mode:
                self.toggle_button.setText("Switch to Standard")
                self.toggle_button.setStyleSheet("""
                    QPushButton {
                        background-color: #2196F3;
                        color: white;
                        font-weight: bold;
                        padding: 10px 20px;
                        border-radius: 5px;
                        border: none;
                    }
                    QPushButton:hover {
                        background-color: #64B5F6;
                    }
                """)
                self.update_status("Status: Listening (Text Entry Mode)")
            else:
                self.toggle_button.setText("Switch to Text Entry")
                self.toggle_button.setStyleSheet("""
                    QPushButton {
                        background-color: #FF9800;
                        color: white;
                        font-weight: bold;
                        padding: 10px 20px;
                        border-radius: 5px;
                        border: none;
                    }
                    QPushButton:hover {
                        background-color: #FFAD33;
                    }
                """)
                self.update_status("Status: Listening (Standard Mode)")
                
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
    
    def changeEvent(self, event):
        """Handle window activation/deactivation events to control cursor insertion."""
        if event.type() == QEvent.ActivationChange:
            if self.isActiveWindow():
                # Window is now active - disable cursor insertion
                if self.dictation:
                    print("Window activated - disabling cursor insertion")
                    # Store the current text entry mode setting to restore later
                    self._previous_text_entry_mode = self.dictation.text_entry_mode
                    # Disable text entry mode to prevent insertion at cursor
                    self.dictation.text_entry_mode = False
                    self.update_status("Cursor insertion disabled while app is active")
            else:
                # Window is now inactive - restore cursor insertion if it was previously enabled
                if self.dictation and hasattr(self, '_previous_text_entry_mode'):
                    print("Window deactivated - restoring cursor insertion setting")
                    # Restore the previous text entry mode
                    self.dictation.text_entry_mode = self._previous_text_entry_mode
                    mode_text = "Text Entry Mode" if self.dictation.text_entry_mode else "Standard Mode"
                    self.update_status(f"Cursor insertion restored - {mode_text}")
        
        # Call the base class implementation
        super().changeEvent(event)
    
    def eventFilter(self, obj, event):
        """Filter events for the text area."""
        # Standard event processing
        return super().eventFilter(obj, event)
    
    def clear_text(self):
        """Clear the text area and reset the last text tracking."""
        self.text_area.clear()
        if hasattr(self, '_last_text'):
            self._last_text = ""
        self.update_status("Text area cleared")
        # Set flag to start a new dictation session
        self.new_dictation_session = True
    
    def on_text_recognized(self, text):
        """Callback for when text is recognized."""
        if text and text.strip():
            # Store the raw text for debugging
            raw_text = text.strip()
            print(f"Raw recognized text: '{raw_text}'")
            
            # Initialize recognized_texts list if it doesn't exist
            if not hasattr(self, 'recognized_texts'):
                self.recognized_texts = []
            
            # Check if this text might contain multiple sentences
            # Look for patterns that suggest multiple sentences concatenated
            processed_text = raw_text
            
            # Split text if we detect capital letters after lowercase letters without spaces
            # This handles cases like "is it workinghow about now" -> "is it working" and "how about now"
            import re
            sentence_splits = re.findall(r'[a-z]([A-Z])', processed_text)
            
            if sentence_splits:
                print(f"Detected potential sentence splits: {sentence_splits}")
                # Split the text at these points
                for split_point in sentence_splits:
                    split_pattern = f'(?<=[a-z]){split_point}'
                    processed_text = re.sub(split_pattern, f' {split_point}', processed_text)
                
                print(f"Processed text after splitting: '{processed_text}'")
                
                # Now split by spaces and process each potential sentence
                words = processed_text.split()
                current_sentence = []
                sentences = []
                
                for word in words:
                    # If word starts with capital and it's not the first word, it might be a new sentence
                    if word and word[0].isupper() and current_sentence and not word.lower() in ['i', 'i\'m', 'i\'ll', 'i\'ve', 'i\'d']:
                        # Complete the current sentence
                        if current_sentence:
                            sentences.append(' '.join(current_sentence))
                            current_sentence = []
                    
                    current_sentence.append(word)
                
                # Add the last sentence
                if current_sentence:
                    sentences.append(' '.join(current_sentence))
                
                # Process each sentence separately
                for sentence in sentences:
                    print(f"Processing sentence: '{sentence}'")
                    self.recognized_texts.append(sentence)
                    self.signals.text_received.emit(sentence)
            else:
                # Just a single sentence
                self.recognized_texts.append(processed_text)
                self.signals.text_received.emit(processed_text)
            
            # Focus the text area to make it the active insertion point for future dictation
            # This ensures there's always a valid insertion point available
            self.text_area.setFocus()
    
    @pyqtSlot(str)
    def add_entry(self, text):
        """Add a new entry to the UI."""
        # Skip empty or duplicate text
        if not text or not text.strip() or (hasattr(self, '_last_text') and self._last_text == text):
            return
        
        # Initialize last_text attribute if it doesn't exist
        if not hasattr(self, '_last_text'):
            self._last_text = ""
            
        # Initialize last_entry_time if it doesn't exist
        if not hasattr(self, '_last_entry_time'):
            self._last_entry_time = 0
            
        # Get current time
        current_time = time.time()
        
        # Check if this is a new sentence based on time gap (more than 1.5 seconds)
        time_gap_new_sentence = (current_time - self._last_entry_time) > 1.5 if self._last_entry_time > 0 else False
        
        # Update last entry time
        self._last_entry_time = current_time
            
        # Add to UI components
        entry_widget = EntryWidget(text)
        self.entries_layout.insertWidget(0, entry_widget)
        self.recent_entries.append(text)
        
        # Add to text area with proper spacing
        current_text = self.text_area.toPlainText()
        
        # Clear the text area if we're in a new dictation session
        if hasattr(self, 'new_dictation_session') and self.new_dictation_session:
            self.text_area.clear()
            self.text_area.setText(text)
            self.new_dictation_session = False
            self._last_text = text
            return
        
        # Check if this is a new sentence
        is_new_sentence = False
        
        # If text starts with a capital letter, it's likely a new sentence
        if text and text[0].isupper():
            is_new_sentence = True
        
        # If the current text ends with sentence-ending punctuation, treat as new sentence
        if current_text and current_text.rstrip().endswith(('.', '?', '!')):
            is_new_sentence = True
            
        # If there's a significant time gap, treat as new sentence
        if time_gap_new_sentence:
            is_new_sentence = True
            
        # If the text doesn't seem to be a continuation of the previous text
        # (based on grammar and context), treat as new sentence
        if self._last_text and text:
            # Check if the new text starts with a conjunction or preposition
            # that would typically continue a sentence
            continuations = ['and', 'or', 'but', 'so', 'because', 'that', 'which', 'with', 'without',
                            'for', 'to', 'in', 'on', 'at', 'by', 'as', 'if', 'when', 'while']
            
            # If the text doesn't start with a continuation word, it might be a new sentence
            first_word = text.split()[0].lower() if text.split() else ""
            if first_word and first_word not in continuations:
                is_new_sentence = True
                
        # Add appropriate spacing between entries
        if current_text:
            if current_text.endswith("\n") or is_new_sentence:
                # For new sentences, add a newline
                if not current_text.endswith("\n"):
                    self.text_area.append("\n" + text)
                else:
                    self.text_area.append(text)
            else:
                # Add a space between words if needed
                if not current_text.endswith(" ") and not text.startswith(" "):
                    self.text_area.append(" " + text)
                else:
                    self.text_area.append(text)
        else:
            self.text_area.setText(text)
        
        # Update last text
        self._last_text = text
        
        # Move cursor to end
        cursor = self.text_area.textCursor()
        cursor.movePosition(cursor.End)
        self.text_area.setTextCursor(cursor)
        
        # Manage entry limit
        if len(self.recent_entries) > self.max_entries:
            self.recent_entries.pop(0)
            if self.entries_layout.count() > self.max_entries + 1:
                item = self.entries_layout.itemAt(self.max_entries)
                if item and item.widget():
                    widget = item.widget()
                    self.entries_layout.removeWidget(widget)
                    widget.deleteLater()
    
    @pyqtSlot(str)
    def update_status(self, status):
        """Update the status label."""
        self.status_label.setText(status)
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.stop_dictation()
        event.accept()

def main():
    """Main function to run the GUI."""
    app = QApplication(sys.argv)
    
    # Set application-wide dark theme
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    gui = VoskDictationGUI()
    gui.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
