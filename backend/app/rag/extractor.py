import logging
import os
import tkinter as tk
from tkinter import filedialog

import pymupdf
from docx import Document
import pandas as pd

logger = logging.getLogger(__name__)

BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))

OUTPUT_FOLDER = os.path.join(
    BASE_FOLDER,
    "extracted_text"
)

# File selector
def select_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Select Document",
        filetypes=[
            ("Supported Files", "*.pdf *.docx *.txt *.csv *.jpg *.jpeg *.png"),
            ("PDF Files", "*.pdf"),
            ("DOCX Files", "*.docx"),
            ("TXT Files", "*.txt"),
            ("CSV Files", "*.csv"),
            ("Image Files", "*.jpg *.jpeg *.png")
        ]
    )

    root.destroy()

    return file_path

# PDF extraction
def extract_pdf(file_path, page_progress_callback=None):
    """
    Hybrid PDF extraction.

    Strategy:
      1. Extract native text from each PDF page using PyMuPDF.
      2. If a page has sufficient native text, use it directly.
      3. If a page is empty or contains very little text, render that
         page and run PaddleOCR on it.
      4. This allows normal PDFs to bypass OCR while scanned/
         handwritten pages still use OCR.
    """

    from app.services.ocr_service import ocr_service

    pdf = pymupdf.open(file_path)
    total_pages = len(pdf)

    text_parts = []
    page_metadata = []

    # Minimum amount of native text that we consider sufficient.
    # Pages below this threshold are considered likely scanned/image
    # pages and are sent through OCR.
    MIN_NATIVE_TEXT_CHARS = 40

    logger.info(
        "[PDF] Hybrid extraction started for '%s' (%d pages)",
        os.path.basename(file_path),
        total_pages
    )

    try:
        for page_index in range(total_pages):
            page_number = page_index + 1
            page = pdf[page_index]

            # First attempt: native PDF text extraction
            native_text = page.get_text("text") or ""
            native_text = native_text.strip()

            if len(native_text) >= MIN_NATIVE_TEXT_CHARS:
                logger.info(
                    "[PDF] Page %d/%d: native text found "
                    "(%d chars) - OCR skipped",
                    page_number,
                    total_pages,
                    len(native_text)
                )

                text_parts.append(
                    f"\n--- Page {page_number} ---\n"
                    f"{native_text}"
                )

                page_metadata.append(
                    {
                        "page_number": page_number,
                        "confidence": 1.0,
                        "source_type": "pdf_text",
                        "extraction_method": "pymupdf"
                    }
                )
            else:
                # Fallback: OCR only this page
                logger.info(
                    "[OCR] Page %d/%d has insufficient native text "
                    "(%d chars) - running PaddleOCR",
                    page_number,
                    total_pages,
                    len(native_text)
                )

                # Render page as image.
                pixmap = page.get_pixmap(
                    dpi=150,
                    alpha=False
                )

                image_bytes = pixmap.tobytes("png")

                try:
                    ocr_result = ocr_service.run_ocr_on_image(
                        image_bytes
                    )

                    ocr_text = (
                        ocr_result.get("text", "")
                        if isinstance(ocr_result, dict)
                        else ""
                    )

                    ocr_text = ocr_text.strip()

                    confidence = (
                        ocr_result.get("confidence", 0.0)
                        if isinstance(ocr_result, dict)
                        else 0.0
                    )

                    if ocr_text:
                        logger.info(
                            "[OCR] Page %d/%d extracted %d chars "
                            "(confidence %.2f)",
                            page_number,
                            total_pages,
                            len(ocr_text),
                            confidence
                        )

                        text_parts.append(
                            f"\n--- Page {page_number} (OCR) ---\n"
                            f"{ocr_text}"
                        )

                        page_metadata.append(
                            {
                                "page_number": page_number,
                                "confidence": confidence,
                                "source_type": "pdf_ocr_page",
                                "extraction_method": "ppocr"
                            }
                        )
                    elif native_text:
                        # If OCR returned nothing but native PDF
                        # text existed, keep the native text.
                        text_parts.append(
                            f"\n--- Page {page_number} ---\n"
                            f"{native_text}"
                        )

                        page_metadata.append(
                            {
                                "page_number": page_number,
                                "confidence": 1.0,
                                "source_type": "pdf_text",
                                "extraction_method": "pymupdf"
                            }
                        )
                    else:
                        logger.warning(
                            "[PDF] Page %d/%d contains no readable "
                            "native text or OCR text",
                            page_number,
                            total_pages
                        )

                except Exception as ocr_error:
                    logger.exception(
                        "[OCR] Failed on PDF page %d: %s",
                        page_number,
                        ocr_error
                    )

                    # Don't lose native text if it existed.
                    if native_text:
                        text_parts.append(
                            f"\n--- Page {page_number} ---\n"
                            f"{native_text}"
                        )

                        page_metadata.append(
                            {
                                "page_number": page_number,
                                "confidence": 1.0,
                                "source_type": "pdf_text",
                                "extraction_method": "pymupdf"
                            }
                        )

            # Progress callback
            if page_progress_callback:
                try:
                    page_progress_callback(
                        page_number,
                        total_pages
                    )
                except Exception as callback_error:
                    logger.warning(
                        "[PDF] Progress callback failed: %s",
                        callback_error
                    )

    finally:
        pdf.close()

    combined_text = "\n".join(text_parts)

    # Create image/content records for OCR-derived pages.
    images_metadata = []

    for metadata in page_metadata:
        if metadata.get("source_type") == "pdf_ocr_page":
            page_number = metadata["page_number"]

            # Find OCR text belonging to this page.
            page_marker = (
                f"--- Page {page_number} (OCR) ---"
            )

            page_text = ""

            for block in text_parts:
                if block.startswith(page_marker):
                    page_text = block.replace(
                        page_marker,
                        "",
                        1
                    ).strip()
                    break

            if page_text:
                images_metadata.append(
                    {
                        "content": (
                            "[OCR Page Content "
                            f"(Confidence: "
                            f"{metadata.get('confidence', 0.0):.2f})]\n"
                            f"{page_text}"
                        ),
                        "metadata": {
                            "page_number": page_number,
                            "confidence": metadata.get(
                                "confidence",
                                0.0
                            ),
                            "source_type": "pdf_ocr_page",
                            "extraction_method": "ppocr"
                        }
                    }
                )

    return {
        "text": combined_text,
        "images": images_metadata
    }

