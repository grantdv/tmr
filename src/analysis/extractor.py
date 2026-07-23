import re
from datetime import datetime
from typing import Dict, Optional, Tuple

from .llm_engine import LLMEngine, LLMEngineError
from .normalizer import PrescriptionNormalizer
from .prompts import (
    ENCOUNTER_METADATA_PROMPT,
    LAB_RESULTS_PROMPT,
    PATIENT_INFO_PROMPT,
    PRESCRIPTIONS_PROMPT,
)
from .schema import DocumentSection, LabResult, MedicalRecord, Prescription
from .segmenter import DocumentSegmenter


class EntityExtractor:
    def __init__(self, provider: str = "local", use_llm_cache: bool = True):
        self.provider = provider
        self.brain = LLMEngine(provider=provider, use_cache=use_llm_cache)

    def analyze(self, raw_text: str) -> MedicalRecord:
        contexts = DocumentSegmenter.focused_contexts(raw_text)
        patient_context = contexts["PATIENT_INFO"]
        encounter_context = contexts["ENCOUNTER_METADATA"]
        lab_context = contexts["LAB_RESULTS"]
        rx_context = contexts["PRESCRIPTIONS"]
        full_text = raw_text.strip()

        record = MedicalRecord(
            raw_summary=full_text[:200] + ("..." if len(full_text) > 200 else ""),
            document_sections=[
                DocumentSection(**section) for section in DocumentSegmenter.document_sections(raw_text)
            ],
        )

        requests = (
            ("patient information", PATIENT_INFO_PROMPT, patient_context),
            ("encounter metadata", ENCOUNTER_METADATA_PROMPT, encounter_context),
            ("laboratory results", LAB_RESULTS_PROMPT, lab_context),
            ("prescriptions", PRESCRIPTIONS_PROMPT, rx_context),
        )

        extracted = {}
        for label, prompt, context in requests:
            try:
                extracted[label] = self.brain.query(prompt, context)
            except LLMEngineError as exc:
                reason = f"{label} extraction failed: {exc}"
                record.review_reasons.append(reason)
                print(f"[ERROR] {reason}")
                if "contact LLM model endpoint" in str(exc) or "Connection" in str(exc):
                    record.review_reasons.append(
                        "Remaining extraction requests were not attempted because the LLM is unavailable"
                    )
                    break

        patient_data = extracted.get("patient information", {})
        record.patient_name = patient_data.get("patient_name")
        record.dob = self._parse_date(patient_data.get("dob"))

        encounter_data = extracted.get("encounter metadata", {})
        record.facility_name = encounter_data.get("facility_name")
        record.provider_name = encounter_data.get("provider_name")
        record.date_of_service = self._parse_date(encounter_data.get("date_of_service"))

        for item in (extracted.get("laboratory results", {}).get("lab_results", []) or []):
            if not isinstance(item, dict):
                record.review_reasons.append("LLM returned a non-object laboratory result")
                continue
            if not item.get("test_name"):
                record.review_reasons.append("LLM returned a laboratory result without a test name")
                continue
            self._attach_provenance(item, lab_context, item.get("test_name"))
            try:
                lab = LabResult(**item)
                record.lab_results.append(lab)
                if not lab.source_text:
                    record.review_reasons.append(f"Lab '{lab.test_name}' is missing source text")
            except Exception as exc:
                record.review_reasons.append(f"Invalid laboratory result returned by LLM: {exc}")

        for item in (extracted.get("prescriptions", {}).get("prescriptions", []) or []):
            if not isinstance(item, dict):
                record.review_reasons.append("LLM returned a non-object prescription")
                continue
            if not item.get("medication_name"):
                record.review_reasons.append("LLM returned a prescription without a medication name")
                continue
            self._attach_provenance(item, rx_context, item.get("medication_name"))
            try:
                rx = Prescription(**item)
                record.prescriptions.append(rx)
                if not rx.source_text:
                    record.review_reasons.append(f"Prescription '{rx.medication_name}' is missing source text")
            except Exception as exc:
                record.review_reasons.append(f"Invalid prescription returned by LLM: {exc}")

        self._add_prescription_review_reasons(record)
        self._set_record_status(record)
        return record

    @staticmethod
    def _parse_date(value: object):
        if not value:
            return None
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y"):
            try:
                return datetime.strptime(cleaned, date_format).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _attach_provenance(item: Dict[str, object], context: str, entity_name: Optional[str]) -> None:
        if item.get("source_page") and item.get("source_text"):
            return
        source_page, source_text = EntityExtractor._find_source(entity_name or "", context)
        if source_page and not item.get("source_page"):
            item["source_page"] = source_page
        if source_text and not item.get("source_text"):
            item["source_text"] = source_text

    @staticmethod
    def _find_source(entity_name: str, context: str) -> Tuple[Optional[int], Optional[str]]:
        if not entity_name:
            return None, None
        current_page: Optional[int] = None
        page_re = re.compile(r"---\s*PAGE\s+(\d+)\s*---", re.I)
        target = entity_name.lower()
        for raw_line in context.splitlines():
            line = raw_line.strip()
            page_match = page_re.match(line)
            if page_match:
                current_page = int(page_match.group(1))
                continue
            if line and target in line.lower():
                return current_page, line
        return None, None

    @staticmethod
    def _add_prescription_review_reasons(record: MedicalRecord) -> None:
        for rx in record.prescriptions:
            name = rx.medication_name or "unknown medication"
            dosage = rx.dosage_amount or ""
            if not rx.dosage_amount:
                record.review_reasons.append(f"Prescription '{name}' is missing dosage information")
            if not rx.frequency:
                record.review_reasons.append(f"Prescription '{name}' is missing frequency information")
            record.review_reasons.extend(PrescriptionNormalizer.enrich(rx))
            if name.isupper() and len(name) > 8 and not rx.suggested_medication_name:
                record.review_reasons.append(f"Prescription name may contain OCR uncertainty: {name}")
            if not rx.source_page:
                record.review_reasons.append(f"Prescription '{name}' is missing source page")

    @staticmethod
    def _set_record_status(record: MedicalRecord) -> None:
        if record.review_reasons:
            record.analysis_status = "needs_review"
            record.review_required = True
            record.confidence_score = 0.5 if (
                record.patient_name or record.prescriptions or record.lab_results
            ) else 0.0
        else:
            record.analysis_status = "complete"
            record.review_required = False
            record.confidence_score = 1.0
