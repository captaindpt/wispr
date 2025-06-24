# Wispr Flow Clone

I didn't want to pay for Wispr Flow so I made my own. Hold Fn key to record voice, release to transcribe and paste at cursor.

## Setup

1. Run setup:
   ```bash
   ./setup.sh
   ```

2. Add your AssemblyAI API key to `.env` file:
   ```
   ASSEMBLYAI_API_KEY=your_key_here
   ```
   Get a free key at https://www.assemblyai.com/

3. Grant permissions in System Settings > Privacy & Security:
   - Accessibility (for global hotkey and auto-paste)
   - Microphone (for recording)

## Usage

```bash
./run.sh
```

Hold Fn key anywhere to record, release to transcribe and paste.

## How it works

- Uses macOS native APIs to detect Fn key presses globally
- Captures audio with PyAudio while key is held
- Streams audio to AssemblyAI's real-time transcription API
- Copies result to clipboard and pastes with Cmd+V

## Requirements

- macOS
- Python 3.8+
- AssemblyAI API key 