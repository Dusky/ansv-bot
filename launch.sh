#!/bin/bash

# Starting webapp.py
echo "Starting webapp.py..."
python webapp.py &
WEBAPP_PID=$!
echo "webapp.py started with PID $WEBAPP_PID"

# Starting ansv.py with tts and rebuild-cache options
echo "Starting ansv.py with --tts and --rebuild-cache flags..."
python ansv.py --tts --rebuild-cache &
ANSV_PID=$!
echo "ansv.py started with PID $ANSV_PID"

# Wait for both processes
wait $WEBAPP_PID
wait $ANSV_PID
