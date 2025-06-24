#!/usr/bin/env python3
"""
Wispr Flow Clone using native macOS Cocoa APIs for proper key detection
Based on https://gist.github.com/ljos/3019549
"""

import os
import sys
import time
import json
import threading
import subprocess
import websocket
import pyaudio
from dotenv import load_dotenv

# macOS native imports
from AppKit import NSApplication, NSApp, NSWorkspace
from Foundation import NSObject, NSLog, NSRunLoop, NSDefaultRunLoopMode
from Cocoa import NSEvent, NSKeyDownMask, NSKeyUpMask, NSFlagsChangedMask
from PyObjCTools import AppHelper
from AppKit import NSPasteboard, NSStringPboardType

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
TRIGGER_KEY = os.getenv('WISPR_TRIGGER_KEY', 'fn')

if not API_KEY or API_KEY == 'your_api_key_here':
    print("❌ Please edit .env and add your AssemblyAI API key")
    print("Get one free at: https://www.assemblyai.com/")
    sys.exit(1)

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
FRAMES_PER_BUFFER = 800

# AssemblyAI settings
API_ENDPOINT = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={SAMPLE_RATE}"
YOUR_API_KEY = f"Bearer {API_KEY}"

class WisprCocoa(NSObject):
    def init(self):
        self = NSObject.init()
        if self is None:
            return None
            
        self.trigger_pressed = False
        self.recording = False
        self.final_transcript = ""
        self.audio = None
        self.stream = None
        self.ws_app = None
        self.ws_thread = None
        self.stop_event = threading.Event()
        
        # Initialize audio
        self.init_audio()
        
        print("🚀 Wispr Flow (Cocoa) started")
        print(f"🎯 Trigger key: {TRIGGER_KEY}")
        print("📋 Hold your trigger key to record, release to transcribe and paste")
        
        return self
    
    def init_audio(self):
        """Initialize PyAudio"""
        try:
            self.audio = pyaudio.PyAudio()
            print("✅ Audio system initialized")
        except Exception as e:
            print(f"❌ Audio initialization failed: {e}")
            sys.exit(1)
    
    def applicationDidFinishLaunching_(self, notification):
        """Called when app finishes launching"""
        mask = NSKeyDownMask | NSKeyUpMask | NSFlagsChangedMask
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, self.handle_key_event)
        print("✅ Global key monitoring started")
    
    def handle_key_event(self, event):
        """Handle global key events"""
        try:
            event_type = event.type()
            key_code = event.keyCode()
            flags = event.modifierFlags()
            
            # Debug output
            print(f"🔘 Event: type={event_type}, keyCode={key_code}, flags={flags}")
            
            # Check for trigger key based on configuration
            is_trigger = self.is_trigger_key(key_code, flags, event_type)
            
            if event_type == NSKeyDownMask or event_type == NSFlagsChangedMask:
                if is_trigger and not self.trigger_pressed:
                    print("🎤 Recording started...")
                    self.trigger_pressed = True
                    threading.Thread(target=self.start_recording, daemon=True).start()
            
            elif event_type == NSKeyUpMask or event_type == NSFlagsChangedMask:
                if is_trigger and self.trigger_pressed:
                    print("🛑 Recording stopped...")
                    self.trigger_pressed = False
                    threading.Thread(target=self.stop_recording, daemon=True).start()
                    
        except Exception as e:
            print(f"❌ Key event error: {e}")
    
    def is_trigger_key(self, key_code, flags, event_type):
        """Check if this is our trigger key"""
        if TRIGGER_KEY == 'fn':
            # Fn key is keyCode 63 and often comes with special flags
            return key_code == 63 or (flags & 0x800000)  # NSFunctionKeyMask
        elif TRIGGER_KEY == 'right_cmd':
            return key_code == 54  # Right Command key
        elif TRIGGER_KEY == 'right_ctrl':
            return key_code == 62  # Right Control key
        elif TRIGGER_KEY == 'caps_lock':
            return key_code == 57  # Caps Lock key
        elif TRIGGER_KEY == 'f13':
            return key_code == 105  # F13 key
        elif TRIGGER_KEY == 'backslash':
            return key_code == 42  # Backslash key
        else:
            return False
    
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
    
    def on_ws_open(self, ws):
        """WebSocket connection opened"""
        print("🔗 Connected to AssemblyAI")
        
        def stream_audio():
            while self.recording and not self.stop_event.is_set():
                try:
                    data = self.stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                    ws.send(data, websocket.ABNF.OPCODE_BINARY)
                except Exception as e:
                    print(f"❌ Streaming error: {e}")
                    break
        
        threading.Thread(target=stream_audio, daemon=True).start()
    
    def on_ws_message(self, ws, message):
        """Handle WebSocket messages"""
        try:
            data = json.loads(message)
            if data.get("message_type") == "FinalTranscript":
                text = data.get("text", "").strip()
                if text:
                    print(f"📝 Transcribed: \"{text}\"")
                    self.final_transcript = text
                    self.paste_text(text)
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

def main():
    """Main entry point"""
    print("🎤 Starting Wispr Flow (Cocoa)...")
    print("📋 Make sure to grant Accessibility and Microphone permissions")
    
    # Create app
    app = NSApplication.sharedApplication()
    delegate = WisprCocoa.alloc().init()
    app.setDelegate_(delegate)
    
    try:
        # Run the event loop
        AppHelper.runEventLoop()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Application error: {e}")
    finally:
        if delegate.audio:
            delegate.audio.terminate()

if __name__ == "__main__":
    main() 