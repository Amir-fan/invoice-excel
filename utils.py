import os
import tempfile
from typing import Optional, Union, List
from PIL import Image
import io

# Try to import pdf2image, but handle the case where it's not available
# On Vercel, pdf2image requires poppler which is not available, so we'll use PyMuPDF instead
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except (ImportError, OSError) as e:
    PDF2IMAGE_AVAILABLE = False
    # Don't print warnings on import - can cause issues in serverless
    pass

# Try to import PyMuPDF as an alternative PDF processor
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    # Don't print warnings on import - can cause issues in serverless
    pass

# Arabic digit mapping for normalization
ARABIC_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789..")

def normalize_numbers(s: Optional[Union[str, int, float]]) -> Optional[str]:
    """Normalize Arabic digits to Western digits and clean up formatting."""
    if s is None:
        return None
    
    # Convert to string if it's a number
    s = str(s)
    
    # Translate Arabic digits to Western digits
    normalized = s.translate(ARABIC_DIGIT_MAP)
    
    # Remove commas and clean up
    normalized = normalized.replace(',', '').replace(' ', '')
    
    return normalized

def extract_number(s: Optional[Union[str, int, float]]) -> Optional[float]:
    """Extract and convert a string to float, handling Arabic digits."""
    if s is None:
        return None
    
    normalized = normalize_numbers(s)
    if not normalized:
        return None
    
    try:
        # Remove any remaining non-numeric characters except decimal point
        cleaned = ''.join(c for c in normalized if c.isdigit() or c == '.')
        if cleaned:
            return float(cleaned)
    except ValueError:
        pass
    
    return None

def pdf_to_image_pymupdf(pdf_path: str, page_number: int = 0, dpi: int = 300) -> Optional[Image.Image]:
    """Convert PDF page to PIL Image using PyMuPDF (no external dependencies)."""
    if not PYMUPDF_AVAILABLE:
        return None
    
    try:
        # Open PDF with PyMuPDF
        doc = fitz.open(pdf_path)
        
        if page_number >= len(doc):
            doc.close()
            return None
        
        # Get the page
        page = doc.load_page(page_number)
        
        # Calculate zoom factor for desired DPI
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        
        # Render page to pixmap
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        doc.close()
        return img
        
    except Exception as e:
        print(f"Error converting PDF with PyMuPDF: {e}")
        return None


def extract_pdf_text_lines(pdf_path: str) -> Optional[List[str]]:
    """
    Extract text lines from a PDF using PyMuPDF.

    Returns a list of non-empty lines in reading order, or None if extraction fails.
    """
    if not PYMUPDF_AVAILABLE:
        return None

    try:
        doc = fitz.open(pdf_path)
        lines: List[str] = []
        for page in doc:
            # Get plain text for the page and split into lines
            text = page.get_text("text") or ""
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if line:
                    lines.append(line)
        doc.close()
        return lines if lines else None
    except Exception as e:
        print(f"Error extracting text from PDF with PyMuPDF: {e}")
        return None

def pdf_to_image(pdf_path: str, page_number: int = 0, dpi: int = 300) -> Optional[Image.Image]:
    """Convert PDF page to PIL Image using available methods."""
    
    # First try PyMuPDF (no external dependencies)
    if PYMUPDF_AVAILABLE:
        img = pdf_to_image_pymupdf(pdf_path, page_number, dpi)
        if img:
            return img
    
    # Fall back to pdf2image if available
    if PDF2IMAGE_AVAILABLE:
        try:
            # Check if poppler is available
            try:
                # Try to convert PDF to images
                images = convert_from_path(pdf_path, dpi=dpi)
                
                if images and len(images) > page_number:
                    return images[page_number]
                
                return None
            except Exception as e:
                if "poppler" in str(e).lower() or "path" in str(e).lower():
                    print("Error: Poppler is not installed or not in PATH.")
                    print("Please install PyMuPDF instead: pip install PyMuPDF")
                    return None
                else:
                    raise e
                    
        except Exception as e:
            print(f"Error converting PDF to image: {e}")
            return None
    
    return None

def image_to_bytes(image: Image.Image, format: str = 'PNG') -> bytes:
    """Convert PIL Image to bytes."""
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format=format)
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()

def create_temp_file(suffix: str = '.tmp') -> str:
    """Create a temporary file and return its path."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()
    return temp_file.name

def cleanup_temp_file(file_path: str):
    """Delete a temporary file."""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        print(f"Error cleaning up temp file {file_path}: {e}")

def is_pdf_file(filename: str) -> bool:
    """Check if file is a PDF based on extension."""
    return filename.lower().endswith('.pdf')

def is_image_file(filename: str) -> bool:
    """Check if file is an image based on extension."""
    return filename.lower().endswith(('.jpg', '.jpeg', '.png'))

def check_pdf_dependencies() -> bool:
    """Check if PDF processing dependencies are available."""
    # PyMuPDF is preferred as it has no external dependencies
    if PYMUPDF_AVAILABLE:
        return True
    
    # Fall back to pdf2image if available
    if PDF2IMAGE_AVAILABLE:
        try:
            # Try a simple test to see if poppler is working
            test_pdf = create_temp_file('.pdf')
            try:
                # Create a minimal test PDF content (this is just a test)
                with open(test_pdf, 'wb') as f:
                    f.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids []\n/Count 0\n>>\nendobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \ntrailer\n<<\n/Root 1 0 R\n/Size 3\n>>\nstartxref\n77\n%%EOF')
                
                # Try to convert (this should fail gracefully if poppler is not available)
                try:
                    images = convert_from_path(test_pdf, dpi=72)
                    return True
                except Exception:
                    return False
            finally:
                cleanup_temp_file(test_pdf)
        except Exception:
            return False
    
    return False

def get_pdf_installation_instructions() -> str:
    """Get installation instructions for PDF processing."""
    if PYMUPDF_AVAILABLE:
        return "PDF processing is available with PyMuPDF."
    
    if PDF2IMAGE_AVAILABLE:
        return "PDF processing requires Poppler. Install PyMuPDF instead: pip install PyMuPDF"
    
    return "PDF processing not available. Install PyMuPDF: pip install PyMuPDF"
