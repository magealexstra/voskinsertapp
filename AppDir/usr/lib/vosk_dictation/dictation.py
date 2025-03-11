#!/usr/bin/env python3
"""
VOSK Dictation - A standalone text entry application using voice recognition

This module provides a self-contained dictation tool using VOSK for fast,
reliable speech-to-text conversion with the ability to insert text at the cursor position
using ydotool. It can run independently as a complete dictation solution.
"""

import os
import sys
import logging
import subprocess
import threading
import time
import signal
import select
import queue
import json
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List

# Import our custom modules
from vosk_dictation import audio_utils
from vosk_dictation import text_inserter

# Setup logging
logger = logging.getLogger(__name__)

def check_ydotool_permissions():
    """
    Check if ydotool has the necessary permissions to run without sudo.
    
    Returns:
        bool: True if permissions are set up correctly, False otherwise.
    """
    try:
        # Check if the ydotool socket exists and is accessible
        socket_path = "/tmp/.ydotool_socket"
        if not os.path.exists(socket_path):
            logger.warning(f"ydotool socket not found at {socket_path}")
            return False
            
        # Check if we have write permissions to the socket
        if not os.access(socket_path, os.W_OK):
            logger.warning(f"No write permissions for ydotool socket at {socket_path}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error checking ydotool permissions: {e}")
        return False

