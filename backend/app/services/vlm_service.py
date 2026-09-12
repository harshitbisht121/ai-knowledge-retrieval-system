"""
VLM Service — Visual-Language Model.

Priority (NEW order):
  1. Gemini Vision  ← primary attempt
  2. Local SmolVLM  ← fallback when Gemini fails OR produces poor output

Quality gate:
  is_vlm_output_valid(text) decides whether SmolVLM output is rich enough
  to be stored in ChromaDB.  If not, Gemini is called automatically.

Uses GEMINI_API_KEY / GEMINI_VISION_MODEL from .env.
"""

import base64
import io
import logging
import os
import re

from PIL import Image
from pathlib import Path
from dotenv import load_dotenv

# Load .env so env vars are available when this module is imported
_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=_BACKEND_DIR / ".env")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Prefer the dedicated GEMINI_VISION_MODEL; fall back to GEMINI_VLM_MODEL
GEMINI_VISION_MODEL = (
    os.getenv("GEMINI_VISION_MODEL")
    or os.getenv("GEMINI_VLM_MODEL", "gemini-2.5-flash")
)
print(f"[VLM] Gemini model configured: {GEMINI_VISION_MODEL}")

# Local SmolVLM settings (loaded on demand)
LOCAL_VLM_MODEL = os.getenv("VLM_MODEL", "HuggingFaceTB/SmolVLM-256M-Instruct")
VLM_DEVICE      = os.getenv("VLM_DEVICE", "auto")

# Quality-gate thresholds
_MIN_VALID_LENGTH = 80          # characters
_GENERIC_PHRASES  = [
    "this image shows",
    "this is a diagram",
    "this is an image",
    "this image contains",
    "the image shows",
    "the image depicts",
    "i cannot",
    "i can't",
    "i am unable",
    "no text",
    "no visible text",
    "i don't see",
    "i do not see",
]

class InvalidImageError(Exception):
    pass


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

def is_vlm_output_valid(text: str) -> bool:
    """
    Return True when *text* contains genuinely useful extracted content.

    A result is considered POOR (returns False) when:
    - text is None or empty
    - fewer than _MIN_VALID_LENGTH characters
    - consists of a single line with no full stop or comma (title-only)
    - starts with a known generic/evasive phrase
    """
    if not text or not text.strip():
        return False

    stripped = text.strip()

    # Too short to be useful (increased threshold)
    if len(stripped) < 200:
        return False

    # Check word count
    words = stripped.split()
    if len(words) < 30:
        return False

    # Structural check: a detailed extraction should have structure (newlines, colons, bullets)
    # If it's relatively short (e.g. < 400 chars) but has no structure, it's likely a summary.
    has_structure = any(char in stripped for char in ("\n", ":", "-", "*", "•"))
    if len(stripped) < 400 and not has_structure:
        return False

    # Only one line with no sentence punctuation → likely just a title/topic
    lines = [ln for ln in stripped.splitlines() if ln.strip()]
    if len(lines) == 1:
        single = lines[0].lower()
        if not any(ch in single for ch in (".", ",", ":", "-", "→", "->", "\t")):
            return False

    # Generic / evasive openers
    lower = stripped.lower()
    for phrase in _GENERIC_PHRASES:
        if lower.startswith(phrase):
            return False
            
    # Check for vague summary language
    vague_phrases = [
        "provides an overview",
        "shows a diagram",
        "is a visual representation",
        "is an illustration of",
    ]
    for phrase in vague_phrases:
        if phrase in lower and len(stripped) < 300:
            return False

    return True


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _image_bytes_to_pil(image_bytes: bytes) -> Image.Image:
    """Open, validate, and RGB-convert image bytes.  Resize very large images."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()  # verify it's an image
        image = Image.open(io.BytesIO(image_bytes)) # reopen since verify closes it
    except Exception as e:
        raise InvalidImageError(f"Invalid or corrupted image: {e}")

    if image.mode not in ("RGB",):
        image = image.convert("RGB")
    max_dim = 1024
    if image.width > max_dim or image.height > max_dim:
        image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return image


def _image_bytes_to_base64_jpeg(image_bytes: bytes) -> str:
    """Bytes → PIL → base64-encoded JPEG string."""
    pil = _image_bytes_to_pil(image_bytes)
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ---------------------------------------------------------------------------
# Extraction prompts
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """\
You are extracting information from an image for a RAG knowledge base.

Analyze the entire image carefully.

Do not give a short summary.
Do not return only the title or topic.

Extract all meaningful information visible in the image.

For normal text:
- transcribe important visible text
- preserve headings and sections
- preserve technical terms
- preserve examples and definitions

For diagrams:
- identify every visible component
- explain the relationship between components
- describe arrows and communication direction
- describe the sequence of operations
- describe inputs and outputs

