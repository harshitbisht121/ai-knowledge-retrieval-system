import logging
import os
import tkinter as tk
from tkinter import filedialog

from pypdf import PdfReader
from docx import Document
import pandas as pd

# Keep logger for non-VLM use; VLM messages use print() to match codebase convention
logger = logging.getLogger(__name__)

BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))

OUTPUT_FOLDER = os.path.join(
    BASE_FOLDER,
    "extracted_text"
)

IMAGE_OUTPUT_FOLDER = os.path.join(
    BASE_FOLDER,
    "extracted_images"
)


def select_file():

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Select Document",
        filetypes=[
            ("Supported Files", "*.pdf *.docx *.txt *.csv"),
            ("PDF Files", "*.pdf"),
            ("DOCX Files", "*.docx"),
            ("TXT Files", "*.txt"),
            ("CSV Files", "*.csv")
        ]
    )

    root.destroy()

    return file_path


def extract_pdf(file_path):
    from app.services.vlm_service import vlm_service
    import uuid
    
    reader = PdfReader(file_path)
    text = ""
    images_metadata = []
    image_count = 0
    MAX_IMAGES = 20 # Limit images to avoid extreme slowdowns

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()
        if page_text:
            text += f"\n--- Page {page_number} ---\n"
            text += page_text
            
        for img_idx, image_file_object in enumerate(page.images):
            if image_count >= MAX_IMAGES:
                break
                
            try:
                # Ensure image directory exists
                os.makedirs(IMAGE_OUTPUT_FOLDER, exist_ok=True)
                
                # Save the image to disk
                img_filename = f"{uuid.uuid4().hex}_{image_file_object.name}"
                img_path = os.path.join(IMAGE_OUTPUT_FOLDER, img_filename)
                with open(img_path, "wb") as f:
                    f.write(image_file_object.data)

                # Use vlm_service to analyze the image (SmolVLM → Gemini fallback)
                display_name = f"{os.path.basename(file_path)}:page{page_number}:img{img_idx}"
                print(f"[VLM] Starting Gemini Vision processing: {display_name}")
                vlm_answer = vlm_service.analyze_image(
                    image_file_object.data,
                    filename=display_name,
                    max_tokens=1024,
                )
                
                vlm_text = vlm_answer.get("text") if isinstance(vlm_answer, dict) else vlm_answer
                
                if vlm_text:
                    if isinstance(vlm_answer, dict):
                        print(f"[VLM] Processing times - Gemini: {vlm_answer.get('gemini_time', 0):.2f}s, SmolVLM: {vlm_answer.get('smolvlm_time', 0):.2f}s")
                    
                    image_id = f"page{page_number}_img{img_idx}"
                    # Create a separate metadata record for the image
                    metadata = {
                        "page_number": page_number,
                        "image_index": img_idx,
                        "image_id": image_id,
                        "source_type": "pdf_image",
                        "content_type": "image",
                        "image_path": img_path,
                    }
                    if isinstance(vlm_answer, dict):
                        if vlm_answer.get("vision_model"):
                            metadata["vision_model"] = vlm_answer["vision_model"]
                        if vlm_answer.get("fallback_reason"):
                            metadata["fallback_reason"] = vlm_answer["fallback_reason"]
                    
                    print(f"\n[VLM] Final extracted text for {display_name}:\n{vlm_text}\n" + "-"*40)
                    
                    images_metadata.append({
                        "content": f"[Visual Content: {vlm_text}]",
                        "metadata": metadata
                    })
                    print(f"[RAG] Image content chunks stored: 1 (page={page_number}, img={img_idx})")
                else:
                    print(f"[VLM] Both Gemini and SmolVLM failed for {display_name} — skipping chunk.")
                image_count += 1
            except Exception as e:
                # Ignore extraction errors for individual images
                print(f"[VLM] Failed to process image on page {page_number}: {e}")

    return {"text": text, "images": images_metadata}


