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
        
        # Handle Expect: 100-continue header (required for CUPS/macOS)
        if self.headers.get('Expect', '').lower() == '100-continue':
            self.send_response_only(100)
            self.end_headers()
        
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
                self._handle_get_printer_attributes(request_data, request_id)
            elif operation_id == 0x0004:  # Validate-Job
                self._handle_validate_job(request_id)
            elif operation_id == 0x0005:  # Create-Job
                self._handle_create_job(request_id)
            elif operation_id == 0x0006:  # Send-Document
                self._handle_send_document(request_data, client_info, request_id)
            elif operation_id in [0x0008, 0x0009, 0x000A]:  # Cancel/Get-Job-Attributes/Get-Jobs
                if operation_id == 0x0009:
                    self._handle_get_job_attributes(request_id)
                elif operation_id == 0x000A:
                    self._handle_get_jobs(request_id)
                else:
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
    
    def _parse_ipp_attributes(self, request_data):
        """Parse IPP request attributes."""
        requested_attrs = []
        pos = 8  # Skip version, operation-id, request-id
        
        try:
            while pos < len(request_data):
                if pos >= len(request_data):
                    break
                    
                tag = request_data[pos]
                pos += 1
                
                # End of attributes
                if tag == 0x03:
                    break
                
                # Delimiter tags
                if tag in [0x01, 0x02, 0x04, 0x05]:
                    continue
                
                # Read name length
                if pos + 2 > len(request_data):
                    break
                name_len = struct.unpack('>H', request_data[pos:pos+2])[0]
                pos += 2
                
                # Read name
                if pos + name_len > len(request_data):
                    break
                name = request_data[pos:pos+name_len].decode('utf-8', errors='ignore')
                pos += name_len
                
                # Read value length
                if pos + 2 > len(request_data):
                    break
                value_len = struct.unpack('>H', request_data[pos:pos+2])[0]
                pos += 2
                
                # Read value
                if pos + value_len > len(request_data):
                    break
                value = request_data[pos:pos+value_len]
                pos += value_len
                
                # If this is requested-attributes, parse the value
                if name == 'requested-attributes':
                    attr_name = value.decode('utf-8', errors='ignore')
                    requested_attrs.append(attr_name)
                    print(f"  Requested attribute: {attr_name}")
                    
        except Exception as e:
            print(f"Error parsing attributes: {e}")
        
        return requested_attrs
    
    def _handle_get_printer_attributes(self, request_data, request_id):
        """Handle Get-Printer-Attributes request with debug info."""
        print(f"Get-Printer-Attributes request headers: {dict(self.headers)}")
        print(f"Client User-Agent: {self.headers.get('User-Agent', 'Unknown')}")
        
        # Parse requested attributes
        requested_attrs = []
        if b'requested-attributes' in request_data:
            print("CUPS is requesting specific attributes:")
            requested_attrs = self._parse_ipp_attributes(request_data)
        
        self._send_ipp_response(0x0000, include_printer_attrs=True, request_id=request_id, requested_attrs=requested_attrs)
    
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
    
    def _handle_get_job_attributes(self, request_id):
        """Handle Get-Job-Attributes request."""
        print("Get-Job-Attributes: Returning job completed status")
        self._send_ipp_response(0x0000, include_job_attrs=True, request_id=request_id)
    
    def _handle_get_jobs(self, request_id):
        """Handle Get-Jobs request."""
        print("Get-Jobs: Returning empty job list")
        self._send_ipp_response(0x0000, request_id=request_id)

    def _send_ipp_response(self, status_code, include_printer_attrs=False, include_job_attrs=False, request_id=1,
                           requested_attrs=None):
        """Send a simple IPP response."""
        response = bytearray()
        response.extend([0x02, 0x00])  # IPP version 2.0
        response.extend(struct.pack('>H', status_code))
        response.extend(struct.pack('>I', request_id))

        # Operation attributes group (REQUIRED)
        response.append(0x01)

        # attributes-charset
        response.append(0x47)  # charset tag
        response.extend(struct.pack('>H', 18))  # "attributes-charset"
        response.extend(b'attributes-charset')
        response.extend(struct.pack('>H', 5))  # "utf-8"
        response.extend(b'utf-8')

        # attributes-natural-language
        response.append(0x48)  # naturalLanguage tag
        response.extend(struct.pack('>H', 27))  # "attributes-natural-language"
        response.extend(b'attributes-natural-language')
        response.extend(struct.pack('>H', 5))  # "en-us"
        response.extend(b'en-us')

        if include_job_attrs:
            # Job attributes group
            response.append(0x02)

            ipp_port = int(os.getenv("IPP_PORT", "6310"))
            job_uri = f'ipp://{get_local_ip()}:{ipp_port}/ipp/print/1'

            response.append(0x45)  # uri tag
            response.extend(struct.pack('>H', 7))  # "job-uri"
            response.extend(b'job-uri')
            response.extend(struct.pack('>H', len(job_uri)))
            response.extend(job_uri.encode())

            # job-id
            response.append(0x21)  # integer tag
            response.extend(struct.pack('>H', 6))  # "job-id"
            response.extend(b'job-id')
            response.extend(struct.pack('>H', 4))
            response.extend(struct.pack('>I', 1))

            # job-state: 9 = completed
            response.append(0x23)  # enum tag
            response.extend(struct.pack('>H', 9))  # "job-state"
            response.extend(b'job-state')
            response.extend(struct.pack('>H', 4))
            response.extend(struct.pack('>I', 9))

            response.append(0x44)  # keyword tag
            response.extend(struct.pack('>H', 17))  # "job-state-reasons"
            response.extend(b'job-state-reasons')
            reason = b'job-completed-successfully'
            response.extend(struct.pack('>H', len(reason)))
            response.extend(reason)

        if include_printer_attrs:
            # Printer attributes group
            response.append(0x04)

            ipp_port = int(os.getenv("IPP_PORT", "6310"))
            printer_uri = f'ipp://{get_local_ip()}:{ipp_port}/ipp/print'

            # printer-uri-supported
            response.append(0x45)  # uri tag
            response.extend(struct.pack('>H', 21))  # "printer-uri-supported"
            response.extend(b'printer-uri-supported')
            response.extend(struct.pack('>H', len(printer_uri)))
            response.extend(printer_uri.encode())

            # printer-name
            response.append(0x42)  # nameWithoutLanguage tag
            response.extend(struct.pack('>H', 12))  # "printer-name"
            response.extend(b'printer-name')
            name = b'PrintDown'
            response.extend(struct.pack('>H', len(name)))
            response.extend(name)

            # printer-state: 3 = idle
            response.append(0x23)  # enum tag
            response.extend(struct.pack('>H', 13))  # "printer-state"
            response.extend(b'printer-state')
            response.extend(struct.pack('>H', 4))
            response.extend(struct.pack('>I', 3))

            # printer-state-reasons
            response.append(0x44)  # keyword tag
            response.extend(struct.pack('>H', 21))  # "printer-state-reasons"
            response.extend(b'printer-state-reasons')
            response.extend(struct.pack('>H', 4))
            response.extend(b'none')

            # printer-is-accepting-jobs
            response.append(0x22)  # boolean tag
            response.extend(struct.pack('>H', 26))  # name length
            response.extend(b'printer-is-accepting-jobs')
            response.extend(struct.pack('>H', 1))  # value length = 1
            response.append(0x01)  # boolean true value

            # operations-supported
            ops = [0x0002, 0x0004, 0x0005, 0x0008, 0x0009, 0x000A, 0x000B]
            for i, op in enumerate(ops):
                response.append(0x23)  # enum tag
                if i == 0:
                    response.extend(struct.pack('>H', 20))  # "operations-supported"
                    response.extend(b'operations-supported')
                else:
                    response.extend(struct.pack('>H', 0))  # additional value
                response.extend(struct.pack('>H', 4))
                response.extend(struct.pack('>I', op))

            # document-format-supported
            formats = [b'application/pdf', b'application/postscript',
                       b'text/plain', b'application/octet-stream']
            for i, fmt in enumerate(formats):
                response.append(0x49)  # mimeMediaType tag
                if i == 0:
                    response.extend(struct.pack('>H', 25))  # "document-format-supported"
                    response.extend(b'document-format-supported')
                else:
                    response.extend(struct.pack('>H', 0))  # additional value
                response.extend(struct.pack('>H', len(fmt)))
                response.extend(fmt)

            # document-format-default
            response.append(0x49)  # mimeMediaType tag
            response.extend(struct.pack('>H', 23))  # "document-format-default"
            response.extend(b'document-format-default')
            fmt = b'application/pdf'
            response.extend(struct.pack('>H', len(fmt)))
            response.extend(fmt)

            # compression-supported
            response.append(0x44)  # keyword tag
            response.extend(struct.pack('>H', 21))  # "compression-supported"
            response.extend(b'compression-supported')
            response.extend(struct.pack('>H', 4))
            response.extend(b'none')

            # charset-supported
            response.append(0x47)  # charset tag
            response.extend(struct.pack('>H', 17))  # "charset-supported"
            response.extend(b'charset-supported')
            response.extend(struct.pack('>H', 5))
            response.extend(b'utf-8')

            # ipp-versions-supported
            versions = [b'1.1', b'2.0']
            for i, ver in enumerate(versions):
                response.append(0x44)  # keyword tag
                if i == 0:
                    response.extend(struct.pack('>H', 23))  # "ipp-versions-supported"
                    response.extend(b'ipp-versions-supported')
                else:
                    response.extend(struct.pack('>H', 0))  # additional value
                response.extend(struct.pack('>H', len(ver)))
                response.extend(ver)

        # End of attributes
        response.append(0x03)

        # Debug the response structure

        self._debug_response(response)
        self.send_response(200)
        self.send_header('Content-Type', 'application/ipp')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)
    
    def log_message(self, format, *args):
        """Override to customize logging."""
        print(f"IPP: {self.client_address[0]} - {format % args}")

    def _debug_response(self, response):
        """Debug IPP response structure."""
        print("\n=== IPP Response Debug ===")
        print(f"Total length: {len(response)} bytes")
        pos = 0

        # Version and status
        print(f"Version: {response[0]}.{response[1]}")
        print(f"Status: 0x{struct.unpack('>H', response[2:4])[0]:04x}")
        print(f"Request ID: {struct.unpack('>I', response[4:8])[0]}")
        pos = 8

        # Parse attributes
        while pos < len(response) and response[pos] != 0x03:
            tag = response[pos]
            pos += 1

            if tag in [0x01, 0x02, 0x04, 0x05]:
                group_names = {0x01: "operation", 0x02: "job", 0x04: "printer", 0x05: "unsupported"}
                print(f"\n--- {group_names.get(tag, 'unknown')} attributes group ---")
                continue

            name_len = struct.unpack('>H', response[pos:pos + 2])[0]
            pos += 2
            name = response[pos:pos + name_len].decode('utf-8',
                                                       errors='ignore') if name_len > 0 else "(additional-value)"
            pos += name_len

            value_len = struct.unpack('>H', response[pos:pos + 2])[0]
            pos += 2

            tag_names = {0x21: "integer", 0x22: "boolean", 0x23: "enum",
                         0x42: "nameWithoutLanguage", 0x44: "keyword",
                         0x45: "uri", 0x47: "charset", 0x48: "naturalLanguage", 0x49: "mimeMediaType"}
            print(f"  {name} ({tag_names.get(tag, f'0x{tag:02x}')}): length={value_len}")

            if tag == 0x22 and value_len != 1:
                print(f"    ERROR: Boolean value length is {value_len}, should be 1!")

            pos += value_len

        print(f"\nEnd tag at position {pos}")
        print("=========================\n")


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

