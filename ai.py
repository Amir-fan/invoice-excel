import json
import base64
import re
import os
from typing import Optional, Dict, Any, List
from openai import OpenAI
from pydantic import BaseModel, Field
from utils import extract_number, normalize_numbers

# Initialize OpenAI client with API key from environment variable
# Lazy initialization - only create client when needed to avoid errors during import
_client = None

def get_openai_client():
    """Get or create OpenAI client. Lazy initialization."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not set. "
                "Please set it in your environment or .env file."
            )
        _client = OpenAI(api_key=api_key)
    return _client

# ============================================================================
# DATA MODELS
# ============================================================================

class InvoiceItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None  # المبلغ (line amount before discount)
    discount: Optional[float] = None  # الخصم (discount)
    line_subtotal: Optional[float] = None
    tax_rate: Optional[Any] = None  # Can be number or "exempt"
    tax_amount: Optional[float] = None
    line_total: Optional[float] = None  # الاجمالي (line total after discount and tax)

class InvoiceData(BaseModel):
    # Seller information
    commercial_name: Optional[str] = None  # الاسم التجاري
    tax_number: Optional[str] = None  # الرقم الضريبي
    income_source_sequence: Optional[str] = None  # تسلسل مصدر الدخل
    
    # Invoice identification
    electronic_invoice_number: Optional[str] = None  # رقم الفاتورة الإلكترونية
    seller_invoice_number: Optional[str] = None  # رقم فاتورة البائع
    invoice_date: Optional[str] = None  # تاريخ إصدار الفاتورة
    invoice_type: Optional[str] = None  # نوع الفاتورة
    currency: Optional[str] = None  # نوع العملة
    
    # Buyer information
    buyer_name: Optional[str] = None  # اسم المشتري
    buyer_number: Optional[str] = None  # رقم المشتري
    phone_number: Optional[str] = None  # رقم الهاتف
    city: Optional[str] = None  # المدينة
    
    # Line items
    items: list[InvoiceItem] = Field(default_factory=list)
    
    # Totals
    total_discount: Optional[float] = None  # مجموع قيمة الخصم
    grand_total: Optional[float] = None  # إجمالي قيمة الفاتورة
    
    # Legacy fields for backwards compatibility
    invoice_number: Optional[str] = None
    customer_name: Optional[str] = None
    seller_name: Optional[str] = None
    subtotal: Optional[float] = None
    total_tax: Optional[float] = None


# ============================================================================
# EXTRACTION SYSTEM PROMPTS
# ============================================================================

def _get_system_prompt() -> str:
    """Get the system prompt for AI extraction."""
    return """You are an expert at extracting structured data from Arabic/English invoices (Jordan, Iraq). 

CRITICAL RULES:
1. Read the ACTUAL text visible in the image - do NOT invent, guess, or correct data
2. Normalize Arabic digits (٠١٢٣٤٥٦٧٨٩٫٬) to Western (0123456789.)
3. Extract ALL fields even if they seem small or in corners
4. Look carefully at header sections, seller info sections, buyer info sections
5. Return ONLY valid JSON matching the schema
6. If a field is missing or unclear, use null (not empty string or placeholder) - do NOT guess
7. Numbers should be numbers (not strings with commas/spaces)
8. Dates in DD-MM-YYYY format
9. The invoice text is the single source of truth - do NOT rewrite, summarize, translate, or \"fix\" it.
10. If there is a mathematical inconsistency on the invoice, keep the printed numbers EXACTLY as they appear.
11. For any text fields (names, descriptions, city, etc.), EVERY NON-NUMERIC WORD you output MUST appear somewhere in the invoice image. Do NOT introduce new words that are not in the invoice."""


def _get_user_prompt() -> str:
    """Get the detailed user prompt for field extraction."""
    return """Extract ALL invoice data from this image. Be thorough and check every section.

**SELLER INFORMATION (البائع) - Usually in top-right or header:**
Look for sections labeled "البائع" or seller info boxes:
- الاسم التجاري (Commercial Name) - In many invoices this is labeled "الاسم التجاري".
  - On some invoices it is labeled ONLY "الاسم" under the البائع section. In that case,
    treat that value as commercial_name as well.
- الرقم الضريبي (Tax Number) - Look for label "الرقم الضريبي:" followed by numbers (e.g., 48832456)
- تسلسل مصدر الدخل (Income Source Sequence) - Look for "تسلسل مصدر الدخل:" followed by a long number (e.g., 15970493). 
  VERY IMPORTANT: If this label exists, you MUST return that number in the field income_source_sequence (as digits only, no spaces or other characters).

**INVOICE IDENTIFICATION (معلومات الفاتورة) - Usually top-left or header:**
- رقم الفاتورة الإلكترونية (Electronic Invoice Number) - Look for "رقم الفاتورة الإلكترونية:" or "EIN" prefix (e.g., EIN00001)
- رقم فاتورة البائع (Seller Invoice Number) - Look for "رقم فاتورة البائع:" or just a number (e.g., 1)
- تاريخ إصدار الفاتورة (Invoice Date) - Look for "تاريخ إصدار الفاتورة:" followed by date (e.g., 26-05-2025)
- نوع الفاتورة (Invoice Type) - Look for "نوع الفاتورة:" followed by text like "فاتورة محلية" or "Local Invoice"
- نوع العملة (Currency) - Look for "نوع العملة:" followed by "دينار أردني" or "JOD" or currency code

