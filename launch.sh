#!/bin/bash

# ANSI Color Codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Emoji Constants
ROCKET="🚀"
ROBOT="🤖"
GLOBE="🌐"
TOOLS="🛠️"
PARTY="🎉"
ALIEN="👽"
FIRE="🔥"
BRAIN="🧠"
MUSIC="🎵"

# Environment Setup
VENV_DIR=".venv"
CONFIG_FILE="settings.conf"
EXAMPLE_CONFIG="settings.example.conf"
TTS_MODELS_DIR="models/tts"
TTS_OUTPUT_DIR="static/outputs"
TTS_VOICES_DIR="voices"

# ASCII Art Banner with Animation Frames
print_banner() {
    clear
    frames=(
        "    █████╗ ███╗   ██╗███████╗██╗   ██╗    "
        "   ██╔══██╗████╗  ██║██╔════╝██║   ██║    "
        "   ███████║██╔██╗ ██║███████╗██║   ██║    "
        "   ██╔══██║██║╚██╗██║╚════██║██║   ██║    "
        "   ██║  ██║██║ ╚████║███████║╚██████╔╝    "
        "   ╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝ ╚═════╝     "
    )
    
    echo -e "${MAGENTA}"
    for frame in "${frames[@]}"; do
        echo "$frame"
        sleep 0.1
    done
    echo -e "${NC}"
}

# Fun Loading Spinner
show_loading() {
    echo -n -e "${YELLOW}Preparing the party "
    while true; do
        for c in "🌑" "🌒" "🌓" "🌔" "🌕" "🌖" "🌗" "🌘"; do
            echo -ne "\b$c"
            sleep 0.1
        done
    done
}

# First-Run Dance Party 🎉
first_run_dance() {
    echo -e "\n${CYAN}First run detected! Let's dance!${NC}"
    dances=("💃" "🕺" "🎊" "🎈")
    for i in {1..10}; do
        echo -n -e "${dances[$RANDOM % ${#dances[@]}]} "
        sleep 0.2
    done
    echo -e "\n"
}

# Configuration Wizard with Personality
first_run_wizard() {
    echo -e "${BRAIN} ${YELLOW}Hi! I'm ANSV-Buddy! Let's get you set up!${NC}"
    
    read -p "$(echo -e ${ROBOT}" What's your bot's name? ➤ ")" bot_name
    read -p "$(echo -e ${ALIEN}" Your Twitch username? ➤ ")" owner
    read -p "$(echo -e ${GLOBE}" Channels to join (comma-separated)? ➤ ")" channels
    
    # Create config with proper sections
    cat > "$CONFIG_FILE" << EOF
[auth]
tmi_token = oauth:your_token_here
client_id = your_client_id_here
nickname = $bot_name
owner = $owner

[channels]
channels = $channels
EOF
    
    echo -e "\n${PARTY} ${GREEN}All set! Let's get this party started!${NC}"
    first_run_dance
}

# Fun Security Check
check_security() {
    if grep -q "oauth:your" settings.conf; then
        echo -e "${RED}🚨 RED ALERT! 🚨"
        echo -e "${FIRE} You're using placeholder credentials! ${FIRE}"
        echo -e "${YELLOW}Visit ${CYAN}https://dev.twitch.tv/console${YELLOW}"
        echo -e "to get your real credentials!${NC}"
        exit 1
    fi
}

# Fun Status Dashboard
show_status() {
    echo -e "\n${CYAN}=== System Status Dashboard ==="
    echo -e "${ROCKET} Bot Running:    $(ps aux | grep [a]nsv.py | wc -l)"
    echo -e "${GLOBE} Web Interface:  $(netstat -tuln | grep ':5001' | wc -l)"
    echo -e "${MUSIC} TTS Enabled:    ${TTS:-false}"
    echo -e "${MUSIC} Voice Models:   $(find "$HF_HOME/hub" -type d -name "snapshots" 2>/dev/null | wc -l)"
    echo -e "${MUSIC} Voice Presets:  $(find "$TTS_VOICES_DIR" -name "*.npz" 2>/dev/null | wc -l)"
    echo -e "${BRAIN} Models Loaded:  $(ls cache/*.json 2>/dev/null | wc -l)"
    echo -e "${ROBOT} Messages in DB: $(sqlite3 messages.db "SELECT COUNT(*) FROM messages" 2>/dev/null)"
    echo -e "${TOOLS} Python Version: $(python3.11 --version 2>&1 | cut -d' ' -f2)"
    echo -e "${ALIEN} Disk Usage:     $(du -sh . | cut -f1)"
    echo -e "${PARTY} Last Modified:  $(stat -f "%Sm" -t "%Y-%m-%d %H:%M" ansv.py)"
    echo -e "${FIRE} Active Users:   $(who | wc -l | tr -d ' ')"
    echo -e "==============================${NC}\n"
}

