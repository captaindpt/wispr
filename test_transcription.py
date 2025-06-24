#!/usr/bin/env python3
"""
Simple command-line test for real-time transcription
Press SPACE to start/stop recording, see transcription in real-time
"""

import pyaudio
import websocket
import json
import threading
import time
import sys
import os
from urllib.parse import urlencode
from dotenv import load_dotenv
from audio_feedback import AudioFeedback, SystemAudioFeedback

# Load environment variables
load_dotenv()

# Get API key from environment
API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
if not API_KEY:
    print("❌ ASSEMBLYAI_API_KEY not found in .env file")
    sys.exit(1)

print(f"✅ Loaded API key: {API_KEY[:8]}...")

# Configuration
CONNECTION_PARAMS = {
    "sample_rate": 16000,
    "format_turns": True,
}
API_ENDPOINT = f"wss://streaming.assemblyai.com/v3/ws?{urlencode(CONNECTION_PARAMS)}"

# Audio settings
FRAMES_PER_BUFFER = 800
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16

class TranscriptionTester:
    def __init__(self):
        self.audio = None
        self.stream = None
        self.ws_app = None
        self.audio_thread = None
        self.recording = False
        self.stop_event = threading.Event()
        self.partial_transcript = ""
        self.final_transcript = ""
        
        # Initialize audio feedback
        try:
            self.audio_feedback = AudioFeedback(enabled=True, volume=0.6)
            print("✅ Audio feedback initialized")
        except Exception as e:
            print(f"⚠️ Audio feedback failed, using system sounds: {e}")
            self.audio_feedback = SystemAudioFeedback(enabled=True)
        
        # Initialize audio
        try:
            self.audio = pyaudio.PyAudio()
            print("✅ Audio initialized")
        except Exception as e:
            print(f"❌ Audio initialization failed: {e}")
            sys.exit(1)

    def test_microphone(self):
        """Quick microphone test"""
        try:
            test_stream = self.audio.open(
                input=True,
                frames_per_buffer=1024,
                channels=CHANNELS,
                format=FORMAT,
                rate=SAMPLE_RATE,
            )
            print("🎤 Testing microphone...")
            for i in range(5):
                data = test_stream.read(1024, exception_on_overflow=False)
                print(f"📊 Audio level test {i+1}/5: {len(data)} bytes")
                time.sleep(0.2)
            test_stream.close()
            print("✅ Microphone working!")
            return True
        except Exception as e:
            print(f"❌ Microphone test failed: {e}")
            return False

    def on_ws_open(self, ws):
        """WebSocket opened"""
        print("🔗 Connected to AssemblyAI")
        
        def stream_audio():
            while self.recording and not self.stop_event.is_set():
                try:
                    if self.stream and self.stream.is_active():
                        audio_data = self.stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                        ws.send(audio_data, websocket.ABNF.OPCODE_BINARY)
                except Exception as e:
                    print(f"\n❌ Streaming error: {e}")
                    break
        
        self.audio_thread = threading.Thread(target=stream_audio)
        self.audio_thread.daemon = True
        self.audio_thread.start()

    def on_ws_message(self, ws, message):
        """Handle transcription messages"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == "Begin":
                session_id = data.get('id', 'unknown')
                print(f"📝 Session started: {session_id[:8]}...")
                
            elif msg_type == "Turn":
                transcript = data.get('transcript', '').strip()
                formatted = data.get('turn_is_formatted', False)
                
                if formatted and transcript:
                    # Final transcript
                    self.final_transcript = transcript
                    print(f"\n✅ FINAL: {transcript}")
                elif transcript:
                    # Partial transcript - update on same line
                    self.partial_transcript = transcript
                    print(f"\r💭 {transcript}...", end='', flush=True)
                    
            elif msg_type == "Termination":
                print(f"\n🔚 Session ended")
                if self.final_transcript:
                    print(f"📝 Last transcription: {self.final_transcript}")
                    
        except Exception as e:
            print(f"\n❌ Message error: {e}")

    def on_ws_error(self, ws, error):
        """WebSocket error"""
        print(f"\n❌ WebSocket error: {error}")

    def on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket closed"""
        print(f"\n🔌 Connection closed")
        self.cleanup_audio()

    def start_recording(self):
        """Start recording and transcription"""
        if self.recording:
            print("⚠️ Already recording!")
            return
            
        self.recording = True
        self.partial_transcript = ""
        self.final_transcript = ""
        self.stop_event.clear()
        
        # Play press sound
        self.audio_feedback.play_press_sound()
        
        print("\n🎤 Starting recording...")
        
        try:
            # Open microphone
            self.stream = self.audio.open(
                input=True,
                frames_per_buffer=FRAMES_PER_BUFFER,
                channels=CHANNELS,
                format=FORMAT,
                rate=SAMPLE_RATE,
            )
            
            # Connect to WebSocket
            self.ws_app = websocket.WebSocketApp(
                API_ENDPOINT,
                header={"Authorization": API_KEY},
                on_open=self.on_ws_open,
                on_message=self.on_ws_message,
                on_error=self.on_ws_error,
                on_close=self.on_ws_close,
            )
            
            # Start WebSocket in thread
            ws_thread = threading.Thread(target=self.ws_app.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
        except Exception as e:
            print(f"❌ Recording failed: {e}")
            self.recording = False

    def stop_recording(self):
        """Stop recording"""
        if not self.recording:
            print("⚠️ Not recording!")
            return
            
        print("\n🛑 Stopping recording...")
        self.recording = False
        
        # Play release sound
        self.audio_feedback.play_release_sound()
        
        # Send termination message
        if self.ws_app and hasattr(self.ws_app, 'sock') and self.ws_app.sock:
            try:
                terminate_msg = {"type": "Terminate"}
                self.ws_app.send(json.dumps(terminate_msg))
                time.sleep(1.5)  # Wait for final result
            except Exception as e:
                print(f"❌ Termination error: {e}")
        
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
            except:
                pass
            self.stream = None

    def run_test(self):
        """Main test loop"""
        print("\n" + "="*50)
        print("🎤 WISPR FLOW TRANSCRIPTION TEST")
        print("="*50)
        print("🔘 Press SPACE to start/stop recording")
        print("🔘 Press 'q' to quit")
        print("🔘 Press 't' to test microphone")
        print("🔘 Press 's' to test audio feedback")
        print("="*50)
        
        try:
            while True:
                command = input("\nCommand (SPACE=record, t=test mic, s=test sounds, q=quit): ").strip().lower()
                
                if command == 'q':
                    print("👋 Goodbye!")
                    break
                    
                elif command == 't':
                    if not self.test_microphone():
                        print("❌ Fix microphone issues before testing transcription")
                        
                elif command == 's':
                    print("🔊 Testing audio feedback...")
                    self.audio_feedback.test_sounds()
                        
                elif command == ' ' or command == '':
                    if not self.recording:
                        self.start_recording()
                        print("🔴 Recording... (press SPACE again to stop)")
                    else:
                        self.stop_recording()
                        print("⭕ Recording stopped")
                        
                else:
                    print("❓ Unknown command. Use SPACE, t, s, or q")
                    
        except KeyboardInterrupt:
            print("\n👋 Interrupted")
        finally:
            if self.recording:
                self.stop_recording()
            if self.audio:
                self.audio.terminate()

def main():
    print("🚀 Initializing transcription test...")
    
    tester = TranscriptionTester()
    tester.run_test()

if __name__ == "__main__":
    main() 