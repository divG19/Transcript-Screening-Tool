"""Improved OCR with image preprocessing and PDF highlighting"""

import sys
import json
import fitz
from PIL import Image
import pytesseract
import io
import cv2
import numpy as np
import re
import os

# Resolve paths relative to the exe when frozen, or the script otherwise
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(SCRIPT_DIR, 'session_config.json')
PROCESSED_DIR = os.path.join(SCRIPT_DIR, 'processed_transcripts')

DEFAULT_KEYWORDS = ['linear algebra', 'maths', 'mathematics', 'calculus', 'calc']


def preprocess_image(image):
    """Preprocess image for better OCR"""
    img_array = np.array(image)
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    denoised = cv2.fastNlMeansDenoising(thresh)
    return Image.fromarray(denoised)


def highlight_using_ocr_boxes(page, keyword, ocr_data, img_w, img_h):
    """Highlight keyword on an image-only PDF page using OCR bounding boxes.
    Converts Tesseract pixel coordinates to PDF point coordinates."""
    highlights_added = 0
    kw_words = keyword.lower().split()
    n = len(kw_words)

    words = ocr_data['text']
    lefts = ocr_data['left']
    tops = ocr_data['top']
    widths = ocr_data['width']
    heights = ocr_data['height']

    scale_x = page.rect.width / img_w
    scale_y = page.rect.height / img_h

    clean_words = [re.sub('[^a-zA-Z0-9]', '', w).lower() for w in words]

    for i in range(len(clean_words) - n + 1):
        if not clean_words[i]:
            continue
        window = clean_words[i:i + n]
        if window == kw_words:
            x0 = min(lefts[i:i + n])
            y0 = min(tops[i:i + n])
            x1 = max(lefts[j] + widths[j] for j in range(i, i + n))
            y1 = max(tops[j] + heights[j] for j in range(i, i + n))
            rect = fitz.Rect(x0 * scale_x, y0 * scale_y, x1 * scale_x, y1 * scale_y)
            highlight = page.add_highlight_annot(rect)
            highlight.set_colors(stroke=[1, 1, 0])
            highlight.update()
            highlights_added += 1

    return highlights_added


def highlight_text_on_page(page, text_to_find):
    """Search and highlight text using the native PDF text layer."""
    highlights_added = 0
    for inst in page.search_for(text_to_find):
        highlight = page.add_highlight_annot(inst)
        highlight.set_colors(stroke=[1, 1, 0])
        highlight.update()
        highlights_added += 1
    return highlights_added


def process_pdf(pdf_path, keywords_to_search):
    """OCR a PDF, search for keywords, save highlighted PDF and extracted text."""
    pdf_name = os.path.basename(pdf_path)
    base_name = os.path.splitext(pdf_name)[0]

    doc = fitz.open(pdf_path)
    all_text = []
    page_texts = []
    page_has_text_layer = {}
    ocr_data_per_page = {}
    img_size_per_page = {}

    print(f"  Processing {len(doc)} page(s)...")

    for page_num in range(len(doc)):
        page = doc[page_num]
        print(f"    Page {page_num + 1}...", end=' ')

        has_layer = len(page.get_text().strip()) > 0
        page_has_text_layer[page_num] = has_layer

        pix = page.get_pixmap(dpi=400)
        image = Image.open(io.BytesIO(pix.tobytes('png')))
        processed = preprocess_image(image)

        custom_config = '--oem 1 --psm 3'
        text = pytesseract.image_to_string(processed, config=custom_config)
        all_text.append(text)
        page_texts.append((page_num, text))

        if not has_layer:
            ocr_data_per_page[page_num] = pytesseract.image_to_data(
                processed, config=custom_config, output_type=pytesseract.Output.DICT)
            img_size_per_page[page_num] = (processed.width, processed.height)

        print('Done')

    doc.close()

    # Search for keywords in the OCR text
    results = {}
    keyword_pages = {}

    for keyword in keywords_to_search:
        keyword_pages[keyword] = []
        for page_num, page_text in page_texts:
            if keyword.lower() in page_text.lower():
                lines = page_text.split('\n')
                for i, line in enumerate(lines):
                    if keyword.lower() in line.lower():
                        if keyword not in results:
                            results[keyword] = []
                        results[keyword].append((page_num + 1, i + 1, line.strip()))
                        if page_num not in keyword_pages[keyword]:
                            keyword_pages[keyword].append(page_num)

    # Highlight matches in a fresh copy of the document
    doc_highlight = fitz.open(pdf_path)
    total_highlights = 0

    for keyword in keywords_to_search:
        if keyword in keyword_pages and keyword_pages[keyword]:
            for page_num in keyword_pages[keyword]:
                page = doc_highlight[page_num]

                if page_has_text_layer[page_num]:
                    highlights = highlight_text_on_page(page, keyword)
                    highlights += highlight_text_on_page(page, keyword.upper())
                    highlights += highlight_text_on_page(page, keyword.capitalize())
                    highlights += highlight_text_on_page(page, keyword.title())
                elif page_num in ocr_data_per_page:
                    img_w, img_h = img_size_per_page[page_num]
                    highlights = highlight_using_ocr_boxes(
                        page, keyword, ocr_data_per_page[page_num], img_w, img_h)
                else:
                    highlights = 0

                total_highlights += highlights

    output_filename = os.path.join(PROCESSED_DIR, f"{base_name}_highlighted.pdf")
    if total_highlights > 0:
        doc_highlight.save(output_filename)
    doc_highlight.close()

    # Report results
    print(f"\n  {'=' * 56}")
    if results:
        print(f"  FOUND {len(results)} KEYWORD(S) in {pdf_name}:\n")
        for keyword in keywords_to_search:
            if keyword in results:
                matches = results[keyword]
                pages = sorted(set([m[0] for m in matches]))
                label = '(default)' if keyword in DEFAULT_KEYWORDS else '(user)'
                print(f"  '{keyword}' {label} - {len(matches)} occurrence(s) on page(s): {', '.join(map(str, pages))}")
                for page_num, _, line in matches[:3]:
                    print(f"      Page {page_num}: {line[:80]}...")
                if len(matches) > 3:
                    print(f"      ... and {len(matches) - 3} more matches")
                print()
        if total_highlights > 0:
            print(f"  Highlighted PDF : {output_filename}")
            print(f"  Highlights added: {total_highlights}")
        else:
            print('  WARNING: Keywords found in OCR text but could not be highlighted.')
    else:
        print(f"  NOT FOUND: No keywords found in {pdf_name}")
    print(f"  {'=' * 56}\n")