# Enhanced Menu System with Emojis
interactive_menu() {
    while true; do
        print_banner
        echo -e "${CYAN}=== MAIN MENU ==="
        echo -e "0) ${TOOLS} Clean Install & Setup"
        echo -e "1) ${ROCKET} Launch Bot Only"
        echo -e "2) ${GLOBE} Bot + Web Interface"
        echo -e "3) ${MUSIC} Bot + Web + TTS"
        echo -e "4) ${TOOLS} Web Interface Only"
        echo -e "5) ${FIRE} Development Server"
        echo -e "6) ${BRAIN} Rebuild Cache & Start"
        echo -e "7) ${ALIEN} System Status"
        echo -e "8) ${PARTY} Exit"
        echo -n -e "\n${YELLOW}What's your pleasure? [0-8]: ${NC}"

        read -r choice
        case $choice in
            0) 
                echo -e "${YELLOW}Enable TTS for clean install? (y/n): ${NC}"
                read -r tts_choice
                [ "$tts_choice" = "y" ] && TTS=true
                clean_install
                break
                ;;
            1) start_bot; break ;;
            2) WEB=true; start_bot; break ;;
            3) 
                WEB=true 
                TTS=true
                check_dependencies
                install_requirements
                start_bot
                break
                ;;
            4) start_web; break ;;
            5) dev_server; break ;;
            6) REBUILD=true; start_bot; break ;;
            7) show_status;;
            8) echo -e "${PARTY} ${RED}Exiting...${NC}"; exit 0 ;;
            *) echo -e "${RED}Invalid choice! Try again! ${FIRE}"; sleep 1 ;;
        esac
    done
}

# Add this function near the top with other helper functions
need_dependencies_check() {
    # Create a marker file when dependencies are installed
    local DEPS_MARKER=".deps_installed"
    
    # If marker doesn't exist or is older than 7 days, return true (need check)
    if [ ! -f "$DEPS_MARKER" ] || [ $(find "$DEPS_MARKER" -mtime +7 -print 2>/dev/null | wc -l) -gt 0 ]; then
        return 0 # true, need to check deps
    else
        return 1 # false, no need to check deps
    fi
}

# Then modify the start_bot function
start_bot() {
    echo -e "\n${GREEN}${ROCKET} Launch sequence initiated! ${ROCKET}${NC}"
    show_loading &
    LOAD_PID=$!
    
    # Only check deps if not coming from clean install and deps need checking
    if [ -z "$CLEAN_INSTALL_DONE" ] && need_dependencies_check; then
        check_dependencies
        install_requirements
        # Create or update the deps marker file
        touch .deps_installed
    else
        echo -e "${GREEN}Using existing dependencies${NC}"
    fi
    
    source $VENV_DIR/bin/activate
    local command="python ansv.py"
    
    [ "$WEB" = true ] && command+=" --web"
    [ "$TTS" = true ] && command+=" --tts"
    [ "$REBUILD" = true ] && command+=" --rebuild-cache"
    if [ -n "$VOICE_PRESET" ]; then
        command+=" --voice-preset $VOICE_PRESET"
    fi
    
    kill $LOAD_PID
    echo -e "\n${GREEN}${FIRE} BLAST OFF! ${FIRE}${NC}"
    trap 'echo "Caught signal, shutting down cleanly..."; kill -TERM $PID 2>/dev/null' INT TERM
    eval $command
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo -e "${RED}Bot exited with error code $EXIT_CODE${NC}"
    fi
    exit $EXIT_CODE
}

# Helper Functions
check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${RED}Virtual environment not found!${NC}"
        echo -e "Run: ${YELLOW}python3.11 -m venv $VENV_DIR${NC}"
        exit 1
    fi
}

