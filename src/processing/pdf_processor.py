import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import fitz  # PyMuPDF
from PIL import Image

from .image_processor import ImageProcessor


class PDFProcessor:
    CACHE_SCHEMA_VERSION = "1.0"
    CACHE_DIR = Path("data/output/ocr_cache")

    @staticmethod
    def extract_text(file_path, use_cache: bool = True):
        """Extract page-aware text from a PDF, using a local OCR cache when possible."""
        source_path = Path(file_path)
        print(f"Extracting text from PDF: {file_path}")

        if use_cache:
            cached = PDFProcessor._load_cache(source_path)
            if cached:
                print(f"  [OCR Cache] HIT: {cached['cache_path']}")
                print(
                    f"  [Summary] Total Pages: {cached['page_count']}, "
                    f"Total Characters: {cached['total_chars']} (from cache)"
                )
                return cached["combined_text"]
            print("  [OCR Cache] MISS: extracting PDF text/OCR")

        pages: List[Dict[str, object]] = []
        combined_text = ""
        total_chars = 0

        with fitz.open(source_path) as doc:
            for page_num, page in enumerate(doc, start=1):
                page_text = page.get_text()

                if page_text.strip():
                    method = "native_text"
                    extracted_text = page_text
                    print(f"  Page {page_num}: Found {len(extracted_text)} characters of native text.")
                else:
                    method = "ocr"
                    print(f"  Page {page_num}: No native text found. Attempting OCR...")
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_data = pix.tobytes("ppm")
                    img = Image.open(io.BytesIO(img_data))
                    extracted_text = ImageProcessor.extract_text(img)
                    print(f"  Page {page_num}: OCR extracted {len(extracted_text)} characters.")

                page_block = f"\n--- PAGE {page_num} ---\n{extracted_text}\n"
                combined_text += page_block
                total_chars += len(extracted_text)
                pages.append(
                    {
                        "page_number": page_num,
                        "method": method,
                        "char_count": len(extracted_text),
                        "text": extracted_text,
                    }
                )

        print(f"  [Summary] Total Pages: {len(pages)}, Total Characters: {total_chars}")
        if use_cache:
            cache_path = PDFProcessor._write_cache(source_path, pages, combined_text, total_chars)
            print(f"  [OCR Cache] WROTE: {cache_path}")
        return combined_text

    @staticmethod
    def _source_fingerprint(source_path: Path) -> Dict[str, object]:
        stat = source_path.stat()
        sha256 = hashlib.sha256()
        with source_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha256.update(chunk)
        return {
            "source_file": str(source_path),
            "source_name": source_path.name,
            "source_size": stat.st_size,
            "source_mtime_ns": stat.st_mtime_ns,
            "source_sha256": sha256.hexdigest(),
        }

    @staticmethod
    def _cache_path(source_path: Path, fingerprint: Dict[str, object]) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source_path.name)
        digest = str(fingerprint["source_sha256"])[:16]
        return PDFProcessor.CACHE_DIR / f"{safe_name}.{digest}.ocr.json"

    @staticmethod
    def _load_cache(source_path: Path):
        try:
            fingerprint = PDFProcessor._source_fingerprint(source_path)
            cache_path = PDFProcessor._cache_path(source_path, fingerprint)
            if not cache_path.exists():
                return None
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("cache_schema_version") != PDFProcessor.CACHE_SCHEMA_VERSION:
                return None
            if payload.get("source_sha256") != fingerprint["source_sha256"]:
                return None
            return {
                "cache_path": cache_path,
                "combined_text": payload.get("combined_text", ""),
                "page_count": len(payload.get("pages", [])),
                "total_chars": sum(page.get("char_count", 0) for page in payload.get("pages", [])),
            }
        except Exception as exc:
            print(f"  [OCR Cache] Ignoring unreadable cache: {exc}")
            return None

    @staticmethod
    def _write_cache(
        source_path: Path,
        pages: List[Dict[str, object]],
        combined_text: str,
        total_chars: int,
    ) -> Path:
        fingerprint = PDFProcessor._source_fingerprint(source_path)
        cache_path = PDFProcessor._cache_path(source_path, fingerprint)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cache_schema_version": PDFProcessor.CACHE_SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **fingerprint,
            "page_count": len(pages),
            "total_chars": total_chars,
            "pages": pages,
            "combined_text": combined_text,
        }
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return cache_path
