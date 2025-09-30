import socket
import threading
from escpos.printer import Usb
import gc
import tempfile
import os
import re
import queue
import time
from threading import Lock
from enum import Enum
from dataclasses import dataclass
from typing import Union
from dotenv import load_dotenv
import ippserver
import markitdown
from zeroconf import ServiceInfo, Zeroconf


load_dotenv()


class PrintJobType(Enum):
    TEXT = "text"
    IMAGE = "image"


@dataclass
class PrintJob:
    job_type: PrintJobType
    data: Union[str, bytes]
    client_info: str = ""
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class PrinterManager:
    """Thread-safe printer manager using a queue-based approach."""

    def __init__(self):
        self.vendor_id = int(os.getenv("VENDOR_ID", "0x0483"), 16)
        self.product_id = int(os.getenv("PRODUCT_ID", "0x5743"), 16)
        self.print_queue = queue.Queue()
        self.printer_lock = Lock()
        self.is_running = True
        self.worker_thread = None

    def start(self):
        """Start the printer worker thread."""
        self.worker_thread = threading.Thread(target=self._printer_worker, daemon=True)
        self.worker_thread.start()
        print("Printer manager started")

    def stop(self):
        """Stop the printer manager gracefully."""
        self.is_running = False
        # Add a sentinel value to wake up the worker thread
        self.print_queue.put(None)
        if self.worker_thread:
            self.worker_thread.join()
        print("Printer manager stopped")

    def add_print_job(self, job_type: PrintJobType, data: Union[str, bytes], client_info: str = ""):
        """Add a print job to the queue."""
        job = PrintJob(job_type, data, client_info)
        self.print_queue.put(job)
        print(f"Print job queued: {job_type.value} from {client_info}")

    def _printer_worker(self):
        """Worker thread that processes print jobs sequentially."""
        while self.is_running:
            try:
                # Wait for a job (with timeout to check if we should stop)
                job = self.print_queue.get(timeout=1.0)

                # Check for sentinel value (stop signal)
                if job is None:
                    break

                self._process_print_job(job)
                self.print_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in printer worker: {e}")

    def _process_print_job(self, job: PrintJob):
        """Process a single print job with printer locking."""
        with self.printer_lock:
            try:
                print(f"Processing {job.job_type.value} job from {job.client_info}")

                if job.job_type == PrintJobType.TEXT:
                    self._print_text_job(job.data)
                elif job.job_type == PrintJobType.IMAGE:
                    self._print_image_job(job.data)

                print(f"Completed {job.job_type.value} job from {job.client_info}")

            except Exception as e:
                print(f"Error processing {job.job_type.value} job from {job.client_info}: {e}")
            finally:
                # Small delay between jobs to ensure printer stability
                time.sleep(0.1)

    def _print_text_job(self, data: str):
        """Handle text printing with markdown support."""
        try:
            p = Usb(self.vendor_id, self.product_id, 0)
            p.codepage = "CP437"

            # Check if data contains markdown formatting
            markdown_patterns = ['**', '__', '~~', '#', '<L>', '<C>', '<R>', '<2H>', '<2W>', '<', 'x', '>>>']
            has_markdown = any(pattern in data for pattern in markdown_patterns)

            if has_markdown:
                print("Processing markdown formatted text...")
                parsed_data = parse_markdown_formatting(data)
                self._print_markdown_formatted_data(p, parsed_data)
            else:
                print("Processing plain text...")
                p.text(data)

        except Exception as e:
            print(f"Error during text printing: {e}")
        finally:
            p = None
            gc.collect()

    def _print_image_job(self, image_data: bytes):
        """Handle image printing."""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_image:
                temp_image.write(image_data)
                temp_image_path = temp_image.name

            p = Usb(self.vendor_id, self.product_id, 0)
            p.image(temp_image_path)
            os.remove(temp_image_path)

        except Exception as e:
            print(f"Error during image printing: {e}")
        finally:
            p = None
            gc.collect()

    def _print_markdown_formatted_data(self, p, parsed_data):
        """Print data with markdown formatting applied."""
        for item in parsed_data:
            item_type = item[0]

            if item_type == 'text':
                p.text(item[1])

            elif item_type == 'paper_cut':
                p.text('\n\n\n')
                p.cut()
                print("Paper cut executed with 3 break lines")

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

                if level == 1:
                    p.set(double_height=True, double_width=True, bold=True, align='center')
                elif level == 2:
                    p.set(double_height=True, bold=True, align='center')
                elif level == 3:
                    p.set(double_width=True, bold=True)
                else:
                    p.set(bold=True, underline=1)

                p.text(text)
                p.set(normal_textsize=True)

            elif item_type == 'align':
                align_type = item[1]
                text = item[2]

                align_map = {'l': 'left', 'c': 'center', 'r': 'right'}
                p.set(align=align_map[align_type])
                p.text(text)
                p.set(align='left')

            elif item_type == 'custom_size':
                width = item[1]
                height = item[2]
                text = item[3]

                p.set(custom_size=True, width=width, height=height)
                p.text(text)
                p.set(normal_textsize=True)

        p.set(normal_textsize=True)


# Global printer manager instance
printer_manager = PrinterManager()


def parse_markdown_formatting(text):
    """Parse markdown-like formatting and return structured data."""
    result = []
    i = 0

    while i < len(text):
        # Check for paper cut pattern (>>> at beginning of line)
        if i == 0 or (i > 0 and text[i - 1] == '\n'):
            # We're at the beginning of a line
            if text[i:].startswith('>>>') and len(text[i:].split('\n')[0].strip('>')) == 0:
                # Count consecutive = characters
                equals_count = 0
                j = i
                while j < len(text) and text[j] == '>':
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


