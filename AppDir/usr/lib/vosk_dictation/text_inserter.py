#!/usr/bin/env python3
"""
Text insertion utilities for the VOSK dictation application.

This module provides different methods for inserting text, allowing the application
to work on various Linux distributions and desktop environments.
"""

import subprocess
import logging
import shutil
from enum import Enum

logger = logging.getLogger(__name__)

class InsertionMethod(Enum):
    """Supported text insertion methods."""
    YDOTOOL = "ydotool"
    XDOTOOL = "xdotool"
    WTYPE = "wtype"
    CLIPBOARD = "clipboard"
    NONE = "none"

def check_insertion_point():
    """Check if there is a valid insertion point for text using a harmless key press."""
    # Check ydotool first (preferred method)
    if shutil.which("ydotool") is not None:
        try:
            if subprocess.run(["ydotool", "key", "shift"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
                return True
        except Exception:
            pass
    
    # Try xdotool next
    if shutil.which("xdotool") is not None:
        try:
            if subprocess.run(["xdotool", "key", "shift"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
                return True
        except Exception:
            pass
    
    # Finally try wtype
    if shutil.which("wtype") is not None:
        try:
            if subprocess.run(["wtype", "-k", "shift"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
                return True
        except Exception:
            pass
    
    return False

def detect_available_methods():
    """
    Detect which text insertion methods are available on the system.
    
    Returns:
        A list of available InsertionMethod values
    """
    available_methods = []
    
    # Check for ydotool
    if shutil.which("ydotool") is not None:
        available_methods.append(InsertionMethod.YDOTOOL)
    
    # Check for xdotool (X11 environments)
    if shutil.which("xdotool") is not None:
        available_methods.append(InsertionMethod.XDOTOOL)
    
    # Check for wtype (Wayland environments)
    if shutil.which("wtype") is not None:
        available_methods.append(InsertionMethod.WTYPE)
    
    # Clipboard is always available as a fallback
    available_methods.append(InsertionMethod.CLIPBOARD)
    
    # None is always available (just display text)
    available_methods.append(InsertionMethod.NONE)
    
    return available_methods

def insert_text(text, method=InsertionMethod.YDOTOOL, mode="append"):
    """
    Insert text using the specified method.
    
    Args:
        text (str): The text to insert
        method (InsertionMethod): The method to use for insertion
        mode (str): The insertion mode ("append" adds a space, "insert" doesn't)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if method == InsertionMethod.YDOTOOL:
        return _insert_with_ydotool(text, mode)
    elif method == InsertionMethod.XDOTOOL:
        return _insert_with_xdotool(text, mode)
    elif method == InsertionMethod.WTYPE:
        return _insert_with_wtype(text, mode)
    elif method == InsertionMethod.CLIPBOARD:
        return _insert_with_clipboard(text)
    elif method == InsertionMethod.NONE:
        # Just print the text, don't insert it
        print(f"Recognized text: {text}")
        return True
    else:
        logger.error(f"Unknown insertion method: {method}")
        return False

def _insert_with_ydotool(text, mode="append"):
    """Insert text using ydotool."""
    try:
        # Check if ydotool is available
        if shutil.which("ydotool") is None:
            logger.error("ydotool not found in PATH")
            return False
            
        # Prepare text for ydotool
        escaped_text = text.replace("'", "'\\''")
        
        # First, check if we can insert text by trying a simple no-op command
        # This helps detect if the cursor is in a valid insertion point
        check_cmd = ["ydotool", "key", "shift"]
        check_result = subprocess.run(
            check_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if check_result.returncode != 0:
            logger.error(f"No valid insertion point detected: {check_result.stderr}")
            return False
            
        # Add a small delay before typing to prevent accidental shortcut triggering
        subprocess.run(["ydotool", "sleep", "100"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Determine typing command based on mode
        if mode == "append":
            # Append mode: add a space after the text
            escaped_text += " "
            command = ["ydotool", "type", escaped_text]
        elif mode == "insert":
            # Insert mode: just insert the text without a trailing space
            command = ["ydotool", "type", escaped_text]
        else:
            logger.error(f"Unknown typing mode: {mode}")
            return False
            
        # Execute the ydotool command
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Error typing with ydotool: {result.stderr}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error typing with ydotool: {e}")
        return False

def _insert_with_xdotool(text, mode="append"):
    """Insert text using xdotool (for X11 environments)."""
    try:
        # Check if xdotool is available
        if shutil.which("xdotool") is None:
            logger.error("xdotool not found in PATH")
            return False
            
        # First, check if we can insert text by trying a simple no-op command
        # This helps detect if the cursor is in a valid insertion point
        check_cmd = ["xdotool", "key", "shift"]
        check_result = subprocess.run(
            check_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if check_result.returncode != 0:
            logger.error(f"No valid insertion point detected: {check_result.stderr}")
            return False
            
        # Prepare text for xdotool
        if mode == "append":
            # Append mode: add a space after the text
            text += " "
        
        # Add a small delay before typing to prevent accidental shortcut triggering
        subprocess.run(["xdotool", "sleep", "100"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
        # Execute the xdotool command
        result = subprocess.run(
            ["xdotool", "type", text],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Error typing with xdotool: {result.stderr}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error typing with xdotool: {e}")
        return False

def _insert_with_wtype(text, mode="append"):
    """Insert text using wtype (for Wayland environments)."""
    try:
        # Check if wtype is available
        if shutil.which("wtype") is None:
            logger.error("wtype not found in PATH")
            return False
            
        # First, check if we can insert text by trying a simple no-op command
        # For wtype, we'll try a simple key press to check if input is possible
        # We use a key that won't affect the text (shift key)
        check_cmd = ["wtype", "-k", "shift"]
        check_result = subprocess.run(
            check_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if check_result.returncode != 0:
            logger.error(f"No valid insertion point detected: {check_result.stderr}")
            return False
            
        # Prepare text for wtype
        if mode == "append":
            # Append mode: add a space after the text
            text += " "
        
        # Add a small delay before typing to prevent accidental shortcut triggering
        # wtype doesn't have a sleep command, so we use system sleep
        time.sleep(0.1)
            
        # Execute the wtype command
        result = subprocess.run(
            ["wtype", text],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Error typing with wtype: {result.stderr}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error typing with wtype: {e}")
        return False

def _insert_with_clipboard(text):
    """
    Insert text by copying to clipboard.
    
    This is a fallback method that copies the text to the clipboard
    and notifies the user to paste it manually.
    """
    try:
        # Try to use pyperclip if available
        try:
            import pyperclip
            pyperclip.copy(text)
            print(f"Text copied to clipboard: {text}")
            print("Press Ctrl+V to paste it where needed.")
            return True
        except ImportError:
            pass
            
        # Try using xclip for X11
        if shutil.which("xclip") is not None:
            process = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            process.communicate(input=text.encode())
            if process.returncode == 0:
                print(f"Text copied to clipboard: {text}")
                print("Press Ctrl+V to paste it where needed.")
                return True
                
        # Try using wl-copy for Wayland
        if shutil.which("wl-copy") is not None:
            process = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
            process.communicate(input=text.encode())
            if process.returncode == 0:
                print(f"Text copied to clipboard: {text}")
                print("Press Ctrl+V to paste it where needed.")
                return True
                
        # If all else fails, just print the text
        print(f"Recognized text (clipboard method not available): {text}")
        return False
        
    except Exception as e:
        logger.error(f"Error copying to clipboard: {e}")
        print(f"Recognized text (clipboard error): {text}")
        return False