**BUYER INFORMATION (المشتري) - Usually middle section:**
Look for sections labeled "المشتري" or buyer info:
- اسم المشتري (Buyer Name) - Look for "اسم المشتري:" or just "الاسم" inside the المشتري section,
  followed by the buyer's name
- رقم المشتري (Buyer Number) - Look for "رقم المشتري:" followed by numbers
- رقم الهاتف (Phone Number) - Look for "رقم الهاتف:" followed by phone number (may have spaces/dashes)
- المدينة (City) - Look for "المدينة:" followed by city name (e.g., عمان)

**LINE ITEMS TABLE (جدول البنود):**
For each row in the items table, extract:
- الوصف (Description) - Item description. COPY THE TEXT EXACTLY as it appears in the table cell.
  - Do NOT summarize, change wording, or add extra words.
  - Do NOT translate between Arabic and English. Keep the original language and spelling.
  - Do NOT use any word in the description that does NOT already appear somewhere in the invoice (e.g., do not invent phrases like \"زيارة متحف العملات الملكي\" if that exact phrase is not printed).
- الكمية (Quantity) - Number quantity. Use the exact digits printed on the invoice.
- سعر الوحدة (Unit Price) - Price per unit. Use the exact digits printed on the invoice.
- المبلغ (Amount) - Use the exact amount printed on the invoice. Do NOT recalculate or round.
- الخصم (Discount) - Discount amount (may be 0). Use the exact printed value.
- الاجمالي (Line Total) - Total for this line. Use the exact printed value.

**TOTALS (الإجماليات) - Usually bottom-right:**
- مجموع قيمة الخصم (Total Discount) - Look for this label followed by amount. Use the exact printed number.
- إجمالي قيمة الفاتورة (Total Invoice Value) - Look for this label at the bottom. Use the exact printed number.

SPECIAL ATTENTION:
- Tax numbers are usually 8-10 digits
- Phone numbers may have formats: 0799031778 or 079-903-1778
- Income source sequence is usually a long number
- Seller invoice number is often a simple sequential number (1, 2, 3...)
- Invoice type is usually text like "فاتورة محلية" or "فاتورة ضريبية"

SCHEMA (VERY IMPORTANT):
- You MUST return a single JSON object that matches this schema EXACTLY.
- Use these exact English keys (even though the invoice is Arabic):

{
  "commercial_name": string or null,
  "tax_number": string or null,
  "income_source_sequence": string or null,
  "electronic_invoice_number": string or null,
  "seller_invoice_number": string or null,
  "invoice_date": string or null,           // DD-MM-YYYY
  "invoice_type": string or null,
  "currency": string or null,
  "buyer_name": string or null,
  "buyer_number": string or null,
  "phone_number": string or null,
  "city": string or null,
  "items": [
    {
      "description": string or null,
      "quantity": number or null,
      "unit_price": number or null,
      "amount": number or null,
      "discount": number or null,
      "line_subtotal": number or null,
      "tax_rate": number or string or null,
      "tax_amount": number or null,
      "line_total": number or null
    }
  ],
  "total_discount": number or null,
  "grand_total": number or null
}

CRITICAL:
- Do NOT invent fake items or totals. Read what is really on the invoice.
- Do NOT paraphrase or rewrite descriptions. Copy them character-for-character from the invoice.
- Do NOT \"correct\" numbers, even if math does not match. The printed invoice is always right.
- If a field truly does not exist on the invoice, set it to null.
- If the invoice clearly shows line items, you MUST return at least one item entry.
- If the invoice clearly shows a grand total, you MUST return grand_total as a number using the printed value.

Return ONLY this JSON object, nothing else."""


# ============================================================================
# FIELD POST-PROCESSING FUNCTIONS
# ============================================================================

def _clean_tax_number(value: Optional[str]) -> Optional[str]:
    """Clean and validate tax number."""
    if not value:
        return None
    # Remove spaces, dashes, and extract only digits
    cleaned = re.sub(r'[^\d]', '', str(value))
    return cleaned if cleaned else None


def _clean_phone_number(value: Optional[str]) -> Optional[str]:
    """Clean and validate phone number."""
    if not value:
        return None
    # Remove spaces, dashes, parentheses
    cleaned = re.sub(r'[\s\-\(\)]', '', str(value))
    # Keep only digits
    cleaned = re.sub(r'[^\d]', '', cleaned)
    return cleaned if cleaned else None


def _clean_income_source_sequence(value: Optional[str]) -> Optional[str]:
    """Clean income source sequence number."""
    if not value:
        return None
    # Extract only digits
    cleaned = re.sub(r'[^\d]', '', str(value))
    return cleaned if cleaned else None


def _clean_invoice_type(value: Optional[str]) -> Optional[str]:
    """Clean invoice type text."""
    if not value:
        return None
    # Remove extra whitespace
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def _clean_city(value: Optional[str]) -> Optional[str]:
    """Clean city name."""
    if not value:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def _post_process_extracted_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Post-process extracted data to clean and normalize fields."""
    if not isinstance(data, dict):
        return {}

    # Map common Arabic keys to our English schema if the model used Arabic keys
    arabic_to_english = {
        "الاسم التجاري": "commercial_name",
        "الرقم الضريبي": "tax_number",
        "تسلسل مصدر الدخل": "income_source_sequence",
        "رقم الفاتورة الإلكترونية": "electronic_invoice_number",
        "رقم فاتورة البائع": "seller_invoice_number",
        "تاريخ إصدار الفاتورة": "invoice_date",
        "نوع الفاتورة": "invoice_type",
        "نوع العملة": "currency",
        "اسم المشتري": "buyer_name",
        "رقم المشتري": "buyer_number",
        "رقم الهاتف": "phone_number",
        "المدينة": "city",
        "مجموع قيمة الخصم": "total_discount",
        "إجمالي قيمة الفاتورة": "grand_total",
    }

    for ar_key, en_key in arabic_to_english.items():
        if ar_key in data and en_key not in data:
            data[en_key] = data[ar_key]

    # Also handle common English variations the model might use for this field
    if "income_source_number" in data and "income_source_sequence" not in data:
        data["income_source_sequence"] = data["income_source_number"]
    if "income_source" in data and "income_source_sequence" not in data:
        data["income_source_sequence"] = data["income_source"]

    # Normalize items list if item objects use Arabic keys
    raw_items = data.get("items")
    if isinstance(raw_items, list):
        normalized_items = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            norm_item: Dict[str, Any] = {
                "description": item.get("description") or item.get("الوصف"),
                "quantity": item.get("quantity") or item.get("الكمية"),
                "unit_price": item.get("unit_price") or item.get("سعر الوحدة"),
                "amount": item.get("amount") or item.get("المبلغ"),
                "discount": item.get("discount") or item.get("الخصم"),
                "line_subtotal": item.get("line_subtotal"),
                "tax_rate": item.get("tax_rate"),
                "tax_amount": item.get("tax_amount"),
                "line_total": item.get("line_total") or item.get("الاجمالي"),
            }
            normalized_items.append(norm_item)
        data["items"] = normalized_items

    # Clean seller information
    if 'tax_number' in data and data['tax_number']:
        data['tax_number'] = _clean_tax_number(data['tax_number'])
    
    if 'income_source_sequence' in data and data['income_source_sequence']:
        data['income_source_sequence'] = _clean_income_source_sequence(data['income_source_sequence'])
    
    # Clean invoice identification
    if 'seller_invoice_number' in data and data['seller_invoice_number']:
        # Extract number if it's mixed with text
        if isinstance(data['seller_invoice_number'], str):
            numbers = re.findall(r'\d+', data['seller_invoice_number'])
            if numbers:
                data['seller_invoice_number'] = numbers[0]
    
    if 'invoice_type' in data and data['invoice_type']:
        data['invoice_type'] = _clean_invoice_type(data['invoice_type'])
    
    # Clean buyer information
    if 'phone_number' in data and data['phone_number']:
        data['phone_number'] = _clean_phone_number(data['phone_number'])
    
    if 'city' in data and data['city']:
        data['city'] = _clean_city(data['city'])
    
    return data


# ============================================================================
# MAIN EXTRACTION FUNCTIONS
# ============================================================================

def extract_invoice_data_from_image(image_bytes: bytes) -> Optional[InvoiceData]:
    """Extract invoice data from image using GPT-4o vision with OCR fallback."""
    try:
        # First try AI vision
        ai_result = _extract_with_ai_vision(image_bytes)
        # If we got any structured result back from AI, trust it and return it.
        # We previously applied extra validation here which was too strict and
        # caused real invoices to be discarded as None.
        if ai_result:
            return ai_result
        
        # If AI vision fails or gives invalid data, try OCR
        ocr_result = _extract_with_ocr(image_bytes)
        
        if ocr_result and _is_valid_extraction(ocr_result):
            return ocr_result
        
        # If both fail, return None
        return None
        
    except Exception as e:
        error_msg = str(e)
        import traceback
        traceback.print_exc()
        return None


def _extract_with_ai_vision(image_bytes: bytes) -> Optional[InvoiceData]:
    """Extract invoice data using GPT-4o vision."""
    try:
        # Encode image to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Get prompts
        system_prompt = _get_system_prompt()
        user_prompt = _get_user_prompt()
        
        # Call OpenAI API with image
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]}
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2000  # Increased for more detailed extraction
        )
        
        # Extract JSON from response
        json_content = response.choices[0].message.content

        # Optional debug: print raw JSON when DEBUG is enabled
        if os.getenv("DEBUG", "false").lower() == "true":
            try:
                print("DEBUG: Raw AI JSON response:")
                print(json_content)
            except Exception:
                pass

        data = json.loads(json_content)
        
        # Post-process extracted data
        data = _post_process_extracted_data(data)
        
        # Validate and convert using Pydantic
        invoice_data = InvoiceData(**data)
        
        # Post-process numeric fields
        invoice_data = _post_process_invoice_data(invoice_data)
        
        return invoice_data
        
    except Exception as e:
        error_msg = str(e)
        # Check for specific error types
        if "authentication" in error_msg.lower() or "api key" in error_msg.lower() or "invalid" in error_msg.lower():
            raise ValueError("Invalid or missing OpenAI API key. Please check your API key.")
        elif "rate limit" in error_msg.lower():
            raise ValueError("OpenAI API rate limit exceeded. Please try again later.")
        elif "quota" in error_msg.lower():
            raise ValueError("OpenAI API quota exceeded. Please check your account.")
        else:
            import traceback
            traceback.print_exc()
        return None


