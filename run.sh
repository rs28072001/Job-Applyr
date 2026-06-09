#!/bin/bash

# Smart Job Assistant - Local Development Startup Script
# This script starts both the backend and frontend servers

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Smart Job Assistant - Local Development ===${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Creating from .env.example if available...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}Created .env from .env.example. Please edit it with your credentials.${NC}"
    else
        echo -e "${YELLOW}Please create a .env file with your configuration.${NC}"
    fi
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping servers...${NC}"
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}Servers stopped.${NC}"
    exit 0
}

# Function to kill processes on specific ports
kill_ports() {
    echo -e "${YELLOW}Cleaning up existing processes on project ports...${NC}"
    for port in 5173 5174 5175 5176 8001; do
        pids=$(lsof -ti :$port 2>/dev/null || true)
        if [ -n "$pids" ]; then
            for pid in $pids; do
                echo -e "  Killing process on port $port (PID: $pid)"
                kill -9 $pid 2>/dev/null || true
            done
        fi
    done
    echo -e "${GREEN}Port cleanup complete.${NC}"
}

# Function to clean webdriver-manager lock file
clean_wdm_lock() {
    echo -e "${YELLOW}Cleaning webdriver-manager lock file...${NC}"
    rm -f ~/.wdm/.wdm-lock-chromedriver-mac_arm64 2>/dev/null || true
    echo -e "${GREEN}WDM lock cleanup complete.${NC}"
}

# Function to kill Chrome processes
kill_chrome() {
    echo -e "${YELLOW}Killing existing Chrome processes...${NC}"
    pkill -f "Google Chrome" 2>/dev/null || true
    pkill -f "chromedriver" 2>/dev/null || true
    echo -e "${GREEN}Chrome cleanup complete.${NC}"
}

# Register cleanup function
trap cleanup SIGINT SIGTERM

# Kill existing processes on project ports
kill_ports

# Clean webdriver-manager lock file
clean_wdm_lock

# Kill existing Chrome processes
kill_chrome

# Start Backend
echo -e "${BLUE}Starting Backend...${NC}"
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing/updating Python dependencies...${NC}"
pip install -q -r requirements.txt

# Initialize database
echo -e "${YELLOW}Initializing database...${NC}"
python -c "from api.database import init_db; init_db()" 2>/dev/null || true

# Start backend server in background
echo -e "${GREEN}Starting backend server on http://localhost:8001${NC}"
python -m uvicorn api.server:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!

# Go back to project root
cd "$SCRIPT_DIR"

# Wait a moment for backend to start
sleep 3

# Start Frontend
echo -e "${BLUE}Starting Frontend...${NC}"
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing Node.js dependencies...${NC}"
    npm install
fi

# Start frontend server in background
echo -e "${GREEN}Starting frontend server on http://localhost:5173${NC}"
npm run dev &
FRONTEND_PID=$!

# Go back to project root
cd "$SCRIPT_DIR"

echo ""
echo -e "${GREEN}=== Both servers are running ===${NC}"
echo -e "${GREEN}Frontend: http://localhost:5173${NC}"
echo -e "${GREEN}Backend:  http://localhost:8001${NC}"
echo -e "${GREEN}API Docs:  http://localhost:8001/docs${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
echo ""

# Wait for any process to exit
wait
