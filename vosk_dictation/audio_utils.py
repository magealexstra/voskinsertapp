#!/usr/bin/env python3
"""
Audio utilities for the VOSK dictation application.
"""

import logging

logger = logging.getLogger(__name__)

def get_audio_devices():
    """
    Get all available audio input devices.
    
    Returns:
        A list of dictionaries containing device information
    """
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = []
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    'index': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'default_samplerate': device['default_samplerate']
                })
                
        return input_devices
    except ImportError:
        logger.error("Error: sounddevice module not available.")
        return []
    except Exception as e:
        logger.error(f"Error getting audio devices: {e}")
        return []

def list_audio_devices():
    """
    List all available audio input devices.
    
    Returns:
        A list of dictionaries containing device information
    """
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = []
        
        print("Available audio input devices:")
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"[{i}] {device['name']} (Channels: {device['max_input_channels']}, Default Sample Rate: {device['default_samplerate']}Hz)")
                input_devices.append({
                    'index': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'default_samplerate': device['default_samplerate']
                })
                
        if not input_devices:
            print("No input devices found.")
            
        return input_devices
    except ImportError:
        print("Error: sounddevice module not available. Cannot list audio devices.")
        return []
    except Exception as e:
        print(f"Error listing audio devices: {e}")
        return []

def get_default_device():
    """
    Get the default audio input device.
    
    Returns:
        The index of the default input device, or None if not available
    """
    try:
        import sounddevice as sd
        return sd.default.device[0]  # Return default input device
    except ImportError:
        logger.error("Error: sounddevice module not available.")
        return None
    except Exception as e:
        logger.error(f"Error getting default device: {e}")
        return None

def get_device_sample_rate(device_index):
    """
    Get the default sample rate for a specific device.
    
    Args:
        device_index: The index of the device
        
    Returns:
        The default sample rate for the device, or 16000 if not available
    """
    try:
        import sounddevice as sd
        if device_index is not None:
            device_info = sd.query_devices(device_index)
            return int(device_info['default_samplerate'])
        return 16000  # Default sample rate
    except ImportError:
        logger.error("Error: sounddevice module not available.")
        return 16000
    except Exception as e:
        logger.error(f"Error getting device sample rate: {e}")
        return 16000
