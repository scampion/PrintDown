#!/bin/sh

set -e

# This script installs the printserver service for OpenRC.
# It creates a dedicated user, installs Python dependencies,
# and sets up the init script to start the server at boot.

# --- Variables ---
APP_NAME="printserver"
APP_DIR="/opt/${APP_NAME}"
INIT_SCRIPT_DEST="/etc/init.d/${APP_NAME}"
SERVICE_USER="printserver"
SERVICE_GROUP="printserver"
LOG_FILE="/var/log/${APP_NAME}.log"
PID_FILE="/run/${APP_NAME}.pid"
PYTHON_CMD="/usr/bin/python3"

# --- Functions ---

# Check for root privileges
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "This script must be run as root." >&2
        exit 1
    fi
}

# Create a dedicated user and group for the service
create_service_user() {
    if ! getent group "${SERVICE_GROUP}" >/dev/null; then
        echo "Creating group '${SERVICE_GROUP}'..."
        addgroup -S "${SERVICE_GROUP}"
    fi

    if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
        echo "Creating user '${SERVICE_USER}'..."
        adduser -S -G "${SERVICE_GROUP}" -h /dev/null -s /sbin/nologin "${SERVICE_USER}"
    fi
}

# Install Python dependencies from requirements.txt
install_dependencies() {
    echo "Installing system dependencies for USB printing..."
    apk add --no-cache libusb-compat-dev
    echo "Installing Python dependencies..."
    if ! command -v pip >/dev/null 2>&1; then
        echo "Error: pip is not installed. Please install it to continue." >&2
        exit 1
    fi
    if [ ! -f "requirements.txt" ]; then
        echo "Error: requirements.txt not found in the current directory." >&2
        exit 1
    fi
    pip install -r requirements.txt
}

# Create application directory and copy files
setup_app_directory() {
    echo "Setting up application directory at ${APP_DIR}..."
    mkdir -p "${APP_DIR}"
    cp server.py requirements.txt "${APP_DIR}/"
    chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${APP_DIR}"
    chmod -R 750 "${APP_DIR}"
}

# Create and install the OpenRC init script
create_init_script() {
    echo "Creating OpenRC init script at ${INIT_SCRIPT_DEST}..."
    cat > "${INIT_SCRIPT_DEST}" <<EOF
#!/sbin/openrc-run

description="Python Print Server"
command="${PYTHON_CMD}"
command_args="${APP_DIR}/server.py"
command_user="${SERVICE_USER}"
pidfile="${PID_FILE}"
directory="${APP_DIR}"

depend() {
    need net
    after firewall
}

start() {
    ebegin "Starting Print Server"
    start-stop-daemon --start --background \
        --make-pidfile --pidfile "\$pidfile" \
        --user "\$command_user" \
        --chdir "\$directory" \
        --exec "\$command" -- "\$command_args"
    eend \$?
}

stop() {
    ebegin "Stopping Print Server"
    start-stop-daemon --stop --pidfile "\$pidfile"
    eend \$?
}
EOF
    chmod 755 "${INIT_SCRIPT_DEST}"
}

# Enable and start the service
enable_and_start_service() {
    echo "Enabling and starting the '${APP_NAME}' service..."
    rc-update add "${APP_NAME}" default
    rc-service "${APP_NAME}" start
}

# --- Main Execution ---

main() {
    echo "--- Print Server Setup ---"
    check_root
    create_service_user
    install_dependencies
    setup_app_directory
    create_init_script
    enable_and_start_service
    echo "--------------------------"
    echo "Setup complete."
    echo "The print server is now running."
    echo "Logs are available in ${LOG_FILE}"
    echo "To manage the service, use: rc-service ${APP_NAME} [start|stop|restart]"
}

main
