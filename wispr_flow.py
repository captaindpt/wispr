#!/usr/bin/env python3
"""
Wispr Flow Clone - Voice-to-text with Fn key trigger
Hold Fn key to record, release to transcribe and paste at cursor
"""

import pyaudio
import websocket
import json
import threading
import time
from urllib.parse import urlencode
import sys
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

# macOS-specific imports
import Quartz
from AppKit import NSPasteboard, NSStringPboardType
from Cocoa import (
    NSEvent, NSEventMaskFlagsChanged, NSEventModifierFlagFunction,
    NSApplication, NSApplicationActivationPolicyProhibited
)
import objc

# --- Configuration ---
YOUR_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
if not YOUR_API_KEY:
    print("❌ Error: ASSEMBLYAI_API_KEY not found in environment variables")
    print("Please create a .env file with your AssemblyAI API key")
    sys.exit(1)

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

class WisprFlow:
    def __init__(self):
        self.audio = None
        self.stream = None
        self.ws_app = None
        self.audio_thread = None
        self.ws_thread = None
        self.stop_event = threading.Event()
        self.recording = False
        self.final_transcript = ""
        self.fn_pressed = False
        self.running = True
        
        # Initialize PyAudio
        try:
            self.audio = pyaudio.PyAudio()
            print("✅ Audio system initialized")
        except Exception as e:
            print(f"❌ Failed to initialize audio: {e}")
            sys.exit(1)
        
        print("🚀 Wispr Flow started")
        print("📋 Hold Fn key to record, release to transcribe and paste")
        print("🔘 Press Ctrl+C to exit")

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
                    # Show partial transcript
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
            
            # Paste with AppleScript for reliability
            time.sleep(0.1)
            script = 'tell application "System Events" to keystroke "v" using command down'
            subprocess.run(['osascript', '-e', script], check=True)
            
            print(f"📋 Pasted: \"{text}\"")
            
        except Exception as e:
            print(f"❌ Paste error: {e}")
            print(f"📝 Text was: \"{text}\"")

    def handle_fn_key_event(self, event):
        """Handle Fn key press/release events"""
        try:
            flags = event.modifierFlags()
            fn_currently_pressed = bool(flags & NSEventModifierFlagFunction)
            
            if fn_currently_pressed and not self.fn_pressed:
                # Fn key was just pressed
                self.fn_pressed = True
                threading.Thread(target=self.start_recording, daemon=True).start()
                
            elif not fn_currently_pressed and self.fn_pressed:
                # Fn key was just released
                self.fn_pressed = False
                threading.Thread(target=self.stop_recording, daemon=True).start()
                
        except Exception as e:
            print(f"❌ Key event error: {e}")

    def run(self):
        """Main application loop with Fn key monitoring"""
        # Test microphone first
        if not self.test_microphone():
            print("❌ Microphone not accessible. Check permissions.")
            return
            
        try:
            # Set up NSApplication for event monitoring
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)
            
            # Monitor for flag changed events (modifier keys)
            NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskFlagsChanged,
                self.handle_fn_key_event
            )
            
            print("✅ Fn key monitoring started")
            
            # Keep the app running
            try:
                while self.running:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                self.running = False
                
        except Exception as e:
            print(f"❌ Event monitoring error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Final cleanup"""
        self.running = False
        self.stop_event.set()
        if self.recording:
            self.stop_recording()
        if self.audio:
            self.audio.terminate()
        print("🧹 Cleanup complete")

def main():
    """Entry point"""
    print("🚀 Starting Wispr Flow...")
    print("📋 Make sure to grant Accessibility and Microphone permissions")
    
    app = WisprFlow()
    app.run()

if __name__ == "__main__":
    main() 