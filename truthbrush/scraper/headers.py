import os

def parse_headers_from_file(filepath="browser_headers.txt"):
    """
    Parse HTTP headers from a text file in the format:
    
    GET /path HTTP/2
    Host: example.com
    User-Agent: Mozilla/5.0...
    Accept: application/json
    ...
    
    Returns a dictionary of headers (excluding the request line and Host).
    """
    headers = {}
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(script_dir, filepath)
        
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and the request line (e.g., "GET /path HTTP/2")
            if not line or line.startswith('GET') or line.startswith('POST') or line.startswith('HEAD'):
                continue
            
            # Skip the Host: line since requests handles that
            if line.startswith('Host:'):
                continue
            
            # Parse header lines in the format "Header-Name: value"
            if ':' in line:
                header_name, header_value = line.split(':', 1)
                headers[header_name.strip()] = header_value.strip()
        
        return headers
    
    except FileNotFoundError:
        print(f"Warning: {filepath} not found. Using default headers.")
        return {}
    except Exception as e:
        print(f"Error parsing headers from {filepath}: {e}")
        return {}


# Load headers from browser_headers.txt
HEADERS = parse_headers_from_file()

if HEADERS:
    print(f"Loaded {len(HEADERS)} headers from browser_headers.txt")
else:
    print("No headers loaded from browser_headers.txt, using defaults")

