#!/usr/bin/env python3
"""
Wispr - Voice-to-Text Transcription Service for macOS
Professional background service with Fn key trigger and auto-paste functionality
"""

import os
import sys
import time
import json
import threading
import subprocess
import websocket
import pyaudio
import wave
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# macOS imports
from AppKit import NSApplication, NSApp
from Foundation import NSObject, NSLog
from Cocoa import NSEvent, NSKeyDownMask, NSKeyUpMask, NSFlagsChangedMask
from PyObjCTools import AppHelper
from AppKit import NSPasteboard, NSStringPboardType

# Load environment
load_dotenv()

# Configure logging
def setup_logging():
    """Setup logging to standard macOS location"""
    log_dir = Path.home() / "Library" / "Logs" / "Wispr"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "wispr.log"
    transcript_log_file = log_dir / "transcriptions.log"
    
    # Configure main app logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Configure transcript logging (separate file for all voice interactions)
    transcript_logger = logging.getLogger('wispr.transcripts')
    transcript_handler = logging.FileHandler(transcript_log_file)
    transcript_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    transcript_logger.addHandler(transcript_handler)
    transcript_logger.setLevel(logging.INFO)
    transcript_logger.propagate = False  # Don't propagate to main logger
    
    return logging.getLogger('wispr'), transcript_logger

logger, transcript_logger = setup_logging()

# Config
API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
TRIGGER_KEY = os.getenv('WISPR_TRIGGER_KEY', 'fn')

if not API_KEY or API_KEY == 'your_api_key_here':
    logger.error("Please edit .env and add your AssemblyAI API key")
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
connection_active = False  # Track if we have an active connection
audio = None
stream = None
ws_app = None
ws_thread = None
stop_event = threading.Event()
final_transcript = ""
last_trigger_time = 0
last_stop_time = 0
recording_start_time = 0  # Track actual recording start
DEBOUNCE_DELAY = 0.3 # 300ms debounce
MIN_RECORDING_DURATION = 0.5  # 500ms minimum recording
CONNECTION_COOLDOWN = 2.0  # 2 seconds between connections (more conservative)

def init_audio():
    """Initialize PyAudio"""
    global audio
    try:
        audio = pyaudio.PyAudio()
        logger.info("✅ Audio system initialized")
        return True
    except Exception as e:
        logger.error(f"❌ Audio initialization failed: {e}")
        return False

def play_sound(sound_file):
    """Play a sound file asynchronously"""
    def _play():
        try:
            # Use macOS built-in afplay for simple and reliable playback
            subprocess.run(['afplay', sound_file], check=True, capture_output=True)
        except Exception as e:
            logger.error(f"❌ Sound playback error: {e}")
    
    # Play sound in background thread to not block main functionality
    threading.Thread(target=_play, daemon=True).start()

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
    global recording, connecting, recording_start_time, connection_active
    logger.info("🔗 Connected to AssemblyAI")
    connecting = False
    recording = True
    connection_active = True
    recording_start_time = time.time()  # Set actual recording start time
    
    def stream_audio():
        global recording, stream, stop_event
        while recording and not stop_event.is_set():
            try:
                if stream and stream.is_active():
                    data = stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                    ws.send(data, websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                logger.error(f"❌ Streaming error: {e}")
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
            logger.info(f"🔗 Session started: {session_id}")
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
                    logger.info(f"📝 Added segment: \"{transcript_text}\"")
                    logger.info(f"📝 Full transcript so far: \"{final_transcript}\"")
                    # Log transcript segment to dedicated log
                    transcript_logger.info(f"SEGMENT: {transcript_text}")
                    # Don't paste yet! Wait for Fn key release
            else:
                # Partial transcript, show as it comes
                logger.info(f"\r{transcript}", end='')
        elif msg_type == "Termination":
            logger.info("🔚 Session terminated")
    except Exception as e:
        logger.error(f"❌ Message handling error: {e}")

def on_ws_error(ws, error):
    """WebSocket error"""
    global recording, connecting, connection_active
    logger.error(f"❌ Connection error: {error}")
    stop_event.set()
    recording = False
    connecting = False
    connection_active = False

def on_ws_close(ws, close_status_code, close_msg):
    """WebSocket closed"""
    global recording, connecting, last_stop_time, connection_active
    if close_status_code:
        logger.warning(f"🔌 Disconnected: {close_status_code}")
        if close_status_code == 1008:
            logger.warning("⚠️ Policy violation detected - enforcing longer cooldown")
            last_stop_time = time.time()  # Force cooldown
    recording = False
    connecting = False
    connection_active = False
    cleanup_audio()

def start_recording():
    """Start recording"""
    global recording, connecting, stream, ws_app, ws_thread, stop_event, final_transcript, last_stop_time, connection_active
    
    if recording or connecting or connection_active:
        logger.warning("⚠️ Recording already in progress or connection active")
        return
    
    # Enforce connection cooldown (longer after 1008 errors)
    current_time = time.time()
    cooldown_needed = CONNECTION_COOLDOWN
    if current_time - last_stop_time < cooldown_needed:
        logger.info(f"⏳ Connection cooldown: {cooldown_needed - (current_time - last_stop_time):.1f}s remaining")
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
        logger.error(f"❌ Recording start error: {e}")
        connecting = False
        recording = False
        connection_active = False

def stop_recording():
    """Stop recording"""
    global recording, connecting, ws_app, final_transcript, recording_start_time, last_stop_time, ws_thread, connection_active
    
    if not recording and not connecting and not connection_active:
        return
    
    # Check minimum recording duration (only if we actually started recording)
    current_time = time.time()
    if recording_start_time > 0:
        recording_duration = current_time - recording_start_time
        
        if recording_duration < MIN_RECORDING_DURATION:
            logger.warning(f"⚠️ Recording too short ({recording_duration:.1f}s < {MIN_RECORDING_DURATION}s), ignoring")
            recording = False
            connecting = False
            connection_active = False
            recording_start_time = 0
            cleanup_audio()
            return
    elif connecting:
        # If we're still connecting, don't allow immediate stop
        logger.warning(f"⚠️ Still connecting, ignoring rapid stop")
        return
    
    recording = False
    connecting = False
    connection_active = False
    recording_start_time = 0  # Reset recording start time
    last_stop_time = current_time
    
    # Send termination with better error handling
    if ws_app and hasattr(ws_app, 'sock') and ws_app.sock:
        try:
            if ws_app.sock.connected:
                terminate_message = {"type": "Terminate"}
                ws_app.send(json.dumps(terminate_message))
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"❌ Termination error: {e}")
    
    # Close WebSocket with proper cleanup sequence
    if ws_app:
        try:
            # Signal stop first
            stop_event.set()
            time.sleep(0.1)  # Brief pause
            
            # Close WebSocket
            ws_app.close()
            
            # Wait for WebSocket thread to finish with robust checking
            thread_to_join = ws_thread  # Capture reference
            if thread_to_join and hasattr(thread_to_join, 'is_alive'):
                try:
                    if thread_to_join.is_alive():
                        thread_to_join.join(timeout=3.0)
                        if thread_to_join.is_alive():
                            logger.warning("⚠️ WebSocket thread did not terminate cleanly")
                except Exception as e:
                    logger.error(f"❌ Thread join error: {e}")
        except Exception as e:
            logger.error(f"❌ WebSocket close error: {e}")
        finally:
            # Force cleanup
            ws_app = None
            ws_thread = None
    
    # NOW paste the final transcript when Fn key is released
    if final_transcript:
        logger.info(f"📋 Pasting: \"{final_transcript}\"")
        # Log complete transcription to dedicated log
        transcript_logger.info(f"COMPLETE_TRANSCRIPT: {final_transcript}")
        paste_text(final_transcript)
        final_transcript = ""  # Clear it
    
    cleanup_audio()

