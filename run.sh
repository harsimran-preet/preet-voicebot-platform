#!/bin/bash

# Preet Voicebot Platform Concurrent Runner
# This script starts both the Python FastAPI server and the React Vite dev server,
# and handles clean shutdown of both processes when you press Ctrl+C.

# Function to gracefully stop both servers on exit
cleanup() {
    echo -e "\n\033[0;31mStopping all servers...\033[0m"
    # Kill background jobs
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

# Trap Ctrl+C (SIGINT) and termination (SIGTERM) signals
trap cleanup SIGINT SIGTERM

echo -e "\033[0;34m===================================================\033[0m"
echo -e "\033[0;32m      PREET VOICEBOT PLATFORM — STARTER COMMAND\033[0m"
echo -e "\033[0;34m===================================================\033[0m"

# 1. Verify .env file exists
if [ ! -f "server/.env" ]; then
    echo -e "\033[0;33mWarning: server/.env file not found. Creating one from template...\033[0m"
    cp server/.env.example server/.env
    echo -e "\033[0;33mPlease open server/.env and add your API keys before running the bot!\033[0m"
fi

# 2. Start Backend FastAPI Server
echo -e "\033[0;32m[1/2] Starting Backend FastAPI Server (http://localhost:8765)...\033[0m"
PYTHONPATH=. server/.venv/bin/python server/app.py > server.log 2>&1 &
BACKEND_PID=$!

# Let the backend initialize for a brief moment
sleep 2

# Check if the backend is still running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "\033[0;31mError: Backend failed to start. Please check 'server.log' for details.\033[0m"
    exit 1
fi

# 3. Start Frontend Vite Console
echo -e "\033[0;32m[2/2] Starting Frontend Vite Console (http://localhost:5173)...\033[0m"
npm run --prefix web dev &
FRONTEND_PID=$!

echo -e "\033[0;34m===================================================\033[0m"
echo -e "\033[1;32mBoth servers running concurrently! Press [Ctrl+C] to stop.\033[0m"
echo -e "\033[0;34m===================================================\033[0m"

# Keep the shell script alive and wait for background processes to finish
wait
