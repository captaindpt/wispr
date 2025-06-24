#!/usr/bin/env python3
"""
Wispr Flow Service - Production Ready Version
Runs as a background service with comprehensive logging and error recovery
"""

import pyaudio
import websocket
import json
import threading
import time
import sys
import os
import logging
import signal
import argparse
from urllib.parse import urlencode
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import subprocess
import traceback
from audio_feedback import AudioFeedback, SystemAudioFeedback

# macOS-specific imports
try:
    from pynput import keyboard
    from pynput.keyboard import Key
    from AppKit import NSPasteboard, NSStringPboardType
    MACOS_AVAILABLE = True
except ImportError:
    MACOS_AVAILABLE = False
    print("⚠️ macOS features not available")

class WisprService:
    def __init__(self, log_dir="/tmp/wispr", trigger_key='fn', log_level='INFO'):
        # Setup logging first
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.setup_logging(log_level)
        
        self.logger = logging.getLogger('wispr.service')
        self.logger.info("🚀 Initializing Wispr Flow Service")
        
        # Load environment
        load_dotenv()
        self.api_key = os.getenv('ASSEMBLYAI_API_KEY')
        if not self.api_key:
            self.logger.error("ASSEMBLYAI_API_KEY not found in environment")
            raise ValueError("API key required")
        
        self.logger.info(f"✅ API key loaded: {self.api_key[:8]}...")
        
        # Configuration
        self.trigger_key = trigger_key
        self.connection_params = {
            "sample_rate": 16000,
            "format_turns": True,
        }
        self.api_endpoint = f"wss://streaming.assemblyai.com/v3/ws?{urlencode(self.connection_params)}"
        
        # Audio settings
        self.frames_per_buffer = 800
        self.sample_rate = 16000
        self.channels = 1
        self.format = pyaudio.paInt16
        
        # State
        self.audio = None
        self.stream = None
        self.ws_app = None
        self.audio_thread = None
        self.recording = False
        self.trigger_pressed = False
        self.stop_event = threading.Event()
        self.final_transcript = ""
        self.running = True
        
        # Statistics
        self.stats = {
            'sessions_started': 0,
            'transcriptions_completed': 0,
            'errors': 0,
            'start_time': datetime.now(),
            'last_activity': None
        }
        
        # Initialize audio feedback
        try:
            audio_enabled = os.getenv('WISPR_AUDIO_FEEDBACK', 'true').lower() == 'true'
            audio_volume = float(os.getenv('WISPR_AUDIO_VOLUME', '0.5'))
            self.audio_feedback = AudioFeedback(enabled=audio_enabled, volume=audio_volume)
            self.logger.info(f"✅ Audio feedback initialized (enabled: {audio_enabled}, volume: {audio_volume})")
        except Exception as e:
            self.logger.warning(f"Audio feedback failed, using system sounds: {e}")
            self.audio_feedback = SystemAudioFeedback(enabled=True)
        
        # Initialize audio
        self.init_audio()
        
        self.logger.info(f"✅ Service initialized with trigger: {trigger_key}")

    def setup_logging(self, log_level):
        """Setup comprehensive logging with rotation"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Create formatters
        formatter = logging.Formatter(log_format)
        
        # File handler with rotation
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            self.log_dir / 'wispr.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            handlers=[file_handler, console_handler]
        )
        
        # Disable verbose websocket logging
        logging.getLogger('websocket').setLevel(logging.WARNING)

    def init_audio(self):
        """Initialize PyAudio with error handling"""
        try:
            self.audio = pyaudio.PyAudio()
            self.logger.info("✅ Audio system initialized")
            
            # Test microphone access
            self.test_microphone()
            
        except Exception as e:
            self.logger.error(f"❌ Audio initialization failed: {e}")
            raise

    def test_microphone(self):
        """Test microphone access"""
        try:
            test_stream = self.audio.open(
                input=True,
                frames_per_buffer=1024,
                channels=self.channels,
                format=self.format,
                rate=self.sample_rate,
            )
            # Quick test read
            test_stream.read(1024, exception_on_overflow=False)
            test_stream.close()
            self.logger.info("✅ Microphone test successful")
            return True
        except Exception as e:
            self.logger.error(f"❌ Microphone test failed: {e}")
            return False

    def on_ws_open(self, ws):
        """WebSocket connection established"""
        self.logger.info("🔗 WebSocket connected to AssemblyAI")
        
        def stream_audio():
            self.logger.info("🎤 Audio streaming started")
            while self.recording and not self.stop_event.is_set():
                try:
                    if self.stream and self.stream.is_active():
                        audio_data = self.stream.read(self.frames_per_buffer, exception_on_overflow=False)
                        ws.send(audio_data, websocket.ABNF.OPCODE_BINARY)
                except Exception as e:
                    self.logger.error(f"Audio streaming error: {e}")
                    break
            self.logger.info("🛑 Audio streaming stopped")
        
        self.audio_thread = threading.Thread(target=stream_audio, name='AudioStream')
        self.audio_thread.daemon = True
        self.audio_thread.start()

    def on_ws_message(self, ws, message):
        """Handle WebSocket messages"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == "Begin":
                session_id = data.get('id', 'unknown')
                self.logger.info(f"📝 Transcription session started: {session_id}")
                self.stats['sessions_started'] += 1
                
            elif msg_type == "Turn":
                transcript = data.get('transcript', '').strip()
                formatted = data.get('turn_is_formatted', False)
                
                if formatted and transcript:
                    self.final_transcript = transcript
                    self.logger.info(f"✅ Final transcript: {transcript}")
                elif transcript:
                    self.logger.debug(f"💭 Partial: {transcript[:50]}...")
                    
            elif msg_type == "Termination":
                self.logger.info("🔚 Transcription session ended")
                if self.final_transcript:
                    self.paste_text(self.final_transcript)
                    self.stats['transcriptions_completed'] += 1
                    self.stats['last_activity'] = datetime.now()
                    
        except Exception as e:
            self.logger.error(f"Message handling error: {e}")
            self.stats['errors'] += 1

    def on_ws_error(self, ws, error):
        """WebSocket error handler"""
        self.logger.error(f"WebSocket error: {error}")
        self.stats['errors'] += 1

    def on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket close handler"""
        if close_status_code:
            self.logger.info(f"🔌 WebSocket closed: {close_status_code} - {close_msg}")
        else:
            self.logger.info("🔌 WebSocket disconnected")
        self.cleanup_audio()

    def start_recording(self):
        """Start recording and transcription"""
        if self.recording:
            self.logger.warning("Recording already in progress")
            return
            
        self.logger.info("🎤 Starting recording session")
        self.recording = True
        self.final_transcript = ""
        self.stop_event.clear()
        
        # Play press sound feedback
        try:
            self.audio_feedback.play_press_sound()
        except Exception as e:
            self.logger.debug(f"Audio feedback error: {e}")
        
        try:
            # Open microphone
            self.stream = self.audio.open(
                input=True,
                frames_per_buffer=self.frames_per_buffer,
                channels=self.channels,
                format=self.format,
                rate=self.sample_rate,
            )
            
            # Create WebSocket
            self.ws_app = websocket.WebSocketApp(
                self.api_endpoint,
                header={"Authorization": self.api_key},
                on_open=self.on_ws_open,
                on_message=self.on_ws_message,
                on_error=self.on_ws_error,
                on_close=self.on_ws_close,
            )
            
            # Start WebSocket
            ws_thread = threading.Thread(target=self.ws_app.run_forever, name='WebSocket')
            ws_thread.daemon = True
            ws_thread.start()
            
        except Exception as e:
            self.logger.error(f"Recording start failed: {e}")
            self.recording = False
            self.stats['errors'] += 1

    def stop_recording(self):
        """Stop recording"""
        if not self.recording:
            self.logger.warning("Not currently recording")
            return
            
        self.logger.info("🛑 Stopping recording session")
        self.recording = False
        
        # Play release sound feedback
        try:
            self.audio_feedback.play_release_sound()
        except Exception as e:
            self.logger.debug(f"Audio feedback error: {e}")
        
        # Send termination
        if self.ws_app and hasattr(self.ws_app, 'sock') and self.ws_app.sock:
            try:
                terminate_msg = {"type": "Terminate"}
                self.ws_app.send(json.dumps(terminate_msg))
                time.sleep(1.5)  # Wait for final transcription
            except Exception as e:
                self.logger.error(f"Termination error: {e}")
        
        # Close WebSocket
        if self.ws_app:
            self.ws_app.close()

    def cleanup_audio(self):
        """Clean up audio resources"""
        if self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                self.logger.error(f"Audio cleanup error: {e}")
            self.stream = None

    def paste_text(self, text):
        """Paste text at cursor location"""
        if not MACOS_AVAILABLE:
            self.logger.warning("macOS features not available for pasting")
            return
            
        try:
            # Copy to clipboard
            pasteboard = NSPasteboard.generalPasteboard()
            pasteboard.clearContents()
            pasteboard.setString_forType_(text, NSStringPboardType)
            
            # Paste using AppleScript
            time.sleep(0.1)
            script = 'tell application "System Events" to keystroke "v" using command down'
            subprocess.run(['osascript', '-e', script], check=True, timeout=5)
            
            self.logger.info(f"📋 Pasted text: {text}")
            
        except Exception as e:
            self.logger.error(f"Paste error: {e}")
            self.logger.info(f"📝 Text was: {text}")

    def is_trigger_key(self, key):
        """Check if pressed key is trigger"""
        try:
            if self.trigger_key == 'fn':
                # Fn key is not reliably detectable on macOS, use right_cmd instead
                self.logger.warning("Fn key not supported, using right_cmd instead")
                self.trigger_key = 'right_cmd'
                return key == Key.cmd_r
            elif self.trigger_key == 'right_cmd':
                return key == Key.cmd_r
            elif self.trigger_key == 'right_ctrl':
                return key == Key.ctrl_r
            elif self.trigger_key == 'caps_lock':
                return key == Key.caps_lock
            elif self.trigger_key == 'f13':
                return (hasattr(key, 'vk') and key.vk == 105)
            return False
        except Exception as e:
            self.logger.error(f"Key detection error: {e}")
            return False

    def on_key_press(self, key):
        """Handle key press"""
        if self.is_trigger_key(key) and not self.trigger_pressed:
            self.trigger_pressed = True
            self.logger.debug(f"🔘 Trigger key pressed: {self.trigger_key}")
            threading.Thread(target=self.start_recording, daemon=True).start()

    def on_key_release(self, key):
        """Handle key release"""
        if self.is_trigger_key(key) and self.trigger_pressed:
            self.trigger_pressed = False
            self.logger.debug(f"🔘 Trigger key released: {self.trigger_key}")
            threading.Thread(target=self.stop_recording, daemon=True).start()

    def log_stats(self):
        """Log current statistics"""
        uptime = datetime.now() - self.stats['start_time']
        self.logger.info(f"📊 Stats - Sessions: {self.stats['sessions_started']}, "
                        f"Transcriptions: {self.stats['transcriptions_completed']}, "
                        f"Errors: {self.stats['errors']}, Uptime: {uptime}")

    def health_check(self):
        """Perform health check"""
        try:
            # Test microphone
            if not self.test_microphone():
                self.logger.error("❌ Health check failed: Microphone not accessible")
                return False
            
            # Check if audio system is still working
            if not self.audio:
                self.logger.error("❌ Health check failed: Audio system not initialized")
                return False
                
            self.logger.debug("✅ Health check passed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Health check failed: {e}")
            return False

    def run_service(self):
        """Main service loop"""
        if not MACOS_AVAILABLE:
            self.logger.error("❌ macOS features required but not available")
            return
            
        self.logger.info("🚀 Starting Wispr Flow Service")
        self.logger.info(f"🎯 Trigger key: {self.trigger_key}")
        
        # Log stats every 10 minutes
        last_stats_log = time.time()
        last_health_check = time.time()
        
        try:
            with keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release,
                suppress=False
            ) as listener:
                
                while self.running and not self.stop_event.is_set():
                    current_time = time.time()
                    
                    # Periodic stats logging
                    if current_time - last_stats_log > 600:  # 10 minutes
                        self.log_stats()
                        last_stats_log = current_time
                    
                    # Periodic health check
                    if current_time - last_health_check > 300:  # 5 minutes
                        if not self.health_check():
                            self.logger.warning("⚠️ Health check failed, attempting recovery")
                            self.recover()
                        last_health_check = current_time
                    
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            self.logger.info("👋 Service interrupted by user")
        except Exception as e:
            self.logger.error(f"❌ Service error: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.cleanup()

    def recover(self):
        """Attempt to recover from errors"""
        self.logger.info("🔄 Attempting service recovery")
        try:
            # Stop any ongoing recording
            if self.recording:
                self.stop_recording()
            
            # Reinitialize audio if needed
            if not self.audio:
                self.init_audio()
                
            self.logger.info("✅ Recovery completed")
        except Exception as e:
            self.logger.error(f"❌ Recovery failed: {e}")

    def stop_service(self):
        """Stop the service gracefully"""
        self.logger.info("🛑 Stopping Wispr Flow Service")
        self.running = False
        self.stop_event.set()
        if self.recording:
            self.stop_recording()

    def cleanup(self):
        """Final cleanup"""
        self.log_stats()
        if self.recording:
            self.stop_recording()
        if self.audio:
            self.audio.terminate()
        self.logger.info("🧹 Service cleanup completed")

def signal_handler(signum, frame):
    """Handle termination signals"""
    global service
    if 'service' in globals():
        service.stop_service()
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description='Wispr Flow Service')
    parser.add_argument('--trigger', 
                       choices=['right_cmd', 'right_ctrl', 'caps_lock', 'f13'],
                       default='right_cmd', help='Trigger key (default: right_cmd)')
    parser.add_argument('--log-dir', default='/tmp/wispr', help='Log directory')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Log level')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    global service
    service = WisprService(
        log_dir=args.log_dir,
        trigger_key=args.trigger,
        log_level=args.log_level
    )
    
    if args.daemon:
        # Daemon mode - redirect stdout/stderr
        import atexit
        atexit.register(service.cleanup)
    
    service.run_service()

if __name__ == "__main__":
    main() 