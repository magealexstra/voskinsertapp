#!/usr/bin/env python3
"""
GUI for VOSK Dictation Tool
A simple PyQt5-based GUI for controlling the VOSK dictation tool.
"""

import os
import sys
import json
import time
import threading
import subprocess
from pathlib import Path

try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                QHBoxLayout, QPushButton, QLabel, QScrollArea, 
                                QFrame, QSizePolicy)
    from PyQt5.QtCore import Qt, QSize, pyqtSignal, QObject, pyqtSlot
    from PyQt5.QtGui import QFont, QIcon, QColor, QPalette
except ImportError:
    print("PyQt5 is not installed. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PyQt5"], check=True)
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                QHBoxLayout, QPushButton, QLabel, QScrollArea, 
                                QFrame, QSizePolicy)
    from PyQt5.QtCore import Qt, QSize, pyqtSignal, QObject, pyqtSlot
    from PyQt5.QtGui import QFont, QIcon, QColor, QPalette

# Add the parent directory to the path so we can import the dictation module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from vosk_dictation.dictation import VoskDictation

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
        
        self.stop_button.setEnabled(False)
        self.toggle_button.setEnabled(False)
        
        self.start_button.clicked.connect(self.start_dictation)
        self.stop_button.clicked.connect(self.stop_dictation)
        self.toggle_button.clicked.connect(self.toggle_mode)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.toggle_button)
        
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
    
    def start_dictation(self):
        """Start the dictation process."""
        if self.is_listening:
            return
        
        try:
            # Create the dictation object
            self.dictation = VoskDictation(text_entry_mode=self.text_entry_mode)
            
            # Set up callback for recognized text
            self.dictation.callback = self.on_text_recognized
            
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
    
    def on_text_recognized(self, text):
        """Callback for when text is recognized."""
        if text and text.strip():
            self.signals.text_received.emit(text.strip())
    
    @pyqtSlot(str)
    def add_entry(self, text):
        """Add a new entry to the UI."""
        # Create the entry widget
        entry_widget = EntryWidget(text)
        
        # Add to the layout at the beginning (newest at top)
        self.entries_layout.insertWidget(0, entry_widget)
        
        # Add to recent entries
        self.recent_entries.append(text)
        
        # Remove oldest if we exceed max entries
        if len(self.recent_entries) > self.max_entries:
            self.recent_entries.pop(0)
            # Remove the oldest widget (but skip the stretch at the end)
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