def _extract_with_ocr(image_bytes: bytes) -> Optional[InvoiceData]:
    """
    Extract invoice data using a simple approach without external OCR dependencies.

    NOTE: Previously this function returned a *hardcoded sample invoice* as a
    fallback. That caused every invoice to look identical when the AI vision
    path failed, which is very dangerous/wrong for real usage.

    For safety and correctness, this fallback is now disabled and simply
    returns None so that we never fabricate invoice data.
    """
    return None


def _is_valid_extraction(invoice_data: InvoiceData) -> bool:
    """
    Check if the extracted data looks valid (not clearly fake/placeholder).

    Previously this function was too strict and rejected extractions that were
    missing invoice number *and* buyer name, even if they had valid items/totals.
    That caused real invoices to be discarded and reported as failures.

    Now we only reject:
      - obvious fake placeholders (\"Test\", \"Sample\", etc.)
      - results that have *no* identifiers, *no* items, and *no* totals
    """
    # Check for common fake data patterns
    fake_patterns = [
        "INV123", "12345", "XYZ", "Corporation", "Company", "Test",
        "Sample", "Example", "Demo", "Placeholder"
    ]

    # Check invoice number (try both new and legacy fields)
    invoice_num = (
        invoice_data.electronic_invoice_number
        or invoice_data.seller_invoice_number
        or invoice_data.invoice_number
    )
    if invoice_num:
        invoice_num_str = str(invoice_num).lower()
        if any(pattern.lower() in invoice_num_str for pattern in fake_patterns):
            return False

    # Check buyer/customer name (try both new and legacy fields)
    buyer_name = invoice_data.buyer_name or invoice_data.customer_name
    if buyer_name:
        buyer_name_str = str(buyer_name).lower()
        if any(pattern.lower() in buyer_name_str for pattern in fake_patterns):
            return False

    # If we have items or a grand total, consider it valid even if IDs/names are missing
    has_items = bool(invoice_data.items)
    has_grand_total = invoice_data.grand_total is not None

    # Reject only if there are no identifiers AND no items AND no totals
    if not (invoice_num or buyer_name or has_items or has_grand_total):
        return False

    return True


