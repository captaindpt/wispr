#!/usr/bin/env python3
"""
Wispr Flow Launcher - Background Service
Lightweight launcher that can run as a daemon/background process
"""

import sys
import os
import subprocess
import time
import argparse
import signal
from pathlib import Path

class WisprLauncher:
    def __init__(self):
        self.process = None
        self.running = False
        
    def check_dependencies(self):
        """Check if all dependencies are installed"""
        try:
            import pyaudio
            import websocket
            import pynput
            from AppKit import NSPasteboard
            print("✅ All dependencies available")
            return True
        except ImportError as e:
            print(f"❌ Missing dependency: {e}")
            print("📦 Run: pip install -r requirements.txt")
            return False
    
    def check_permissions(self):
        """Check if required permissions are granted"""
        print("🔒 Checking permissions...")
        
        # Test microphone access
        try:
            import pyaudio
            audio = pyaudio.PyAudio()
            stream = audio.open(
                input=True,
                frames_per_buffer=1024,
                channels=1,
                format=pyaudio.paInt16,
                rate=16000,
            )
            stream.close()
            audio.terminate()
            print("✅ Microphone access OK")
        except Exception as e:
            print(f"❌ Microphone access denied: {e}")
            return False
        
        # Test accessibility (by trying to use pynput)
        try:
            from pynput import keyboard
            # This will fail if accessibility isn't granted
            listener = keyboard.Listener(on_press=lambda k: None, on_release=lambda k: None)
            listener.start()
            time.sleep(0.1)
            listener.stop()
            print("✅ Accessibility access OK")
        except Exception as e:
            print(f"❌ Accessibility access denied: {e}")
            print("📋 Grant accessibility permission in System Preferences")
            return False
        
        return True
    
    def start_wispr(self, trigger='fn', background=False):
        """Start the Wispr Flow application"""
        if not self.check_dependencies():
            return False
        
        if not background and not self.check_permissions():
            return False
        
        script_path = Path(__file__).parent / "wispr_flow_improved.py"
        
        cmd = [sys.executable, str(script_path), "--trigger", trigger]
        
        if background:
            print(f"🚀 Starting Wispr Flow in background with trigger: {trigger}")
            # Redirect stdout/stderr to devnull for background operation
            with open(os.devnull, 'w') as devnull:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=devnull,
                    stderr=devnull,
                    stdin=devnull
                )
        else:
            print(f"🚀 Starting Wispr Flow with trigger: {trigger}")
            self.process = subprocess.Popen(cmd)
        
        self.running = True
        return True
    
    def stop_wispr(self):
        """Stop the Wispr Flow application"""
        if self.process:
            print("🛑 Stopping Wispr Flow...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                print("🔥 Force killed Wispr Flow")
            self.process = None
        self.running = False
    
    def status(self):
        """Check if Wispr Flow is running"""
        if self.process:
            if self.process.poll() is None:
                print(f"✅ Wispr Flow is running (PID: {self.process.pid})")
                return True
            else:
                print("❌ Wispr Flow process ended")
                self.process = None
                self.running = False
        else:
            print("❌ Wispr Flow is not running")
        return False
    
    def restart(self, trigger='fn', background=False):
        """Restart Wispr Flow"""
        print("🔄 Restarting Wispr Flow...")
        self.stop_wispr()
        time.sleep(1)
        return self.start_wispr(trigger, background)

def signal_handler(sig, frame):
    """Handle interrupt signals"""
    print("\n🛑 Received interrupt signal")
    launcher.stop_wispr()
    sys.exit(0)

def main():
    global launcher
    
    parser = argparse.ArgumentParser(description='Wispr Flow Launcher')
    parser.add_argument('action', 
                       choices=['start', 'stop', 'restart', 'status', 'test'], 
                       help='Action to perform')
    parser.add_argument('--trigger', 
                       choices=['fn', 'right_cmd', 'right_ctrl', 'right_alt', 'caps_lock', 'f13'],
                       default='fn',
                       help='Trigger key (default: fn)')
    parser.add_argument('--background', '-b', 
                       action='store_true',
                       help='Run in background (daemon mode)')
    parser.add_argument('--keep-alive', '-k',
                       action='store_true', 
                       help='Keep launcher running and restart if crashed')
    
    args = parser.parse_args()
    launcher = WisprLauncher()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if args.action == 'start':
        if launcher.start_wispr(args.trigger, args.background):
            if args.keep_alive and not args.background:
                print("🔄 Keep-alive mode enabled")
                try:
                    while True:
                        if launcher.process and launcher.process.poll() is not None:
                            print("💀 Wispr Flow crashed, restarting...")
                            launcher.restart(args.trigger, args.background)
                        time.sleep(5)
                except KeyboardInterrupt:
                    pass
            elif not args.background:
                # Wait for process to complete
                try:
                    launcher.process.wait()
                except KeyboardInterrupt:
                    pass
        
    elif args.action == 'stop':
        launcher.stop_wispr()
        
    elif args.action == 'restart':
        launcher.restart(args.trigger, args.background)
        
    elif args.action == 'status':
        launcher.status()
        
    elif args.action == 'test':
        print("🧪 Testing system compatibility...")
        if launcher.check_dependencies() and launcher.check_permissions():
            print("✅ System ready for Wispr Flow")
        else:
            print("❌ System not ready")
            sys.exit(1)

if __name__ == "__main__":
    main() 