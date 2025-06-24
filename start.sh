#!/bin/bash

# Start Wispr Voice-to-Text Service

PLIST_FILE="$HOME/Library/LaunchAgents/com.wispr.service.plist"

if [ ! -f "$PLIST_FILE" ]; then
    echo "❌ Wispr service not installed. Run ./install.sh first."
    exit 1
fi

echo "🚀 Starting Wispr service..."

# Stop any existing service
launchctl unload "$PLIST_FILE" 2>/dev/null || true

# Start the service
launchctl load "$PLIST_FILE"

# Check if service is running
sleep 2
if launchctl list | grep -q "com.wispr.service"; then
    echo "✅ Wispr service started successfully!"
    echo "🎤 Hold Fn key to record, release to transcribe and paste"
    echo "📁 Logs: ~/Library/Logs/Wispr/"
    echo "🛑 To stop: ./stop.sh"
else
    echo "❌ Failed to start Wispr service"
    echo "📋 Check logs: ~/Library/Logs/Wispr/wispr_error.log"
    exit 1
fi 