#!/usr/bin/env python3
"""
Audio Feedback Module for Wispr Flow
Provides subtle, soft press/release sound effects
"""

import subprocess
import threading
import time
import os
import tempfile
import wave
import struct
import math
from pathlib import Path

class AudioFeedback:
    def __init__(self, enabled=True, volume=0.3):
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))  # Clamp between 0-1
        self.sounds_dir = Path(__file__).parent / "sounds"
        self.sounds_dir.mkdir(exist_ok=True)
        self.volume_supported = None  # Cache whether volume control works
        
        # Sound file paths
        self.press_sound_path = self.sounds_dir / "press.wav"
        self.release_sound_path = self.sounds_dir / "release.wav"
        
        # Check for custom sound files first, otherwise use system sounds
        if not self._has_custom_sounds():
            self._install_default_system_sounds()

    def _has_custom_sounds(self):
        """Check if custom sound files exist"""
        return (self.press_sound_path.exists() and 
                self.release_sound_path.exists() and
                self.press_sound_path.stat().st_size > 1000)  # At least 1KB

    def _install_default_system_sounds(self):
        """Install macOS system sounds as defaults (Hero + Blow)"""
        try:
            import shutil
            
            # Use Hero sound for press (subtle rising tone)
            hero_path = Path("/System/Library/Sounds/Hero.aiff")
            if hero_path.exists():
                shutil.copy(hero_path, self.press_sound_path)
                print("✅ Installed Hero as default press sound")
            
            # Use Blow sound for release (gentle confirmation)
            blow_path = Path("/System/Library/Sounds/Blow.aiff")
            if blow_path.exists():
                shutil.copy(blow_path, self.release_sound_path)
                print("✅ Installed Blow as default release sound")
            
            print("🎵 Default system sounds installed")
            
        except Exception as e:
            print(f"⚠️ System sounds failed, generating fallback: {e}")
            self._generate_soft_sounds()

    def _generate_soft_sounds(self):
        """Generate very subtle, soft notification sounds (fallback)"""
        print("🎵 Generating fallback audio feedback sounds...")
        
        # Press sound: Gentle rising tone (like a soft notification)
        self._generate_soft_tone(
            self.press_sound_path,
            base_freq=800,
            duration=0.12,
            tone_type='rise'
        )
        
        # Release sound: Gentle falling tone (like a soft confirmation)
        self._generate_soft_tone(
            self.release_sound_path,
            base_freq=600,
            duration=0.15,
            tone_type='fall'
        )
        
        print("✅ Fallback audio feedback sounds generated")

    def _generate_soft_tone(self, filepath, base_freq, duration, tone_type='rise'):
        """Generate a very soft, subtle notification tone"""
        sample_rate = 44100
        samples = int(sample_rate * duration)
        
        audio_data = []
        for i in range(samples):
            t = i / sample_rate
            progress = i / samples
            
            # Gentle frequency modulation
            if tone_type == 'rise':
                freq = base_freq + (base_freq * 0.15 * progress)  # Rise by 15%
            else:  # fall
                freq = base_freq - (base_freq * 0.1 * progress)   # Fall by 10%
            
            # Very soft sine wave with gentle attack/decay
            sample = math.sin(2 * math.pi * freq * t)
            
            # Soft envelope (gentle fade in/out)
            envelope = 1.0
            if progress < 0.2:  # 20% fade in
                envelope = progress / 0.2
            elif progress > 0.6:  # 40% fade out
                envelope = (1 - progress) / 0.4
            
            # Apply envelope and make it very quiet
            sample *= envelope * 0.15  # Very low volume
            
            # Convert to 16-bit
            sample_int = int(sample * 32767)
            sample_int = max(-32768, min(32767, sample_int))
            audio_data.append(sample_int)
        
        # Write WAV file
        with wave.open(str(filepath), 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            
            # Pack audio data
            packed_data = struct.pack('<' + 'h' * len(audio_data), *audio_data)
            wav_file.writeframes(packed_data)

    def install_custom_sounds(self, press_file=None, release_file=None):
        """Install custom sound files"""
        try:
            if press_file and Path(press_file).exists():
                import shutil
                shutil.copy(press_file, self.press_sound_path)
                print(f"✅ Installed custom press sound: {press_file}")
            
            if release_file and Path(release_file).exists():
                import shutil
                shutil.copy(release_file, self.release_sound_path)
                print(f"✅ Installed custom release sound: {release_file}")
                
            return True
        except Exception as e:
            print(f"❌ Failed to install custom sounds: {e}")
            return False

    def play_press_sound(self):
        """Play the press/start recording sound"""
        if self.enabled:
            threading.Thread(
                target=self._play_sound, 
                args=(self.press_sound_path,),
                daemon=True
            ).start()

    def play_release_sound(self):
        """Play the release/stop recording sound"""
        if self.enabled:
            threading.Thread(
                target=self._play_sound, 
                args=(self.release_sound_path,),
                daemon=True
            ).start()

    def _play_sound(self, sound_path):
        """Play a sound file using afplay (macOS built-in)"""
        if not sound_path.exists():
            return
            
        # Test volume support on first use
        if self.volume_supported is None:
            self._test_volume_support()
        
        try:
            if self.volume_supported:
                # Use volume control
                subprocess.run(
                    ['afplay', '-v', str(self.volume), str(sound_path)], 
                    check=True,
                    capture_output=True,
                    timeout=1.0
                )
            else:
                # Simple playback without volume control
                subprocess.run(
                    ['afplay', str(sound_path)], 
                    check=True,
                    capture_output=True,
                    timeout=1.0
                )
        except:
            pass  # Silently fail for audio feedback

    def _test_volume_support(self):
        """Test if afplay supports volume control"""
        try:
            # Test with a very short silent command
            result = subprocess.run(
                ['afplay', '--help'], 
                capture_output=True,
                timeout=1.0
            )
            # If help shows volume option, assume it's supported
            self.volume_supported = b'-v' in result.stderr or b'volume' in result.stderr
        except:
            self.volume_supported = False

    def test_sounds(self):
        """Test both press and release sounds"""
        print("🔊 Testing press sound (Hero)...")
        self.play_press_sound()
        time.sleep(0.8)  # Give more time between sounds
        
        print("🔊 Testing release sound (Blow)...")
        self.play_release_sound()
        time.sleep(0.8)
        
        print("✅ Audio feedback test completed")

    def set_enabled(self, enabled):
        """Enable or disable audio feedback"""
        self.enabled = enabled

    def set_volume(self, volume):
        """Set volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))

# macOS system sounds - much more subtle
class SystemAudioFeedback:
    """Use subtle macOS system sounds"""
    
    def __init__(self, enabled=True):
        self.enabled = enabled
        
    def play_press_sound(self):
        if self.enabled:
            # Use very subtle system sound
            threading.Thread(target=self._play_system_sound, args=('Hero',), daemon=True).start()
    
    def play_release_sound(self):
        if self.enabled:
            # Use gentle system sound
            threading.Thread(target=self._play_system_sound, args=('Blow',), daemon=True).start()
    
    def _play_system_sound(self, sound_name):
        try:
            # Try with very low volume
            subprocess.run(['afplay', '-v', '0.2', f'/System/Library/Sounds/{sound_name}.aiff'], 
                         check=True, capture_output=True, timeout=1.0)
        except:
            pass  # Silently fail
    
    def test_sounds(self):
        print("🔊 Testing subtle system press sound...")
        self.play_press_sound()
        time.sleep(0.6)
        
        print("🔊 Testing subtle system release sound...")
        self.play_release_sound()
        time.sleep(0.6)
        
        print("✅ System audio feedback test completed")
    
    def set_enabled(self, enabled):
        self.enabled = enabled

def show_sound_options():
    """Show available macOS system sounds and how to add custom ones"""
    print("\n🎵 SOUND OPTIONS")
    print("=" * 40)
    
    print("\n1. 📁 Available macOS System Sounds:")
    system_sounds_dir = Path("/System/Library/Sounds")
    if system_sounds_dir.exists():
        sounds = list(system_sounds_dir.glob("*.aiff"))
        for sound in sorted(sounds)[:10]:  # Show first 10
            print(f"   • {sound.stem}")
        if len(sounds) > 10:
            print(f"   ... and {len(sounds) - 10} more")
    
    print("\n2. 🎧 Professional Sound Sources:")
    print("   • Freesound.org - Free sound effects")
    print("   • Zapsplat.com - Professional sound library")
    print("   • UI Sounds Pack - Search for 'UI notification sounds'")
    print("   • Apple's own sounds in /System/Library/Sounds/")
    
    print("\n3. 🔧 Custom Sound Installation:")
    print("   • Place your .wav files in: ./sounds/")
    print("   • Name them: press.wav and release.wav")
    print("   • Recommended: Short (0.1-0.3s), subtle, high quality")
    
    print("\n4. 🎼 Sound Characteristics for Voice Apps:")
    print("   • Keep it under 300ms")
    print("   • Soft/gentle (not sharp or jarring)")
    print("   • Mid-frequency range (400-1000Hz)")
    print("   • Quick fade-in/fade-out")
    print("   • Low volume (let user adjust)")

def main():
    """Test the audio feedback module"""
    print("🎵 Wispr Flow Audio Feedback")
    print("=" * 30)
    
    # Test default sounds (now system sounds)
    print("\n1. Testing default sounds (Hero + Blow):")
    feedback = AudioFeedback(enabled=True, volume=0.4)
    feedback.test_sounds()
    
    # Show options
    show_sound_options()

if __name__ == "__main__":
    main() 