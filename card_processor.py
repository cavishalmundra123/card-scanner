"""PDF/Image -> individual card crops -> Gemini Vision -> structured contact data.

Cloud version: card images are uploaded to Supabase Storage instead of
being saved to a local folder.
"""

import os
import json
import io
import time
import uuid
from datetime import datetime

import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_path
from dotenv import load_dotenv
from google import genai
from google.genai import types

import cloud_db

load_dotenv()

MAX_UPLOAD_DIM = 2000
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [2, 4, 8]

SERVICE_CATEGORIES = [
    "Construction", "IT Services", "Manufacturing", "Trading",
    "Healthcare", "Education", "Finance", "Real Estate",
    "Logistics", "Hospitality", "Retail", "Consulting",
    "Legal", "Marketing", "Automotive", "Telecommunications",
    "Energy", "Agriculture", "Media", "Other"
]

EXPECTED_KEYS = [
    "full_name", "designation", "company_name", "service_category",
    "email", "phone_primary", "phone_secondary", "whatsapp", "website",
    "address_line", "area", "city", "state", "country", "postal_code",
    "social_linkedin"
]


def pdf_to_images(pdf_path, dpi=300):
    return convert_from_path(pdf_path, dpi=dpi)


def resize_for_upload(pil_image, max_dim=MAX_UPLOAD_DIM):
    w, h = pil_image.size
    longest = max(w, h)
    if longest <= max_dim:
        return pil_image
    scale = max_dim / longest
    new_size = (int(w * scale), int(h * scale))
    return pil_image.resize(new_size, Image.LANCZOS)


def pil_to_jpeg_bytes(pil_image, quality=90):
    img = pil_image.convert("RGB") if pil_image.mode != "RGB" else pil_image
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def pil_to_png_bytes(pil_image):
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return buf.getvalue()