def cleanup_audio():
    """Clean up audio with better error handling"""
    global stream, ws_app, ws_thread, stop_event
    
    # Signal all threads to stop
    stop_event.set()
    
    # Clean up audio stream with retries
    if stream:
        try:
            # Wait a moment for any ongoing reads to complete
            time.sleep(0.1)
            
            if hasattr(stream, 'is_active') and stream.is_active():
                stream.stop_stream()
                time.sleep(0.05)  # Brief pause after stopping
            
            if hasattr(stream, 'close'):
                stream.close()
                
        except Exception as e:
            logger.error(f"❌ Audio cleanup error: {e}")
        finally:
            stream = None
    
    # Ensure WebSocket cleanup
    if ws_app:
        try:
            ws_app.close()
        except:
            pass
        finally:
            ws_app = None
    
    # Clean up thread reference
    ws_thread = None

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
        
        logger.info(f"📋 Pasted: \"{text}\"")
        # Log paste action to transcript log
        transcript_logger.info(f"PASTED: {text}")
        
    except Exception as e:
        logger.error(f"❌ Paste error: {e}")
        transcript_logger.error(f"PASTE_ERROR: {e}")

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
                logger.info("🎤 Recording started...")
                play_sound("sounds/press.wav")  # Play press sound
                trigger_pressed = True
                last_trigger_time = current_time
                threading.Thread(target=start_recording, daemon=True).start()
            elif not fn_currently_pressed and trigger_pressed:
                logger.info("🛑 Recording stopped...")
                play_sound("sounds/release.wav")  # Play release sound
                trigger_pressed = False
                last_trigger_time = current_time
                threading.Thread(target=stop_recording, daemon=True).start()
        
        # Regular key handling for other trigger keys
        elif TRIGGER_KEY != 'fn' and is_trigger:
            # Key down or flags changed (for modifier keys)
            if (event_type == NSKeyDownMask or event_type == NSFlagsChangedMask) and not trigger_pressed:
                logger.info("🎤 Recording started...")
                play_sound("sounds/press.wav")  # Play press sound
                trigger_pressed = True
                last_trigger_time = current_time
                threading.Thread(target=start_recording, daemon=True).start()
            
            # Key up or flags changed (for modifier keys)
            elif (event_type == NSKeyUpMask or event_type == NSFlagsChangedMask) and trigger_pressed:
                logger.info("🛑 Recording stopped...")
                play_sound("sounds/release.wav")  # Play release sound
                trigger_pressed = False
                last_trigger_time = current_time
                threading.Thread(target=stop_recording, daemon=True).start()
        
    except Exception as e:
        logger.error(f"❌ Key handler error: {e}")

class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        """App finished launching"""
        mask = NSKeyDownMask | NSKeyUpMask | NSFlagsChangedMask
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, handler)
        logger.info("✅ Global key monitoring started")

def main():
    """Main function"""
    logger.info("🎤 Starting Wispr Flow (Simple)...")
    logger.info("📋 Make sure to grant Accessibility and Microphone permissions")
    logger.info(f"🎯 Trigger key: {TRIGGER_KEY}")
    
    if not init_audio():
        sys.exit(1)
    
    # Create NSApplication
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    NSApp().setDelegate_(delegate)
    
    try:
        AppHelper.runEventLoop()
    except KeyboardInterrupt:
        logger.info("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        if audio:
            audio.terminate()

if __name__ == "__main__":
    main() 