# DOCX extraction
def extract_docx(file_path):
    from app.services.ocr_service import ocr_service
    from app.utils.image_filter import is_valid_document_image

    document = Document(file_path)
    text = ""
    images_metadata = []

    for paragraph in document.paragraphs:
        paragraph_text = paragraph.text.strip()

        if paragraph_text:
            text += paragraph_text + "\n"

    image_count = 0
    MAX_IMAGES = 20
    page_hashes_map = {}

    # Extract images from docx parts
    for rel in document.part.rels.values():
        if "image" not in rel.target_ref:
            continue

        if image_count >= MAX_IMAGES:
            break

        try:
            image_data = rel.target_part.blob

            # Filter out tiny/repeated logo images
            valid, reason = is_valid_document_image(
                image_data,
                page_number=1,
                page_hashes_map=page_hashes_map
            )

            if not valid:
                logger.info(
                    "[DOCX] Skipping image %d: %s",
                    image_count,
                    reason
                )
                image_count += 1
                continue

            # Run PP-OCRv5 Mobile on embedded DOCX image
            ocr_result = ocr_service.run_ocr_on_image(
                image_data
            )

            ocr_text = (
                ocr_result.get("text", "")
                if isinstance(ocr_result, dict)
                else ""
            )

            ocr_text = ocr_text.strip()

            if ocr_text:
                images_metadata.append(
                    {
                        "content": (
                            f"[Image OCR Text: {ocr_text}]"
                        ),
                        "metadata": {
                            "image_index": image_count,
                            "source_type": "docx_image",
                            "extraction_method": "ppocr"
                        }
                    }
                )

            image_count += 1

        except Exception as error:
            print(
                f"Failed to process image in DOCX: {error}"
            )
            image_count += 1

    return {
        "text": text,
        "images": images_metadata
    }

# TXT extraction
def extract_txt(file_path):
    encodings = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin1"
    ]

    for encoding in encodings:
        try:
            with open(
                file_path,
                "r",
                encoding=encoding
            ) as file:
                return file.read()

        except UnicodeDecodeError:
            continue

    raise ValueError(
        "Unable to read the TXT file."
    )

# CSV extraction
def extract_csv(file_path):
    encodings = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin1"
    ]

    dataframe = None
    last_error = None

    for encoding in encodings:
        try:
            dataframe = pd.read_csv(
                file_path,
                sep=None,
                engine="python",
                encoding=encoding,
                on_bad_lines="skip",
                comment="#"
            )
            break

        except Exception as error:
            last_error = error

    if dataframe is None:
        raise ValueError(
            f"Unable to read CSV file: {last_error}"
        )

    if dataframe.empty:
        return ""

    text = ""

    columns = list(dataframe.columns)

    text += "--- CSV Columns ---\n"
    text += ", ".join(
        str(column)
        for column in columns
    )
    text += "\n"

    for index, row in dataframe.iterrows():
        text += (
            f"\n--- Row {index + 1} ---\n"
        )

        for column in columns:
            value = row[column]

            if pd.isna(value):
                value = ""

            text += (
                f"{column}: "
                f"{str(value).strip()}\n"
            )

    return text

