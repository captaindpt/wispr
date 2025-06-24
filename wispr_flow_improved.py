#!/usr/bin/env python3
"""
Wispr Flow Clone - Improved Version
Voice-to-text with multiple trigger options for better compatibility
"""

import pyaudio
import websocket
import json
import threading
import time
from urllib.parse import urlencode
from datetime import datetime
import queue
import sys
import os
import argparse

# macOS-specific imports
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import Cocoa
from AppKit import NSPasteboard, NSStringPboardType
from ApplicationServices import CGEventCreateKeyboardEvent, CGEventPost, kCGHIDEventTap
import subprocess

# --- Configuration ---
YOUR_API_KEY = "ccd1e5d5bbd94d3bbb652eb35e219b09"  # Replace with your API key

CONNECTION_PARAMS = {
    "sample_rate": 16000,
    "format_turns": True,
}
API_ENDPOINT_BASE_URL = "wss://streaming.assemblyai.com/v3/ws"
API_ENDPOINT = f"{API_ENDPOINT_BASE_URL}?{urlencode(CONNECTION_PARAMS)}"

# Audio Configuration
FRAMES_PER_BUFFER = 800
SAMPLE_RATE = CONNECTION_PARAMS["sample_rate"]
CHANNELS = 1
FORMAT = pyaudio.paInt16