def extract_invoice_data_from_text(text: str) -> Optional[InvoiceData]:
    """Extract invoice data from text using GPT-4o."""
    try:
        system_prompt = _get_system_prompt()
        user_prompt = f"""Extract invoice data from this text. Return JSON only per schema.

---- BEGIN TEXT ----
{text}
---- END TEXT ----

{_get_user_prompt()}

- All monetary values should be numbers without currency symbols
- Dates should be in DD-MM-YYYY format"""

        # Call OpenAI API
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2000  # Increased for more detailed extraction
        )
        
        # Extract JSON from response
        json_content = response.choices[0].message.content
        data = json.loads(json_content)
        
        # Post-process extracted data
        data = _post_process_extracted_data(data)
        
        # Validate and convert using Pydantic
        invoice_data = InvoiceData(**data)
        
        # Post-process numeric fields
        invoice_data = _post_process_invoice_data(invoice_data)
        
        return invoice_data
        
    except Exception as e:
        return None


# ============================================================================
# HELPERS: ALIGN DESCRIPTIONS WITH ORIGINAL PDF LINES (NO REORDERING)
# ============================================================================

def _find_description_from_lines_for_item(
    lines: List[str], item: InvoiceItem
) -> Optional[str]:
    """
    Given the numeric fields of an item, find the PDF text line that contains
    those numbers in order and return the description part (tokens before the
    first numeric token used).

    This guarantees the description text is taken verbatim from the PDF, with
    the same word order, not from GPT.
    """
    original_desc = (item.description or "").strip()

    # Require all key numeric fields to be present to safely match by numbers
    have_all_numbers = not any(
        v is None
        for v in (
            item.quantity,
            item.unit_price,
            item.amount,
            item.discount,
            item.line_total,
        )
    )

    if have_all_numbers:
        target_nums = [
            float(item.quantity),
            float(item.unit_price),
            float(item.amount),
            float(item.discount),
            float(item.line_total),
        ]

    def almost_equal(a: float, b: float, tol: float = 0.01) -> bool:
        return abs(a - b) <= tol

    if have_all_numbers:
        # Some invoices split the description across multiple lines, with numbers on
        # the last line. To handle this, scan sliding windows of 1–3 consecutive
        # lines and look for the numeric pattern inside the merged text.
        max_window = 3
        n_lines = len(lines)

        for start_line in range(n_lines):
            for window_size in range(1, max_window + 1):
                end_line = start_line + window_size
                if end_line > n_lines:
                    break
                window_lines = lines[start_line:end_line]
                merged = " ".join(window_lines).strip()
                if not merged:
                    continue

                tokens = merged.split()
                num_positions: List[tuple[int, float]] = []
                for idx, tok in enumerate(tokens):
                    num = extract_number(tok)
                    if num is not None:
                        num_positions.append((idx, float(num)))

                if len(num_positions) < len(target_nums):
                    continue

                # Look for a contiguous slice of numbers matching our target sequence
                for start in range(0, len(num_positions) - len(target_nums) + 1):
                    slice_positions = num_positions[start : start + len(target_nums)]
                    if all(
                        almost_equal(slice_positions[i][1], target_nums[i])
                        for i in range(len(target_nums))
                    ):
                        first_num_token_idx = slice_positions[0][0]
                        desc_tokens = tokens[:first_num_token_idx]
                        description = " ".join(desc_tokens).strip()
                        if description:
                            return description

    # Fallback: match by bag-of-words of the GPT description (ignore order),
    # and then return the exact PDF line to preserve word order.
    if original_desc:
        def tokens_no_numbers(s: str) -> List[str]:
            parts = s.split()
            return [tok for tok in parts if extract_number(tok) is None]

        target_tokens = tokens_no_numbers(original_desc)
        if target_tokens:
            target_set = set(target_tokens)
            for line in lines:
                line_tokens = tokens_no_numbers(line)
                if not line_tokens:
                    continue
                line_set = set(line_tokens)
                # Require that all GPT description tokens appear in the line,
                # but allow the line to contain extra tokens (e.g., punctuation).
                if target_set.issubset(line_set):
                    # Use the line as-is to preserve word order from PDF
                    return line.strip()
    return None


