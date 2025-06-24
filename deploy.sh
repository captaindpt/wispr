#!/bin/bash

# Wispr Flow Deployment Script
# Installs and configures Wispr Flow as a system service on macOS

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WISPR_USER=$(whoami)
WISPR_HOME="$HOME/.wispr"
WISPR_LOG_DIR="$WISPR_HOME/logs"
WISPR_BIN_DIR="$WISPR_HOME/bin"
PLIST_NAME="com.wispr.flow"
PLIST_FILE="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE} Wispr Deployment Script${NC}"
echo "================================"

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running on macOS
check_macos() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        print_error "This script is designed for macOS only"
        exit 1
    fi
    print_success "Running on macOS"
}

# Check dependencies
check_dependencies() {
    print_info "Checking system dependencies..."
    
    # Check Homebrew
    if ! command -v brew &> /dev/null; then
        print_error "Homebrew not found. Installing..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    print_success "Homebrew available"
    
    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found. Installing..."
        brew install python
    fi
    print_success "Python 3 available"
    
    # Check portaudio
    if ! brew list portaudio &> /dev/null; then
        print_info "Installing portaudio..."
        brew install portaudio
    fi
    print_success "PortAudio available"
}

# Install Python dependencies
install_python_deps() {
    print_info "Installing Python dependencies..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "$WISPR_HOME/venv" ]; then
        python3 -m venv "$WISPR_HOME/venv"
    fi
    
    # Activate virtual environment and install deps
    source "$WISPR_HOME/venv/bin/activate"
    pip install --upgrade pip
    pip install -r "$CURRENT_DIR/requirements.txt"
    
    print_success "Python dependencies installed"
}

# Create directory structure
setup_directories() {
    print_info "Setting up directory structure..."
    
    mkdir -p "$WISPR_HOME"
    mkdir -p "$WISPR_LOG_DIR"
    mkdir -p "$WISPR_BIN_DIR"
    mkdir -p "$HOME/Library/LaunchAgents"
    
    print_success "Directories created"
}

# Copy files
install_files() {
    print_info "Installing Wispr Flow files..."
    
    # Copy main service script
    cp "$CURRENT_DIR/wispr_service.py" "$WISPR_BIN_DIR/"
    chmod +x "$WISPR_BIN_DIR/wispr_service.py"
    
    # Copy .env file if it exists
    if [ -f "$CURRENT_DIR/.env" ]; then
        cp "$CURRENT_DIR/.env" "$WISPR_HOME/"
    else
        print_warning ".env file not found. You'll need to create it manually."
    fi
    
    # Copy control script
    cat > "$WISPR_BIN_DIR/wispr" << 'EOF'
#!/bin/bash
WISPR_HOME="$HOME/.wispr"
VENV_PYTHON="$WISPR_HOME/venv/bin/python"
SERVICE_SCRIPT="$WISPR_HOME/bin/wispr_service.py"

# Load environment
cd "$WISPR_HOME"

case "$1" in
    start)
        echo "🚀 Starting Wispr Flow service..."
        launchctl load "$HOME/Library/LaunchAgents/com.wispr.flow.plist"
        ;;
    stop)
        echo "Stopping Wispr Flow service..."
        launchctl unload "$HOME/Library/LaunchAgents/com.wispr.flow.plist"
        ;;
    restart)
        echo "Restarting Wispr Flow service..."
        launchctl unload "$HOME/Library/LaunchAgents/com.wispr.flow.plist" 2>/dev/null || true
        sleep 2
        launchctl load "$HOME/Library/LaunchAgents/com.wispr.flow.plist"
        ;;
    status)
        if launchctl list | grep -q "com.wispr.flow"; then
            echo "Wispr Flow is running"
            echo "Recent activity:"
            tail -n 20 "$WISPR_HOME/logs/wispr.log" | grep -E "(Starting|Stopping|transcript|error)" || echo "No recent activity"
        else
            echo "Wispr Flow is not running"
        fi
        ;;
    logs)
        echo "Wispr Flow logs (press Ctrl+C to exit):"
        tail -f "$WISPR_HOME/logs/wispr.log"
        ;;
    test)
        echo "🧪 Testing Wispr Flow..."
        "$VENV_PYTHON" "$SERVICE_SCRIPT" --log-dir "$WISPR_HOME/logs" --log-level DEBUG
        ;;
    *)
        echo "Usage: wispr {start|stop|restart|status|logs|test}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the Wispr Flow service"
        echo "  stop    - Stop the Wispr Flow service"
        echo "  restart - Restart the Wispr Flow service"
        echo "  status  - Show service status"
        echo "  logs    - Show real-time logs"
        echo "  test    - Run in test mode (foreground)"
        exit 1
        ;;
