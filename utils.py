import logging
from paddleocr import PaddleOCR
import streamlit as st
import cv2
import numpy as np
import fitz  # PyMuPDF
from pydantic import BaseModel, Field
import instructor
from openai import OpenAI
import concurrent.futures

# --- SILENCE LOGS ---
logging.getLogger("ppocr").setLevel(logging.ERROR)

# ====================== LLM SETUP ======================
# Connect to your local LLM (e.g., running via Ollama on port 11434, or vLLM on 8000)
# We use OpenAI client format because Instructor wraps it perfectly.
llm_client = instructor.from_openai(
    OpenAI(
        base_url="http://localhost:11434/v1", # Change to your local LLM endpoint
        api_key="ollama" # Dummy key for local open-source models
    ),
    mode=instructor.Mode.JSON
)

# ====================== PYDANTIC SCHEMA ======================
class DocumentData(BaseModel):
    vendor_name: str = Field(
        default="Unknown", 
        description="The name of the company or store issuing the receipt/invoice. Examples: Simyo, Ben, Megekko, NTVT, Simyo, The Madras Curry House."
    )
    total_amount: float = Field(
        default=0.0, 
        description="The final total amount due. Look for 'Totaal', 'Bedrag', 'Kaartbetaling', 'Totaalbedrag te betalen','Total'. Ignore subtotals or taxes."
    )
    receipt_number: str = Field(
        default="None",
        description=(
            "Extract the exact receipt number, invoice number, factuurnummer, bonnummer, "
            "transactie nummer, or order number from the receipt.\n\n"
            "IMPORTANT — The OCR text may use either ordering:\n"
            "  1. Label-first:  'Factuurnummer | 92596234'  → value comes AFTER the label\n"
            "  2. Value-first:  '92596234 | Factuurnummer' → value comes BEFORE the label\n"
            "You MUST check both orderings. Scan the full text for labels such as:\n"
            "Factuurnummer, Bonnummer, Receipt No., Transaction ID, Bon, Order Nr., "
            "Transactie, Referentie, # or similar — then take the alphanumeric token "
            "immediately adjacent to that label (before OR after it).\n\n"
            "Rules (follow strictly):\n"
            "- Ignore any number that looks like a date (DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, etc.)\n"
            "- Ignore page numbers (Page, Pagina, p. 1, 1van5, etc.)\n"
            "- Ignore labels itself and | \n "
            "- For Simyo receipt files, receipt number is 8 digits, for example, 92596234. Find similar pattern and return.\n"
            "- Do not return 5505RG Veldhoven.\n"
            "- Ignore numbers that appear right after store name, POI, merchant ID, or terminal ID\n"
            "- Ignore totals, VAT numbers, BTW numbers, and phone numbers\n"
            "- If multiple candidates exist, prefer the token clearly adjacent to Factuurnummer/Bonnummer\n"
            "- If no clear receipt number is found, return 'None'"
        )
    )
    date: str = Field(
        default="2100-01-01", 
        description="The date of the invoice in YYYY-MM-DD format."
    )
    category: str = Field(
        default="Other",
        description=(
            "Categorize the vendor/store into one of these categories:\n"
            "- Eten (Food & Groceries)\n"
            "- Transport (fuel, public transport, taxi, parking, etc.)\n"
            "- Electronics\n"
            "- Home & Garden\n"
            "- Drugstore (pharmacy, drogist, beauty, personal care)\n"
            "- Dining (restaurants, cafés, takeaway food)\n"
            "- Clothing & Fashion\n"
            "- Other\n\n"
            "Important rules:\n"
            "- All Albert Heijn stores (including Albert Heijn MIRA, Albert Heijn XL, AH to go, etc.) must be categorized as 'Eten'.\n"
            "- Any supermarket, grocery store, or food retailer (Jumbo, Plus, Dirk, Lidl, Aldi, etc.) should be 'Eten'.\n"
            "- Restaurants, cafés, food delivery, and takeaway places go to 'Dining'.\n"
            "- Gas stations / fuel = 'Transport'\n"
            "- Pharmacies, Kruidvat, Etos, Douglas = 'Drugstore'\n"
            "- If the vendor sells mainly food/groceries, always prefer 'Eten' over 'Other'.\n"
            "- Be consistent: the same chain should always get the same category."
        )
    )
    currency: str = Field(
        default=None,
        description=(
            "Extract the currency **symbol** used for the final total amount on the receipt. "
            "Return **only the symbol**, never the three-letter code or the full name.\n\n"
            "Examples of correct output:\n"
            "- '€' if the receipt shows EUR, Euro, or €\n"
            "- '$' if the receipt shows USD or Dollar\n"
            "- '£' if the receipt shows GBP or Pound\n"
            "- '¥' if the receipt shows JPY or Yen\n"
            "- 'CHF', 'SEK', 'NOK', 'DKK' as they are (these are both code and symbol)\n\n"
            "Strict rules:\n"
            "- If you see 'EUR' or 'Euro', always convert it to the symbol '€'\n"
            "- Never return 'EUR', 'USD', 'GBP', 'Euro', 'Dollar', etc.\n"
            "- Only return the visual symbol used on the receipt.\n"
            "- If no currency symbol or code is visible, return null."
        )
    )