def _align_descriptions_with_pdf_lines(
    invoice_data: InvoiceData, lines: List[str]
) -> InvoiceData:
    """
    For each line item, replace the GPT-generated description with the exact
    text taken from the original PDF line that contains that row's numbers.
    """
    if not lines or not invoice_data.items:
        return invoice_data

    for item in invoice_data.items:
        desc = _find_description_from_lines_for_item(lines, item)
        if desc:
            item.description = desc
    return invoice_data


def _clean_item_description(description: Optional[str], quantity: Optional[float]) -> Optional[str]:
    """
    Post-process a line-item description to remove artifacts like:
    - The row index from the '#' column (e.g. trailing '1' / '2' stuck to the last word)
    - A duplicated quantity stuck to the beginning of the description (e.g. '43.000ساعات ...')

    We are conservative: only strip numeric prefixes/suffixes that clearly match the
    item's quantity or look like a small index, and we never touch numbers in the
    middle of the sentence (like '25 طن 26 يوم شهر 8').
    """
    if not description:
        return description

    s = description.strip()
    if not s:
        return description

    parts = s.split()

    # 1) Remove trailing small integer suffix from the last token (row index '#')
    if parts:
        last = parts[-1]
        m = re.match(r"^(.*?)(\d+)$", last)
        if m:
            core, digits = m.groups()
            try:
                idx_val = int(digits)
            except ValueError:
                idx_val = None
            # Treat 1–9 as likely row indices, not part of the description word
            if idx_val is not None and 1 <= idx_val <= 9:
                parts[-1] = core or ""
                parts = [p for p in parts if p]  # drop empty

    # 2) Remove quantity duplicated as a numeric prefix glued to the first token
    if quantity is not None and parts:
        first = parts[0]
        m2 = re.match(r"^([0-9\.,]+)(.+)$", first)
        if m2:
            num_str, rest = m2.groups()
            num_val = extract_number(num_str)
            if num_val is not None and abs(num_val - float(quantity)) <= 0.01:
                parts[0] = rest or ""
                parts = [p for p in parts if p]

    cleaned = " ".join(parts).strip()
    return cleaned or description


# ============================================================================
# PDF TEXT → STRUCTURED DATA (PRIMARY, GPT OVER TEXT + DESCRIPTION ALIGNMENT)
# ============================================================================

def extract_invoice_data_from_pdf_text_with_lines(
    text: str, lines: List[str]
) -> Optional[InvoiceData]:
    """
    High-level helper for PDFs with a text layer:
    1. Use GPT-4o over the full text (same as extract_invoice_data_from_text).
    2. Then, for each item, align the description field to the exact PDF line
       containing that row's numeric values, so word order is preserved.
    """
    base = extract_invoice_data_from_text(text)
    if not base:
        return None

    corrected = _align_descriptions_with_pdf_lines(base, lines)
    return corrected


# ============================================================================
# PDF TEXT → STRUCTURED DATA (LEGACY DETERMINISTIC PARSER - UNUSED)
# ============================================================================

