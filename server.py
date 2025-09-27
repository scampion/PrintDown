import socket
import threading
from escpos.printer import Usb
import gc
import tempfile
import os
import re


def parse_markdown_formatting(text):
    """Parse markdown-like formatting and return structured data."""
    result = []
    i = 0

    while i < len(text):
        # Check for paper cut pattern (=== at beginning of line)
        if i == 0 or (i > 0 and text[i - 1] == '\n'):
            # We're at the beginning of a line
            if text[i:].startswith('===') and len(text[i:].split('\n')[0].strip('=')) == 0:
                # Count consecutive = characters
                equals_count = 0
                j = i
                while j < len(text) and text[j] == '=':
                    equals_count += 1
                    j += 1

                if equals_count >= 3:
                    # Add paper cut command
                    result.append(('paper_cut',))

                    # Skip to end of line
                    line_end = text.find('\n', j)
                    if line_end == -1:
                        i = len(text)
                    else:
                        i = line_end + 1
                    continue

        # Look for formatting markers
        if text[i:i + 2] == '**':  # Bold
            end_pos = text.find('**', i + 2)
            if end_pos != -1:
                bold_text = text[i + 2:end_pos]
                result.append(('format', 'bold', bold_text))
                i = end_pos + 2
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i:i + 2] == '__':  # Underline
            end_pos = text.find('__', i + 2)
            if end_pos != -1:
                underline_text = text[i + 2:end_pos]
                result.append(('format', 'underline', underline_text))
                i = end_pos + 2
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i:i + 2] == '~~':  # Invert (strikethrough repurposed)
            end_pos = text.find('~~', i + 2)
            if end_pos != -1:
                invert_text = text[i + 2:end_pos]
                result.append(('format', 'invert', invert_text))
                i = end_pos + 2
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i] == '#':  # Headers (different sizes)
            # Count hash symbols
            hash_count = 0
            j = i
            while j < len(text) and text[j] == '#':
                hash_count += 1
                j += 1

            # Find end of line
            line_end = text.find('\n', j)
            if line_end == -1:
                line_end = len(text)

            # Skip space after hashes
            if j < len(text) and text[j] == ' ':
                j += 1

            header_text = text[j:line_end]
            if header_text.strip():
                result.append(('header', hash_count, header_text.strip()))
                if line_end < len(text):  # Include the newline
                    result.append(('text', '\n'))
            i = line_end + 1 if line_end < len(text) else len(text)

        elif text[i:i + 3] in ['<L>', '<C>', '<R>']:  # Alignment tags
            align_type = text[i + 1]  # L, C, or R
            end_tag = f'</{align_type}>'
            end_pos = text.find(end_tag, i + 3)
            if end_pos != -1:
                align_text = text[i + 3:end_pos]
                result.append(('align', align_type.lower(), align_text))
                i = end_pos + len(end_tag)
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i:i + 3] == '<2H>':  # Double height
            end_pos = text.find('</2H>', i + 4)
            if end_pos != -1:
                double_text = text[i + 4:end_pos]
                result.append(('format', 'double_height', double_text))
                i = end_pos + 5
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i:i + 3] == '<2W>':  # Double width
            end_pos = text.find('</2W>', i + 4)
            if end_pos != -1:
                double_text = text[i + 4:end_pos]
                result.append(('format', 'double_width', double_text))
                i = end_pos + 5
            else:
                result.append(('text', text[i]))
                i += 1

        elif text[i] == '<' and 'x' in text[i:i + 10]:  # Custom size <4x2>text</4x2>
            # Match pattern like <3x2>
            match = re.match(r'<(\d)x(\d)>', text[i:i + 10])
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
                tag_len = len(match.group(0))
                end_tag = f'</{width}x{height}>'
                end_pos = text.find(end_tag, i + tag_len)
                if end_pos != -1:
                    custom_text = text[i + tag_len:end_pos]
                    result.append(('custom_size', width, height, custom_text))
                    i = end_pos + len(end_tag)
                else:
                    result.append(('text', text[i]))
                    i += 1
            else:
                result.append(('text', text[i]))
                i += 1
        else:
            # Regular character
            result.append(('text', text[i]))
            i += 1

    return result


def print_markdown_formatted_data(parsed_data):
    """Print data with markdown formatting applied."""
    try:
        p = Usb(0x0483, 0x5743, 0)
        p.codepage = "CP437"

        for item in parsed_data:
            item_type = item[0]

            if item_type == 'text':
                p.text(item[1])

            elif item_type == 'paper_cut':
                # Add 4 break lines before paper cut
                p.text('\n\n\n\n')
                p.cut()
                print("Paper cut executed with 4 break lines")

            elif item_type == 'format':
                format_type = item[1]
                text = item[2]

                if format_type == 'bold':
                    p.set(bold=True)
                    p.text(text)
                    p.set(bold=False)

                elif format_type == 'underline':
                    p.set(underline=1)
                    p.text(text)
                    p.set(underline=0)

                elif format_type == 'invert':
                    p.set(invert=True)
                    p.text(text)
                    p.set(invert=False)

                elif format_type == 'double_height':
                    p.set(double_height=True)
                    p.text(text)
                    p.set(normal_textsize=True)

                elif format_type == 'double_width':
                    p.set(double_width=True)
                    p.text(text)
                    p.set(normal_textsize=True)

            elif item_type == 'header':
                level = item[1]
                text = item[2]

                # Different header sizes based on level
                if level == 1:  # # Header - largest
                    p.set(double_height=True, double_width=True, bold=True, align='center')
                elif level == 2:  # ## Header - large
                    p.set(double_height=True, bold=True, align='center')
                elif level == 3:  # ### Header - medium
                    p.set(double_width=True, bold=True)
                else:  # #### and beyond - small headers
                    p.set(bold=True, underline=1)

                p.text(text)
                p.set(normal_textsize=True)

            elif item_type == 'align':
                align_type = item[1]  # 'l', 'c', or 'r'
                text = item[2]

                align_map = {'l': 'left', 'c': 'center', 'r': 'right'}
                p.set(align=align_map[align_type])
                p.text(text)
                p.set(align='left')  # Reset to left

            elif item_type == 'custom_size':
                width = item[1]
                height = item[2]
                text = item[3]

                p.set(custom_size=True, width=width, height=height)
                p.text(text)
                p.set(normal_textsize=True)

        # Final reset
        p.set(normal_textsize=True)

        print("Markdown formatted text print job successful.")
    except Exception as e:
        print(f"Error during markdown formatted text printing: {e}")
    finally:
        p = None
        gc.collect()


