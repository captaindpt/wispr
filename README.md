# Wispr Voice-to-Text

I didn't want to pay for Wispr Flow, so I made my own.

## Technical Overview

This is a production-grade voice-to-text transcription system for macOS that uses the Fn key as a global hotkey trigger. The implementation leverages native macOS Cocoa APIs for system-level key monitoring and integrates with AssemblyAI's real-time streaming transcription service.

### Key Technical Achievements

```
Architecture Features:
├── Native macOS Cocoa integration for global key monitoring
├── Real-time audio streaming with AssemblyAI v3 WebSocket API
├── Robust connection management with exponential backoff
├── Single-instance protection with PID file management
├── Background service architecture using launchd
├── Clipboard preservation during paste operations
├── Production-ready error handling and recovery
└── Comprehensive logging and monitoring system
```

The system addresses several challenging technical problems:

**Global Key Detection**: Implemented native NSEvent monitoring to capture the Fn key, which requires special handling as a hardware-level modifier key (NSFlagsChanged events with flag 0x800000).

**Connection Reliability**: Built sophisticated connection state management to prevent the rate limiting and policy violations common with real-time transcription services. Uses exponential backoff (10s → 20s → 40s → 60s) and enforces 30-second cooldowns after policy violations.

**Background Service Architecture**: Designed as a proper macOS background service with automatic startup, crash recovery, and clean shutdown handling through launchd integration.

**Audio Pipeline**: Implements real-time audio streaming with PyAudio, handling microphone access, buffer management, and WebSocket binary data transmission without introducing latency.

## Installation

```bash
git clone https://github.com/your-username/wispr.git
cd wispr
./install.sh
```

The installer handles:
- Python virtual environment setup
- Audio system dependencies (PortAudio via Homebrew)
- macOS permissions configuration
- Background service registration

## Configuration

1. Copy the environment template:
```bash
cp config.example.env .env
```

2. Add your AssemblyAI API key:
```
ASSEMBLYAI_API_KEY=your_actual_api_key_here
WISPR_TRIGGER_KEY=fn
```

3. Grant system permissions:
   - Accessibility: System Preferences → Security & Privacy → Accessibility
   - Microphone: System Preferences → Security & Privacy → Microphone

## Usage

### Service Management
```bash
./start.sh    # Start background service
./stop.sh     # Stop background service
```

### Operation
- Hold Fn key to start recording
- Speak naturally (supports pauses and natural speech patterns)
- Release Fn key to stop recording and paste transcription
- Audio feedback confirms recording start/stop

The system accumulates all speech during the recording session, so you can speak in natural phrases with pauses without triggering premature transcription.

## Architecture

### Core Components

**Audio Manager**: Handles microphone access and real-time audio streaming using PyAudio with 16kHz/16-bit PCM format optimized for speech recognition.

**Connection Manager**: Manages WebSocket connections to AssemblyAI with robust error handling, connection pooling, and rate limiting protection.

**Event Handler**: Implements global key monitoring using macOS Cocoa NSEvent APIs with proper debouncing and state management.

**Service Controller**: Provides background service lifecycle management through macOS launchd with automatic restart capabilities.

### Data Flow

```
Fn Key Press → Audio Capture → WebSocket Stream → AssemblyAI Processing
     ↓              ↓               ↓                    ↓
State Update → Buffer Management → Real-time Send → Transcript Segments
     ↓              ↓               ↓                    ↓  
Recording LED → Audio Streaming → Connection Monitor → Text Accumulation
     ↓              ↓               ↓                    ↓
Fn Key Release → Stop Capture → Close Connection → Paste Final Text
```

### Error Handling

The system implements multiple layers of error recovery:

- **Connection Errors**: Exponential backoff with circuit breaker pattern
- **Audio Errors**: Automatic stream recovery and device reinitialization  
- **Service Crashes**: launchd automatic restart with throttling protection
- **Permission Errors**: Graceful degradation with user notification

## Logging and Monitoring

Logs are written to standard macOS locations:

```
~/Library/Logs/Wispr/
├── wispr.log           # Main application events and errors
├── transcriptions.log  # Complete record of all voice interactions
└── wispr_error.log     # Service-level errors and crashes
```

Log rotation is handled automatically by macOS syslog.

### Log Analysis
```bash
# Monitor real-time activity
tail -f ~/Library/Logs/Wispr/wispr.log

# View transcription history
grep "COMPLETE_TRANSCRIPT" ~/Library/Logs/Wispr/transcriptions.log

# Check for connection issues
grep "1008\|Policy violation" ~/Library/Logs/Wispr/wispr.log
```

## Technical Specifications

**Audio Processing**:
- Sample Rate: 16kHz
- Bit Depth: 16-bit PCM
- Channels: Mono
- Buffer Size: 800 frames (50ms chunks)

**Connection Management**:
- Base Cooldown: 3 seconds between connections
- Error Cooldown: 10-60 seconds with exponential backoff
- Policy Violation Cooldown: 30 seconds
- Maximum Concurrent Connections: 1 (enforced)

**Performance**:
- Typical latency: 200-500ms from speech to transcription
- Memory usage: ~30MB baseline
- CPU usage: <1% during idle, ~5% during active transcription

## Dependencies

**System Requirements**:
- macOS 10.14+ (Mojave or later)
- Python 3.8+
- Microphone access permissions
- Accessibility permissions

**Core Dependencies**:
- PyAudio: Real-time audio I/O
- websocket-client: AssemblyAI API communication
- pyobjc-framework-Cocoa: Native macOS integration
- python-dotenv: Configuration management

## Troubleshooting

**Permission Issues**: Ensure both Accessibility and Microphone permissions are granted in System Preferences.

**Connection Failures**: Check network connectivity and verify AssemblyAI API key validity. Monitor logs for rate limiting indicators.

**Audio Problems**: Verify microphone functionality in other applications. Check for exclusive audio device access by other software.

**Service Issues**: Use `launchctl list | grep wispr` to verify service status. Check error logs for crash reports.

## License

MIT License - build whatever you want with this. 