# ====================== OCR PIPELINE (Kept from your code) ======================
@st.cache_resource
def load_ocr_model(lang: str = 'ch'):
    return PaddleOCR(ocr_version='PP-OCRv5', lang=lang, use_angle_cls=True, device=device)
    #return PaddleOCR(ocr_version='PP-OCRv5', lang=lang, use_angle_cls=True, device='gpu')



def load_file_as_images(uploaded_file):
    file_bytes = uploaded_file.read()
    images = []

    if uploaded_file.name.lower().endswith('.pdf'):
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            pix = page.get_pixmap(dpi=250)        # ← lowered
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            images.append(img_cv)
        doc.close()
    else:
        np_arr = np.frombuffer(file_bytes, np.uint8)
        img_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img_cv is not None:
            split_images = split_tall_image(img_cv)
            images.extend(split_images)

    return images

def split_tall_image(image: np.ndarray) -> list:
    """
    If the image is very tall (stacked pages), split it into 2 parts.
    Returns list of images (1 or 2).
    """
    h, w = image.shape[:2]
    if h > 1.8 * w:  # typical for email screenshots with 2 pages
        mid = h // 2
        # Small overlap to avoid cutting text at the split line
        top = image[:mid + 50, :]
        bottom = image[mid - 50:, :]
        return [top, bottom]
    return [image]  # normal single-page image

