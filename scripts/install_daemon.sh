#!/usr/bin/env bash
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (e.g., sudo ./scripts/install_daemon.sh)"
  exit 1
fi

if [ -n "$SUDO_USER" ]; then
    RUN_USER=$SUDO_USER
    RUN_GROUP=$(id -gn "$SUDO_USER")
else
    RUN_USER=$(whoami)
    RUN_GROUP=$(id -gn "$RUN_USER")
fi

echo "Installing AXIOM Node daemon to run as user: $RUN_USER"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NODE_SCRIPT="$PROJECT_ROOT/axiom-node.py"

if [ ! -f "$NODE_SCRIPT" ]; then
    echo "Error: Could not find axiom-node.py at $NODE_SCRIPT"
    exit 1
fi

if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
    EXEC_START="$PROJECT_ROOT/.venv/bin/python $NODE_SCRIPT"
    echo "Found uv virtual environment at $PROJECT_ROOT/.venv"
else
    if command -v uv >/dev/null 2>&1; then
        UV_PATH=$(command -v uv)
        EXEC_START="$UV_PATH run $NODE_SCRIPT"
        echo "Using global uv at $UV_PATH"
    else
        echo "Error: Could not find .venv directory or global uv executable."
        exit 1
    fi
fi

SERVICE_FILE="/etc/systemd/system/axiom-node.service"

echo "Generating systemd service file at $SERVICE_FILE..."

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=AXIOM Headless Remote Swarm Node
After=network.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_GROUP
WorkingDirectory=$PROJECT_ROOT
ExecStart=$EXEC_START
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling axiom-node.service..."
systemctl enable axiom-node.service

echo "Starting axiom-node.service..."
systemctl restart axiom-node.service

echo ""
echo "AXIOM Node daemon installed and started successfully!"
echo "Check status with: sudo systemctl status axiom-node.service"
echo "View logs with: sudo journalctl -u axiom-node.service -f"