def detect_cards_in_image(pil_image, min_area_ratio=0.03, max_area_ratio=0.6):
    img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    h, w = img.shape[:2]
    page_area = h * w

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 240, 255, cv2.THRESH_BINARY_INV)

    kernel = np.ones((15, 15), np.uint8)
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    cards = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        area = cw * ch
        if ch == 0:
            continue
        aspect = cw / ch

        if not (page_area * min_area_ratio < area < page_area * max_area_ratio):
            continue
        if not (1.3 < aspect < 2.1 or 0.47 < aspect < 0.77):
            continue

        pad = 10
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + cw + pad), min(h, y + ch + pad)
        crop = img[y0:y1, x0:x1]
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        cards.append((Image.fromarray(crop_rgb), (x0, y0, x1, y1)))

    cards.sort(key=lambda c: (c[1][1] // 50, c[1][0]))
    return [c[0] for c in cards]


def split_page_into_grid(pil_image, n_cards):
    w, h = pil_image.size
    crops = []

    if n_cards <= 1:
        return [pil_image]
    elif n_cards == 2:
        crops.append(pil_image.crop((0, 0, w, h // 2)))
        crops.append(pil_image.crop((0, h // 2, w, h)))
    elif n_cards in (3, 4):
        for row in range(2):
            for col in range(2):
                if len(crops) >= n_cards:
                    break
                x0 = col * (w // 2)
                y0 = row * (h // 2)
                x1 = (col + 1) * (w // 2) if col == 0 else w
                y1 = (row + 1) * (h // 2) if row == 0 else h
                crops.append(pil_image.crop((x0, y0, x1, y1)))
    else:
        rows = n_cards
        for i in range(rows):
            y0 = i * (h // rows)
            y1 = (i + 1) * (h // rows) if i < rows - 1 else h
            crops.append(pil_image.crop((0, y0, w, y1)))

    return crops


def save_card_image_to_cloud(user_email, pil_image):
    """Upload card image to Supabase Storage. Returns storage path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    filename = f"card_{timestamp}_{unique_id}.png"
    image_bytes = pil_to_png_bytes(pil_image)
    return cloud_db.upload_card_image(user_email, image_bytes, filename)


MULTI_CARD_PROMPT = f"""You are looking at a scanned page that may contain MULTIPLE business cards (typically 1 to 6 cards arranged on the page).

Identify EVERY distinct business card visible on the page and extract its contact information.

Return ONLY valid JSON (no markdown, no code fences, no commentary). The JSON must be an ARRAY of objects, one object per card, in reading order (top-to-bottom, left-to-right).

Each object must have exactly these keys:
{{
  "full_name": string or null,
  "designation": string or null,
  "company_name": string or null,
  "service_category": string,
  "email": string or null,
  "phone_primary": string or null,
  "phone_secondary": string or null,
  "whatsapp": string or null,
  "website": string or null,
  "address_line": string or null,
  "area": string or null,
  "city": string or null,
  "state": string or null,
  "country": string or null,
  "postal_code": string or null,
  "social_linkedin": string or null
}}

CRITICAL RULES:
- If you see 4 cards, return an array with 4 objects. If you see 1 card, return an array with 1 object.
- Do NOT merge information from different cards. Each person/company gets its own object.
- Use null when a field is not present on that specific card.
- "service_category" MUST be one of: {SERVICE_CATEGORIES}. Infer from company name, designation, or tagline. Use "Other" only if truly unclear.
- Mobile numbers go in phone_primary; landlines/office in phone_secondary. Format with country code if visible (e.g., "+91 98765 43210").
- Normalize country to its full English name ("United Arab Emirates" not "UAE", "India" not "IN", "Oman" for Sultanate of Oman).
- "area" = locality/neighborhood (e.g., "Bandra West", "Karama", "Ruwi") -- separate from city.
- Trim whitespace. Do not invent data not visible on the card.

Return ONLY the JSON array. Start your response with [ and end with ].
"""

SINGLE_CARD_PROMPT = f"""Analyze this business card image and extract contact information.

Return ONLY valid JSON (no markdown, no code fences) with these exact keys:
{{
  "full_name": string or null,
  "designation": string or null,
  "company_name": string or null,
  "service_category": string,
  "email": string or null,
  "phone_primary": string or null,
  "phone_secondary": string or null,
  "whatsapp": string or null,
  "website": string or null,
  "address_line": string or null,
  "area": string or null,
  "city": string or null,
  "state": string or null,
  "country": string or null,
  "postal_code": string or null,
  "social_linkedin": string or null
}}

RULES:
- Use null when a field is not present on the card.
- "service_category" MUST be one of: {SERVICE_CATEGORIES}. Use "Other" if truly unclear.
- Mobile numbers go in phone_primary; landlines in phone_secondary.
- Format phone numbers with country code if visible.
- Normalize country to its full English name.
- "area" = locality/neighborhood, separate from city.
- Trim whitespace. Do not invent data.
"""


def _strip_code_fence(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _normalize_record(record):
    for k in EXPECTED_KEYS:
        record.setdefault(k, None)
    cat = record.get("service_category")
    if not cat or cat not in SERVICE_CATEGORIES:
        record["service_category"] = "Other"
    return record


def _gemini_generate_with_retry(client, image_bytes, prompt,
                                mime_type="image/jpeg"):
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt
                ],
            )
            return response.text
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            transient = any(s in err_str for s in [
                "disconnect", "timeout", "503", "502", "504",
                "unavailable", "deadline", "reset", "connection"
            ])
            if attempt < MAX_RETRIES - 1 and transient:
                wait = RETRY_BACKOFF_SECONDS[attempt]
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"Gemini retry exhausted: {last_error}")


def extract_all_cards_from_page(pil_image):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")

    client = genai.Client(api_key=api_key)
    resized = resize_for_upload(pil_image)
    image_bytes = pil_to_jpeg_bytes(resized, quality=92)

    text = _gemini_generate_with_retry(client, image_bytes, MULTI_CARD_PROMPT)
    text = _strip_code_fence(text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON parse failed: {e}; raw: {text[:300]}")

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise RuntimeError(f"Response is not a list. Raw: {text[:300]}")

    return [_normalize_record(r) for r in data if isinstance(r, dict)]


def extract_single_card(pil_image):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")

    client = genai.Client(api_key=api_key)
    resized = resize_for_upload(pil_image, max_dim=1500)
    image_bytes = pil_to_jpeg_bytes(resized, quality=92)

    text = _gemini_generate_with_retry(client, image_bytes, SINGLE_CARD_PROMPT)
    text = _strip_code_fence(text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return _normalize_record({"_parse_error": "Could not parse JSON"})

    if not isinstance(data, dict):
        return _normalize_record({"_parse_error": "Response not a dict"})

    return _normalize_record(data)


def process_file(file_path, user_email):
    """Process a PDF or image file end-to-end.
    Returns: [{"image_path": <storage_path>, "data": {...}, "page": int}, ...]
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        pages = pdf_to_images(file_path)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        pages = [Image.open(file_path).convert("RGB")]
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    results = []

    for page_num, page_img in enumerate(pages, start=1):
        records = None
        primary_error = None

        try:
            records = extract_all_cards_from_page(page_img)
        except Exception as e:
            primary_error = str(e)
            records = None

        if records is None:
            cropped = detect_cards_in_image(page_img)
            if not cropped:
                cropped = [page_img]

            records = []
            crop_images_for_save = []
            for card_img in cropped:
                try:
                    rec = extract_single_card(card_img)
                except Exception as e:
                    rec = _normalize_record({
                        "_extraction_error": f"Whole-page failed: {primary_error}; "
                                             f"per-card also failed: {e}"
                    })
                records.append(rec)
                crop_images_for_save.append(card_img)

            for i, rec in enumerate(records):
                storage_path = save_card_image_to_cloud(
                    user_email, crop_images_for_save[i]
                )
                results.append({
                    "image_path": storage_path,
                    "data": rec,
                    "page": page_num
                })
            continue

        n = len(records)
        cropped = detect_cards_in_image(page_img)

        if len(cropped) == n and n > 0:
            card_images = cropped
        elif n > 0:
            card_images = split_page_into_grid(page_img, n)
        else:
            card_images = [page_img]
            records = [_normalize_record(
                {"_extraction_error": "No cards detected"}
            )]

        for i, record in enumerate(records):
            img = card_images[i] if i < len(card_images) else page_img
            storage_path = save_card_image_to_cloud(user_email, img)
            results.append({
                "image_path": storage_path,
                "data": record,
                "page": page_num
            })

    return results


if __name__ == "__main__":
    print("Cloud card processor module loaded.")
    print(f"Service categories: {len(SERVICE_CATEGORIES)}")
    print(f"Storage bucket: {cloud_db.BUCKET_NAME}")