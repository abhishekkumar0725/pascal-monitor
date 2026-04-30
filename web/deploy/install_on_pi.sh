#!/usr/bin/env bash
#
# install_on_pi.sh — Idempotent setup/upgrade script for Pascal Web Logger
#
# Usage:
#   sudo bash install_on_pi.sh
#
# This script:
#   1. Installs system dependencies
#   2. Creates the 'pascal' service user
#   3. Sets up the application in /opt/pascal-web
#   4. Creates a Python virtual environment
#   5. Runs database migrations
#   6. Installs and starts the systemd service
#
# Re-running this script will upgrade an existing installation.

set -euo pipefail

# Configuration
APP_DIR="/opt/pascal-web"
VENV_DIR="$APP_DIR/web/.venv"
SERVICE_NAME="pascal-web"
SERVICE_USER="pascal"
ENV_FILE="/etc/pascal-web.env"
EXPORT_DIR="/opt/pascal-web/exports"
BACKUP_DIR="/opt/pascal-web/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root (use sudo)"
    exit 1
fi

log_info "Starting Pascal Web Logger installation..."

# --- Step 1: Install system dependencies ---
log_info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip sqlite3 git

# Check Python version (need 3.11+)
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log_info "Python version: $PYTHON_VERSION"

# --- Step 2: Create service user ---
if id "$SERVICE_USER" &>/dev/null; then
    log_info "User '$SERVICE_USER' already exists"
else
    log_info "Creating user '$SERVICE_USER'..."
    useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# --- Step 3: Set up application directory ---
if [[ -d "$APP_DIR/.git" ]]; then
    log_info "Updating existing installation..."
    cd "$APP_DIR"

    # Stop service if running (for upgrade)
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_info "Stopping $SERVICE_NAME for upgrade..."
        systemctl stop "$SERVICE_NAME"
    fi

    # Pull latest changes
    git pull --ff-only
else
    log_info "Fresh installation - please clone the repo to $APP_DIR first"
    log_info "Example: git clone <your-repo-url> $APP_DIR"

    if [[ ! -d "$APP_DIR" ]]; then
        log_error "Directory $APP_DIR does not exist."
        log_error "Please clone the repository first:"
        log_error "  git clone <repo-url> $APP_DIR"
        exit 1
    fi
fi

# Create export and backup directories
mkdir -p "$EXPORT_DIR" "$BACKUP_DIR"

# --- Step 4: Set up Python virtual environment ---
log_info "Setting up Python virtual environment..."
cd "$APP_DIR/web"

if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi

# Upgrade pip and install dependencies
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r requirements.txt -q

# --- Step 5: Create environment file ---
if [[ ! -f "$ENV_FILE" ]]; then
    log_info "Creating environment file at $ENV_FILE..."
    cat > "$ENV_FILE" << 'EOF'
# Pascal Web Logger Configuration
# Uncomment and modify as needed

# Database URL (default: SQLite in app directory)
# DATABASE_URL=sqlite+aiosqlite:///pascal.db

# Server port (default: 8000)
# PORT=8000

# Timezone for display (default: America/New_York)
# TIMEZONE=America/New_York

# CSV export directory
CSV_EXPORT_DIR=/opt/pascal-web/exports

# Comma-separated list of user names for the "Logged by" dropdown
# LOG_USERS=Abhishek,Partner,Walker
EOF
    chmod 600 "$ENV_FILE"
else
    log_info "Environment file already exists at $ENV_FILE"
fi

# --- Step 6: Run database migrations ---
log_info "Running database migrations..."
cd "$APP_DIR/web"
"$VENV_DIR/bin/alembic" upgrade head

# --- Step 7: Set ownership ---
log_info "Setting file ownership..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

# --- Step 8: Install systemd service ---
log_info "Installing systemd service..."
cp "$APP_DIR/web/deploy/pascal-web.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# --- Step 9: Start the service ---
log_info "Starting $SERVICE_NAME..."
systemctl start "$SERVICE_NAME"

# Wait a moment for startup
sleep 2

# --- Step 10: Verify ---
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log_info "Service is running!"
else
    log_error "Service failed to start. Check logs with: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# Test health endpoint
if curl -sf http://localhost:8000/healthz > /dev/null 2>&1; then
    log_info "Health check passed!"
else
    log_warn "Health check failed - service may still be starting up"
fi

# --- Done ---
echo ""
log_info "============================================"
log_info "Pascal Web Logger installed successfully!"
log_info "============================================"
echo ""
echo "Access the app at:"
echo "  http://$(hostname).local:8000"
echo "  http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Useful commands:"
echo "  View logs:      journalctl -u $SERVICE_NAME -f"
echo "  Restart:        sudo systemctl restart $SERVICE_NAME"
echo "  Stop:           sudo systemctl stop $SERVICE_NAME"
echo "  Status:         sudo systemctl status $SERVICE_NAME"
echo ""
echo "Configuration:    $ENV_FILE"
echo "Database:         $APP_DIR/web/pascal.db"
echo "CSV exports:      $EXPORT_DIR"
echo ""