check_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${YELLOW}Warning: settings.conf not found${NC}"
        echo -e "Copying example config... (${BLUE}edit before production!${NC})"
        cp "$EXAMPLE_CONFIG" "$CONFIG_FILE"
    fi
}

# Command Handlers
start_web() {
    echo -e "${GREEN}🌐 Starting Web Interface...${NC}"
    source $VENV_DIR/bin/activate
    python webapp.py
}

dev_server() {
    echo -e "${GREEN}🔧 Starting Development Server...${NC}"
    export FLASK_DEBUG=1
    export FLASK_ENV=development
    source $VENV_DIR/bin/activate
    python webapp.py
}

# Main Execution
parse_arguments() {
    # Default values
    WEB=false
    TTS=false
    REBUILD=false
    DEV=false
    WEB_ONLY=false
    CLEAN=false
    VOICE_PRESET=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --web) WEB=true ;;
            --tts) TTS=true ;;
            --voice-preset)
                VOICE_PRESET="$2"
                shift 
                ;;
            --download-models) 
                export HF_HOME="${PWD}/.hf_cache"
                source $VENV_DIR/bin/activate
                prepare_tts_directories
                check_tts_models
                download_voice_preset "v2/en_speaker_6"
                echo -e "${GREEN}✅ Models downloaded successfully!${NC}"
                exit 0 
                ;;
            --rebuild) REBUILD=true ;;
            --dev) DEV=true ;;
            --web-only) WEB_ONLY=true ;;
            --clean) CLEAN=true ;;
            -h|--help) show_help; exit 0 ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
        shift
    done
    
    # Second pass: execute commands based on flags
    if [ "$CLEAN" = true ]; then
        clean_install
        # After clean install, continue with other commands
        [ "$TTS" = true ] && TTS=true
    fi
    
    # Handle post-clean operations
    if [ "$DEV" = true ]; then
        dev_server
        exit 0
    elif [ "$WEB_ONLY" = true ]; then
        start_web
        exit 0
    elif [ "$CLEAN" = true ]; then
        # If clean was only command, start normally
        start_bot
        exit 0
    fi
    start_bot
}

show_help() {
    echo -e "${YELLOW}Usage:${NC}"
    echo "  ./launch.sh [options] - Command-line mode"
    echo "  ./launch.sh           - Interactive menu mode"
    echo
    echo "${YELLOW}Options:${NC}"
    echo "  --web       : Enable web interface with bot"
    echo "  --tts       : Enable TTS functionality"
    echo "  --voice-preset PRESET : Use specific voice preset (e.g., v2/en_speaker_6)"
    echo "  --download-models : Only download TTS models and exit"
    echo "  --rebuild   : Rebuild Markov cache at startup"
    echo "  --dev       : Start web interface in development mode"
    echo "  --web-only  : Start web interface without bot"
    echo "  --clean     : Perform fresh install"
    echo "  --help      : Show this help message"
    echo
    echo "${YELLOW}Examples:${NC}"
    echo "  ./launch.sh --web --tts      # Bot + Web + TTS"
    echo "  ./launch.sh --tts --voice-preset v2/en_speaker_9  # Use specific voice"
    echo "  ./launch.sh --download-models # Pre-download models"
    echo "  ./launch.sh --dev            # Dev server with hot reload"
}

check_dependencies() {
    echo -e "${CYAN}🔍 Checking system dependencies...${NC}"
    
    # Detect platform
    case "$(uname -s)" in
        Darwin*)    PLATFORM="macos" ;;
        Linux*)     PLATFORM="linux" ;;
        MINGW*|CYGWIN*) PLATFORM="windows" ;;
    esac

    # Check for Homebrew on macOS
    if [ "$PLATFORM" = "macos" ] && ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}Installing Homebrew...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi

    # Check Python version
    if ! python3.11 --version &> /dev/null; then
        echo -e "${RED}Python 3.11 not found!${NC}"
        echo -e "${YELLOW}Installing via Homebrew...${NC}"
        brew install python@3.11
    fi

    # Check TTS dependencies if requested
    if [ "$TTS" = true ]; then
        if ! command -v ffmpeg &> /dev/null; then
            echo -e "${YELLOW}Installing ffmpeg...${NC}"
            case "$PLATFORM" in
                "macos")   brew install ffmpeg ;;
                "linux")   sudo apt-get install -y ffmpeg ;;
                "windows") echo "Please install ffmpeg from https://ffmpeg.org/download.html" ;;
            esac
        fi
    fi
}

