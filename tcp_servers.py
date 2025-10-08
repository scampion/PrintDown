"""TCP servers for text and image printing."""
import socket
from printer_manager import PrintJobType

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
                    conn.settimeout(0.2)  # Process after 2 seconds of no data
                    full_data = b""
                    
                    while True:
                        try:
                            chunk = conn.recv(1024)
                            if not chunk:
                                break
                            full_data += chunk
                        except socket.timeout:
                            break
                    
                    if full_data:
                        handler_func(full_data, f"{addr[0]}:{addr[1]}")
            except Exception as e:
                print(f"Server error on port {port}: {e}")



def create_text_server(printer_manager):
    """Create text server that queues print jobs."""
    def text_handler(data, client_info):
        try:
            decoded_data = data.decode('cp437', errors='ignore')
            print(
                f"Received text data from {client_info}:\n---\n{decoded_data[:100]}{'...' if len(decoded_data) > 100 else ''}\n---")
            printer_manager.add_print_job(PrintJobType.TEXT, decoded_data, client_info)
        except Exception as e:
            print(f"Error handling text data from {client_info}: {e}")

    def text_server():
        start_server('0.0.0.0', 9100, text_handler)
    
    return text_server


def create_image_server(printer_manager):
    """Create image server that queues print jobs."""
    def image_handler(data, client_info):
        print(f"Received {len(data)} bytes of image data from {client_info}")
        printer_manager.add_print_job(PrintJobType.IMAGE, data, client_info)

    def image_server():
        start_server('0.0.0.0', 9101, image_handler)
    
    return image_server