For flowcharts:
- describe each step in order
- describe decision points
- describe arrow direction

For architecture diagrams:
- identify all components
- explain how components communicate
- identify external resources
- explain request/response flow

For tables:
- extract the headers and values.

For handwritten notes:
- transcribe the handwriting as accurately as possible.
- If something is unclear, mark it as unclear rather than inventing it.

The extracted result will be stored in a vector database and used later to answer questions.

Therefore, preserve detailed factual information instead of summarizing it.

Return structured, detailed text."""


# ---------------------------------------------------------------------------
# Local SmolVLM (PRIMARY)
# ---------------------------------------------------------------------------

_local_model     = None
_local_processor = None
_local_device    = None


def _load_local_model():
    global _local_model, _local_processor, _local_device
    if _local_model is not None:
        return

    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    print(f"[VLM] Loading local SmolVLM model: {LOCAL_VLM_MODEL}")

    _local_device = (
        "cuda" if (VLM_DEVICE == "auto" and __import__("torch").cuda.is_available())
        else VLM_DEVICE if VLM_DEVICE != "auto"
        else "cpu"
    )
    dtype = __import__("torch").bfloat16 if _local_device == "cuda" else __import__("torch").float32

    _local_processor = AutoProcessor.from_pretrained(LOCAL_VLM_MODEL)
    _local_model = AutoModelForImageTextToText.from_pretrained(
        LOCAL_VLM_MODEL, torch_dtype=dtype, _attn_implementation="eager"
    ).to(_local_device)
    _local_model.eval()


def _call_local_vlm(image_bytes: bytes, prompt_text: str, max_tokens: int = 1024) -> str:
    import torch
    _load_local_model()
    pil = _image_bytes_to_pil(image_bytes)
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt_text}]}]
    prompt = _local_processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = _local_processor(text=prompt, images=[pil], return_tensors="pt").to(_local_device)
    with torch.inference_mode():
        generated = _local_model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)
    out = generated[0][inputs.input_ids.shape[1]:]
    return _local_processor.decode(out, skip_special_tokens=True).strip()


# ---------------------------------------------------------------------------
# Gemini Vision (FALLBACK)
# ---------------------------------------------------------------------------

def _call_gemini_vision(image_bytes: bytes, prompt_text: str, max_tokens: int = 2048) -> str:
    """
    Call Gemini vision model using the google-genai SDK.
    Raises RuntimeError on failure.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai is not installed. Run: pip install google-genai")

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Encode image as inline base64 part
    b64_data = _image_bytes_to_base64_jpeg(image_bytes)
    image_part = types.Part.from_bytes(
        data=base64.b64decode(b64_data),
        mime_type="image/jpeg",
    )

    response = client.models.generate_content(
        model=GEMINI_VISION_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    image_part,
                    types.Part.from_text(text=prompt_text),
                ],
            )
        ],
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=0.2,
        ),
    )

    return response.text.strip()


# ---------------------------------------------------------------------------
# Unified dispatcher  —  SmolVLM → quality gate → Gemini fallback
# ---------------------------------------------------------------------------

def _analyze_with_fallback(
    image_bytes: bytes,
    prompt_text: str,
    max_tokens: int,
    filename: str = "<image>",
) -> dict:
    """
    1. Try Gemini (primary).
    2. Quality-check the result with is_vlm_output_valid().
    3. If Gemini failed technically OR quality is POOR → call SmolVLM.
    4. If SmolVLM also fails → return empty text.
    """
    import time
    
    # Validation step to trigger InvalidImageError before processing
    try:
        _image_bytes_to_pil(image_bytes)
    except InvalidImageError:
        raise

    gemini_result: str | None = None
    gemini_time = 0.0
    smolvlm_time = 0.0
    fallback_reason = None
    vision_model = None
    
    print(f"[VLM] Processing: {filename}")
    print("[VLM] Primary model: Gemini")
    print("[VLM] Gemini processing started")

    t0 = time.perf_counter()
    try:
        gemini_result = _call_gemini_vision(image_bytes, prompt_text, max_tokens)
        gemini_time = time.perf_counter() - t0
        output_len = len(gemini_result) if gemini_result else 0
        print(f"[VLM] Gemini output length: {output_len}")
    except Exception as gem_err:
        gemini_time = time.perf_counter() - t0
        print(f"[VLM] Gemini failed: {gem_err}")
        fallback_reason = str(gem_err)

    if gemini_result is not None:
        if is_vlm_output_valid(gemini_result):
            print("[VLM] Gemini output quality: GOOD")
            print("[VLM] Final VLM model: Gemini")
            return {
                "text": gemini_result,
                "vision_model": GEMINI_VISION_MODEL,
                "fallback_reason": None,
                "gemini_time": gemini_time,
                "smolvlm_time": 0.0
            }
        else:
            fallback_reason = "insufficient visual extraction"
            print(f"[VLM] Gemini output quality: POOR")
            print(f"[VLM] Reason: {fallback_reason}")
            print(f"[VLM] Falling back to SmolVLM")
    print("[VLM] SmolVLM processing started")
    t1 = time.perf_counter()
    try:
        smolvlm_result = _call_local_vlm(image_bytes, prompt_text, max_tokens)
        smolvlm_time = time.perf_counter() - t1
        output_len = len(smolvlm_result) if smolvlm_result else 0
        print(f"[VLM] SmolVLM output length: {output_len}")
        
        print("[VLM] Final VLM model: SmolVLM")
        return {
            "text": smolvlm_result,
            "vision_model": LOCAL_VLM_MODEL,
            "fallback_reason": fallback_reason,
            "gemini_time": gemini_time,
            "smolvlm_time": smolvlm_time
        }

    except Exception as smol_err:
        smolvlm_time = time.perf_counter() - t1
        print(f"[VLM] SmolVLM failed: {smol_err}")
        raise RuntimeError(f"Both VLM methods failed. Gemini failed due to '{fallback_reason}'. SmolVLM error: {smol_err}")


