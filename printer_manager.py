"""Printer manager module for handling print jobs."""
import queue
import time
import tempfile
import os
import gc
from threading import Lock, Thread
from enum import Enum
from dataclasses import dataclass
from typing import Union
from escpos.printer import Usb
from markdown_parser import parse_markdown_formatting


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
        self.worker_thread = Thread(target=self._printer_worker, daemon=True)
        self.worker_thread.start()
        print("Printer manager started")

    def stop(self):
        """Stop the printer manager gracefully."""
        self.is_running = False
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
                job = self.print_queue.get(timeout=1.0)
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
                time.sleep(0.1)

    def _print_text_job(self, data: str):
        """Handle text printing with markdown support."""
        try:
            p = Usb(self.vendor_id, self.product_id, 0)
            p.codepage = "CP437"

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

