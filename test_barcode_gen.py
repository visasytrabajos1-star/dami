import os
import barcode
from barcode.writer import ImageWriter

def test_generate_barcode():
    # Ensure directory exists
    os.makedirs("static/barcodes", exist_ok=True)
    
    test_code = "123456789012" # Valid 12 digit (EAN13 will add check digit to make 13)
    filename = "test_ean13"
    file_path = f"static/barcodes/{filename}"
    
    try:
        ean = barcode.get('ean13', test_code, writer=ImageWriter())
        filename = ean.save(file_path)
        print(f"Success: Generated {filename}")
    except Exception as e:
        print(f"Error generating EAN13: {e}")
        
    # Test Code128 fallback
    test_code_alpha = "ABC-123"
    filename_alpha = "test_code128"
    file_path_alpha = f"static/barcodes/{filename_alpha}"
    
    try:
        code128 = barcode.get('code128', test_code_alpha, writer=ImageWriter())
        filename = code128.save(file_path_alpha)
        print(f"Success: Generated {filename}")
    except Exception as e:
        print(f"Error generating Code128: {e}")

if __name__ == "__main__":
    test_generate_barcode()
