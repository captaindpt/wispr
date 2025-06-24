#!/usr/bin/env python3
"""
Sound Installer for Wispr Flow
Easy way to install custom press/release sounds
"""

import shutil
import sys
from pathlib import Path
from audio_feedback import AudioFeedback

def install_sounds():
    print("🎵 Wispr Flow Sound Installer")
    print("=" * 35)
    
    sounds_dir = Path("sounds")
    sounds_dir.mkdir(exist_ok=True)
    
    print("\n📁 Current sound files:")
    press_file = sounds_dir / "press.wav"
    release_file = sounds_dir / "release.wav"
    
    if press_file.exists():
        size = press_file.stat().st_size
        print(f"   ✅ press.wav ({size} bytes)")
    else:
        print("   ❌ press.wav (missing)")
    
    if release_file.exists():
        size = release_file.stat().st_size
        print(f"   ✅ release.wav ({size} bytes)")
    else:
        print("   ❌ release.wav (missing)")
    
    print("\n🎯 Options:")
    print("1. Install custom sound files")
    print("2. Use macOS system sounds")
    print("3. Test current sounds")
    print("4. Download recommended sounds")
    print("5. Quit")
    
    while True:
        choice = input("\nChoice (1-5): ").strip()
        
        if choice == '1':
            install_custom_files()
        elif choice == '2':
            use_system_sounds()
        elif choice == '3':
            test_current_sounds()
        elif choice == '4':
            show_download_info()
        elif choice == '5':
            print("👋 Goodbye!")
            break
        else:
            print("❓ Invalid choice")

def install_custom_files():
    print("\n📥 Installing Custom Sound Files")
    print("-" * 30)
    
    print("Drop your sound files here or enter file paths:")
    print("(Supported: .wav, .aiff, .mp3 - will convert to .wav)")
    
    press_path = input("Press sound file path: ").strip().strip('"')
    release_path = input("Release sound file path: ").strip().strip('"')
    
    feedback = AudioFeedback()
    
    if press_path and release_path:
        if feedback.install_custom_sounds(press_path, release_path):
            print("✅ Custom sounds installed!")
            test_current_sounds()
        else:
            print("❌ Installation failed")
    else:
        print("⚠️ Please provide both files")

def use_system_sounds():
    print("\n🔧 Using macOS System Sounds")
    print("-" * 25)
    
    # Copy system sounds to our directory
    sounds_dir = Path("sounds")
    sounds_dir.mkdir(exist_ok=True)
    
    try:
        # Copy Hero sound as press
        hero_path = Path("/System/Library/Sounds/Hero.aiff")
        if hero_path.exists():
            shutil.copy(hero_path, sounds_dir / "press.wav")
            print("✅ Installed Hero as press sound")
        
        # Copy Blow sound as release
        blow_path = Path("/System/Library/Sounds/Blow.aiff")
        if blow_path.exists():
            shutil.copy(blow_path, sounds_dir / "release.wav")
            print("✅ Installed Blow as release sound")
        
        test_current_sounds()
        
    except Exception as e:
        print(f"❌ Failed to copy system sounds: {e}")

def test_current_sounds():
    print("\n🔊 Testing Current Sounds")
    print("-" * 20)
    
    feedback = AudioFeedback(enabled=True, volume=0.5)
    feedback.test_sounds()

def show_download_info():
    print("\n📱 Recommended Sound Sources")
    print("-" * 25)
    
    print("🎧 Free Professional Sources:")
    print("   • Freesound.org - Search 'UI notification'")
    print("   • Pixabay.com - UI sound effects")
    print("   • Mixkit.co - Free interface sounds")
    
    print("\n🎼 Specific Recommendations:")
    print("   • 'Soft notification' or 'gentle beep'")
    print("   • 'UI confirmation' sounds")
    print("   • 'Subtle click' or 'soft pop'")
    print("   • iPhone/iOS notification sounds")
    
    print("\n⚙️ Technical Requirements:")
    print("   • Format: WAV, AIFF, or MP3")
    print("   • Duration: 0.1-0.3 seconds")
    print("   • Volume: Moderate (you can adjust)")
    print("   • Quality: 44.1kHz recommended")
    
    print("\n💡 Pro Tip:")
    print("   Search for 'minimal UI sound pack' or 'subtle notification sounds'")
    print("   Many apps like Slack, Discord have great subtle sounds you can find")

if __name__ == "__main__":
    install_sounds() 