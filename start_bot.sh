#!/bin/bash
# Start Xvfb virtual display if not already running on :99
if ! pgrep -f "Xvfb :99" > /dev/null; then
    Xvfb :99 -screen 0 1366x768x24 &
    sleep 2
fi

export DISPLAY=:99
export PYTHONUNBUFFERED=1
export PYTHONPATH=/home/romeshjainn/PyNaurkiAutomation

cd /home/romeshjainn/PyNaurkiAutomation
exec /usr/bin/python3 -m services.scheduler.scheduler_service
