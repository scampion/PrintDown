"""TCP servers for text and image printing."""
import socket
import logging
from printer_manager import PrintJobType


def start_server(host, port, handler_func, timeout=30.0, buffer_size=4096):
    """
    Generic TCP server that uses a given handler function.
    
    Args:
        host: Host address to bind to
        port: Port number to listen on
        handler_func: Callback function(data: bytes, client_addr: str) -> None
        timeout: Socket timeout in seconds for idle connections (default: 30.0)
        buffer_size: Size of receive buffer in bytes (default: 4096)
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((host, port))
        server_socket.listen(5)  # Backlog of 5 connections
        logging.info(f"Server listening on {host}:{port}")
        
        while True:
            conn = None
            try:
                conn, addr = server_socket.accept()
                client_addr = f"{addr[0]}:{addr[1]}"
                logging.info(f"Connection from {client_addr}")
                
                conn.settimeout(timeout)
                
                # Process data as it arrives (streaming mode)
                while True:
                    try:
                        chunk = conn.recv(buffer_size)
                        if not chunk:
                            # Client closed connection gracefully
                            logging.info(f"Connection closed by {client_addr}")
                            break
                        
                        # Process each chunk immediately as it arrives
                        try:
                            handler_func(bytes(chunk), client_addr)
                        except Exception as e:
                            logging.error(f"Handler error for {client_addr}: {e}", exc_info=True)
                            
                    except socket.timeout:
                        # No data for timeout period - client may still be connected
                        logging.debug(f"Timeout waiting for data from {client_addr}")
                        # Continue waiting for more data
                        continue
                    
            except socket.timeout:
                logging.debug(f"Connection timeout on port {port}")
            except OSError as e:
                logging.error(f"Socket error on port {port}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error on port {port}: {e}", exc_info=True)
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                        
    except KeyboardInterrupt:
        logging.info(f"Server on port {port} shutting down...")
    except Exception as e:
        logging.error(f"Fatal server error on port {port}: {e}", exc_info=True)
    finally:
        server_socket.close()
        logging.info(f"Server on port {port} closed")





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