# ---------------------------------------------------------------------------
# Public VLMService class
# ---------------------------------------------------------------------------

class VLMService:
    """
    Unified VLM service.

    analyze_image()           — upload-time: rich extraction for ChromaDB indexing
    analyze_image_for_query() — query-time:  targeted evidence extraction
    """

    # ------------------------------------------------------------------
    # Upload-time: rich description for ChromaDB indexing
    # ------------------------------------------------------------------
    def analyze_image(
        self,
        image_bytes: bytes,
        question: str = "",
        max_tokens: int = 1024,
        filename: str = "<image>",
    ) -> dict:
        """
        Extract comprehensive content from an image for semantic indexing.

        Gemini Vision is tried first. If it fails technically or the output is too
        short / generic, SmolVLM is called automatically using the same original image bytes.

        Returns a dictionary with extracted text and metadata, or empty string on failure.
        """
        # Build the prompt: start with the shared extraction template and
        # optionally append any caller-supplied extra instruction.
        prompt = _EXTRACTION_PROMPT
        if question and question.strip():
            prompt = prompt + f"\n\nAdditional instruction: {question.strip()}"

        try:
            return _analyze_with_fallback(image_bytes, prompt, max_tokens, filename=filename)
        except InvalidImageError as e:
            raise e
        except Exception as e:
            print(f"[VLM] analyze_image failed for '{filename}': {e}")
            return {"text": "", "vision_model": None, "fallback_reason": str(e), "gemini_time": 0.0, "smolvlm_time": 0.0}

    # ------------------------------------------------------------------
    # Query-time: targeted visual evidence extraction
    # ------------------------------------------------------------------
    def analyze_image_for_query(
        self,
        image_bytes: bytes,
        question: str,
        max_tokens: int = 1024,
        filename: str = "<image>",
    ) -> str:
        """
        Extract focused visual evidence from the image based on the user's query.
        Called at query time; output injected into the LLM prompt as VISUAL EVIDENCE.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty for query-time visual analysis.")

        prompt = f"""You are the visual understanding component of a document question-answering system.

Carefully analyze the image below. Your role is to extract structured visual evidence that will help another AI answer the user's question.

USER'S QUESTION:
{question}

ANALYSIS INSTRUCTIONS:
- Focus specifically on visual elements relevant to the question above
- Transcribe ALL text visible in the image, exactly as written (including handwriting)
- For diagrams/flowcharts: describe ALL nodes, connections, arrows, labels, and flows
- For tables: read ALL rows and columns with their exact values
- For graphs/charts: read axis labels, data values, legends, and trends
- For equations: write them out exactly as shown
- For handwritten content: transcribe every word precisely
- Note spatial relationships, directions, and hierarchies
- Mark anything unclear as [unclear]

DO NOT:
- Guess or invent content that isn't visible
- Give only a general description — be specific and precise
- Ignore any element relevant to the question

Return structured, detailed visual evidence ready for final reasoning:"""

        try:
            res = _analyze_with_fallback(image_bytes, prompt, max_tokens, filename=filename)
            return res.get("text", "")
        except InvalidImageError as e:
            raise e
        except Exception as e:
            print(f"[VLM] analyze_image_for_query failed for '{filename}': {e}")
            return "Visual analysis failed. Please ensure the image is a clear JPEG or PNG."

    # ------------------------------------------------------------------
    # Legacy compatibility (used by /vlm/analyze endpoint)
    # ------------------------------------------------------------------
    def validate_and_preprocess_image(self, image_bytes: bytes) -> Image.Image:
        return _image_bytes_to_pil(image_bytes)


# Singleton instance
vlm_service = VLMService()