# Image extraction
def extract_image(file_path):
    from app.services.ocr_service import ocr_service

    with open(
        file_path,
        "rb"
    ) as file:
        image_data = file.read()

    try:
        ocr_result = ocr_service.run_ocr_on_image(
            image_data
        )

        ocr_text = (
            ocr_result.get("text", "")
            if isinstance(ocr_result, dict)
            else ""
        )

        confidence = (
            ocr_result.get(
                "confidence",
                0.0
            )
            if isinstance(ocr_result, dict)
            else 0.0
        )

        ocr_text = ocr_text.strip()

        if not ocr_text:
            raise ValueError(
                "No readable text detected in image."
            )

        logger.info(
            "[OCR] Extracted %d characters from '%s' "
            "(confidence %.2f)",
            len(ocr_text),
            os.path.basename(file_path),
            confidence
        )

        return {
            "text": (
                "[OCR Extracted Text "
                f"(Confidence: {confidence:.2f})]\n"
                f"{ocr_text}"
            ),
            "images": []
        }

    except Exception as error:
        raise ValueError(
            f"Failed to process image with OCR: {error}"
        )

# Text cleanup
def clean_text(text):
    if not text:
        return ""

    cleaned_lines = []

    for line in text.splitlines():
        line = line.strip()

        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)

# Main extractor
def extract_document(
    file_path,
    page_progress_callback=None
):
    """
    Main extraction dispatcher.

    PDF:
        Native text first → OCR fallback

    DOCX:
        Native text + OCR embedded images

    TXT:
        Native extraction

    CSV:
        Tabular extraction

    JPG/JPEG/PNG:
        PaddleOCR
    """

    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            "File not found."
        )

    extension = os.path.splitext(
        file_path
    )[1].lower()

    logger.info(
        "[EXTRACTOR] File: %s",
        os.path.basename(file_path)
    )

    logger.info(
        "[EXTRACTOR] Type: %s",
        extension
    )

    images = []

    if extension == ".pdf":
        result = extract_pdf(
            file_path,
            page_progress_callback=page_progress_callback
        )

        text = result["text"]
        images = result["images"]

    elif extension == ".docx":
        result = extract_docx(file_path)

        text = result["text"]
        images.extend(result["images"])

        if page_progress_callback:
            try:
                page_progress_callback(1, 1)
            except Exception:
                pass

    elif extension == ".txt":
        text = extract_txt(file_path)

        if page_progress_callback:
            try:
                page_progress_callback(1, 1)
            except Exception:
                pass

    elif extension == ".csv":
        text = extract_csv(file_path)

        if page_progress_callback:
            try:
                page_progress_callback(1, 1)
            except Exception:
                pass

    elif extension in (
        ".jpg",
        ".jpeg",
        ".png"
    ):
        result = extract_image(file_path)

        text = result["text"]
        images.extend(result["images"])

        if page_progress_callback:
            try:
                page_progress_callback(1, 1)
            except Exception:
                pass

    else:
        raise ValueError(
            "Unsupported file type. "
            "Use PDF, DOCX, TXT, CSV, JPG, JPEG or PNG."
        )

    return {
        "text": clean_text(text),
        "images": images
    }

# Optional standalone text saving
def save_extracted_text(
    text,
    original_file
):
    os.makedirs(
        OUTPUT_FOLDER,
        exist_ok=True
    )

    file_name = os.path.splitext(
        os.path.basename(original_file)
    )[0]

    output_file = os.path.join(
        OUTPUT_FOLDER,
        file_name + "_extracted.txt"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(text)

    return output_file

# Standalone testing
def main():
    print("=" * 70)
    print(
        "        AI KNOWLEDGE BASE EXTRACTOR"
    )
    print("=" * 70)

    print("\nSupported formats:")
    print(
        "PDF | DOCX | TXT | CSV | JPG | JPEG | PNG"
    )

    print("\nSelect a file...")

    file_path = select_file()

    if not file_path:
        print("\nNo file selected.")
        return

    print("\nSelected file:")
    print(
        os.path.basename(file_path)
    )

    print("\n" + "=" * 70)
    print("EXTRACTING TEXT")
    print("=" * 70)

    try:
        result = extract_document(
            file_path
        )

        extracted_text = result.get(
            "text",
            ""
        )

        if not extracted_text:
            print(
                "\nNo text could be extracted."
            )
            return

        print(
            "\nExtraction successful!"
        )

        print(
            "Characters extracted:",
            len(extracted_text)
        )

        print("\nExtracted text:")
        print("-" * 70)

        print(
            extracted_text[:5000]
        )

        print("-" * 70)

        output_file = save_extracted_text(
            extracted_text,
            file_path
        )

        print(
            "\nExtracted text saved to:"
        )

        print(
            os.path.abspath(
                output_file
            )
        )

        print(
            "\nExtraction completed successfully."
        )

    except Exception as error:
        print("\nERROR:")
        print(error)


if __name__ == "__main__":
    main()