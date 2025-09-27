import socket
import re
from PIL import Image
import io

class MarkdownToEscPosTCP:
    def __init__(self, printer_ip, printer_port=9100):
        self.printer_ip = printer_ip
        self.printer_port = printer_port
        self.line_width = 42  # Default for 80mm printers

    def send_to_printer(self, data):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.printer_ip, self.printer_port))
            s.sendall(data)

    def print_markdown(self, markdown_text):
        escpos_commands = bytearray()
        lines = markdown_text.split('\n')
        for line in lines:
            if line.startswith('!['):
                # Handle image
                image_path = self._extract_image_path(line)
                if image_path:
                    escpos_commands.extend(self._image_to_escpos(image_path))
            else:
                # Handle text
                escpos_commands.extend(self._process_line(line))
        self.send_to_printer(escpos_commands)

    def _extract_image_path(self, line):
        # Extract image path from Markdown: ![alt](path)
        match = re.match(r'!\[.*\]\((.*)\)', line)
        return match.group(1) if match else None

    def _image_to_escpos(self, image_path):
        try:
            img = Image.open(image_path)
            # Convert to 1-bit monochrome
            img = img.convert('1')
            width, height = img.size
            # ESC/POS commands for image
            escpos = bytearray()
            escpos.extend(b'\x1B\x40')  # Initialize printer
            escpos.extend(b'\x1B\x33\x00')  # Set line spacing
            escpos.extend(b'\x1D\x76\x30\x00')  # Set raster mode
            escpos.extend(bytes([width % 256, width // 256]))  # Width (LSB, MSB)
            escpos.extend(bytes([height % 256, height // 256]))  # Height (LSB, MSB)
            # Image data (1-bit per pixel)
            for y in range(height):
                for x in range(0, width, 8):
                    byte = 0
                    for i in range(8):
                        if x + i < width and img.getpixel((x + i, y)) == 0:
                            byte |= (1 << (7 - i))
                    escpos.extend(bytes([byte]))
            escpos.extend(b'\n')  # Line feed
            return escpos
        except Exception as e:
            print(f"Error processing image: {e}")
            return bytearray()

    def _process_line(self, line):
        escpos_line = bytearray()

        # Headers (e.g., #, ##, ###)
        if line.startswith('#'):
            header_level = 0
            while line.startswith('#') and header_level < 3:
                header_level += 1
                line = line[1:].strip()
            if header_level == 1:
                escpos_line.extend(b'\x1B!\x38')  # Double height
            elif header_level == 2:
                escpos_line.extend(b'\x1B!\x10')  # Normal height, double width
            line = line.strip()

        # Bold and Italic (simulated with ESC/POS)
        line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)  # Remove bold markers
        line = re.sub(r'\*(.*?)\*', r'\1', line)      # Remove italic markers

        # Lists (e.g., - item, * item)
        if line.startswith(('- ', '* ')):
            line = line[2:]
            escpos_line.extend(b'\x2E ')  # Bullet point
            escpos_line.extend(self._wrap_text(line))

        # Normal text
        else:
            escpos_line.extend(self._wrap_text(line))

        # Reset font
        escpos_line.extend(b'\x1B!\x00')
        escpos_line.extend(b'\n')

        return escpos_line

    def _wrap_text(self, text):
        escpos_text = bytearray()
        words = text.split()
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= self.line_width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                escpos_text.extend(' '.join(current_line).encode('utf-8'))
                escpos_text.extend(b'\n')
                current_line = [word]
                current_length = len(word)

        if current_line:
            escpos_text.extend(' '.join(current_line).encode('utf-8'))

        return escpos_text

# Example Usage
if __name__ == "__main__":
    printer_ip = "192.168.1.100"  # Replace with your printer's IP
    converter = MarkdownToEscPosTCP(printer_ip)

    # Example Markdown with image
    markdown_text = """
    # Hello, World!
    This is a **test** of the *Markdown* converter.
    - Item 1
    - Item 2
    ![Logo](logo.jpeg)
    """

    converter.print_markdown(markdown_text)



