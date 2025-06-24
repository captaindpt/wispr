#!/usr/bin/env python3
"""
Debug script to test key detection
"""
import sys
from pynput import keyboard
from pynput.keyboard import Key

def on_key_press(key):
    """Debug key press handler"""
    print(f"🔘 KEY PRESSED: {key}")
    if hasattr(key, 'char'):
        print(f"   - char: '{key.char}'")
    if hasattr(key, 'vk'):
        print(f"   - vk: {key.vk}")
    if hasattr(key, 'name'):
        print(f"   - name: {key.name}")
    
    # Test specific keys we're interested in
    if hasattr(key, 'vk') and key.vk == 179:
        print("   ⭐ DETECTED FN KEY (vk=179)!")
    elif hasattr(key, 'char') and key.char == '\\':
        print("   ⭐ DETECTED BACKSLASH!")
    elif key == Key.cmd_r:
        print("   ⭐ DETECTED RIGHT CMD!")
    elif key == Key.esc:
        print("   👋 ESC pressed - exiting!")
        return False
    
    print("---")

def on_key_release(key):
    """Debug key release handler"""
    print(f"🔺 KEY RELEASED: {key}")
    if key == Key.esc:
        return False

def main():
    print("🐛 Key Detection Debug Tool")
    print("Press any keys to see what gets detected...")
    print("Press ESC to exit")
    print("=" * 50)
    
    try:
        with keyboard.Listener(
            on_press=on_key_press,
            on_release=on_key_release,
            suppress=False
        ) as listener:
            listener.join()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 