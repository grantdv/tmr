import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from analysis.extractor import EntityExtractor
from analysis.schema import MedicalRecord
from ingestion.scanner import FileScanner
from processing.image_processor import ImageProcessor
from processing.pdf_processor import PDFProcessor
from version import OUTPUT_SCHEMA_VERSION, TMR_VERSION


def parse_args():
    parser = argparse.ArgumentParser(description="TMR local medical-record extraction")
    parser.add_argument(
        "--file",
        help="Process a single PDF/image instead of scanning the input directory",
    )
    parser.add_argument(
        "--input-dir",
        default="./data/input",
        help="Directory to scan when --file is not provided",
    )
    parser.add_argument(
        "--output",
        help="Write structured JSON to this path instead of a timestamped output file",
    )
    parser.add_argument(
        "--no-ocr-cache",
        action="store_true",
        help="Bypass the OCR cache and regenerate PDF OCR/native text extraction",
    )
    parser.add_argument(
        "--no-llm-cache",
        action="store_true",
        help="Bypass the local LLM response cache",
    )
    return parser.parse_args()


def collect_files(args) -> List[str]:
    if args.file:
        return [args.file]
    scanner = FileScanner(input_dir=args.input_dir)
    return scanner.scan()


def file_metadata(file_path: str) -> Dict[str, object]:
    path = Path(file_path)
    stat = path.stat()
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(chunk)
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256.hexdigest(),
    }


def process_file(file_path: str, extractor: EntityExtractor, use_ocr_cache: bool) -> MedicalRecord:
    print(f"\n--- Processing: {file_path} ---")
    lower_path = file_path.lower()

    if lower_path.endswith(".pdf"):
        content = PDFProcessor.extract_text(file_path, use_cache=use_ocr_cache)
    elif lower_path.endswith((".jpg", ".png", ".jpeg")):
        content = ImageProcessor.extract_text(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    return extractor.analyze(content)


def build_output_artifact(
    output_records: List[Dict[str, object]],
    extractor: EntityExtractor,
    started_at: str,
    finished_at: str,
    args,
) -> Dict[str, object]:
    return {
        "tmr_version": TMR_VERSION,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "created_at": finished_at,
        "processing_started_at": started_at,
        "processing_finished_at": finished_at,
        "runtime": {
            "entry_point": str(Path(__file__).resolve()),
            "working_directory": str(Path.cwd()),
            "input_mode": "single_file" if args.file else "scan_directory",
            "input_dir": args.input_dir,
            "ocr_cache_enabled": not args.no_ocr_cache,
            "llm_cache_enabled": not args.no_llm_cache,
        },
        "llm": {
            "provider": extractor.provider,
            "base_url": extractor.brain.base_url,
            "model": extractor.brain.model,
            "timeout_seconds": extractor.brain.timeout,
        },
        "record_count": len(output_records),
        "records": output_records,
    }


def write_output(artifact: Dict[str, object], output_path_arg: str = "") -> Path:
    if output_path_arg:
        output_path = Path(output_path_arg)
    else:
        output_dir = Path("./data/output")
        output_path = output_dir / f"extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return output_path


def print_summary(results: List[MedicalRecord]) -> None:
    print("\n" + "=" * 40)
    print(f"FINAL EXTRACTION SUMMARY ({len(results)} files):")
    for i, res in enumerate(results):
        print(f"File {i + 1}: {res.patient_name} (DOB: {res.dob})")
        print(f"  - Facility: {res.facility_name}")
        print(f"  - Provider: {res.provider_name}")
        print(f"  - Date of Service: {res.date_of_service}")
        print(f"  - Document Sections Retained: {len(res.document_sections)}")
        print(f"  - Labs Found: {len(res.lab_results)}")
        if res.lab_results:
            for lab in res.lab_results:
                print(f"    * {lab.test_name}: {lab.numeric_value} {lab.unit} ({lab.status})")
                print(f"      Source: page {lab.source_page}, text: {lab.source_text}")

        print(f"  - Prescriptions Found: {len(res.prescriptions)}")
        if res.prescriptions:
            for rx in res.prescriptions:
                print(f"    * {rx.medication_name} ({rx.dosage_amount}) - {rx.frequency} {rx.route}")
                if rx.suggested_medication_name:
                    print(f"      Suggested medication name: {rx.suggested_medication_name}")
                if rx.suggested_dosage_amount:
                    print(f"      Suggested dosage: {rx.suggested_dosage_amount}")
                if rx.normalized_frequency:
                    print(f"      Normalized frequency: {rx.normalized_frequency}")
                print(f"      Source: page {rx.source_page}, text: {rx.source_text}")

        print(f"  - Analysis Status: {res.analysis_status}")
        print(f"  - Review Required: {res.review_required}")
        print(f"  - Confidence: {res.confidence_score}")
        for reason in res.review_reasons:
            print(f"  - Review Reason: {reason}")


def main():
    args = parse_args()
    started_at = datetime.now(timezone.utc).isoformat()
    print("Starting TMR Ingestion Engine...")
    print(f"[DEBUG] Entry point: {Path(__file__).resolve()}")
    print(f"[DEBUG] Working directory: {Path.cwd()}")
    print("[DEBUG] Provider: local; base URL: http://localhost:8080")
    print(f"[DEBUG] OCR cache enabled: {not args.no_ocr_cache}")
    print(f"[DEBUG] LLM cache enabled: {not args.no_llm_cache}")
    print(f"[DEBUG] TMR version: {TMR_VERSION}; output schema: {OUTPUT_SCHEMA_VERSION}")

    files = collect_files(args)
    if not files:
        print(f"No new files found in {args.input_dir}.")
        return

    extractor = EntityExtractor(provider="local", use_llm_cache=not args.no_llm_cache)
    results: List[MedicalRecord] = []
    output_records = []

    for file_path in files:
        try:
            analysis = process_file(file_path, extractor, use_ocr_cache=not args.no_ocr_cache)
        except Exception as exc:
            print(f"[ERROR] Failed to process {file_path}: {exc}")
            continue
        results.append(analysis)
        output_records.append(
            {
                "source_file": file_metadata(file_path),
                "record": analysis.model_dump(mode="json"),
            }
        )

    finished_at = datetime.now(timezone.utc).isoformat()
    print_summary(results)
    artifact = build_output_artifact(output_records, extractor, started_at, finished_at, args)
    output_path = write_output(artifact, args.output)
    print(f"Structured output written to: {output_path}")
    print("=" * 40)


if __name__ == "__main__":
    main()