def print_text_data(data_to_print):
    """Sends raw text data to the USB printer (fallback for plain text)."""
    try:
        p = Usb(0x0483, 0x5743, 0)
        p.codepage = "CP437"
        p.text(data_to_print)
        print("Plain text print job successful.")
    except Exception as e:
        print(f"Error during text printing: {e}")
    finally:
        p = None
        gc.collect()


def print_image_data(image_data):
    """Saves image data to a temporary file and prints it."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_image:
            temp_image.write(image_data)
            temp_image_path = temp_image.name

        p = Usb(0x0483, 0x5743, 0)
        p.image(temp_image_path)
        os.remove(temp_image_path)
        print("Image print job successful.")
    except Exception as e:
        print(f"Error during image printing: {e}")
    finally:
        p = None
        gc.collect()


def start_server(host, port, handler_func):
    """Generic TCP server that uses a given handler function."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((host, port))
        server_socket.listen()
        print(f"Server listening on {host}:{port}")
        while True:
            conn, addr = server_socket.accept()
            with conn:
                print(f"Connection from {addr} on port {port}")
                full_data = b""
                while True:
                    chunk = conn.recv(1024)
                    if not chunk:
                        break
                    full_data += chunk

                if full_data:
                    handler_func(full_data)


def text_server():
    """Wrapper to handle markdown formatted text data."""

    def text_handler(data):
        try:
            decoded_data = data.decode('cp437', errors='ignore')
            print(f"Received text data to print:\n---\n{decoded_data}\n---")

            # Check if data contains markdown formatting (including paper cut)
            markdown_patterns = ['**', '__', '~~', '#', '<L>', '<C>', '<R>', '<2H>', '<2W>', '<', 'x', '===']
            has_markdown = any(pattern in decoded_data for pattern in markdown_patterns)

            if has_markdown:
                print("Processing markdown formatted text...")
                parsed_data = parse_markdown_formatting(decoded_data)
                print_markdown_formatted_data(parsed_data)
            else:
                print("Processing plain text...")
                print_text_data(decoded_data)

        except Exception as e:
            print(f"Error handling text data: {e}")

    start_server('0.0.0.0', 9100, text_handler)


def image_server():
    """Wrapper for the image handler."""

    def image_handler(data):
        print(f"Received {len(data)} bytes of image data to print.")
        print_image_data(data)

    start_server('0.0.0.0', 9101, image_handler)


def create_sample_receipt():
    """Create a sample receipt with markdown formatting."""
    receipt = """# COFFEE SHOP
## 123 Main Street
### Phone: (555) 123-4567

----------------------------------------

**Regular Coffee**        <R>$3.50</R>
**Blueberry Muffin**      <R>$2.25</R>
__Chocolate Chip Cookie__ <R>$1.75</R>

----------------------------------------
**Subtotal:**             <R>$7.50</R>
**Tax (8%):**             <R>$0.60</R>

<2H>**TOTAL: $8.10**</2H>

<C>~~PAID BY CARD~~</C>

<C>Thank you for your visit!</C>
<C>Please come again!</C>

===

# SECOND RECEIPT
## Another Transaction

**Item 1**                <R>$5.00</R>
**Item 2**                <R>$3.00</R>

**TOTAL: $8.00**

======

<4x2>END</4x2>
"""
    return receipt


def test_markdown_formatting():
    """Test function to demonstrate markdown formatting."""
    sample = create_sample_receipt()
    print("Sample receipt with markdown formatting:")
    print(sample)
    print("\n" + "=" * 50 + "\n")

    parsed = parse_markdown_formatting(sample)
    print("Parsed formatting structure:")
    for item in parsed:
        print(f"  {item}")

    # Uncomment to actually print:
    # print_markdown_formatted_data(parsed)


if __name__ == "__main__":
    print("Markdown Formatting Guide:")
    print("=" * 40)
    print("**bold text**           - Bold formatting")
    print("__underlined text__     - Underlined text")
    print("~~inverted text~~       - White on black")
    print("# Header 1              - Largest header (double height+width, bold, centered)")
    print("## Header 2             - Large header (double height, bold, centered)")
    print("### Header 3            - Medium header (double width, bold)")
    print("#### Header 4+          - Small header (bold, underlined)")
    print("<L>left text</L>        - Left aligned")
    print("<C>center text</C>      - Center aligned")
    print("<R>right text</R>       - Right aligned")
    print("<2H>double height</2H>  - Double height text")
    print("<2W>double width</2W>   - Double width text")
    print("<3x2>custom size</3x2>  - Custom size (width x height)")
    print("=== (3+ at line start)  - Paper cut with 4 break lines")
    print("=" * 40)
    print()

    # Uncomment to test formatting
    # test_markdown_formatting()

    text_thread = threading.Thread(target=text_server)
    image_thread = threading.Thread(target=image_server)

    text_thread.start()
    image_thread.start()

    text_thread.join()
    image_thread.join()