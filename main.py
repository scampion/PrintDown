"""Main entry point for the PrintDown thermal printer server."""
import threading
from dotenv import load_dotenv

from printer_manager import PrinterManager, PrintJobType
from tcp_servers import create_text_server, create_image_server
from ipp_server import create_ipp_server
from discovery_service import DiscoveryService


# Load environment variables
load_dotenv()


def print_help():
    """Print help information about available services."""
    print("PrintDown Server Started!")
    print("Available services:")
    print("- Text server: port 9100")
    print("- Image server: port 9101")
    print("- IPP server: port 631")
    print("")
    print("Send text, images, or IPP print jobs to these ports.")


def test_markdown_formatting(printer_manager):
    """Test markdown formatting with the printer."""
    test_text = "# Header\n**Bold text** and *italic text*\n- List item 1\n- List item 2"
    print("Testing markdown formatting...")
    printer_manager.add_print_job(PrintJobType.TEXT, test_text, "test")


def main():
    """Main application entry point."""
    print_help()

    # Initialize components
    printer_manager = PrinterManager()
    discovery_service = DiscoveryService()

    # Start the printer manager
    printer_manager.start()
    
    # Start service discovery
    discovery_service.start()

    try:
        # Uncomment to test formatting
        # test_markdown_formatting(printer_manager)

        # Create server functions with printer_manager dependency
        text_server = create_text_server(printer_manager)
        image_server = create_image_server(printer_manager)
        ipp_server = create_ipp_server(printer_manager)

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
        discovery_service.stop()
        printer_manager.stop()


if __name__ == "__main__":
    main()

