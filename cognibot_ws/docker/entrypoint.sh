#!/usr/bin/env bash
# Source ROS 2, the shared underlay, the workspace overlay and the Python venv, then run the command.
set -e
source /opt/ros/jazzy/setup.bash
[ -f /opt/cognibot/underlay/setup.bash ] && source /opt/cognibot/underlay/setup.bash
[ -f /ws/install/setup.bash ] && source /ws/install/setup.bash
[ -f /opt/venv/bin/activate ] && source /opt/venv/bin/activate
if [ -d /opt/venv/lib/python3.12/site-packages ]; then
  export PYTHONPATH="/opt/venv/lib/python3.12/site-packages:${PYTHONPATH}"
fi
exec "$@"