def setup_ydotool_permissions():
    """
    Set up the necessary permissions for ydotool to run without sudo.
    
    Returns:
        bool: True if setup was successful, False otherwise.
    """
    try:
        # Create a udev rule for ydotool
        rule_path = "/etc/udev/rules.d/60-ydotool.rules"
        rule_content = 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"'
        
        # Check if the rule already exists
        if os.path.exists(rule_path):
            with open(rule_path, 'r') as f:
                if rule_content in f.read():
                    logger.info("ydotool udev rule already exists")
                    return True
        
        # Create the rule
        print("Setting up ydotool permissions...")
        print("This requires sudo access to create a udev rule.")
        
        # Write the rule to a temporary file
        temp_rule_path = "/tmp/60-ydotool.rules"
        with open(temp_rule_path, 'w') as f:
            f.write(rule_content)
        
        # Copy the rule to the udev rules directory
        result = subprocess.run(
            ["sudo", "cp", temp_rule_path, rule_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to create udev rule: {result.stderr}")
            print(f"Failed to create udev rule: {result.stderr}")
            return False
        
        # Reload udev rules
        subprocess.run(["sudo", "udevadm", "control", "--reload-rules"])
        subprocess.run(["sudo", "udevadm", "trigger"])
        
        # Add the user to the input group
        username = os.getlogin()
        subprocess.run(["sudo", "usermod", "-aG", "input", username])
        
        print("ydotool permissions set up successfully.")
        print("Please log out and log back in for the changes to take effect.")
        
        return True
    except Exception as e:
        logger.error(f"Error setting up ydotool permissions: {e}")
        print(f"Error setting up ydotool permissions: {e}")
        return False

def is_ydotool_running():
    """
    Check if the ydotool daemon is running.
    
    Returns:
        bool: True if ydotool daemon is running, False otherwise.
    """
    try:
        result = subprocess.run(
            ["pgrep", "ydotoold"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error checking if ydotool is running: {e}")
        return False

def start_ydotool_daemon():
    """
    Start the ydotool daemon.
    
    Returns:
        bool: True if daemon was started successfully, False otherwise.
    """
    try:
        print("Starting ydotool daemon...")
        result = subprocess.run(
            ["sudo", "ydotoold"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        # Check if the daemon is running
        time.sleep(1)  # Give it a moment to start
        if is_ydotool_running():
            print("ydotool daemon started successfully.")
            return True
        else:
            print(f"Failed to start ydotool daemon: {result.stderr.decode()}")
            return False
    except Exception as e:
        logger.error(f"Error starting ydotool daemon: {e}")
        print(f"Error starting ydotool daemon: {e}")
        return False

def setup_virtual_env(base_dir):
    """
    Set up a virtual environment and install dependencies needed for the dictation tool.
    
    Args:
        base_dir (Path): Base directory of the project
        
    Returns:
        bool: True if setup was successful, False otherwise
    """
    try:
        venv_dir = base_dir / "venv"
        standalone_requirements = [
            "vosk==0.3.45",
            "sounddevice==0.4.6",
            "python-dotenv==1.0.0",
            "requests==2.31.0"
        ]
        
        # Use existing requirements file if it exists, otherwise create one
        standalone_req_file = base_dir / "requirements.txt"
        if not standalone_req_file.exists():
            with open(standalone_req_file, "w") as f:
                f.write("\n".join(standalone_requirements))
        
        # Check if virtual environment exists
        if not venv_dir.exists():
            print("Virtual environment not found. Creating one...")
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True
            )
            print("Virtual environment created successfully.")
        
        # Determine pip path
        if sys.platform == "win32":
            pip_path = venv_dir / "Scripts" / "pip"
        else:
            pip_path = venv_dir / "bin" / "pip"
        
        # Install dependencies
        print("Installing required dependencies...")
        subprocess.run(
            [str(pip_path), "install", "-r", str(standalone_req_file)],
            check=True
        )
        print("Dependencies installed successfully.")
        
        return True
    except Exception as e:
        print(f"Error setting up virtual environment: {e}")
        return False

class VoskDictation:
    """
    A standalone dictation tool using VOSK for speech recognition.
    
    This class provides a complete dictation solution with the ability to:
    - Recognize speech and insert it at the cursor position
    - Toggle between different insertion modes
    - Suspend and resume dictation
    - Control the dictation tool through voice commands or keyboard input
    """
    
    def __init__(
        self,
        language="en-US",
        model=None,
        config_dir=None,
        setup_ydotool=False,
        no_ydotool=False,
        text_entry_mode=True,
        device=None,
        sample_rate=16000,
        block_size=8000,
        insertion_method=None,
        silence_timeout=1.0
    ):
        """
        Initialize the VOSK dictation tool.
        
        Args:
            language (str): Language code to use
            model (str): Path to the VOSK model directory
            config_dir (str): Path to a custom config directory
            setup_ydotool (bool): Whether to set up ydotool permissions
            no_ydotool (bool): Whether to disable ydotool for input simulation
            text_entry_mode (bool): Whether to run in text entry mode
            device (int, optional): Audio device index to use for recording. None uses default device.
            sample_rate (int): Sample rate for audio recording (default: 16000)
            block_size (int): Block size for audio processing (default: 8000)
            insertion_method (str, optional): Text insertion method to use (ydotool, xdotool, wtype, clipboard, none)
            silence_timeout (float): Time in seconds to continue listening after speech has stopped (default: 1.0)
        """
        # Configuration
        self.language = language
        self.model_path = model
        self.config_dir = config_dir
        
        # Audio configuration
        self.device = device
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.silence_timeout = silence_timeout
        
        # State tracking
        self.is_listening = False
        self.is_suspended = False
        self.audio_thread = None
        self.stop_event = threading.Event()
        self.last_text = ""
        
        # Output configuration
        self.setup_ydotool = setup_ydotool
        self.no_ydotool = no_ydotool
        self.text_entry_mode = text_entry_mode
        
        # Determine the text insertion method to use
        available_methods = text_inserter.detect_available_methods()
        
        if insertion_method:
            # User specified a method, try to use it
            try:
                self.insertion_method = text_inserter.InsertionMethod(insertion_method.lower())
                if self.insertion_method not in available_methods:
                    logger.warning(f"Requested insertion method '{insertion_method}' is not available. Using fallback.")
                    self.insertion_method = available_methods[0] if available_methods else text_inserter.InsertionMethod.NONE
            except ValueError:
                logger.warning(f"Unknown insertion method '{insertion_method}'. Using default.")
                self.insertion_method = available_methods[0] if available_methods else text_inserter.InsertionMethod.NONE
        else:
            # No method specified, use ydotool if available and not disabled
            if not no_ydotool and text_inserter.InsertionMethod.YDOTOOL in available_methods:
                self.insertion_method = text_inserter.InsertionMethod.YDOTOOL
            elif available_methods:
                self.insertion_method = available_methods[0]
            else:
                self.insertion_method = text_inserter.InsertionMethod.NONE
                
        # For backward compatibility
        self.use_ydotool = self.insertion_method == text_inserter.InsertionMethod.YDOTOOL
        
        # Audio queue for processing
        self.audio_queue = queue.Queue()
        
        # Callback function for recognized text
        self.callback = None
        
        # Base directory for the project
        self.base_dir = Path(__file__).resolve().parent.parent
        
        # Check if dependencies are installed
        self._check_dependencies()
        
        # Set up signal handlers for suspend/resume
        signal.signal(signal.SIGUSR1, self._signal_handler)
        signal.signal(signal.SIGUSR2, self._signal_handler)
    
    def _check_dependencies(self):
        """Check if VOSK and ydotool are installed."""
        missing_deps = False
        try:
            # Check for VOSK
            try:
                import vosk
                logger.info("VOSK is installed.")
            except ImportError:
                print("VOSK not found. Please install it: pip install vosk")
                missing_deps = True
                
            # Check for sounddevice
            try:
                import sounddevice
                logger.info("sounddevice is installed.")
            except ImportError:
                print("sounddevice not found. Please install it: pip install sounddevice")
                missing_deps = True
                
            # Check for requests (needed for model download)
            try:
                import requests
                logger.info("requests is installed.")
            except ImportError:
                print("requests not found. Please install it: pip install requests")
                missing_deps = True
                
            # If dependencies are missing, try to set up virtual environment
            if missing_deps:
                print("\nSetting up virtual environment for VOSK dictation...")
                if setup_virtual_env(self.base_dir):
                    venv_activate = self.base_dir / "venv" / "bin" / "activate"
                    print(f"\nPlease activate the virtual environment and run again:")
                    print(f"  source {venv_activate}")
                    print(f"  python -m vosk_dictation.dictation --text-entry")
                    sys.exit(1)
                else:
                    print("Failed to set up virtual environment. Please install dependencies manually.")
                    sys.exit(1)
                
            # Check for ydotool
            if not self.no_ydotool:
                result = subprocess.run(["which", "ydotool"], 
                                      capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning("ydotool not found in PATH. Please install it for "
                                  "keyboard simulation functionality.")
                    print("ydotool not found. Please install it: sudo apt install ydotool")
                    print("Without ydotool, text will not be inserted at cursor position.")
                else:
                    # Check if ydotool daemon is running
                    if not is_ydotool_running():
                        print("ydotool daemon is not running. Starting it...")
                        if not start_ydotool_daemon():
                            print("Failed to start ydotool daemon. Please start it manually:")
                            print("  sudo ydotoold")
                            print("Without ydotool daemon, text will not be inserted at cursor position.")
                
        except Exception as e:
            logger.error(f"Error checking dependencies: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle signals for suspend/resume."""
        if signum == signal.SIGUSR1:
            # Suspend
            self.suspend()
        elif signum == signal.SIGUSR2:
            # Resume
            self.resume()
    
    def _get_model_path(self):
        """
        Get the path to the VOSK model.
        
        Returns:
            str: Path to the VOSK model directory
        """
        if self.model_path:
            return self.model_path
            
        # Check common locations
        common_locations = [
            os.path.expanduser("~/.cache/vosk"),
            os.path.expanduser("~/vosk-models"),
            "/usr/share/vosk",
            "/usr/local/share/vosk",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        ]
        
        # Add config directory if specified
        if self.config_dir:
            common_locations.insert(0, os.path.join(self.config_dir, "models"))
        
        # Check for model in common locations
        for location in common_locations:
            if os.path.exists(location):
                # Look for model directories
                for item in os.listdir(location):
                    if os.path.isdir(os.path.join(location, item)) and item.startswith(f"vosk-model-{self.language.lower()}"):
                        return os.path.join(location, item)
        
        # If no model found, use the small English model
        for location in common_locations:
            if os.path.exists(location):
                for item in os.listdir(location):
                    if os.path.isdir(os.path.join(location, item)) and item.startswith("vosk-model-small-en"):
                        return os.path.join(location, item)
        
        # If still no model found, return None
        return None
    
    def _download_model(self):
        """
        Download the VOSK model for the specified language.
        
        Returns:
            str: Path to the downloaded model directory, or None if download failed
        """
        try:
            import requests
            import zipfile
            import io
            
            # Create models directory in user's home cache directory
            cache_dir = os.path.expanduser("~/.cache/vosk")
            os.makedirs(cache_dir, exist_ok=True)
            
            # Known working model URLs are defined below, no need for these variables
            # We'll keep the URLs hardcoded for simplicity
            
            # Known working model URLs
            model_urls = [
                "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
                "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip"
            ]
            
            for url in model_urls:
                try:
                    print(f"Attempting to download model from {url}...")
                    response = requests.get(url, stream=True)
                    response.raise_for_status()  # Raise an exception for HTTP errors
                    
                    # Get the model name from the URL
                    model_name = os.path.basename(url).replace(".zip", "")
                    model_dir = os.path.join(cache_dir, model_name)
                    
                    # Extract the model
                    print("Downloading and extracting model...")
                    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                        # Create the model directory
                        os.makedirs(model_dir, exist_ok=True)
                        
                        # Check the structure of the ZIP file
                        zip_contents = zip_file.namelist()
                        zip_root_dirs = {item.split('/')[0] for item in zip_contents if '/' in item}
                        
                        # Create a temporary directory for extraction
                        temp_dir = os.path.join(cache_dir, "temp_extract")
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        # Extract to temporary directory first
                        zip_file.extractall(path=temp_dir)
                        
                        # Check for common model files in the extracted content
                        model_files = ['final.mdl', 'conf/mfcc.conf', 'ivector/final.ie']
                        model_found = False
                        
                        # Check if the model files are directly in the temp directory
                        if any(os.path.exists(os.path.join(temp_dir, f)) for f in model_files):
                            # Model files are at the root of the ZIP
                            if os.path.exists(model_dir):
                                import shutil
                                shutil.rmtree(model_dir)
                            os.rename(temp_dir, model_dir)
                            model_found = True
                        else:
                            # Check subdirectories for model files
                            for root_dir in zip_root_dirs:
                                root_path = os.path.join(temp_dir, root_dir)
                                if os.path.isdir(root_path) and any(os.path.exists(os.path.join(root_path, f)) for f in model_files):
                                    # Found model files in a subdirectory
                                    if os.path.exists(model_dir):
                                        import shutil
                                        shutil.rmtree(model_dir)
                                    os.rename(root_path, model_dir)
                                    model_found = True
                                    break
                        
                        # Clean up the temp directory if it still exists
                        if os.path.exists(temp_dir):
                            import shutil
                            shutil.rmtree(temp_dir)
                            
                        if not model_found:
                            print("Warning: Could not identify model files in the downloaded archive.")
                            print("The model may not work correctly.")
                    
                    print(f"Model downloaded and extracted to {model_dir}")
                    return model_dir
                    
                except requests.exceptions.HTTPError as e:
                    print(f"Error downloading model: {e}")
                    continue
                except Exception as e:
                    print(f"Error extracting model: {e}")
                    continue
            
            # If we get here, all download attempts failed
            print("Failed to download VOSK model. Please download it manually.")
            return None
            
        except Exception as e:
            logger.error(f"Error downloading model: {e}")
            print(f"Error downloading model: {e}")
            return None
    
    def _type_text(self, text, mode="append"):
        """Type text using the configured insertion method."""
        if not text:
            return False
            
        # First check if we can safely insert text
        can_insert = text_inserter.check_insertion_point()
        callback_called = False
        
        # If we have a callback, but we're not in text entry mode, use the callback
        if self.callback and not self.text_entry_mode:
            self.callback(text)
            return True
        
        # If we're in text entry mode, insert at cursor
        if self.text_entry_mode:
            try:
                # Try to insert text at cursor
                result = text_inserter.insert_text(text, self.insertion_method, mode)
                
                if result:
                    # Text was successfully inserted at cursor
                    return True
                else:
                    # Insertion failed, fall back to callback if available
                    if self.callback:
                        self.callback(text)
                        return True
                    else:
                        logger.info(f"Recognized text (not inserted): {text}")
                        return False
            except Exception as e:
                # Log the error and fall back to callback
                logger.error(f"Error inserting text: {e}")
                if self.callback:
                    self.callback(text)
                    return True
                else:
                    return False
        else:
            # In standard mode, try the normal insertion method
            if can_insert:
                result = text_inserter.insert_text(text, self.insertion_method, mode)
            else:
                result = False
            
            # Always notify the callback
            if self.callback and not callback_called:
                self.callback(text)
                return True
                
            return result
    
    def _type_with_ydotool(self, text, mode="append"):
        """
        Type text using ydotool with optimized error handling.
        This method is maintained for backward compatibility.
        
        Args:
            text (str): Text to type
            mode (str): Insertion mode - 'append', 'insert', or 'replace'
        
        Returns:
            bool: True if successful, False otherwise
        """
        # For backward compatibility, redirect to the new method
        return self._type_text(text, mode)
    
    def _process_audio(self, sounddevice, Model, KaldiRecognizer):
        """
        Process audio input using VOSK.
        
        Args:
            sounddevice: The sounddevice module
            Model: The VOSK Model class
            KaldiRecognizer: The VOSK KaldiRecognizer class
        """
        # Get the model path
        model_path = self._get_model_path()
        if not model_path:
            print("No VOSK model found. Attempting to download...")
            model_path = self._download_model()
            if not model_path:
                print("Failed to download VOSK model. Please download it manually.")
                return
        
        # Load the model
        print(f"Loading VOSK model from {model_path}...")
        model = Model(model_path)
        
        # Create a recognizer
        rec = KaldiRecognizer(model, self.sample_rate)
        
        # Start audio capture
        with sounddevice.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            dtype="int16",
            channels=1,
            device=self.device,
            callback=lambda indata, frames, time, status: self.audio_queue.put(bytes(indata))
        ):
            print("Listening... Speak to dictate text.")
            if self.text_entry_mode:
                print("Text entry mode: Dictated text will be inserted at cursor position.")
                print("Type 'toggle-mode' to switch to standard mode.")
            else:
                print("Standard mode: Dictated text will be appended with spaces.")
                print("Type 'toggle-mode' to switch to text entry mode.")
            
            print("Available commands: suspend, resume, restart, status, toggle-mode, exit, help")
            
            # Process audio until stopped
            # Variables for silence detection
            last_speech_time = None
            in_speech = False
            partial_speech = ""
            
            while not self.stop_event.is_set():
                # Skip processing if suspended
                if self.is_suspended:
                    time.sleep(0.1)
                    continue
                
                # Get audio data from queue with a shorter timeout for better responsiveness
                try:
                    data = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    # If we're in speech mode and silence timeout has elapsed, process any remaining speech
                    if in_speech and last_speech_time is not None:
                        silence_duration = time.time() - last_speech_time
                        if silence_duration > self.silence_timeout:
                            # Process any remaining partial speech
                            if partial_speech:
                                print(f"Processing after silence: {partial_speech}")
                                
                                # Process the partial speech
                                # If we're in text entry mode, insert at cursor first, then call callback
                                # Process partial speech based on text entry mode
                                if self.text_entry_mode:
                                    # In text entry mode, insert text at cursor and add a space
                                    # Try to insert text at cursor
                                    text_inserter.insert_text(partial_speech, self.insertion_method, "append")
                                
                                # Always call the callback to update the GUI
                                if self.callback:
                                    self.callback(partial_speech)
                                
                                # Reset speech tracking
                                partial_speech = ""
                                in_speech = False
                    continue
                
                # Check stop event again to ensure we can exit quickly
                if self.stop_event.is_set():
                    break
                
                # Get partial results to detect ongoing speech
                partial_result = json.loads(rec.PartialResult())
                if partial_result.get('partial', ''):
                    # Speech is happening
                    in_speech = True
                    last_speech_time = time.time()
                    new_partial = partial_result.get('partial', '')
                    
                    # Check if this is a new sentence starting
                    if new_partial and partial_speech and new_partial.strip() != partial_speech.strip():
                        # If the new partial starts with a capital letter and is shorter than previous partial,
                        # it's likely a new sentence
                        if (len(new_partial.strip()) < len(partial_speech.strip()) and 
                            new_partial.strip() and new_partial.strip()[0].isupper()):
                            # Process the previous complete sentence
                            if self.callback and partial_speech.strip():
                                self.callback(partial_speech.strip())
                            # Start a new sentence
                            partial_speech = new_partial
                        else:
                            partial_speech = new_partial
                    else:
                        partial_speech = new_partial
                
                # Process audio data for final results
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    recognized_text = result.get('text', '')
                    
                    if recognized_text:
                        print(f"Recognized: {recognized_text}")
                        
                        # Check if this is a continuation of the previous text or a new sentence
                        is_new_sentence = False
                        
                        # If we have previous text and this text starts with a capital letter,
                        # it's likely a new sentence
                        if (self.last_text and recognized_text and 
                            recognized_text[0].isupper() and 
                            not self.last_text.endswith('.') and 
                            not self.last_text.endswith('?') and 
                            not self.last_text.endswith('!')):
                            is_new_sentence = True
                        
                        # Store the recognized text
                        self.last_text = recognized_text
                        
                        # Update speech tracking
                        in_speech = True
                        last_speech_time = time.time()
                        partial_speech = ""
                        
                        # Process the recognized text
                        # If we're in text entry mode, insert at cursor first, then call callback
                        # Process the recognized text based on text entry mode
                        if self.text_entry_mode:
                            # In text entry mode, insert text at cursor and add a space
                            # Try to insert text at cursor
                            text_inserter.insert_text(recognized_text, self.insertion_method, "append")
                        
                        # Always call the callback to update the GUI
                        if self.callback:
                            self.callback(recognized_text)
    
    def start_listening(self):
        """Start listening for audio input."""
        if self.is_listening:
            print("Already listening.")
            return
            
        try:
            # Import required modules
            import vosk
            import sounddevice
            
            # Clear the stop event
            self.stop_event.clear()
            
            # Start the audio processing thread
            self.audio_thread = threading.Thread(
                target=self._process_audio,
                args=(sounddevice, vosk.Model, vosk.KaldiRecognizer)
            )
            self.audio_thread.daemon = True
            self.audio_thread.start()
            
            self.is_listening = True
            self.is_suspended = False
            
            # Start the command loop
            self._command_loop()
            
        except ImportError as e:
            print(f"Error importing required modules: {e}")
            print(f"Error: {e}")
            print("Please make sure you have the required packages installed:")
            print("  pip install vosk sounddevice")
            
        except Exception as e:
            logger.error(f"Error starting listener: {e}")
            print(f"Error starting listener: {e}")
    
    def stop_listening(self):
        """Stop listening for audio input."""
        if not self.is_listening:
            return
            
        # Set the stop event
        self.stop_event.set()
        
        # Clear the audio queue to prevent blocking
        try:
            while not self.audio_queue.empty():
                self.audio_queue.get_nowait()
        except Exception:
            pass
        
        # Wait for the audio thread to finish
        if self.audio_thread and self.audio_thread.is_alive():
            try:
                self.audio_thread.join(timeout=2)
                # If thread is still alive after timeout, we need to be more forceful
                if self.audio_thread.is_alive():
                    print("Warning: Audio thread did not terminate properly.")
            except Exception as e:
                print(f"Error stopping audio thread: {e}")
        
        # Reset state
        self.is_listening = False
        self.is_suspended = False
        print("Stopped listening.")
    
    def suspend(self):
        """Suspend listening temporarily."""
        if not self.is_listening or self.is_suspended:
            return
            
        self.is_suspended = True
        print("Dictation suspended. Type 'resume' to continue.")
    
    def resume(self):
        """Resume listening after suspension."""
        if not self.is_listening or not self.is_suspended:
            return
            
        self.is_suspended = False
        print("Dictation resumed. Speak to dictate text.")
    
    def restart(self):
        """Restart the listener."""
        self.stop_listening()
        time.sleep(0.5)
        self.start_listening()
        print("Dictation restarted.")
    
    def toggle_mode(self):
        """Toggle between text entry and standard modes."""
        self.text_entry_mode = not self.text_entry_mode
        if self.text_entry_mode:
            print("Switched to text entry mode: Dictated text will be inserted at cursor position.")
        else:
            print("Switched to standard mode: Dictated text will be appended with spaces.")
    
    def status(self):
        """Print the current status of the listener."""
        status_str = "Status: "
        if not self.is_listening:
            status_str += "Not listening"
        elif self.is_suspended:
            status_str += "Suspended"
        else:
            status_str += "Listening"
            
        mode_str = "Text entry mode" if self.text_entry_mode else "Standard mode"
        print(f"{status_str} ({mode_str})")
    
    def _command_loop(self):
        """Run the command loop for user input."""
        # Create a pipe for non-blocking input
        pipe_r, pipe_w = os.pipe()
        
        # Set the pipe to non-blocking mode
        os.set_blocking(pipe_r, False)
        
        # Create a thread to read from stdin and write to the pipe
        def stdin_reader():
            while not self.stop_event.is_set():
                try:
                    line = input()
                    os.write(pipe_w, f"{line}\n".encode())
                except (KeyboardInterrupt, EOFError):
                    self.stop_event.set()
                    break
        
        stdin_thread = threading.Thread(target=stdin_reader)
        stdin_thread.daemon = True
        stdin_thread.start()
        
        # Process commands
        while not self.stop_event.is_set():
            # Check for input
            r, _, _ = select.select([pipe_r], [], [], 0.1)
            if pipe_r in r:
                try:
                    command = os.read(pipe_r, 1024).decode().strip()
                    self._process_command(command)
                except Exception as e:
                    logger.error(f"Error processing command: {e}")
            
            time.sleep(0.1)
        
        # Clean up
        os.close(pipe_r)
        os.close(pipe_w)
    
    def _process_command(self, command):
        """
        Process a command from the user.
        
        Args:
            command (str): The command to process
        """
        if not command:
            return
            
        command = command.lower()
        
        if command in ["exit", "quit"]:
            print("Exiting...")
            self.stop_event.set()
            
        elif command in ["suspend", "pause"]:
            self.suspend()
            
        elif command in ["resume", "continue"]:
            self.resume()
            
        elif command == "restart":
            self.restart()
            
        elif command == "status":
            self.status()
            
        elif command == "toggle-mode":
            self.toggle_mode()
            
        elif command == "help":
            self._print_help()
            
        else:
            print(f"Unknown command: {command}")
            print("Type 'help' for a list of commands.")
    
    def _print_help(self):
        """Print help information."""
        print("\nVOSK Dictation - Available Commands:")
        print("  suspend, pause      - Temporarily stop listening")
        print("  resume, continue    - Resume listening after suspension")
        print("  restart             - Restart the listener")
        print("  status              - Show the current status")
        print("  toggle-mode         - Switch between text entry and standard modes")
        print("  exit, quit          - Exit the program")
        print("  help                - Show this help message")
        
        print("\nCurrent mode:")
        if self.text_entry_mode:
            print("  Text entry mode: Dictated text will be inserted at cursor position.")
        else:
            print("  Standard mode: Dictated text will be appended with spaces.")
    
    def _get_user_input(self, prompt="Command: "):
        """
        Get input from the user.
        
        Args:
            prompt (str): The prompt to display
            
        Returns:
            str: The text input by the user.
        """
        try:
            text = input(prompt)
            return text
        except (KeyboardInterrupt, EOFError):
            return None


def main():
    """
    Run the VOSK dictation tool as a standalone program.
    """
    import argparse
    
    # Check if we're in a virtual environment
    def is_in_virtualenv():
        return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="VOSK Dictation Tool")
    parser.add_argument("--model-dir", help="Path to the VOSK model directory")
    parser.add_argument("--config-dir", help="Path to a custom config directory")
    parser.add_argument("--language", default="en-US", help="Language code to use")
    parser.add_argument("--setup-ydotool", action="store_true", help="Set up ydotool permissions")
    parser.add_argument("--no-ydotool", action="store_true", help="Disable ydotool for input simulation")
    parser.add_argument("--text-entry", action="store_true", help="Run in text entry mode (insert at cursor position)")
    parser.add_argument("--setup", action="store_true", help="Set up virtual environment and install dependencies")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-venv-check", action="store_true", help="Skip virtual environment check")
    
    # Audio device options
    parser.add_argument("--list-devices", action="store_true", help="List available audio input devices and exit")
    parser.add_argument("--device", type=int, help="Audio device index to use for recording")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Sample rate for audio recording (default: 16000)")
    parser.add_argument("--block-size", type=int, default=8000, help="Block size for audio processing (default: 8000)")
    
    # Text insertion options
    parser.add_argument("--insertion-method", choices=["ydotool", "xdotool", "wtype", "clipboard", "none"],
                        help="Text insertion method to use")
    
    args = parser.parse_args()
    
    # Set up logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # List audio devices if requested
    if args.list_devices:
        audio_utils.list_audio_devices()
        sys.exit(0)
    
    # Get the base directory (project root)
    base_dir = Path(__file__).resolve().parent.parent
    
    # Check if we need to set up the virtual environment
    if not args.no_venv_check and (args.setup or not is_in_virtualenv()):
        if args.setup:
            print(f"Setting up VOSK dictation environment in {base_dir}...")
        elif not is_in_virtualenv():
            print("Not running in a virtual environment. Setting up...")
            
        if setup_virtual_env(base_dir):
            # If this is just a setup command, exit with instructions
            if args.setup:
                venv_activate = base_dir / "venv" / "bin" / "activate"
                if sys.platform == "win32":
                    venv_activate = base_dir / "venv" / "Scripts" / "activate.bat"
                print(f"\nSetup complete! To use the VOSK dictation tool:")
                print(f"1. Activate the virtual environment:")
                if sys.platform == "win32":
                    print(f"   {venv_activate}")
                else:
                    print(f"   source {venv_activate}")
                print(f"2. Run the dictation tool:")
                print(f"   python -m vosk_dictation.dictation --text-entry")
                sys.exit(0)
            # Otherwise, restart with the virtual environment
            elif not is_in_virtualenv():
                venv_python = base_dir / "venv" / "bin" / "python"
                if sys.platform == "win32":
                    venv_python = base_dir / "venv" / "Scripts" / "python.exe"
                    
                if venv_python.exists():
                    print(f"Restarting with virtual environment: {venv_python}")
                    # Add --no-venv-check to avoid infinite loop
                    new_args = sys.argv.copy()
                    if "--no-venv-check" not in new_args:
                        new_args.append("--no-venv-check")
                    os.execl(str(venv_python), str(venv_python), *new_args)
                    return  # This will not be reached if execl succeeds
                else:
                    print("Virtual environment created but Python executable not found.")
                    print("Continuing with system Python...")
        else:
            print("Failed to set up virtual environment.")
            if args.setup:
                sys.exit(1)
    
    # Create and start the dictation tool
    dictation = VoskDictation(
        language=args.language,
        model=args.model_dir,
        config_dir=args.config_dir,
        setup_ydotool=args.setup_ydotool,
        no_ydotool=args.no_ydotool,
        text_entry_mode=args.text_entry,
        device=args.device,
        sample_rate=args.sample_rate,
        block_size=args.block_size,
        insertion_method=args.insertion_method
    )
    
    # Set up ydotool permissions if requested
    if args.setup_ydotool:
        setup_ydotool_permissions()
    
    # Start the dictation tool
    dictation.start_listening()
    

if __name__ == "__main__":
    main()
