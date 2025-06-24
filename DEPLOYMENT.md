# Wispr Flow Deployment Guide 🚀

This guide covers deploying Wispr Flow as a production service on macOS.

## Quick Deploy 🏃‍♂️

```bash
# 1. Clone and setup
git clone <your-repo>
cd wispr

# 2. Run deployment script
./deploy.sh

# 3. Configure API key
echo "ASSEMBLYAI_API_KEY=your_key_here" > ~/.wispr/.env

# 4. Grant permissions (System Preferences > Security & Privacy)
# - Add Terminal to Microphone access
# - Add Terminal to Accessibility access

# 5. Start service
source ~/.zshrc  # Reload PATH
wispr start
```

## Service Management 🔧

### Commands
```bash
wispr start     # Start the service
wispr stop      # Stop the service  
wispr restart   # Restart the service
wispr status    # Check service status
wispr logs      # View real-time logs
wispr test      # Run in foreground for testing
```

### Service Status
```bash
# Check if running
wispr status

# View recent activity
tail -f ~/.wispr/logs/wispr.log

# Check system service
launchctl list | grep wispr
```

## File Locations 📁

```
~/.wispr/                    # Main directory
├── .env                     # Configuration
├── bin/
│   ├── wispr               # Control script
│   └── wispr_service.py    # Main service
├── logs/
│   ├── wispr.log          # Main log (rotated)
│   ├── error.log          # Service errors
│   └── output.log         # Service output
└── venv/                   # Python virtual environment

~/Library/LaunchAgents/
└── com.wispr.flow.plist    # macOS service configuration
```

## Configuration ⚙️

### Environment Variables (.env)
```bash
# Required
ASSEMBLYAI_API_KEY=your_key_here

# Optional
WISPR_TRIGGER_KEY=fn        # fn, right_cmd, caps_lock, etc.
WISPR_LOG_LEVEL=INFO        # DEBUG, INFO, WARNING, ERROR
```

### Trigger Key Options
- `fn` - Function key (default)
- `right_cmd` - Right Command key
- `right_ctrl` - Right Control key  
- `caps_lock` - Caps Lock key
- `f13` - F13 key (if available)

## Logging 📝

### Log Levels
- **DEBUG**: Detailed debugging info
- **INFO**: General operational info (default)
- **WARNING**: Warning messages
- **ERROR**: Error messages only

### Log Files
- `wispr.log` - Main application log (10MB, 5 backups)
- `error.log` - stderr from service
- `output.log` - stdout from service

### Viewing Logs
```bash
# Real-time logs
wispr logs

# Recent activity
tail -n 50 ~/.wispr/logs/wispr.log

# Errors only
grep ERROR ~/.wispr/logs/wispr.log

# Statistics
grep "Stats -" ~/.wispr/logs/wispr.log
```

## Troubleshooting 🔧

### Service Won't Start
```bash
# Check permissions
./deploy.sh check-permissions

# Test manually
wispr test

# Check service configuration
launchctl list | grep wispr
cat ~/Library/LaunchAgents/com.wispr.flow.plist
```

### Audio Issues
```bash
# Test microphone access
python3 -c "import pyaudio; print('Audio OK')"

# Check system audio preferences
# System Preferences > Sound > Input
```

### Permission Issues
```bash
# Grant permissions in System Preferences > Security & Privacy:
# - Microphone: Add Terminal
# - Accessibility: Add Terminal

# For other terminal apps (iTerm, etc.), add that app instead
```

### API Issues
```bash
# Check API key
cat ~/.wispr/.env

# Test API connection
curl -H "Authorization: YOUR_API_KEY" \
  "https://api.assemblyai.com/v2/transcript"
```

## Auto-Start on Login 🔄

The service is configured to start automatically when you log in via macOS LaunchAgent.

### Manual Control
```bash
# Disable auto-start
launchctl unload ~/Library/LaunchAgents/com.wispr.flow.plist

# Enable auto-start  
launchctl load ~/Library/LaunchAgents/com.wispr.flow.plist
```

## Health Monitoring 💊

The service includes built-in health monitoring:

- **Health checks**: Every 5 minutes
- **Statistics logging**: Every 10 minutes  
- **Auto-recovery**: Attempts to recover from errors
- **Keep-alive**: Restarts if crashed

### Monitoring Commands
```bash
# View service statistics
grep "Stats -" ~/.wispr/logs/wispr.log | tail -5

# Check for errors
grep ERROR ~/.wispr/logs/wispr.log | tail -10

# Check health status
grep "Health check" ~/.wispr/logs/wispr.log | tail -5
```

## Uninstall 🗑️

```bash
# Complete removal
./deploy.sh uninstall

# This removes:
# - ~/.wispr directory
# - LaunchAgent plist
# - PATH entries from shell profile
```

## Security Notes 🔒

- API key stored in `~/.wispr/.env` (user-readable only)
- Logs may contain transcribed text
- Service runs with user permissions only
- No network access except to AssemblyAI API

## Performance 📊

### Expected Resource Usage
- **RAM**: ~50-100MB idle, ~150MB during transcription
- **CPU**: <1% idle, ~5-10% during transcription  
- **Network**: Minimal, only during voice recording
- **Disk**: Log rotation keeps usage under 50MB

### Optimization
- Logs auto-rotate (5x 10MB files)
- Service includes memory cleanup
- Graceful WebSocket connection handling
- Efficient audio buffer management 