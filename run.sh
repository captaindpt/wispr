#!/bin/bash

# Quick run script for Wispr Flow
echo "🎤 Starting Wispr Flow..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./setup.sh first"
    exit 1
fi

# Check if .env file exists and has API key
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please run ./setup.sh first"
    exit 1
fi

# Check if API key is set
if ! grep -q "ASSEMBLYAI_API_KEY=.*[^r][^e]$" .env; then
    echo "❌ Please edit .env and add your AssemblyAI API key"
    echo "Get one free at: https://www.assemblyai.com/"
    exit 1
fi

# Activate virtual environment and run
source venv/bin/activate
python wispr_flow.py