import sys
from xml.sax.handler import ContentHandler  # nosec

from defusedxml import ElementTree as ET
from defusedxml.sax import make_parser


class DiagnosticHandler(ContentHandler):
    def __init__(self):
        super().__init__()
        self.line_number = 0
        self.column_number = 0

    def setDocumentLocator(self, locator):
        self.locator = locator

    def characters(self, content):
        # Check for invalid XML characters
        for char in content:
            if ord(char) >= 0xFFFE or (ord(char) <= 0x1F and char not in "\n\r\t"):
                print(
                    f"Found invalid character '0x{ord(char):04x}' at line {self.locator.getLineNumber()}, column {self.locator.getColumnNumber()}"
                )


def diagnose_xml(filename):
    print(f"Analyzing {filename}...")

    # First, try to read the file in chunks to find encoding issues
    try:
        with open(filename, "rb") as f:
            chunk_size = 8192
            chunk_number = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                try:
                    chunk.decode("utf-8")
                except UnicodeDecodeError as e:
                    byte_pos = chunk_number * chunk_size + e.start
                    print(f"Found invalid UTF-8 sequence at byte position {byte_pos}")
                    print(f"Problematic bytes: {chunk[e.start:e.end].decode('utf-8')}")
                chunk_number += 1
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

    # Then try SAX parsing for detailed error reporting
    parser = make_parser()
    handler = DiagnosticHandler()
    parser.setContentHandler(handler)

    try:
        parser.parse(filename)
    except Exception as e:
        print(f"SAX parsing error: {e}")

    # Finally try ElementTree parsing
    try:
        ET.parse(filename)
    except ET.ParseError as e:
        print(f"ElementTree parsing error: {e}")

        # Try to get context around the error
        try:
            with open(filename, encoding="utf-8") as f:
                lines = f.readlines()
                line_num = e.position[0]
                start = max(0, line_num - 2)
                end = min(len(lines), line_num + 3)
                print("\nContext around error:")
                for i in range(start, end):
                    prefix = "-> " if i + 1 == line_num else "   "
                    print(f"{prefix}{i+1}: {lines[i].rstrip()}")
        except Exception as context_error:
            print(f"Could not get context: {context_error}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <xml_file>")
        sys.exit(1)
    diagnose_xml(sys.argv[1])
