#!/usr/bin/env python3
"""Validate TMR extraction against a manually reviewed fixture.

This lightweight regression harness runs the real OCR and real local LLM
extraction pipeline, then compares the result to expected values.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from analysis.extractor import EntityExtractor  # noqa: E402
from processing.pdf_processor import PDFProcessor  # noqa: E402


class Validator:
    def __init__(self) -> None:
        self.failures: List[str] = []
        self.passes: int = 0

    def check(self, label: str, actual: Any, expected: Any) -> None:
        if actual == expected:
            self.passes += 1
            print(f"PASS: {label}")
        else:
            self.failures.append(f"{label}: expected {expected!r}, got {actual!r}")
            print(f"FAIL: {label}")
            print(f"      expected: {expected!r}")
            print(f"      actual:   {actual!r}")

    def check_contains(self, label: str, haystack: Optional[str], needle: str) -> None:
        haystack = haystack or ""
        if needle in haystack:
            self.passes += 1
            print(f"PASS: {label}")
        else:
            self.failures.append(f"{label}: expected {needle!r} to appear in {haystack!r}")
            print(f"FAIL: {label}")
            print(f"      expected substring: {needle!r}")
            print(f"      actual text:        {haystack!r}")

    def ok(self) -> bool:
        return not self.failures

    def summary(self) -> None:
        print("\n" + "=" * 60)
        print(f"Validation checks passed: {self.passes}")
        print(f"Validation checks failed: {len(self.failures)}")
        if self.failures:
            print("\nFailures:")
            for failure in self.failures:
                print(f"- {failure}")
        print("=" * 60)


def load_expected(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_prescription(record: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    target = name.lower()
    for rx in record.get("prescriptions", []):
        if (rx.get("medication_name") or "").lower() == target:
            return rx
    return None


def validate_record(record: Dict[str, Any], expected: Dict[str, Any]) -> Validator:
    validator = Validator()

    validator.check("patient_name", record.get("patient_name"), expected.get("patient_name"))
    validator.check("dob", record.get("dob"), expected.get("dob"))
    validator.check("facility_name", record.get("facility_name"), expected.get("facility_name"))
    validator.check("provider_name", record.get("provider_name"), expected.get("provider_name"))
    validator.check("date_of_service", record.get("date_of_service"), expected.get("date_of_service"))
    validator.check("analysis_status", record.get("analysis_status"), expected.get("analysis_status"))
    validator.check("review_required", record.get("review_required"), expected.get("review_required"))
    validator.check(
        "document section count",
        len(record.get("document_sections", [])),
        expected.get("document_sections", {}).get("expected_count"),
    )
    for expected_section in expected.get("document_sections", {}).get("required_sections", []):
        page_start = expected_section.get("page_start")
        section = next(
            (
                item for item in record.get("document_sections", [])
                if item.get("page_start") == page_start
            ),
            None,
        )
        if section is None:
            validator.failures.append(f"missing document section for page {page_start}")
            print(f"FAIL: document section page {page_start} present")
        else:
            validator.passes += 1
            print(f"PASS: document section page {page_start} present")
            validator.check_contains(
                f"document section page {page_start} text",
                section.get("text"),
                expected_section.get("text_contains", ""),
            )

    validator.check(
        "lab count",
        len(record.get("lab_results", [])),
        expected.get("labs", {}).get("expected_count"),
    )
    validator.check("prescription count", len(record.get("prescriptions", [])), len(expected.get("prescriptions", [])))

    for expected_rx in expected.get("prescriptions", []):
        name = expected_rx["medication_name"]
        actual_rx = find_prescription(record, name)
        if actual_rx is None:
            validator.failures.append(f"missing prescription: {name}")
            print(f"FAIL: prescription present: {name}")
            continue

        validator.passes += 1
        print(f"PASS: prescription present: {name}")
        for field in (
            "dosage_amount",
            "frequency",
            "suggested_medication_name",
            "suggested_dosage_amount",
            "normalized_frequency",
            "source_page",
        ):
            if field in expected_rx:
                validator.check(f"{name}.{field}", actual_rx.get(field), expected_rx[field])

        if "source_text_contains" in expected_rx:
            validator.check_contains(
                f"{name}.source_text",
                actual_rx.get("source_text"),
                expected_rx["source_text_contains"],
            )

    review_text = "\n".join(record.get("review_reasons", []))
    for needle in expected.get("expected_review_reason_contains", []):
        validator.check_contains(f"review reason contains {needle}", review_text, needle)

    return validator


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate extraction for test_record.pdf")
    parser.add_argument(
        "--file",
        default=str(PROJECT_ROOT / "data/input/test_record.pdf"),
        help="PDF file to process",
    )
    parser.add_argument(
        "--expected",
        default=str(PROJECT_ROOT / "tests/fixtures/test_record_expected.json"),
        help="Expected fixture JSON",
    )
    parser.add_argument(
        "--dump-json",
        default="",
        help="Optional path to write the observed record JSON",
    )
    parser.add_argument(
        "--no-ocr-cache",
        action="store_true",
        help="Bypass the OCR cache and regenerate OCR/native PDF text extraction",
    )
    parser.add_argument(
        "--no-llm-cache",
        action="store_true",
        help="Bypass the local LLM response cache",
    )
    args = parser.parse_args()

    input_path = Path(args.file)
    expected_path = Path(args.expected)

    print(f"Processing: {input_path}")
    print(f"Expected fixture: {expected_path}")

    expected = load_expected(expected_path)
    raw_text = PDFProcessor.extract_text(str(input_path), use_cache=not args.no_ocr_cache)
    record_model = EntityExtractor(provider="local", use_llm_cache=not args.no_llm_cache).analyze(raw_text)
    record = record_model.model_dump(mode="json")

    if args.dump_json:
        dump_path = Path(args.dump_json)
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"Observed record written to: {dump_path}")

    validator = validate_record(record, expected)
    validator.summary()
    return 0 if validator.ok() else 1


if __name__ == "__main__":
    raise SystemExit(main())
