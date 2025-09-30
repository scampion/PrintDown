"""Main entry point for the PrintDown thermal printer server."""
import threading
from dotenv import load_dotenv

from printer_manager import PrinterManager
from tcp_servers import create_text_server, create_image_server
from ipp_server import create_ipp_server
from discovery_service import DiscoveryService
from test_utils import print_help, test_markdown_formatting


# Load environment variables
load_dotenv()


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