def extract_invoice_data_from_pdf_text(text: str) -> Optional[InvoiceData]:
    """
    Deterministic parser for PDFs that follow the known Jordan e-invoice layout.
    This does NOT use AI at all – it relies on Arabic labels and regex.
    """
    if not text:
        return None

    # Normalize whitespace
    norm = re.sub(r"[ \t]+", " ", text)

    def search(pattern: str) -> Optional[str]:
        m = re.search(pattern, norm, flags=re.MULTILINE)
        return m.group(1).strip() if m else None

    # Seller / header fields
    commercial_name = search(r"الاسم التجاري[:：]?\s*(.+?)\s*(?:\n|الرقم الضريبي[:：])")
    tax_number_raw = search(r"الرقم الضريبي[:：]?\s*([0-9٠-٩]+)")
    income_source_raw = search(r"تسلسل مصدر الدخل[:：]?\s*([0-9٠-٩]+)")
    electronic_invoice_number = search(
        r"رقم الفاتورة الإلكترونية[:：]?\s*([A-Za-z0-9\-]+)"
    )
    seller_invoice_number = search(r"رقم فاتورة البائع[:：]?\s*([0-9٠-٩]+)")
    invoice_date = search(r"تاريخ إصدار الفاتورة[:：]?\s*([0-9٠-٩\-\/]+)")
    invoice_type = search(r"نوع الفاتورة[:：]?\s*(.+?)(?:\n|نوع العملة[:：])")

    # Currency – capture Arabic text and/or JOD
    currency = search(r"نوع العملة[:：]?\s*(.+?)(?:\n|$)")
    if not currency:
        # Try a simpler JOD match
        if "JOD" in norm:
            currency = "JOD"

    # Buyer, number on same line
    buyer_and_num = search(
        r"اسم المشتري[:：]?\s*(.+?)(?:\s+رقم المشتري[:：]\s*([0-9٠-٩]+))"
    )
    buyer_name = None
    buyer_number = None
    if buyer_and_num:
        # We captured both in one group; re-run with two groups
        m = re.search(
            r"اسم المشتري[:：]?\s*(.+?)\s+رقم المشتري[:：]?\s*([0-9٠-٩]+)", norm
        )
        if m:
            buyer_name = m.group(1).strip()
            buyer_number = m.group(2).strip()

    # Phone, city, postal code on one line
    phone_number_raw = None
    city = None
    m_contact = re.search(
        r"رقم الهاتف[:：]?\s*([0-9٠-٩]+)\s+المدينة[:：]?\s*([^\s]+)\s+الرمز البريدي[:：]?\s*([A-Za-z0-9\-]+)",
        norm,
    )
    if m_contact:
        phone_number_raw = m_contact.group(1).strip()
        city = m_contact.group(2).strip()
        # postal_code = m_contact.group(3)  # not used now

    # Totals (from footer)
    total_discount_raw = search(r"مجموع قيمة الخصم[^\d]*([0-9٠-٩\.,]+)")
    grand_total_raw = search(r"إجمالي قيمة الفاتورة[^\d]*([0-9٠-٩\.,]+)")

    total_discount = extract_number(total_discount_raw) if total_discount_raw else None
    grand_total = extract_number(grand_total_raw) if grand_total_raw else None

    # Line items: find table header and parse following lines until totals
    items: List[InvoiceItem] = []

    # Work with line list for items
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    header_idx = None
    for idx, ln in enumerate(lines):
        # Some PDFs have each header word on its own line; it's enough to find "الوصف"
        if "الوصف" in ln:
            header_idx = idx
            break

    if header_idx is not None:
        current = ""
        for ln in lines[header_idx + 1 :]:
            # Stop when reaching totals
            if "مجموع قيمة الخصم" in ln or "إجمالي قيمة الفاتورة" in ln:
                break
            if not ln.strip():
                continue

            # Accumulate lines until we have enough numeric tokens for one row
            candidate = (current + " " + ln).strip() if current else ln.strip()
            tokens = candidate.split()

            # Find numeric tokens
            numeric_positions: List[tuple[int, float]] = []
            for pos, tok in enumerate(tokens):
                num = extract_number(tok)
                if num is not None:
                    numeric_positions.append((pos, num))

            if len(numeric_positions) >= 5:
                # Assume last 5 numeric tokens are qty, unit_price, amount, discount, total
                last_five = numeric_positions[-5:]
                last_five.sort(key=lambda x: x[0])

                quantity = last_five[0][1]
                unit_price = last_five[1][1]
                amount = last_five[2][1]
                discount = last_five[3][1]
                line_total = last_five[4][1]

                first_num_pos = last_five[0][0]
                desc_tokens = tokens[:first_num_pos]
                description = " ".join(desc_tokens).strip() if desc_tokens else candidate

                items.append(
                    InvoiceItem(
                        description=description or None,
                        quantity=quantity,
                        unit_price=unit_price,
                        amount=amount,
                        discount=discount,
                        line_total=line_total,
                    )
                )
                current = ""  # reset for next row
            else:
                # Not enough numbers yet – keep accumulating
                current = candidate

    data: Dict[str, Any] = {
        "commercial_name": commercial_name,
        "tax_number": tax_number_raw,
        "income_source_sequence": income_source_raw,
        "electronic_invoice_number": electronic_invoice_number,
        "seller_invoice_number": seller_invoice_number,
        "invoice_date": invoice_date,
        "invoice_type": invoice_type,
        "currency": currency,
        "buyer_name": buyer_name,
        "buyer_number": buyer_number,
        "phone_number": phone_number_raw,
        "city": city,
        "items": [item.model_dump() for item in items],
        "total_discount": total_discount,
        "grand_total": grand_total,
    }

    # Clean & normalize
    data = _post_process_extracted_data(data)
    invoice = InvoiceData(**data)
    invoice = _post_process_invoice_data(invoice)

    if not _is_valid_extraction(invoice):
        return None

    return invoice


# ============================================================================
# PDF TEXT LINES → STRUCTURED DATA (INDEX-BASED, NO TEXT GENERATION, FALLBACK)
# ============================================================================

def _build_lines_prompt(lines: List[str]) -> str:
    """Build a prompt that shows numbered lines from the PDF text."""
    numbered_lines = "\n".join(f"{idx}: {line}" for idx, line in enumerate(lines))
    return f"""You are given the text of an invoice as numbered lines.
Each line is shown as: INDEX: TEXT

Your job is to identify which lines correspond to each field and to each line item.

IMPORTANT CONSTRAINTS:
- Do NOT generate or invent any new text.
- You MUST reference only the given lines by their indices.
- For items, group the line indices that together represent one logical row in the items table.

Here are the lines:

{numbered_lines}

Return a single JSON object with this schema:
{{
  "commercial_name_line": int or null,
  "tax_number_line": int or null,
  "income_source_sequence_line": int or null,
  "electronic_invoice_number_line": int or null,
  "seller_invoice_number_line": int or null,
  "invoice_date_line": int or null,
  "invoice_type_line": int or null,
  "currency_line": int or null,
  "buyer_name_line": int or null,
  "buyer_number_line": int or null,
  "phone_number_line": int or null,
  "city_line": int or null,
  "items": [
    {{
      "line_indices": [int, ...]  // indices of one line-item row (may be 1 or more lines)
    }}
  ]
}}

Rules for items:
- Only include real line items that have quantities/prices/amounts.
- Do NOT include totals rows (like إجمالي قيمة الفاتورة) as items.
- If a description spans multiple lines, include all relevant line indices in "line_indices".
"""


