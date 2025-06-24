# Wispr - Voice-to-Text Transcription Service for macOS

**Professional background service with Fn key trigger and auto-paste functionality**

🎤 **Hold Fn key** → Speak → **Release Fn key** → Auto-paste transcribed text

## Features

- ✅ **Global Voice Input**: Works in any application with Fn key trigger
- ✅ **Real-time Transcription**: Powered by AssemblyAI's advanced speech recognition
- ✅ **Smart Pause Handling**: Accumulates speech across natural pauses
- ✅ **Auto-paste**: Automatically pastes transcribed text at cursor location
- ✅ **Audio Feedback**: Press/release sound effects for clear interaction
- ✅ **Background Service**: Runs automatically on macOS startup
- ✅ **Comprehensive Logging**: Tracks all voice interactions and system events
- ✅ **Connection Management**: Robust error handling and automatic recovery

## Installation

### Prerequisites

- **macOS** (tested on macOS 10.15+)
- **Homebrew** for audio dependencies
- **Python 3.8+**
- **AssemblyAI API Key** (free tier available)

### Quick Install

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd wispr
   ```

2. **Run the installer:**
   ```bash
   ./install.sh
   ```

3. **Add your API key:**
   - Edit `.env` file and add your AssemblyAI API key
   - Get a free key at: https://www.assemblyai.com

4. **Grant permissions:**
   - **Accessibility**: System Preferences → Security & Privacy → Accessibility → Add Terminal
   - **Microphone**: Will be prompted automatically on first use

5. **Start the service:**
   ```bash
   ./start.sh
   ```

## Usage

### Basic Operation

1. **Start Recording**: Press and hold the **Fn key**
2. **Speak**: Talk naturally (pauses are handled automatically)
3. **Finish**: Release the **Fn key**
4. **Auto-paste**: Transcribed text is automatically pasted at cursor

### Audio Feedback

- 🔊 **Press sound**: Plays when recording starts
- 🔊 **Release sound**: Plays when recording stops

### Service Management

```bash
# Start the service
./start.sh

# Stop the service  
./stop.sh

# Check service status
launchctl list | grep com.wispr.service
```

## Configuration

### Environment Variables

Edit `.env` file to configure:

```env
# Required: Your AssemblyAI API key
ASSEMBLYAI_API_KEY=your_api_key_here

# Optional: Trigger key (default: fn)
WISPR_TRIGGER_KEY=fn
```

### Trigger Key Options

- `fn` - Function key (default, recommended)
- `right_cmd` - Right Command key
- `right_ctrl` - Right Control key
- `caps_lock` - Caps Lock key
- `backslash` - Backslash key

## Logging

All interactions are logged to standard macOS locations:

### Log Files

```
~/Library/Logs/Wispr/
├── wispr.log              # Main application log
├── transcriptions.log     # All voice interactions
└── wispr_error.log        # Service errors
```

### Log Format

**transcriptions.log** tracks all voice activity:
```
2024-06-24 12:30:15 - SEGMENT: Hello world
2024-06-24 12:30:16 - SEGMENT: How are you
2024-06-24 12:30:17 - COMPLETE_TRANSCRIPT: Hello world. How are you.
2024-06-24 12:30:17 - PASTED: Hello world. How are you.
```

**wispr.log** contains system events:
```
2024-06-24 12:30:14 - INFO - 🎤 Recording started...
2024-06-24 12:30:15 - INFO - 🔗 Connected to AssemblyAI
2024-06-24 12:30:17 - INFO - 🛑 Recording stopped...
2024-06-24 12:30:17 - INFO - 📋 Pasting: "Hello world. How are you."
```

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check logs
tail -f ~/Library/Logs/Wispr/wispr_error.log

# Verify API key
grep ASSEMBLYAI_API_KEY .env

# Check permissions
# System Preferences → Security & Privacy → Accessibility
```

**No audio input:**
```bash
# Check microphone permissions
# System Preferences → Security & Privacy → Microphone

# Test audio system
python3 -c "import pyaudio; print('Audio OK')"
```

**Fn key not working:**
```bash
# Try alternative trigger key
echo "WISPR_TRIGGER_KEY=right_cmd" >> .env
./stop.sh && ./start.sh
```

**Connection errors (1008):**
- Service enforces connection cooldowns to prevent API abuse
- Wait 2 seconds between rapid key presses
- Check internet connection

### Advanced Debugging

**View live logs:**
```bash
tail -f ~/Library/Logs/Wispr/wispr.log
```

**Test without service:**
```bash
./stop.sh
python3 wispr.py  # Run directly for debugging
```

**Reset service:**
```bash
./stop.sh
launchctl unload ~/Library/LaunchAgents/com.wispr.service.plist
./start.sh
```

## Architecture

### Core Components

- **wispr.py**: Main application with voice recognition and key handling
- **com.wispr.service.plist**: macOS launchd service configuration
- **install.sh**: Automated installation and setup
- **start.sh/stop.sh**: Service management scripts

### Dependencies

- **PyAudio**: Audio input/output
- **websocket-client**: AssemblyAI streaming API
- **PyObjC**: macOS Cocoa integration for global key monitoring
- **python-dotenv**: Environment configuration

### Security

- API keys stored in local `.env` file (never transmitted)
- All voice data encrypted in transit to AssemblyAI
- Local logging only (no cloud storage)
- Standard macOS permission system integration

## Uninstall

```bash
# Stop service
./stop.sh

# Remove service file
rm ~/Library/LaunchAgents/com.wispr.service.plist

# Remove logs (optional)
rm -rf ~/Library/Logs/Wispr/

# Remove application (optional)
rm -rf wispr/
```

## Development

### Project Structure

```
wispr/
├── wispr.py                    # Main application
├── sounds/                     # Audio feedback files
│   ├── press.wav              # Recording start sound
│   └── release.wav            # Recording stop sound
├── install.sh                 # Installation script
├── start.sh                   # Service start script
├── stop.sh                    # Service stop script
├── com.wispr.service.plist    # macOS service template
├── requirements.txt           # Python dependencies
├── config.example.env         # Environment template
└── README.md                  # This file
```

### Building from Source

```bash
# Clone and setup
git clone <repository-url>
cd wispr

# Install dependencies manually
brew install portaudio
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp config.example.env .env
# Edit .env with your API key

# Test
python3 wispr.py
```

## License

MIT License - See LICENSE file for details

## Support

- **Documentation**: This README
- **Logs**: `~/Library/Logs/Wispr/`
- **Issues**: Create GitHub issue with logs attached
- **API Support**: https://www.assemblyai.com/docs

---

**Made with ❤️ for seamless voice-to-text on macOS** 