class WisprFlowImproved:
    def __init__(self, trigger_key='fn'):
        self.audio = None
        self.stream = None
        self.ws_app = None
        self.audio_thread = None
        self.ws_thread = None
        self.stop_event = threading.Event()
        self.recording = False
        self.final_transcript = ""
        self.trigger_key = trigger_key
        self.trigger_pressed = False
        
        # Initialize PyAudio
        try:
            self.audio = pyaudio.PyAudio()
            print("✅ Audio system initialized")
        except Exception as e:
            print(f"❌ Failed to initialize audio: {e}")
            sys.exit(1)
        
        print(f"🚀 Wispr Flow started with trigger: {trigger_key}")
        print("📋 Hold your trigger key to record, release to transcribe and paste.")
        print("🔘 Press ESC to exit")

    def test_microphone(self):
        """Test if microphone is accessible"""
        try:
            test_stream = self.audio.open(
                input=True,
                frames_per_buffer=1024,
                channels=CHANNELS,
                format=FORMAT,
                rate=SAMPLE_RATE,
            )
            # Record a brief test
            test_data = test_stream.read(1024, exception_on_overflow=False)
            test_stream.stop_stream()
            test_stream.close()
            print("✅ Microphone test successful")
            return True
        except Exception as e:
            print(f"❌ Microphone test failed: {e}")
            return False

    def on_ws_open(self, ws):
        """WebSocket connection established"""
        print("🔗 Connected to transcription service")
        
        def stream_audio():
            print("🎤 Recording...")
            while self.recording and not self.stop_event.is_set():
                try:
                    if self.stream and self.stream.is_active():
                        audio_data = self.stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                        ws.send(audio_data, websocket.ABNF.OPCODE_BINARY)
                except Exception as e:
                    print(f"❌ Audio streaming error: {e}")
                    break
            print("🛑 Recording stopped")
        
        self.audio_thread = threading.Thread(target=stream_audio)
        self.audio_thread.daemon = True
        self.audio_thread.start()

    def on_ws_message(self, ws, message):
        """Handle WebSocket messages"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == "Begin":
                session_id = data.get('id')
                print(f"📝 Session: {session_id[:8]}...")
                
            elif msg_type == "Turn":
                transcript = data.get('transcript', '').strip()
                formatted = data.get('turn_is_formatted', False)
                
                if formatted and transcript:
                    self.final_transcript = transcript
                    print(f"💬 \"{transcript}\"")
                elif transcript:
                    # Show partial transcript with carriage return
                    print(f"\r💭 {transcript}...", end='', flush=True)
                    
            elif msg_type == "Termination":
                print("\n🔚 Session ended")
                if self.final_transcript:
                    self.paste_text(self.final_transcript)
                    
        except Exception as e:
            print(f"❌ Message handling error: {e}")

    def on_ws_error(self, ws, error):
        """WebSocket error handler"""
        print(f"❌ Connection error: {error}")
        self.stop_event.set()

    def on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket close handler"""
        if close_status_code:
            print(f"🔌 Disconnected: {close_status_code}")
        self.cleanup_audio()

    def start_recording(self):
        """Start audio recording and transcription"""
        if self.recording:
            return
            
        self.recording = True
        self.final_transcript = ""
        self.stop_event.clear()
        
        try:
            # Open microphone stream
            self.stream = self.audio.open(
                input=True,
                frames_per_buffer=FRAMES_PER_BUFFER,
                channels=CHANNELS,
                format=FORMAT,
                rate=SAMPLE_RATE,
            )
            
            # Create WebSocket connection
            self.ws_app = websocket.WebSocketApp(
                API_ENDPOINT,
                header={"Authorization": YOUR_API_KEY},
                on_open=self.on_ws_open,
                on_message=self.on_ws_message,
                on_error=self.on_ws_error,
                on_close=self.on_ws_close,
            )
            
            # Start WebSocket
            self.ws_thread = threading.Thread(target=self.ws_app.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
        except Exception as e:
            print(f"❌ Recording start error: {e}")
            self.recording = False

    def stop_recording(self):
        """Stop recording and get transcription"""
        if not self.recording:
            return
            
        self.recording = False
        
        # Send termination to get final transcript
        if self.ws_app and hasattr(self.ws_app, 'sock') and self.ws_app.sock:
            try:
                terminate_message = {"type": "Terminate"}
                self.ws_app.send(json.dumps(terminate_message))
                time.sleep(1.0)  # Wait for final transcription
            except Exception as e:
                print(f"❌ Termination error: {e}")
        
        # Close WebSocket
        if self.ws_app:
            self.ws_app.close()
            
        self.cleanup_audio()

    def cleanup_audio(self):
        """Clean up audio resources"""
        if self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except:
                pass
            self.stream = None

    def paste_text(self, text):
        """Paste text at cursor location"""
        try:
            # Copy to clipboard
            pasteboard = NSPasteboard.generalPasteboard()
            pasteboard.clearContents()
            pasteboard.setString_forType_(text, NSStringPboardType)
            
            # Paste with short delay
            time.sleep(0.1)
            
            # Use AppleScript for more reliable paste
            script = 'tell application "System Events" to keystroke "v" using command down'
            subprocess.run(['osascript', '-e', script], check=True)
            
            print(f"📋 Pasted: \"{text}\"")
            
        except Exception as e:
            print(f"❌ Paste error: {e}")
            print(f"📝 Text was: \"{text}\"")

    def is_trigger_key(self, key):
        """Check if the pressed key is our trigger"""
        if self.trigger_key == 'fn':
            # Try multiple ways to detect Fn key
            return (
                key == Key.fn or
                (hasattr(key, 'vk') and key.vk == 179) or  # Some systems
                (hasattr(key, 'char') and key.char == 'fn')
            )
        elif self.trigger_key == 'right_cmd':
            return key == Key.cmd_r
        elif self.trigger_key == 'right_ctrl':
            return key == Key.ctrl_r
        elif self.trigger_key == 'right_alt':
            return key == Key.alt_r
        elif self.trigger_key == 'caps_lock':
            return key == Key.caps_lock
        elif self.trigger_key == 'f13':
            return (hasattr(key, 'vk') and key.vk == 105)  # F13 key
        elif self.trigger_key == 'backslash':
            return (hasattr(key, 'char') and key.char == '\\')
        else:
            return False

    def on_key_press(self, key):
        """Handle key press events"""
        if self.is_trigger_key(key) and not self.trigger_pressed:
            self.trigger_pressed = True
            threading.Thread(target=self.start_recording, daemon=True).start()

    def on_key_release(self, key):
        """Handle key release events"""
        if self.is_trigger_key(key) and self.trigger_pressed:
            self.trigger_pressed = False
            threading.Thread(target=self.stop_recording, daemon=True).start()
        elif key == Key.esc:
            print("👋 Goodbye!")
            return False

    def run(self):
        """Main application loop"""
        # Test microphone first
        if not self.test_microphone():
            print("❌ Microphone not accessible. Check permissions.")
            return
        
        try:
            # Set up global key listener
            with keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release,
                suppress=False  # Don't suppress other key events
            ) as listener:
                listener.join()
                
        except KeyboardInterrupt:
            print("\n👋 Interrupted")
        except Exception as e:
            print(f"❌ Listener error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Final cleanup"""
        self.stop_event.set()
        if self.recording:
            self.stop_recording()
        if self.audio:
            self.audio.terminate()
        print("🧹 Cleanup complete")

def main():
    """Entry point with argument parsing"""
    parser = argparse.ArgumentParser(description='Wispr Flow Clone - Voice to Text')
    parser.add_argument('--trigger', 
                       choices=['fn', 'right_cmd', 'right_ctrl', 'right_alt', 'caps_lock', 'f13', 'backslash'],
                       default='fn',
                       help='Key to use as recording trigger (default: fn)')
    parser.add_argument('--test-mic', action='store_true', help='Test microphone and exit')
    
    args = parser.parse_args()
    
    if args.test_mic:
        app = WisprFlowImproved()
        success = app.test_microphone()
        sys.exit(0 if success else 1)
    
    print("🚀 Starting Wispr Flow...")
    print("📋 Ensure Accessibility and Microphone permissions are granted")
    print(f"🎯 Trigger key: {args.trigger}")
    
    app = WisprFlowImproved(trigger_key=args.trigger)
    app.run()

if __name__ == "__main__":
    main() 