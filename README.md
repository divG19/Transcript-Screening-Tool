# Transcript Screening Tool

OCR-powered CLI that screens batches of academic transcript PDFs for required
coursework (e.g. linear algebra, calculus) and produces highlighted copies for
reviewers. Built for a university admissions workflow where staff manually
scanned hundreds of applicant transcripts per cycle.

## What it does

1. Watches a folder of transcript PDFs and processes new files on demand.
2. Renders each page at 400 DPI and runs it through an OpenCV preprocessing
   pipeline (grayscale → Otsu binarization → non-local means denoising) to
   maximize Tesseract OCR accuracy on scanned documents.
3. Searches the OCR text for a configurable keyword list (defaults +
   per-session additions) and reports every match with page and line context.
4. Highlights matches directly in the PDF:
   - **Native text layer** pages use PyMuPDF text search (exact rectangles).
   - **Scanned image-only** pages fall back to Tesseract word bounding boxes,
     converting pixel coordinates to PDF points — including multi-word
     phrases matched across consecutive OCR tokens.
5. Saves highlighted copies to `processed_transcripts/` so reviewers can jump
   straight to the evidence instead of reading page by page.

## Setup

1. Install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) and
   make sure `tesseract` is on your PATH.
2. Install Python dependencies:

   ```
   pip install -r requirements.txt
   ```

## Usage

```
python improved_search.py
```

On first run you'll be asked for the folder containing transcript PDFs; the
choice is saved to `session_config.json`. Each session you can add extra
keywords on top of the defaults. Then:

- **Enter** — process all pending PDFs in the folder
- **r** — rescan the folder for newly dropped files
- **q** — quit

## Privacy

This repository contains **no transcripts or student data** — only code.
Input PDFs, highlighted outputs, and local config are all excluded via
`.gitignore`. If you use this on real transcripts, keep the data folder
outside the repo.

## Packaging (optional)

The tool can be distributed to non-technical staff as a standalone Windows
executable with PyInstaller (bundle a portable Tesseract next to the exe and
point `PATH`/`TESSDATA_PREFIX` to it via a `run.bat`).