def _parse_value_from_labeled_line(line: str, label_keywords: List[str]) -> str:
    """
    Given a line like 'الاسم التجاري: سوبرماركت فلان', try to remove the label part
    and return the value. If no label matches, return the whole line.
    """
    for label in label_keywords:
        if label in line:
            # Take the part after the label
            after = line.split(label, 1)[1].strip(" :ـ-")
            if after:
                return after.strip()
    # Fallback: try after first colon
    parts = re.split(r'[:：\-]', line, maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return line.strip()


def _build_invoice_from_lines_and_selection(
    lines: List[str], selection: Dict[str, Any]
) -> InvoiceData:
    """Build an InvoiceData object from raw lines and AI-selected indices."""

    def get_line(idx_key: str) -> Optional[str]:
        idx = selection.get(idx_key)
        if isinstance(idx, int) and 0 <= idx < len(lines):
            return lines[idx]
        return None

    # Seller & header fields
    commercial_line = get_line("commercial_name_line")
    tax_line = get_line("tax_number_line")
    income_src_line = get_line("income_source_sequence_line")
    ein_line = get_line("electronic_invoice_number_line")
    seller_inv_line = get_line("seller_invoice_number_line")
    date_line = get_line("invoice_date_line")
    invoice_type_line = get_line("invoice_type_line")
    currency_line = get_line("currency_line")
    buyer_name_line = get_line("buyer_name_line")
    buyer_number_line = get_line("buyer_number_line")
    phone_line = get_line("phone_number_line")
    city_line = get_line("city_line")

    # Simple label lists for Arabic headers (used to trim labels from lines)
    commercial_name = (
        _parse_value_from_labeled_line(
            commercial_line, ["الاسم التجاري", "الاسم التجاري:"]
        )
        if commercial_line
        else None
    )
    tax_number_raw = tax_line
    income_source_raw = income_src_line

    electronic_invoice_number = (
        _parse_value_from_labeled_line(
            ein_line, ["رقم الفاتورة الإلكترونية", "رقم الفاتورة الالكترونية", "EIN"]
        )
        if ein_line
        else None
    )
    seller_invoice_number = (
        _parse_value_from_labeled_line(
            seller_inv_line, ["رقم فاتورة البائع", "رقم الفاتورة"]
        )
        if seller_inv_line
        else None
    )
    invoice_date = (
        _parse_value_from_labeled_line(
            date_line, ["تاريخ إصدار الفاتورة", "تاريخ الفاتورة"]
        )
        if date_line
        else None
    )
    invoice_type = (
        _parse_value_from_labeled_line(invoice_type_line, ["نوع الفاتورة"])
        if invoice_type_line
        else None
    )
    currency = (
        _parse_value_from_labeled_line(currency_line, ["نوع العملة"])
        if currency_line
        else None
    )
    buyer_name = (
        _parse_value_from_labeled_line(buyer_name_line, ["اسم المشتري"])
        if buyer_name_line
        else None
    )
    buyer_number = (
        _parse_value_from_labeled_line(buyer_number_line, ["رقم المشتري"])
        if buyer_number_line
        else None
    )
    phone_number_raw = (
        _parse_value_from_labeled_line(phone_line, ["رقم الهاتف"])
        if phone_line
        else None
    )
    city = (
        _parse_value_from_labeled_line(city_line, ["المدينة"])
        if city_line
        else None
    )

    # Build items from line indices
    items: List[InvoiceItem] = []
    raw_items = selection.get("items") or []
    for item_spec in raw_items:
        if not isinstance(item_spec, dict):
            continue
        line_indices = item_spec.get("line_indices") or []
        if not isinstance(line_indices, list):
            continue
        # Merge all lines for this item
        merged_line_parts: List[str] = []
        for idx in line_indices:
            if isinstance(idx, int) and 0 <= idx < len(lines):
                merged_line_parts.append(lines[idx])
        if not merged_line_parts:
            continue
        merged_line = " ".join(merged_line_parts).strip()
        if not merged_line:
            continue

        # Split into tokens and detect numeric tokens from the end
        tokens = merged_line.split()
        numeric_positions: List[tuple[int, float]] = []
        for pos, tok in enumerate(tokens):
            num = extract_number(tok)
            if num is not None:
                numeric_positions.append((pos, num))

        quantity = unit_price = amount = discount = line_total = None
        description = merged_line

        # Heuristic: last 5 numeric tokens are [qty, unit_price, amount, discount, line_total]
        if len(numeric_positions) >= 5:
            last_five = numeric_positions[-5:]
            # Ensure they are in order by position
            last_five.sort(key=lambda x: x[0])
            quantity = last_five[0][1]
            unit_price = last_five[1][1]
            amount = last_five[2][1]
            discount = last_five[3][1]
            line_total = last_five[4][1]
            # Description is everything before the first numeric token used for quantity
            first_num_pos = last_five[0][0]
            desc_tokens = tokens[:first_num_pos]
            if desc_tokens:
                description = " ".join(desc_tokens).strip()

        items.append(
            InvoiceItem(
                description=description or None,
                quantity=quantity,
                unit_price=unit_price,
                amount=amount,
                discount=discount,
                line_total=line_total,
            )
        )

    # Build base dict for InvoiceData
    data: Dict[str, Any] = {
        "commercial_name": commercial_name,
        "tax_number": tax_number_raw,
        "income_source_sequence": income_source_raw,
        "electronic_invoice_number": electronic_invoice_number,
        "seller_invoice_number": seller_invoice_number,
        "invoice_date": invoice_date,
        "invoice_type": invoice_type,
        "currency": currency,
        "buyer_name": buyer_name,
        "buyer_number": buyer_number,
        "phone_number": phone_number_raw,
        "city": city,
        "items": [item.model_dump() for item in items],
    }

    # Post-process (clean tax number, phone, etc.)
    data = _post_process_extracted_data(data)

    invoice = InvoiceData(**data)
    invoice = _post_process_invoice_data(invoice)
    return invoice


def extract_invoice_data_from_pdf_lines(lines: List[str]) -> Optional[InvoiceData]:
    """
    High-accuracy extraction for PDFs with a text layer:
    - Use PyMuPDF to get text lines.
    - Use GPT ONLY to select which line indices belong to each field / item.
    - Build all text fields directly from the original PDF lines (no text generation).
    """
    if not lines:
        return None

    try:
        system_prompt = (
            "You map invoice text lines to field indices. "
            "NEVER invent new text; only choose indices of the provided lines."
        )
        user_prompt = _build_lines_prompt(lines)

        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2000,
        )

        json_content = response.choices[0].message.content
        if os.getenv("DEBUG", "false").lower() == "true":
            try:
                print("DEBUG: Raw AI JSON (line index selection):")
                print(json_content)
            except Exception:
                pass

        selection = json.loads(json_content)
        invoice = _build_invoice_from_lines_and_selection(lines, selection)

        # Basic validity check
        if not _is_valid_extraction(invoice):
            return None

        return invoice

    except Exception:
        import traceback
        traceback.print_exc()
        return None


