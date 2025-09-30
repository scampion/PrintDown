"""IPP (Internet Printing Protocol) server implementation."""
import os
import socket
import struct
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
import markitdown
from printer_manager import PrintJobType


def get_local_ip():
    """Get the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


class SimpleIPPHandler(BaseHTTPRequestHandler):
    """Simple IPP request handler that converts documents to markdown."""
    
    printer_manager = None  # Will be set by create_ipp_server
    
    def do_POST(self):
        """Handle IPP POST requests."""
        client_info = f"{self.client_address[0]}:{self.client_address[1]}"
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            request_data = self.rfile.read(content_length)
            
            if len(request_data) < 8:
                self.send_error(400, "Invalid IPP request")
                return
            
            version_major = request_data[0]
            version_minor = request_data[1]
            operation_id = struct.unpack('>H', request_data[2:4])[0]
            request_id = struct.unpack('>I', request_data[4:8])[0]
            
            print(f"IPP Request from {client_info}: version={version_major}.{version_minor}, operation=0x{operation_id:04x}, request_id={request_id}")
            
            if operation_id == 0x0002:  # Print-Job
                self._handle_print_job(request_data, client_info, request_id)
            elif operation_id == 0x000B:  # Get-Printer-Attributes
                self._handle_get_printer_attributes(request_id)
            elif operation_id == 0x0004:  # Validate-Job
                self._handle_validate_job(request_id)
            elif operation_id == 0x0005:  # Create-Job
                self._handle_create_job(request_id)
            elif operation_id == 0x0006:  # Send-Document
                self._handle_send_document(request_data, client_info, request_id)
            elif operation_id in [0x0008, 0x0009, 0x000A]:  # Cancel/Get/Get-Jobs
                self._send_ipp_response(0x0000, request_id=request_id)
            else:
                print(f"Unsupported IPP operation: 0x{operation_id:04x}")
                self._send_ipp_response(0x0501, request_id=request_id)
                
        except Exception as e:
            print(f"Error handling IPP request from {client_info}: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Internal error: {e}")
    
    def _handle_print_job(self, request_data, client_info, request_id):
        """Handle IPP Print-Job operation."""
        try:
            end_of_attrs_pos = request_data.find(b'\x03')
            if end_of_attrs_pos == -1:
                self.send_error(400, "Invalid IPP request: no end-of-attributes tag")
                return
            
            document_data = request_data[end_of_attrs_pos + 1:]
            print(f"Received {len(document_data)} bytes of document data")
            
            if len(document_data) > 0:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(document_data)
                    temp_file_path = temp_file.name
                
                try:
                    md = markitdown.MarkItDown()
                    result = md.convert(temp_file_path)
                    markdown_text = result.text_content
                    
                    print(f"Converted document to markdown ({len(markdown_text)} chars)")
                    self.printer_manager.add_print_job(PrintJobType.TEXT, markdown_text, client_info)
                finally:
                    os.remove(temp_file_path)
                
                self._send_ipp_response(0x0000, request_id=request_id)
            else:
                print("Warning: No document data in Print-Job request")
                self._send_ipp_response(0x0000, request_id=request_id)
                
        except Exception as e:
            print(f"Error processing print job: {e}")
            import traceback
            traceback.print_exc()
            self._send_ipp_response(0x0500, request_id=request_id)

    def _handle_get_printer_attributes(self, request_id):
        """Handle Get-Printer-Attributes request with debug info."""
        print(f"Get-Printer-Attributes request headers: {dict(self.headers)}")
        # Parse and print requested attributes if present
        self._send_ipp_response(0x0000, include_printer_attrs=True, request_id=request_id)
    
    def _handle_validate_job(self, request_id):
        """Handle Validate-Job request."""
        print("Validate-Job: Job accepted")
        self._send_ipp_response(0x0000, request_id=request_id)
    
    def _handle_create_job(self, request_id):
        """Handle Create-Job request."""
        print("Create-Job: Job created")
        self._send_ipp_response(0x0000, request_id=request_id)
    
    def _handle_send_document(self, request_data, client_info, request_id):
        """Handle Send-Document request."""
        print("Send-Document: Processing document")
        self._handle_print_job(request_data, client_info, request_id)
    
    def _add_ipp_attribute(self, response, tag, name, value, value_tag=None):
        """Helper to add an IPP attribute to response."""
        if value_tag:
            response.append(value_tag)
        response.extend(struct.pack('>H', len(name)))
        response.extend(name.encode() if isinstance(name, str) else name)
        
        if isinstance(value, str):
            value = value.encode()
        elif isinstance(value, int):
            value = struct.pack('>I', value)
            
        response.extend(struct.pack('>H', len(value)))
        response.extend(value)
    
    def _send_ipp_response(self, status_code, include_printer_attrs=False, request_id=1):
        """Send a simple IPP response."""
        response = bytearray()
        response.extend([0x02, 0x00])  # IPP version 2.0
        response.extend(struct.pack('>H', status_code))
        response.extend(struct.pack('>I', request_id))
        
        # Operation attributes
        response.append(0x01)
        self._add_ipp_attribute(response, 0x01, 'attributes-charset', 'utf-8', 0x47)
        self._add_ipp_attribute(response, 0x01, 'attributes-natural-language', 'en-us', 0x48)
        
        if include_printer_attrs:
            response.append(0x04)
            
            ipp_port = int(os.getenv("IPP_PORT", "6310"))
            printer_uri = f'ipp://{get_local_ip()}:{ipp_port}/ipp/print'
            
            self._add_ipp_attribute(response, 0x04, 'printer-uri-supported', printer_uri, 0x45)
            self._add_ipp_attribute(response, 0x04, 'printer-name', 'PrintDown', 0x42)
            self._add_ipp_attribute(response, 0x04, 'printer-location', 'Local', 0x42)
            self._add_ipp_attribute(response, 0x04, 'printer-info', 'PrintDown Markdown Printer', 0x42)
            self._add_ipp_attribute(response, 0x04, 'printer-make-and-model', 'PrintDown v1.0', 0x42)

            self._add_ipp_attribute(response, 0x04, 'uri-security-supported', 'none', 0x44)
            self._add_ipp_attribute(response, 0x04, 'uri-authentication-supported', 'none', 0x44)
            self._add_ipp_attribute(response, 0x04, 'charset-supported', 'utf-8', 0x47)
            self._add_ipp_attribute(response, 0x04, 'natural-language-supported', 'en-us', 0x48)

            # Add printer-more-info
            printer_uri = f'http://{get_local_ip()}:{ipp_port}/ipp/print'
            self._add_ipp_attribute(response, 0x04, 'printer-more-info', printer_uri, 0x45)

            # Add job-priority and job-sheets support
            self._add_ipp_attribute(response, 0x04, 'job-priority-supported', '50', 0x21)
            self._add_ipp_attribute(response, 0x04, 'job-sheets-supported', 'none', 0x44)


            # printer-state: 3 = idle
            response.append(0x23)
            response.extend(struct.pack('>H', 13))
            response.extend(b'printer-state')
            response.extend(struct.pack('>H', 4))
            response.extend(struct.pack('>I', 3))
            
            self._add_ipp_attribute(response, 0x04, 'printer-state-reasons', 'none', 0x44)
            
            # printer-is-accepting-jobs
            response.append(0x22)
            response.extend(struct.pack('>H', 26))
            response.extend(b'printer-is-accepting-jobs')
            response.extend(struct.pack('>H', 1))
            response.append(0x01)
            
            # operations-supported
            ops = [0x0002, 0x0004, 0x0005, 0x0008, 0x0009, 0x000A, 0x000B]
            response.append(0x23)
            response.extend(struct.pack('>H', 20))
            response.extend(b'operations-supported')
            for i, op in enumerate(ops):
                if i > 0:
                    response.append(0x23)
                    response.extend(struct.pack('>H', 0))
                response.extend(struct.pack('>H', 4))
                response.extend(struct.pack('>I', op))
            
            # document-format-supported
            formats = [b'application/pdf', b'application/postscript', 
                      b'text/plain', b'application/octet-stream']
            response.append(0x49)
            response.extend(struct.pack('>H', 24))
            response.extend(b'document-format-supported')
            for i, fmt in enumerate(formats):
                if i > 0:
                    response.append(0x49)
                    response.extend(struct.pack('>H', 0))
                response.extend(struct.pack('>H', len(fmt)))
                response.extend(fmt)
            
            self._add_ipp_attribute(response, 0x04, 'document-format-default', 'application/pdf', 0x49)
            self._add_ipp_attribute(response, 0x04, 'pdl-override-supported', 'not-attempted', 0x44)
            self._add_ipp_attribute(response, 0x04, 'compression-supported', 'none', 0x44)
            self._add_ipp_attribute(response, 0x04, 'uri-security-supported', 'none', 0x44)
            self._add_ipp_attribute(response, 0x04, 'uri-authentication-supported', 'none', 0x44)
            self._add_ipp_attribute(response, 0x04, 'charset-supported', 'utf-8', 0x47)
            self._add_ipp_attribute(response, 0x04, 'natural-language-supported', 'en-us', 0x48)
            
            # ipp-versions-supported
            response.append(0x44)
            response.extend(struct.pack('>H', 23))
            response.extend(b'ipp-versions-supported')
            response.extend(struct.pack('>H', 3))
            response.extend(b'1.1')
            response.append(0x44)
            response.extend(struct.pack('>H', 0))
            response.extend(struct.pack('>H', 3))
            response.extend(b'2.0')
        
        response.append(0x03)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/ipp')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)
    
    def log_message(self, format, *args):
        """Override to customize logging."""
        print(f"IPP: {self.client_address[0]} - {format % args}")


def create_ipp_server(printer_manager):
    """Create IPP server function."""
    SimpleIPPHandler.printer_manager = printer_manager
    
    def ipp_server():
        ipp_port = int(os.getenv("IPP_PORT", "6310"))
        print(f"Starting IPP server on 0.0.0.0:{ipp_port}")
        print(f"Note: Standard IPP port is 631, but we're using {ipp_port} to avoid requiring root privileges")
        server = HTTPServer(('0.0.0.0', ipp_port), SimpleIPPHandler)
        server.serve_forever()
    
    return ipp_server

