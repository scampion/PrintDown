# PrintDown TCP Print Server

![PrintDown Logo](logo.jpeg)

This project provides a simple TCP print server in Python that listens for raw text, a special markdown-like formatted text, and image data, and sends it to a connected USB thermal printer. It's designed to make it easy to print richly formatted receipts and labels from any device on your network.

## Features

- **Markdown-like Text Printing:** Listens on port 9100 for text and processes special formatting tags for bold, underline, headers, alignment, and custom text sizes.
- **Image Printing:** Listens on port 9101 for raw image data (e.g., JPG).
- **Paper Cut:** A special command in the markdown text can trigger the printer's paper cutter.
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

Once the server is running, you can send data to the appropriate port to print. You can use a tool like `netcat` (`nc`) to send print jobs from a client machine.

### For Images (Port 9101)

Send raw image data (e.g., the content of a JPG file) to port `9101`.

**Example:**
```bash
cat my_image.jpg | nc <server_ip> 9101
```

### For Text and Markdown (Port 9100)

Send plain text or text with special formatting tags to port `9100`.

**Example (Plain Text):**
```bash
echo "Hello, printer!" | nc <server_ip> 9100
```

**Example (Markdown Formatting):**
```bash
# Create a file named receipt.txt with the following content:
# --- receipt.txt ---
# # MY STORE
# ## 123 Example Lane
#
# **Item 1**      <R>$10.00</R>
# **Item 2**      <R>$5.50</R>
# -----------------
# **TOTAL**       <R>$15.50</R>
#
# <C>Thank you!</C>
#
# ===
# --- end of file ---
#
# Send it to the printer:
cat receipt.txt | nc <server_ip> 9100
```

### Formatting Guide

| Syntax                  | Description                                |
| ----------------------- | ------------------------------------------ |
| `**bold text**`         | Bold formatting                            |
| `__underlined text__`   | Underlined text                            |
| `~~inverted text~~`     | White on black                             |
| `# Header 1`            | Largest header (centered, bold, 2xH, 2xW)  |
| `## Header 2`           | Large header (centered, bold, 2xH)         |
| `### Header 3`          | Medium header (bold, 2xW)                  |
| `#### Header 4+`        | Small header (bold, underlined)            |
| `<L>left</L>`           | Left aligned text                          |
| `<C>center</C>`         | Center aligned text                        |
| `<R>right</R>`          | Right aligned text                         |
| `<2H>double height</2H>`| Double height text                         |
| `<2W>double width</2W>` | Double width text                          |
| `<3x2>custom</3x2>`     | Custom size (Width x Height)               |
| `===` (on a new line)   | Cut the paper                              |