esac
EOF
    
    chmod +x "$WISPR_BIN_DIR/wispr"
    
    print_success "Files installed"
}

# Create LaunchAgent plist
create_launchd_plist() {
    print_info "Creating LaunchAgent configuration..."
    
    cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>$WISPR_HOME/venv/bin/python</string>
        <string>$WISPR_BIN_DIR/wispr_service.py</string>
        <string>--log-dir</string>
        <string>$WISPR_LOG_DIR</string>
        <string>--log-level</string>
        <string>INFO</string>
        <string>--daemon</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$WISPR_HOME</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>$WISPR_LOG_DIR/error.log</string>
    <key>StandardOutPath</key>
    <string>$WISPR_LOG_DIR/output.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF
    
    print_success "LaunchAgent configuration created"
}

# Setup PATH
setup_path() {
    print_info "Setting up PATH..."
    
    # Add to shell profile
    SHELL_PROFILE=""
    if [ -f "$HOME/.zshrc" ]; then
        SHELL_PROFILE="$HOME/.zshrc"
    elif [ -f "$HOME/.bash_profile" ]; then
        SHELL_PROFILE="$HOME/.bash_profile"
    elif [ -f "$HOME/.bashrc" ]; then
        SHELL_PROFILE="$HOME/.bashrc"
    fi
    
    if [ -n "$SHELL_PROFILE" ]; then
        if ! grep -q "WISPR_HOME" "$SHELL_PROFILE"; then
            echo "" >> "$SHELL_PROFILE"
            echo "# Wispr Flow" >> "$SHELL_PROFILE"
            echo "export WISPR_HOME=\"$WISPR_HOME\"" >> "$SHELL_PROFILE"
            echo "export PATH=\"\$WISPR_HOME/bin:\$PATH\"" >> "$SHELL_PROFILE"
        fi
        print_success "PATH updated in $SHELL_PROFILE"
    else
        print_warning "Could not find shell profile. Add $WISPR_BIN_DIR to your PATH manually."
    fi
}

# Check permissions
check_permissions() {
    print_info "Checking system permissions..."
    
    print_warning "You need to grant the following permissions:"
    echo "1. Microphone access to Terminal (or your terminal app)"
    echo "2. Accessibility access to Terminal (for key detection and auto-paste)"
    echo ""
    echo "To grant these permissions:"
    echo "• Go to System Preferences > Security & Privacy > Privacy"
    echo "• Add Terminal to both 'Microphone' and 'Accessibility' sections"
    echo ""
    read -p "Press Enter when you've granted the permissions..."
}

# Main installation function
install() {
    echo "Installing Wispr Flow..."
    echo ""
    
    check_macos
    check_dependencies
    setup_directories
    install_python_deps
    install_files
    create_launchd_plist
    setup_path
    
    print_success "Installation completed!"
    echo ""
    echo "Next steps:"
    echo "1. Make sure you have your ASSEMBLYAI_API_KEY in $WISPR_HOME/.env"
    echo "2. Grant microphone and accessibility permissions"
    echo "3. Start a new terminal session or run: source ~/.zshrc"
    echo "4. Test with: wispr test"
    echo "5. Start service with: wispr start"
    echo ""
    echo "Commands available:"
    echo "• wispr start    - Start the service"
    echo "• wispr stop     - Stop the service"
    echo "• wispr status   - Check service status"
    echo "• wispr logs     - View real-time logs"
    echo "• wispr test     - Run in test mode"
}

# Uninstall function
uninstall() {
    print_info "Uninstalling Wispr Flow..."
    
    # Stop service
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    
    # Remove files
    rm -rf "$WISPR_HOME"
    rm -f "$PLIST_FILE"
    
    # Remove from PATH (basic removal)
    if [ -f "$HOME/.zshrc" ]; then
        sed -i '' '/# Wispr Flow/,+2d' "$HOME/.zshrc" 2>/dev/null || true
    fi
    
    print_success "Wispr Flow uninstalled"
}

# Main script logic
case "${1:-install}" in
    install)
        install
        ;;
    uninstall)
        uninstall
        ;;
    check-permissions)
        check_permissions
        ;;
    *)
        echo "Usage: $0 {install|uninstall|check-permissions}"
        echo ""
        echo "Commands:"
        echo "  install            - Install Wispr Flow (default)"
        echo "  uninstall          - Remove Wispr Flow completely"
        echo "  check-permissions  - Guide through permission setup"
        exit 1
        ;;
esac 