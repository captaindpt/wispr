#!/bin/bash

# Wispr Installation Script for macOS
# This script sets up Wispr as a background service

set -e

echo "🎤 Installing Wispr Voice-to-Text Service..."

# Get current directory
WISPR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH=$(which python3)
LOG_DIR="$HOME/Library/Logs/Wispr"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="com.wispr.service.plist"

# Create directories
echo "📁 Creating directories..."
mkdir -p "$LOG_DIR"
mkdir -p "$PLIST_DIR"

# Check dependencies
echo "🔍 Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew is required for audio dependencies"
    echo "   Install from: https://brew.sh"
    exit 1
fi

# Install system dependencies
echo "🔧 Installing audio dependencies..."
brew install portaudio

# Setup Python virtual environment
echo "🐍 Setting up Python environment..."
if [ ! -d "$WISPR_DIR/venv" ]; then
    python3 -m venv "$WISPR_DIR/venv"
fi

# Activate virtual environment and install packages
source "$WISPR_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$WISPR_DIR/requirements.txt"

# Update Python path to use virtual environment
PYTHON_PATH="$WISPR_DIR/venv/bin/python"

# Check for .env file
if [ ! -f "$WISPR_DIR/.env" ]; then
    echo "⚙️ Creating .env file..."
    cp "$WISPR_DIR/config.example.env" "$WISPR_DIR/.env"
    echo ""
    echo "🔑 IMPORTANT: Edit $WISPR_DIR/.env and add your AssemblyAI API key"
    echo "   Get your free API key at: https://www.assemblyai.com"
    echo ""
fi

# Create launchd plist file
echo "🚀 Setting up background service..."
sed -e "s|REPLACE_WITH_PYTHON_PATH|$PYTHON_PATH|g" \
    -e "s|REPLACE_WITH_WISPR_PATH|$WISPR_DIR|g" \
    -e "s|REPLACE_WITH_LOG_PATH|$LOG_DIR|g" \
    "$WISPR_DIR/com.wispr.service.plist" > "$PLIST_DIR/$PLIST_FILE"

# Set permissions
chmod 644 "$PLIST_DIR/$PLIST_FILE"
chmod +x "$WISPR_DIR/wispr.py"

echo "✅ Installation complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit $WISPR_DIR/.env and add your AssemblyAI API key"
echo "2. Grant Accessibility permissions to Terminal or your terminal app"
echo "3. Grant Microphone permissions when prompted"
echo "4. Run: ./start.sh to start the service"
echo ""
echo "📁 Logs will be available at: $LOG_DIR"
echo "   - wispr.log (main application log)"
echo "   - transcriptions.log (all voice interactions)"
echo ""
echo "🛑 To stop the service, run: ./stop.sh" 