def _post_process_invoice_data(invoice_data: InvoiceData) -> InvoiceData:
    """Post-process invoice data to clean up and normalize values."""
    
    # Process items
    for item in invoice_data.items:
        # Clean description from duplicated indices/quantities artifacts
        item.description = _clean_item_description(item.description, item.quantity)

        # Clean up tax rate
        if item.tax_rate is not None:
            if isinstance(item.tax_rate, str):
                # Handle "exempt" case
                if "exempt" in item.tax_rate.lower() or "معفى" in item.tax_rate:
                    item.tax_rate = "exempt"
                else:
                    # Try to extract number from string like "16%"
                    cleaned_rate = extract_number(item.tax_rate)
                    if cleaned_rate is not None:
                        item.tax_rate = cleaned_rate
            elif isinstance(item.tax_rate, (int, float)):
                item.tax_rate = float(item.tax_rate)
        
        # Ensure numeric fields are floats
        if item.quantity is not None:
            item.quantity = float(item.quantity)
        if item.unit_price is not None:
            item.unit_price = float(item.unit_price)
        if item.amount is not None:
            item.amount = float(item.amount)
        if item.discount is not None:
            item.discount = float(item.discount)
        if item.line_subtotal is not None:
            item.line_subtotal = float(item.line_subtotal)
        if item.tax_amount is not None:
            item.tax_amount = float(item.tax_amount)
        if item.line_total is not None:
            item.line_total = float(item.line_total)
        
        # Calculate missing amount if we have quantity and unit_price
        if item.amount is None and item.quantity is not None and item.unit_price is not None:
            item.amount = item.quantity * item.unit_price
        
        # Calculate missing line_subtotal if we have quantity and unit_price
        if item.line_subtotal is None and item.quantity is not None and item.unit_price is not None:
            item.line_subtotal = item.quantity * item.unit_price
        
        # Calculate missing line_total if we have line_subtotal and tax_amount
        if item.line_total is None and item.line_subtotal is not None:
            if item.tax_amount is not None:
                item.line_total = item.line_subtotal - (item.discount or 0) + item.tax_amount
            else:
                item.line_total = item.line_subtotal - (item.discount or 0)
    
    # Calculate missing totals from line items if not provided
    if invoice_data.subtotal is None:
        calculated_subtotal = sum(
            item.line_subtotal for item in invoice_data.items 
            if item.line_subtotal is not None
        )
        if calculated_subtotal > 0:
            invoice_data.subtotal = calculated_subtotal
    
    if invoice_data.total_tax is None:
        calculated_tax = sum(
            item.tax_amount for item in invoice_data.items 
            if item.tax_amount is not None
        )
        if calculated_tax > 0:
            invoice_data.total_tax = calculated_tax
    
    if invoice_data.grand_total is None:
        if invoice_data.subtotal is not None and invoice_data.total_tax is not None:
            invoice_data.grand_total = invoice_data.subtotal + invoice_data.total_tax
        elif invoice_data.subtotal is not None:
            invoice_data.grand_total = invoice_data.subtotal
        elif invoice_data.total_tax is not None:
            # If we only have tax, try to calculate from line totals
            calculated_total = sum(
                item.line_total for item in invoice_data.items 
                if item.line_total is not None
            )
            if calculated_total > 0:
                invoice_data.grand_total = calculated_total
    
    # Ensure main totals are floats
    if invoice_data.subtotal is not None:
        invoice_data.subtotal = float(invoice_data.subtotal)
    if invoice_data.total_tax is not None:
        invoice_data.total_tax = float(invoice_data.total_tax)
    if invoice_data.grand_total is not None:
        invoice_data.grand_total = float(invoice_data.grand_total)
    if invoice_data.total_discount is not None:
        invoice_data.total_discount = float(invoice_data.total_discount)
    
    return invoice_data