def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """Gentler preprocessing optimized for receipts"""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Mild contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Light sharpening (less aggressive)
    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(enhanced, -1, kernel)

    # Convert back to BGR for PaddleOCR
    processed = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)

    # Resize only if the image is too small
    h, w = processed.shape[:2]
    if max(h, w) < 1800:   # lowered from 2000
        scale = 1800 / max(h, w)
        processed = cv2.resize(processed, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    # Add small white border to help with edge text
    processed = cv2.copyMakeBorder(processed, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=[255,255,255])
    return processed

# Global cached OCR pipeline (loaded only once)
_ocr_model = None


def load_ocr_model(lang: str = 'ch', device: str = "gpu"):
    """Load PaddleOCR only once with selected device"""
    global _ocr_model
    if _ocr_model is None:
        print(f"🔄 Loading OCR models on {device.upper()}...")
        _ocr_model = PaddleOCR(
            use_angle_cls=True,
            ocr_version='PP-OCRv5',
            lang=lang,
            device=device         # ← now dynamic
        )
        print(f"✅ OCR models loaded on {device.upper()}!")
    return _ocr_model

# def load_ocr_model(lang: str = 'ch'):
#     """Load OCR model only once and reuse it"""
#     global _ocr_pipeline
#     if _ocr_pipeline is None:
#         print("🔄 Loading OCR models for the first time (this may take 10-20 seconds)...")
#         from paddlex.inference import create_pipeline
#         _ocr_pipeline = create_pipeline("OCR", lang=lang)   # or however you create it in load_ocr_model
#         print("✅ OCR models loaded and cached.")
#     return _ocr_pipeline


def perform_ocr(image: np.ndarray, lang: str = 'ch'):
    """Uses the device chosen by the user"""
    device = st.session_state.get("ocr_device", "gpu")   # ← get from app.py
    ocr = load_ocr_model(lang=lang, device=device)
    preprocessed = preprocess_for_ocr(image)

    result = ocr.ocr(preprocessed)  # ← this is the correct call

    if not result or not result[0]:
        return []

    res = result[0]

    # Support both old and new return formats
    if isinstance(res, dict) and 'rec_texts' in res:
        return res['rec_texts']
    else:
        # Standard PaddleOCR format: list of [box, (text, score)]
        return [line[1][0] for line in res]

# def perform_ocr(image: np.ndarray, lang: str = 'ch'):
#     ocr = load_ocr_model(lang=lang)
#     preprocessed = preprocess_for_ocr(image)
#     result = ocr.ocr(preprocessed)
#     if not result or not result[0]:
#         return []
#     res = result[0]
#     return res['rec_texts'] if isinstance(res, dict) and 'rec_texts' in res else[line[1][0] for line in res]

# ====================== NEW: SINGLE LLM EXTRACTION FUNCTION ======================
def extract_document_data_llm(ocr_lines: list) -> DocumentData:
    """
    Takes the raw OCR text list, formats it, and asks the LLM to extract everything at once.
    """
    if not ocr_lines:
        return DocumentData()

    # Join the OCR text lines into a single block of text
    raw_text = "\n".join([str(line) for line in ocr_lines])
    
    # System prompt specifically tailored for your Dutch/English edge cases
    system_prompt = """
    You are an expert Dutch, English, Chinese and other european language accounting AI. 
    Analyze the OCR text from a scanned receipt or invoice. 
    Extract the vendor name, total amount, receipt/invoice number (factuurnummer), date and currency.
    Watch out for formatting artifacts like '|' characters. 
    Ensure the total amount is a float (e.g. 382.45).
    """

    try:
        response = llm_client.chat.completions.create(
            model= "qwen2.5:7b-instruct-q4_K_M", # Use your local model name (qwen2.5 or llama3.1 recommended)
            response_model=DocumentData,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"OCR TEXT:\n{raw_text}"}
            ],
            temperature=0.0, # 0.0 forces strict, non-creative extraction
            max_retries=2    # If the LLM hallucinate invalid JSON, instructor automatically retries
        )
        return response
    except Exception as e:
        # ---> ADD THIS PRINT STATEMENT <---
        print(f"\n❌ CRITICAL LLM ERROR: {e}\n")
        # st.error(f"LLM Extraction failed: {e}")
        return DocumentData() # Return safe default empty object

# ====================== NEW: CONCURRENT BATCH PROCESSING ======================
def process_multiple_documents(uploaded_files):
    """
    Handles HUNDREDS of files concurrently so Streamlit doesn't freeze.
    """
    results =[]
    
    # Step 1: Extract Images and run OCR (can also be threaded if you have a GPU)
    ocr_results_per_file = {}
    for file in uploaded_files:
        images = load_file_as_images(file) # From your old code
        full_ocr_text =[]
        for img in images:
            text_lines = perform_ocr(img)
            full_ocr_text.extend(text_lines)
        ocr_results_per_file[file.name] = full_ocr_text

    # Step 2: Run LLM Extraction concurrently
    # Using ThreadPoolExecutor allows 10 API calls to be processed simultaneously
    st.info("Extracting data with AI...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Create a dictionary to map futures to filenames
        future_to_filename = {
            executor.submit(extract_document_data_llm, text_lines): filename 
            for filename, text_lines in ocr_results_per_file.items()
        }
        
        # Collect results as they finish
        for future in concurrent.futures.as_completed(future_to_filename):
            filename = future_to_filename[future]
            try:
                data: DocumentData = future.result()
                results.append({
                    "Filename": filename,
                    "Vendor": data.vendor_name,
                    "Total Amount": f"€ {data.total_amount:.2f}".replace('.', ','),
                    "Receipt No": data.receipt_number,
                    "Date": data.date,
                    "Category": data.category,
                    "Currency": data.currency
                })
            except Exception as exc:
                st.error(f"{filename} generated an exception: {exc}")

    return results