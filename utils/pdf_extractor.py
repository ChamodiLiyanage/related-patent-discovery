import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_bytes
import re
from io import BytesIO

# Set Tesseract path manually (for Windows)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---------------------------------------------------------
# Extract text using PyMuPDF
# ---------------------------------------------------------
def extract_text_fitz(file_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception as e:
        print("Text extraction with fitz failed:", e)
        return ""

# ---------------------------------------------------------
# Extract text using OCR fallback (pdf2image + pytesseract)
# ---------------------------------------------------------
# def extract_text_ocr(file_bytes: bytes, max_pages=10) -> str:
#     try:
#         images = convert_from_bytes(file_bytes, dpi=200)[:max_pages]
#         return "\n".join(pytesseract.image_to_string(img) for img in images)
#     except Exception as e:
#         print("OCR fallback failed:", e)
#         return ""
def extract_text_ocr(file_bytes: bytes, max_pages=5) -> str:
    try:
        images = convert_from_bytes(file_bytes, dpi=200)[:max_pages]
        ocr_result = []
        for i, img in enumerate(images):
            text = pytesseract.image_to_string(img)
            if len(text.strip()) > 100:
                ocr_result.append(text.strip())
            # Stop early if good text found from first 3 pages
            if i >= 2 and len(" ".join(ocr_result)) > 300:
                break
        return "\n".join(ocr_result)
    except Exception as e:
        print("OCR fallback failed:", e)
        return ""

# ---------------------------------------------------------
# Main utility: Extract title, abstract, and claims
# ---------------------------------------------------------
def extract_patent_sections(file_bytes: bytes) -> dict:
    fitz_text = extract_text_fitz(file_bytes).strip()
    source = "PDF"

    # Heuristic to decide fallback — weak text detection
    if len(fitz_text) < 300 or fitz_text.count("\n") < 5:
        print("[INFO] Detected weak text, running OCR fallback...")
        ocr_text = extract_text_ocr(file_bytes)
        full_text = f"{fitz_text}\n\n{ocr_text}".strip()
        source = "OCR"
    else:
        full_text = fitz_text

    lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    lowered = "\n".join(lines).lower()

    # --- Title ---
    title = next((line for line in lines if "patent" in line.lower() and len(line) < 100), "Untitled")

    # --- Abstract ---
    abstract = ""
    abstract_match = re.search(
        r"abstract\s*[:\-\s]*\n?(.*?)(?=\n\s*(field of invention|technical field|background|summary|claims|description|brief description of drawings)|\n\d+\s*\.)",
        lowered, re.IGNORECASE | re.DOTALL
    )
    if abstract_match:
        abstract_text = abstract_match.group(1).strip()
        # Limit abstract length to prevent irrelevant long captures
        abstract_lines = abstract_text.split('\n')
        abstract = " ".join(abstract_lines[:10]).strip()  # Take only first 10 lines at most

    # --- Claims ---
    claim_lines = []
    found_claim_start = False
    for line in lines:
        if re.match(r"^(1[\.\)]|claim\s*1)", line.lower()):
            found_claim_start = True
        if found_claim_start:
            if re.match(r"^(description|background|abstract)", line.lower()):
                break
            claim_lines.append(line)

    grouped_claims = []
    current = ""
    for line in claim_lines:
        if re.match(r"^\d+[\.\)]", line.strip()):
            if current:
                grouped_claims.append(current.strip())
            current = line
        else:
            current += " " + line
    if current:
        grouped_claims.append(current.strip())

    return {
        "title": title.strip(),
        "abstract": abstract.strip(),
        "claims": grouped_claims,
        "source": source  # NEW: add this so app.py can show in frontend
    }