install_requirements() {
    echo -e "${CYAN}📦 Installing Python requirements...${NC}"
    # Configure HF home directory and disable warnings
    export HF_HOME="${PWD}/.hf_cache"
    export HF_HUB_DISABLE_PROGRESS_BARS=1
    export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
    
    # Ensure we're in the virtual environment
    source $VENV_DIR/bin/activate
    
    pip install -r requirements.txt
    
    if [ "$TTS" = true ]; then
        echo -e "${MUSIC} Installing TTS dependencies...${NC}"
        prepare_tts_directories
        
        # Create a temporary requirements file with pinned versions to avoid dependency resolution issues
        TMP_REQ=$(mktemp)
        cat > "$TMP_REQ" << EOF
accelerate==0.26.1
transformers==4.36.2
scipy==1.11.4
numpy==1.26.2
huggingface-hub==0.19.4
soundfile==0.12.1
nltk==3.8.1
EOF

        # Install dependencies with pinned versions first
        echo -e "${CYAN}Installing core dependencies with pinned versions...${NC}"
        pip install -r "$TMP_REQ" --no-cache-dir
        
        # Then install Bark from GitHub
        echo -e "${CYAN}Installing Bark from GitHub...${NC}"
        pip install --no-deps git+https://github.com/suno-ai/bark.git@main
        
        # Platform-specific PyTorch installation
        case "$PLATFORM" in
            "macos")
                echo "Installing PyTorch for macOS..."
                pip install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu
                ;;
            "linux"|"windows")
                if command -v nvidia-smi &> /dev/null; then
                    echo "Installing PyTorch with CUDA support..."
                    pip install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu121
                else
                    echo "Installing PyTorch CPU version..."
                    pip install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu
                fi
                ;;
        esac
        
        # Clean up
        rm "$TMP_REQ"
        
        check_tts_models
    fi
}

clean_install() {
    echo -e "${RED}♻️  Nuclear Option: Fresh Install${NC}"
    rm -rf $VENV_DIR
    python3.11 -m venv $VENV_DIR
    source $VENV_DIR/bin/activate
    check_dependencies
    install_requirements
    export CLEAN_INSTALL_DONE=true
    echo -e "${GREEN}✅ Fresh environment created!${NC}"
}

prepare_tts_directories() {
    echo -e "${CYAN}📂 Setting up TTS directories...${NC}"
    mkdir -p "$TTS_MODELS_DIR"
    mkdir -p "$TTS_OUTPUT_DIR"
    mkdir -p "$TTS_VOICES_DIR"
    
    # Create channel-specific output directories from settings
    if [ -f "$CONFIG_FILE" ]; then
        channels=$(grep -A 1 "channels =" "$CONFIG_FILE" | tail -1 | tr -d ' ' | tr ',' ' ')
        for channel in $channels; do
            mkdir -p "$TTS_OUTPUT_DIR/$channel"
        done
    fi
}

check_tts_models() {
    echo -e "${CYAN}🔍 Checking TTS models...${NC}"
    
    # Basic presence check
    if [ ! -d "$HF_HOME/hub" ]; then
        echo -e "${YELLOW}⚠️ No Hugging Face models found. First run will download models.${NC}"
        echo -e "${YELLOW}   This may take a while (1-2GB). Get some coffee! ☕${NC}"
    else
        model_count=$(find "$HF_HOME/hub" -type d -name "snapshots" | wc -l)
        echo -e "${GREEN}✅ Found $model_count cached model(s)${NC}"
    fi
}

download_voice_preset() {
    preset="$1"
    echo -e "${CYAN}🎤 Downloading voice preset: $preset...${NC}"
    
    python -c "
from transformers import BarkModel
model = BarkModel.from_pretrained('suno/bark-small', cache_dir='$TTS_MODELS_DIR')
model._get_speaker_embedding('$preset')
print('Voice preset downloaded successfully!')
" || echo -e "${RED}Failed to download voice preset${NC}"
}

# Runtime Execution with Flair
print_banner
check_venv
check_config
[ ! -f "$CONFIG_FILE" ] && first_run_wizard
check_security

# Check if arguments were provided
if [ $# -eq 0 ]; then
    # No arguments, show interactive menu
    interactive_menu
else
    # Parse command line arguments
    parse_arguments "$@"
fi 