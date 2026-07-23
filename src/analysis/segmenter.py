import re
from typing import Dict, Iterable, List


class DocumentSegmenter:
    """Create focused contexts and retained document sections."""

    SECTION_HEADERS = {
        "PATIENT_INFO": [r"PATIENT\s*INFO", r"PATIENT\s*DETAILS", r"DEMOGRAPHICS"],
        "LAB_RESULTS": [r"LAB\s*RESULTS", r"LAB\s*WORKUP", r"TEST\s*RESULTS"],
        "PRESCRIPTIONS": [r"PRESCRIPTIONS", r"MEDICATIONS", r"CURRENT\s+MEDS?", r"RX", r"MEDS"],
        "CLINICAL_NOTES": [r"CLINICAL\s*NOTES", r"SUMMARY", r"PLAN", r"ASSESSMENT"],
    }

    KEYWORDS = {
        "PATIENT_INFO": ("patient", "date of birth", "dob", "birth date", "demographic"),
        "ENCOUNTER_METADATA": (
            "visit date",
            "date of service",
            "service date",
            "encounter date",
            "provider",
            " md",
            "facility",
            "health",
            "clinic",
        ),
        "LAB_RESULTS": (
            "lab",
            "laboratory",
            "glucose",
            "a1c",
            "hba1c",
            "cholesterol",
            "mg/dl",
            "reference range",
            "blood test",
        ),
        "PRESCRIPTIONS": (
            "medication",
            "medications",
            "prescription",
            "rx",
            "take ",
            " qday",
            " qhs",
            " bid",
            " tid",
        ),
    }

    @staticmethod
    def segment(text: str) -> Dict[str, str]:
        segments = {name: "" for name in DocumentSegmenter.SECTION_HEADERS}
        headers = []
        for section, patterns in DocumentSegmenter.SECTION_HEADERS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    headers.append((section, match.start()))
                    break
        headers.sort(key=lambda item: item[1])

        if not headers:
            segments["CLINICAL_NOTES"] = text
            return segments

        for index, (section, start) in enumerate(headers):
            end = headers[index + 1][1] if index + 1 < len(headers) else len(text)
            segments[section] += text[start:end].strip()
        if headers[0][1] > 0:
            segments["PATIENT_INFO"] = text[: headers[0][1]].strip()
        return segments

    @staticmethod
    def focused_contexts(text: str, max_chars: int = 9000) -> Dict[str, str]:
        """Return bounded task-specific contexts, preserving page markers."""
        sections = DocumentSegmenter.segment(text)
        contexts = {}
        for section in ("PATIENT_INFO", "ENCOUNTER_METADATA", "LAB_RESULTS", "PRESCRIPTIONS"):
            if section in sections and sections[section].strip():
                context = sections[section][-max_chars:]
            else:
                context = DocumentSegmenter._keyword_windows(
                    text, DocumentSegmenter.KEYWORDS[section], max_chars
                )

            if section == "PRESCRIPTIONS":
                medication_block = DocumentSegmenter._medication_list_block(context)
                if medication_block:
                    context = medication_block
                else:
                    context = DocumentSegmenter._candidate_lines(
                        context,
                        DocumentSegmenter.KEYWORDS[section],
                        max_chars=3500,
                        include_dosage_patterns=True,
                    )
            elif section == "LAB_RESULTS":
                context = DocumentSegmenter._candidate_lines(
                    context,
                    DocumentSegmenter.KEYWORDS[section],
                    max_chars=3500,
                    include_dosage_patterns=False,
                )
            elif section == "ENCOUNTER_METADATA":
                context = DocumentSegmenter._candidate_lines(
                    context,
                    DocumentSegmenter.KEYWORDS[section],
                    max_chars=3500,
                    include_dosage_patterns=False,
                )
            contexts[section] = context
        return contexts

    @staticmethod
    def document_sections(text: str) -> List[Dict[str, object]]:
        """Preserve page-level text sections for review/storage.

        This intentionally retains broad document text. Entity extraction can be
        focused, but future review/database layers should still have access to
        the source clinical narrative.
        """
        page_re = re.compile(r"^---\s*PAGE\s+(\d+)\s*---\s*$", re.I | re.M)
        matches = list(page_re.finditer(text))
        if not matches:
            stripped = text.strip()
            return [
                {
                    "section_type": "document",
                    "title": "Document Text",
                    "page_start": None,
                    "page_end": None,
                    "text": stripped,
                    "char_count": len(stripped),
                }
            ] if stripped else []

        sections = []
        for index, match in enumerate(matches):
            page_number = int(match.group(1))
            content_start = match.end()
            content_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            page_text = text[content_start:content_end].strip()
            sections.append(
                {
                    "section_type": "page",
                    "title": f"Page {page_number}",
                    "page_start": page_number,
                    "page_end": page_number,
                    "text": page_text,
                    "char_count": len(page_text),
                }
            )
        return sections

    @staticmethod
    def _keyword_windows(text: str, keywords: Iterable[str], max_chars: int) -> str:
        lower = text.lower()
        hits = []
        for keyword in keywords:
            start = 0
            while True:
                position = lower.find(keyword.lower(), start)
                if position < 0:
                    break
                hits.append(position)
                start = position + len(keyword)
        if not hits:
            return text[:max_chars]

        snippets = []
        for position in sorted(set(hits)):
            snippets.append(text[max(0, position - 1200) : position + 2200])
        combined = "\n\n--- CONTEXT WINDOW ---\n\n".join(snippets)
        return combined[:max_chars]

    @staticmethod
    def _medication_list_block(text: str) -> str:
        lines = text.splitlines()
        start = None
        end_markers = (
            "medication side effects",
            "medication adherence",
            "past psychiatric medications",
            "medication allergies",
            "non-medication allergies",
        )
        for index, line in enumerate(lines):
            if "current medications" in line.lower():
                page_marker = None
                for prior in range(index, -1, -1):
                    if lines[prior].startswith("--- PAGE "):
                        page_marker = prior
                        break
                start = max(0, index - 3)
                if page_marker is not None and page_marker < start:
                    lines[start] = lines[page_marker] + "\n" + lines[start]
                break
        if start is None:
            return ""
        end = len(lines)
        for index in range(start + 1, len(lines)):
            lowered = lines[index].lower()
            if any(marker in lowered for marker in end_markers):
                end = index
                break
        return "\n".join(lines[start:end]).strip()

    @staticmethod
    def _candidate_lines(
        text: str,
        keywords: Iterable[str],
        max_chars: int,
        include_dosage_patterns: bool,
    ) -> str:
        lines = text.splitlines()
        keep = set()
        dosage_re = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?)\b", re.I)
        frequency_re = re.compile(
            r"\b(?:qday|qhs|bid|tid|qid|prn|daily|nightly|as needed)\b", re.I
        )

        for index, line in enumerate(lines):
            normalized = line.lower()
            keyword_hit = any(keyword.strip().lower() in normalized for keyword in keywords)
            dosage_hit = include_dosage_patterns and (
                dosage_re.search(line) or frequency_re.search(line)
            )
            if keyword_hit or dosage_hit or line.startswith("--- PAGE "):
                for neighbor in range(max(0, index - 1), min(len(lines), index + 2)):
                    keep.add(neighbor)

        if not keep:
            return text[:max_chars]

        selected = [lines[index] for index in sorted(keep)]
        return "\n".join(selected)[:max_chars]