def load_config():
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return None


def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def setup_config():
    """Interactive setup: ask for folder path only, save config."""
    print('\n=== Setup ===')

    while True:
        try:
            folder = input('Enter path to transcripts folder: ').strip().strip('"')
        except EOFError:
            sys.exit(0)
        if not folder:
            print('Folder path is required.')
            continue
        if not os.path.isdir(folder):
            print(f'Folder not found: {folder}')
            continue
        break

    config = {
        'folder_path': folder,
        'default_keywords': DEFAULT_KEYWORDS.copy(),
    }
    save_config(config)
    return config


def ask_session_keywords(default_keywords):
    """Ask for additional keywords every session. Never saved to config."""
    print(f"\nDefault keywords: {', '.join(default_keywords)}")
    try:
        kw_input = input('Enter additional keywords for this session (comma-separated, or press Enter to skip): ').strip()
    except EOFError:
        kw_input = ''
    return [k.strip() for k in kw_input.split(',') if k.strip()] if kw_input else []


os.makedirs(PROCESSED_DIR, exist_ok=True)

config = load_config()
if config is None:
    config = setup_config()
else:
    print('Loaded config:')
    print(f"  Folder  : {config['folder_path']}")
    try:
        change = input('\nChange settings? (y/n, default n): ').strip().lower()
    except EOFError:
        change = 'n'
    if change == 'y':
        config = setup_config()

folder_path = config['folder_path']
session_keywords = ask_session_keywords(config['default_keywords'])
keywords_to_search = config['default_keywords'] + session_keywords

# Track PDFs already processed this session so rescans only pick up new files
processed_this_session = set()


def show_preview():
    """Print config summary and the list of PDFs pending processing."""
    pending = sorted([f for f in os.listdir(folder_path)
                      if f.lower().endswith('.pdf') and f not in processed_this_session])
    print(f'\nWatching : {folder_path}')
    print(f"Keywords : {', '.join(keywords_to_search)}")
    print(f'Output   : {PROCESSED_DIR}')
    if pending:
        print(f'\nPDFs queued for processing ({len(pending)}):')
        for name in pending:
            print(f'  - {name}')
    else:
        print('\nNo new PDFs found in folder.')
    print("\nDrop a new PDF into the folder and press 'r' to rescan,")
    print("press Enter to start processing, or 'q' to quit.")
    return pending


show_preview()

while True:
    try:
        user_input = input('\n> ').strip().lower()
    except EOFError:
        break

    if user_input == 'q':
        print('Exiting.')
        break

    if user_input == 'r':
        show_preview()
    else:
        pending = sorted([f for f in os.listdir(folder_path)
                          if f.lower().endswith('.pdf') and f not in processed_this_session])

        if not pending:
            print('No new PDF files to process.')
            show_preview()
            continue

        for pdf_name in pending:
            print(f'\n--- {pdf_name} ---')
            process_pdf(os.path.join(folder_path, pdf_name), keywords_to_search)
            processed_this_session.add(pdf_name)

        show_preview()
