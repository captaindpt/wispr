#!/bin/bash

echo "🚀 Setting up Wispr Flow Clone..."

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This tool is designed for macOS only"
    exit 1
fi

# Install Homebrew if not present
if ! command -v brew &> /dev/null; then
    echo "📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install portaudio
echo "🔊 Installing PortAudio..."
brew install portaudio

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "🐍 Installing Python 3..."
    brew install python
fi

# Create virtual environment
echo "🔧 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Creating .env file..."
    echo "Please edit .env and add your AssemblyAI API key"
    echo "ASSEMBLYAI_API_KEY=your_api_key_here" > .env
    echo "WISPR_AUDIO_FEEDBACK=true" >> .env
    echo "WISPR_AUDIO_VOLUME=0.6" >> .env
fi

echo "✅ Setup complete!"
echo ""
echo "🔑 NEXT STEPS:"
echo "   1. Edit .env file and add your AssemblyAI API key"
echo "   2. Get free API key at: https://www.assemblyai.com/"
echo ""
echo "🔒 IMPORTANT: Grant these permissions:"
echo "   1. System Settings > Privacy & Security > Accessibility"
echo "   2. System Settings > Privacy & Security > Microphone"
echo "   3. Add Terminal (or your terminal app) to both"
echo ""
echo "🎯 To run Wispr Flow:"
echo "   source venv/bin/activate"
echo "   python wispr_flow.py"
echo ""
echo "🎤 Usage: Hold Fn key to record, release to transcribe and paste" 