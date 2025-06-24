#!/usr/bin/env python3
"""
Simple Wispr Flow implementation using Cocoa global key monitoring
Based on: https://gist.github.com/ljos/3019549
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

# macOS imports
from AppKit import NSApplication, NSApp
from Foundation import NSObject, NSLog
from Cocoa import NSEvent, NSKeyDownMask, NSKeyUpMask, NSFlagsChangedMask
from PyObjCTools import AppHelper
from AppKit import NSPasteboard, NSStringPboardType

# Load environment
load_dotenv()

# Config
API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
TRIGGER_KEY = os.getenv('WISPR_TRIGGER_KEY', 'fn')

if not API_KEY or API_KEY == 'your_api_key_here':
    print("❌ Please edit .env and add your AssemblyAI API key")
    sys.exit(1)

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
FRAMES_PER_BUFFER = 800  # 50ms chunks work fine with v3 API
from urllib.parse import urlencode

CONNECTION_PARAMS = {
    "sample_rate": SAMPLE_RATE,
    "format_turns": True,
}
API_ENDPOINT = f"wss://streaming.assemblyai.com/v3/ws?{urlencode(CONNECTION_PARAMS)}"
YOUR_API_KEY = API_KEY

# Global state
trigger_pressed = False
recording = False
connecting = False  # Track connection state
audio = None
stream = None
ws_app = None
ws_thread = None
stop_event = threading.Event()
final_transcript = ""
last_trigger_time = 0
DEBOUNCE_DELAY = 0.3 # 300ms debounce

def init_audio():
    """Initialize PyAudio"""
    global audio
    try:
        audio = pyaudio.PyAudio()
        print("✅ Audio system initialized")
        return True
    except Exception as e:
        print(f"❌ Audio initialization failed: {e}")
        return False

def is_trigger_key(key_code, flags):
    """Check if this is our trigger key"""
    if TRIGGER_KEY == 'fn':
        # Fn key is code=63, detect by flags: 0x800000 = pressed, 0x100 = released
        return key_code == 63
    elif TRIGGER_KEY == 'right_cmd':
        return key_code == 54
    elif TRIGGER_KEY == 'right_ctrl':
        return key_code == 62
    elif TRIGGER_KEY == 'caps_lock':
        return key_code == 57
    elif TRIGGER_KEY == 'backslash':
        return key_code == 42
    else:
        return False

def is_fn_pressed(flags):
    """Check if Fn key is currently pressed based on flags"""
    return (flags & 0x800000) != 0  # NSFunctionKeyMask

def on_ws_open(ws):
    """WebSocket opened"""
    global recording, connecting
    print("🔗 Connected to AssemblyAI")
    connecting = False
    recording = True
    
    def stream_audio():
        global recording, stream, stop_event
        while recording and not stop_event.is_set():
            try:
                if stream and stream.is_active():
                    data = stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                    ws.send(data, websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                print(f"❌ Streaming error: {e}")
                break
    
    threading.Thread(target=stream_audio, daemon=True).start()

def on_ws_message(ws, message):
    """Handle WebSocket message"""
    global final_transcript
    try:
        data = json.loads(message)
        msg_type = data.get('type')
        
        if msg_type == "Begin":
            session_id = data.get('id')
            print(f"🔗 Session started: {session_id}")
        elif msg_type == "Turn":
            transcript = data.get('transcript', '')
            formatted = data.get('turn_is_formatted', False)
            if formatted:
                transcript_text = transcript.strip()
                if transcript_text:
                    # Accumulate all transcript segments, don't replace!
                    if final_transcript:
                        final_transcript += " " + transcript_text
                    else:
                        final_transcript = transcript_text
                    print(f"📝 Added segment: \"{transcript_text}\"")
                    print(f"📝 Full transcript so far: \"{final_transcript}\"")
                    # Don't paste yet! Wait for Fn key release
            else:
                # Partial transcript, show as it comes
                print(f"\r{transcript}", end='')
        elif msg_type == "Termination":
            print("🔚 Session terminated")
    except Exception as e:
        print(f"❌ Message handling error: {e}")

def on_ws_error(ws, error):
    """WebSocket error"""
    print(f"❌ Connection error: {error}")
    stop_event.set()

def on_ws_close(ws, close_status_code, close_msg):
    """WebSocket closed"""
    global recording, connecting
    if close_status_code:
        print(f"🔌 Disconnected: {close_status_code}")
    recording = False
    connecting = False
    cleanup_audio()

def start_recording():
    """Start recording"""
    global recording, connecting, stream, ws_app, ws_thread, stop_event, final_transcript
    
    if recording or connecting:
        return
    
    connecting = True
    recording = False
    final_transcript = ""
    stop_event.clear()
    
    try:
        # Open microphone
        stream = audio.open(
            input=True,
            frames_per_buffer=FRAMES_PER_BUFFER,
            channels=CHANNELS,
            format=FORMAT,
            rate=SAMPLE_RATE,
        )
        
        # Create WebSocket
        ws_app = websocket.WebSocketApp(
            API_ENDPOINT,
            header={"Authorization": YOUR_API_KEY},
            on_open=on_ws_open,
            on_message=on_ws_message,
            on_error=on_ws_error,
            on_close=on_ws_close,
        )
        
        # Start WebSocket in thread
        ws_thread = threading.Thread(target=ws_app.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
    except Exception as e:
        print(f"❌ Recording start error: {e}")
        connecting = False
        recording = False

def stop_recording():
    """Stop recording"""
    global recording, connecting, ws_app, final_transcript
    
    if not recording and not connecting:
        return
    
    recording = False
    connecting = False
    
    # Send termination
    if ws_app and hasattr(ws_app, 'sock') and ws_app.sock and ws_app.sock.connected:
        try:
            terminate_message = {"type": "Terminate"}
            ws_app.send(json.dumps(terminate_message))
            time.sleep(0.1)  # Shorter wait
        except Exception as e:
            print(f"❌ Termination error: {e}")
    
    # Close WebSocket
    if ws_app:
        ws_app.close()
    
    # NOW paste the final transcript when Fn key is released
    if final_transcript:
        print(f"📋 Pasting: \"{final_transcript}\"")
        paste_text(final_transcript)
        final_transcript = ""  # Clear it
    
    cleanup_audio()

def cleanup_audio():
    """Clean up audio"""
    global stream
    if stream:
        try:
            if stream.is_active():
                stream.stop_stream()
            stream.close()
        except:
            pass
        stream = None

def paste_text(text):
    """Paste text at cursor"""
    try:
        # Copy to clipboard
        pasteboard = NSPasteboard.generalPasteboard()
        pasteboard.clearContents()
        pasteboard.setString_forType_(text, NSStringPboardType)
        
        # Paste
        time.sleep(0.1)
        script = 'tell application "System Events" to keystroke "v" using command down'
        subprocess.run(['osascript', '-e', script], check=True)
        
        print(f"📋 Pasted: \"{text}\"")
        
    except Exception as e:
        print(f"❌ Paste error: {e}")

def handler(event):
    """Global key event handler"""
    global trigger_pressed, last_trigger_time
    
    current_time = time.time()
    if current_time - last_trigger_time < DEBOUNCE_DELAY:
        return # Debounce

    try:
        event_type = event.type()
        key_code = event.keyCode()
        flags = event.modifierFlags()
        
        # Debug output - remove this line to reduce noise
        # print(f"🔘 Key: type={event_type}, code={key_code}, flags={flags}")
        
        is_trigger = is_trigger_key(key_code, flags)
        
        # Special handling for Fn key based on flags
        if TRIGGER_KEY == 'fn' and is_trigger:
            fn_currently_pressed = is_fn_pressed(flags)
            
            if fn_currently_pressed and not trigger_pressed:
                print("🎤 Recording started...")
                trigger_pressed = True
                last_trigger_time = current_time
                threading.Thread(target=start_recording, daemon=True).start()
            elif not fn_currently_pressed and trigger_pressed:
                print("🛑 Recording stopped...")
                trigger_pressed = False
                last_trigger_time = current_time
                threading.Thread(target=stop_recording, daemon=True).start()
        
        # Regular key handling for other trigger keys
        elif TRIGGER_KEY != 'fn' and is_trigger:
            # Key down or flags changed (for modifier keys)
            if (event_type == NSKeyDownMask or event_type == NSFlagsChangedMask) and not trigger_pressed:
                print("🎤 Recording started...")
                trigger_pressed = True
                last_trigger_time = current_time
                threading.Thread(target=start_recording, daemon=True).start()
            
            # Key up or flags changed (for modifier keys)
            elif (event_type == NSKeyUpMask or event_type == NSFlagsChangedMask) and trigger_pressed:
                print("🛑 Recording stopped...")
                trigger_pressed = False
                last_trigger_time = current_time
                threading.Thread(target=stop_recording, daemon=True).start()
        
    except Exception as e:
        print(f"❌ Key handler error: {e}")

class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        """App finished launching"""
        mask = NSKeyDownMask | NSKeyUpMask | NSFlagsChangedMask
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, handler)
        print("✅ Global key monitoring started")

def main():
    """Main function"""
    print("🎤 Starting Wispr Flow (Simple)...")
    print("📋 Make sure to grant Accessibility and Microphone permissions")
    print(f"🎯 Trigger key: {TRIGGER_KEY}")
    
    if not init_audio():
        sys.exit(1)
    
    # Create NSApplication
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    NSApp().setDelegate_(delegate)
    
    try:
        AppHelper.runEventLoop()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if audio:
            audio.terminate()

if __name__ == "__main__":
    main() 