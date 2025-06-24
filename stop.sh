#!/bin/bash

# Stop Wispr Voice-to-Text Service

PLIST_FILE="$HOME/Library/LaunchAgents/com.wispr.service.plist"

echo "🛑 Stopping Wispr service..."

if launchctl list | grep -q "com.wispr.service"; then
    launchctl unload "$PLIST_FILE"
    echo "✅ Wispr service stopped successfully!"
else
    echo "⚠️ Wispr service was not running"
fi

echo "📁 Logs preserved at: ~/Library/Logs/Wispr/" 