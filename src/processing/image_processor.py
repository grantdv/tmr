import cv2
import pytesseract
import numpy as np
from PIL import Image
import io

class ImageProcessor:
    @staticmethod
    def extract_text(image_input):
        """
        Extracts text from a file path (str) or a PIL Image object.
        """
        if isinstance(image_input, str):
            # Handle file path
            img = cv2.imread(image_input)
            if img is None:
                raise ValueError(f"Could not read image at {image_input}")
            # Convert BGR to Grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Thresholding for better OCR
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # Convert to PIL for pytesseract
            img_pil = Image.fromarray(thresh)
            text = pytesseract.image_to_string(img_pil)
            print(f"    [OCR] Extracted {len(text)} characters from file path.")
            return text
        elif isinstance(image_input, Image.Image):
            # Handle PIL Image directly
            # Convert PIL Image to numpy array (RGB)
            img_array = np.array(image_input)
            # Convert RGB to BGR (OpenCV format)
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            # Convert to Grayscale
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            # Thresholding for better OCR
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # Convert back to PIL for pytesseract
            img_pil = Image.fromarray(thresh)
            text = pytesseract.image_to_string(img_pil)
            print(f"    [OCR] Extracted {len(text)} characters from PIL Image.")
            return text
        else:
            raise TypeError("Input must be a file path (str) or a PIL.Image object.")
