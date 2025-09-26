import socket
import threading
from escpos.printer import Usb
import gc
import tempfile
import os

def print_text_data(data_to_print):
    """Sends raw text data to the USB printer."""
    try:
        p = Usb(0x0483, 0x5743, 0)
        p.codepage = "CP437"
        p.text(data_to_print)
        p.cut()
        print("Text print job successful.")
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
        p.cut()
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
    """Wrapper to decode data for the text handler."""
    def text_handler(data):
        decoded_data = data.decode('cp437', errors='ignore')
        print(f"Received text data to print:\n---\n{decoded_data}\n---")
        print_text_data(decoded_data)
    
    start_server('0.0.0.0', 9100, text_handler)

def image_server():
    """Wrapper for the image handler."""
    def image_handler(data):
        print(f"Received {len(data)} bytes of image data to print.")
        print_image_data(data)

    start_server('0.0.0.0', 9101, image_handler)

if __name__ == "__main__":
    text_thread = threading.Thread(target=text_server)
    image_thread = threading.Thread(target=image_server)

    text_thread.start()
    image_thread.start()

    text_thread.join()
    image_thread.join()