def extract_docx(file_path):
    from app.services.vlm_service import vlm_service
    import uuid

    document = Document(file_path)
    text = ""
    images_metadata = []

    for paragraph in document.paragraphs:
        paragraph_text = paragraph.text.strip()
        if paragraph_text:
            text += paragraph_text + "\n"

    image_count = 0
    MAX_IMAGES = 20

    # Extract images from docx parts
    for rel in document.part.rels.values():
        if "image" in rel.target_ref:
            if image_count >= MAX_IMAGES:
                break
            try:
                image_data = rel.target_part.blob
                
                # Ensure image directory exists
                os.makedirs(IMAGE_OUTPUT_FOLDER, exist_ok=True)
                
                # Save the image to disk
                img_filename = f"{uuid.uuid4().hex}_docx_img_{image_count}.png"
                img_path = os.path.join(IMAGE_OUTPUT_FOLDER, img_filename)
                with open(img_path, "wb") as f:
                    f.write(image_data)

                # Use vlm_service to analyze the image (SmolVLM → Gemini fallback)
                display_name = f"{os.path.basename(file_path)}:img{image_count}"
                print(f"[VLM] Starting Gemini Vision processing: {display_name}")
                vlm_answer = vlm_service.analyze_image(
                    image_data,
                    filename=display_name,
                    max_tokens=1024,
                )
                
                vlm_text = vlm_answer.get("text") if isinstance(vlm_answer, dict) else vlm_answer
                
                if vlm_text:
                    if isinstance(vlm_answer, dict):
                        print(f"[VLM] Processing times - Gemini: {vlm_answer.get('gemini_time', 0):.2f}s, SmolVLM: {vlm_answer.get('smolvlm_time', 0):.2f}s")
                        
                    image_id = f"docx_img_{image_count}"
                    # Create a separate metadata record for the image
                    metadata = {
                        "image_index": image_count,
                        "image_id": image_id,
                        "source_type": "docx_image",
                        "content_type": "image",
                        "image_path": img_path,
                    }
                    if isinstance(vlm_answer, dict):
                        if vlm_answer.get("vision_model"):
                            metadata["vision_model"] = vlm_answer["vision_model"]
                        if vlm_answer.get("fallback_reason"):
                            metadata["fallback_reason"] = vlm_answer["fallback_reason"]
                            
                    print(f"\n[VLM] Final extracted text for {display_name}:\n{vlm_text}\n" + "-"*40)
                            
                    images_metadata.append({
                        "content": f"[Visual Content: {vlm_text}]",
                        "metadata": metadata
                    })
                    print(f"[RAG] Image content chunks stored: 1 (img={image_count})")
                else:
                    print(f"[VLM] Both Gemini and SmolVLM failed for {display_name} — skipping chunk.")
                image_count += 1
            except Exception as e:
                print(f"[VLM] Failed to process image in DOCX: {e}")

    return {"text": text, "images": images_metadata}


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

    columns = list(
        dataframe.columns
    )

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


def clean_text(text):

    cleaned_lines = []

    for line in text.splitlines():

        line = line.strip()

        if line:

            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def extract_document(file_path):

    if not os.path.isfile(file_path):

        raise FileNotFoundError(
            "File not found."
        )

    extension = os.path.splitext(
        file_path
    )[1].lower()

    print(
        "\nFile:",
        os.path.basename(file_path)
    )

    print(
        "Type:",
        extension
    )

    images = []

    if extension == ".pdf":

        result = extract_pdf(file_path)
        text = result["text"]
        images = result["images"]

    elif extension == ".docx":

        result = extract_docx(file_path)
        text = result["text"]
        images.extend(result["images"])

    elif extension == ".txt":

        text = extract_txt(file_path)

    elif extension in [".jpg", ".jpeg", ".png"]:
        
        from app.services.vlm_service import vlm_service
        import shutil
        import uuid
        
        # Ensure image directory exists
        os.makedirs(IMAGE_OUTPUT_FOLDER, exist_ok=True)
        
        img_filename = f"{uuid.uuid4().hex}_{os.path.basename(file_path)}"
        img_path = os.path.join(IMAGE_OUTPUT_FOLDER, img_filename)
        shutil.copyfile(file_path, img_path)

        with open(file_path, "rb") as f:
            image_data = f.read()

        original_basename = os.path.basename(file_path)
        print(f"[VLM] Starting Gemini Vision processing: {original_basename}")
        try:
            vlm_answer = vlm_service.analyze_image(
                image_data,
                filename=original_basename,
                max_tokens=1024,
            )
            
            vlm_text = vlm_answer.get("text") if isinstance(vlm_answer, dict) else vlm_answer
            
            if not vlm_text:
                raise ValueError("Both Gemini and SmolVLM returned empty output — cannot index image.")
            
            if isinstance(vlm_answer, dict):
                print(f"[VLM] Processing times - Gemini: {vlm_answer.get('gemini_time', 0):.2f}s, SmolVLM: {vlm_answer.get('smolvlm_time', 0):.2f}s")
                
            text = f"[Image Description: {vlm_text}]"
            image_id = f"standalone_{uuid.uuid4().hex[:8]}"
            
            metadata = {
                "source_type": "image",
                "content_type": "image",
                "image_id": image_id,
                "image_path": img_path,
            }
            
            if isinstance(vlm_answer, dict):
                if vlm_answer.get("vision_model"):
                    metadata["vision_model"] = vlm_answer["vision_model"]
                if vlm_answer.get("fallback_reason"):
                    metadata["fallback_reason"] = vlm_answer["fallback_reason"]
                    
            print(f"\n[VLM] Final extracted text for {original_basename}:\n{vlm_text}\n" + "-"*40)
                    
            images.append({
                "content": text,
                "metadata": metadata
            })
            print(f"[RAG] Image content chunks stored: 1 ({original_basename})")
            text = ""  # content stored via images list
        except Exception as e:
            raise ValueError(f"Failed to process image: {e}")

    elif extension == ".csv":

        text = extract_csv(file_path)

    else:

        raise ValueError(
            "Unsupported file type. "
            "Use PDF, DOCX, TXT or CSV."
        )

    return {"text": clean_text(text), "images": images}


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


def main():

    print("=" * 70)
    print("        AI KNOWLEDGE BASE EXTRACTOR")
    print("=" * 70)

    print("\nSupported formats:")
    print("PDF | DOCX | TXT | CSV")

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

        extracted_text = extract_document(
            file_path
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
            os.path.abspath(output_file)
        )

        print(
            "\nExtraction completed successfully."
        )

    except Exception as error:

        print("\nERROR:")
        print(error)


if __name__ == "__main__":

    main()