def start_server(host, port, handler_func):
    """Generic TCP server that uses a given handler function."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen()
        print(f"Server listening on {host}:{port}")
        while True:
            try:
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
                        handler_func(full_data, f"{addr[0]}:{addr[1]}")
            except Exception as e:
                print(f"Server error on port {port}: {e}")


def text_server():
    """Text server that queues print jobs."""

    def text_handler(data, client_info):
        try:
            decoded_data = data.decode('cp437', errors='ignore')
            print(
                f"Received text data from {client_info}:\n---\n{decoded_data[:100]}{'...' if len(decoded_data) > 100 else ''}\n---")
            printer_manager.add_print_job(PrintJobType.TEXT, decoded_data, client_info)
        except Exception as e:
            print(f"Error handling text data from {client_info}: {e}")

    start_server('0.0.0.0', 9100, text_handler)


def image_server():
    """Image server that queues print jobs."""

    def image_handler(data, client_info):
        print(f"Received {len(data)} bytes of image data from {client_info}")
        printer_manager.add_print_job(PrintJobType.IMAGE, data, client_info)

    start_server('0.0.0.0', 9101, image_handler)


def ipp_server():
    """IPP server that converts documents to markdown and queues them for printing."""

    class MarkdownIPPHandler(ippserver.IPPHandler):
        def print_job(self, data):
            client_info = f"{self.client_address[0]}:{self.client_address[1]}"
            print(f"Received IPP data from {client_info}")

            try:
                # Create a temporary file to store the received data
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(data)
                    temp_file_path = temp_file.name

                # Convert the file to markdown
                markdown_text = markitdown.convert(temp_file_path)
                os.remove(temp_file_path)

                print(
                    f"Converted IPP data to markdown:\n---\n{markdown_text[:100]}{'...' if len(markdown_text) > 100 else ''}\n---")
                printer_manager.add_print_job(PrintJobType.TEXT, markdown_text, client_info)

                return ippserver.ipp.STATUS_OK

            except Exception as e:
                print(f"Error handling IPP data from {client_info}: {e}")
                return ippserver.ipp.STATUS_ERROR_INTERNAL

    print("Starting IPP server on 0.0.0.0:631")
    ippserver.IPPPrinter(
        name="PrintDown",
        host="0.0.0.0",
        port=631,
        handler=MarkdownIPPHandler,
        supported_formats=["application/pdf", "application/postscript", "text/plain"],
    ).run()


zeroconf = None


def get_local_ip():
    """Get the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def start_discovery():
    """Register the IPP, text, and image services with Zeroconf."""
    global zeroconf
    zeroconf = Zeroconf()
    ip_address = get_local_ip()
    hostname = socket.gethostname()

    # IPP Service
    ipp_info = ServiceInfo(
        "_ipp._tcp.local.",
        f"{hostname}._ipp._tcp.local.",
        addresses=[socket.inet_aton(ip_address)],
        port=631,
        properties={'rp': 'ipp/print', 'ty': 'PrintDown IPP Printer'},
        server=f"{hostname}.local.",
    )
    zeroconf.register_service(ipp_info)
    print(f"Registered IPP service on {ip_address}:631")

    # Raw Text Service (Port 9100)
    text_info = ServiceInfo(
        "_pdl-datastream._tcp.local.",
        f"{hostname} Text._pdl-datastream._tcp.local.",
        addresses=[socket.inet_aton(ip_address)],
        port=9100,
        properties={'ty': 'PrintDown Raw Text'},
        server=f"{hostname}.local.",
    )
    zeroconf.register_service(text_info)
    print(f"Registered Raw Text service on {ip_address}:9100")

    # Raw Image Service (Port 9101)
    image_info = ServiceInfo(
        "_pdl-datastream._tcp.local.",
        f"{hostname} Image._pdl-datastream._tcp.local.",
        addresses=[socket.inet_aton(ip_address)],
        port=9101,
        properties={'ty': 'PrintDown Raw Image'},
        server=f"{hostname}.local.",
    )
    zeroconf.register_service(image_info)
    print(f"Registered Raw Image service on {ip_address}:9101")


def stop_discovery():
    """Unregister all services and close Zeroconf."""
    global zeroconf
    if zeroconf:
        print("Unregistering services...")
        zeroconf.unregister_all_services()
        zeroconf.close()





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

>>>

# SECOND RECEIPT
## Another Transaction

**Item 1**                <R>$5.00</R>
**Item 2**                <R>$3.00</R>

**TOTAL: $8.00**

>>>

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

    # Queue the test print job
    printer_manager.add_print_job(PrintJobType.TEXT, sample, "test")


if __name__ == "__main__":
    print("Thread-Safe Printer Server with Queue Management")
    print("=" * 50)
    print("Markdown Formatting Guide:")
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
    print(">>> (3+ at line start)  - Paper cut with 4 break lines")
    print("=" * 50)
    print()

    # Start the printer manager
    printer_manager.start()
    start_discovery()

    try:
        # Uncomment to test formatting
        # test_markdown_formatting()

        # Start server threads
        text_thread = threading.Thread(target=text_server, daemon=True)
        image_thread = threading.Thread(target=image_server, daemon=True)
        ipp_thread = threading.Thread(target=ipp_server, daemon=True)

        text_thread.start()
        image_thread.start()
        ipp_thread.start()

        print("Servers started. Press Ctrl+C to stop.")

        # Keep main thread alive
        text_thread.join()
        image_thread.join()
        ipp_thread.join()

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_discovery()
        printer_manager.stop()