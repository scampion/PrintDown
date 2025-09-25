# ESC/POC Python Print Server

This project provides a simple TCP print server in Python that listens for raw text and image data on separate ports and sends it to a connected USB thermal printer.

## Features

- **Text Printing:** Listens on port 9100 for raw text data (codepage CP437).
- **Image Printing:** Listens on port 9101 for raw image data (e.g., JPG).
- **Concurrent Handling:** Uses separate threads to handle text and image printing servers simultaneously.
- **OpenRC Service:** Includes a setup script to install an OpenRC-compatible init script for running the server as a background service at boot.

## Requirements

- Python 3
- `pip` for installing dependencies
- A connected USB thermal printer compatible with `python-escpos`. The printer VID/PID are currently hardcoded to `0x0483`/`0x5743`.
- An OpenRC-based Linux distribution.

## Installation

The `setup.sh` script automates the installation process. It performs the following actions:

1.  **Creates a dedicated user and group** (`printserver`) to run the service securely.
2.  **Installs Python dependencies** from `requirements.txt`.
3.  **Copies application files** to `/opt/printserver`.
4.  **Creates and installs an OpenRC init script** at `/etc/init.d/printserver`.
5.  **Enables and starts the `printserver` service.**

To install the service, make the setup script executable and run it with root privileges:

```bash
chmod +x setup.sh
sudo ./setup.sh
```

## Service Management

Once installed, you can manage the print server using the `rc-service` command:

- **Start the service:**
  ```bash
  sudo rc-service printserver start
  ```

- **Stop the service:**
  ```bash
  sudo rc-service printserver stop
  ```

- **Restart the service:**
  ```bash
  sudo rc-service printserver restart
  ```

Logs for the service are stored in `/var/log/printserver.log`.

## How to Use

Once the server is running, you can send data to the appropriate port to print.

- **For Text:** Send raw text data to port `9100`.
- **For Images:** Send raw image data (e.g., the content of a JPG file) to port `9101`.

You can use a tool like `netcat` (`nc`) to send print jobs from a client machine.

**Example (Text):**
```bash
echo "Hello, printer!" | nc <server_ip> 9100
```

**Example (Image):**
```bash
cat my_image.jpg | nc <server_ip> 9101
```
