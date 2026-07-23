"""Non-destructive normalization helpers for extracted medical entities.

These functions do not change the original extracted values. They only add
suggested/normalized companion fields and review reasons.
"""
import re
from typing import Optional

from .schema import Prescription


class PrescriptionNormalizer:
    MEDICATION_SUGGESTIONS = {
        "TRIAMCINGLONE": "Triamcinolone",
        "TRIAMCINCLONE": "Triamcinolone",
        "TRIAMCINOLONE": "Triamcinolone",
    }

    FREQUENCY_NORMALIZATION = {
        "qday": "daily",
        "qd": "daily",
        "daily": "daily",
        "qhs": "at bedtime",
        "q h s": "at bedtime",
        "nightly": "at bedtime",
        "bid": "twice daily",
        "tid": "three times daily",
        "qid": "four times daily",
        "prn": "as needed",
        "as needed": "as needed",
    }

    @staticmethod
    def enrich(rx: Prescription) -> list[str]:
        """Attach non-destructive suggestions to a prescription.

        Returns review reasons generated during enrichment.
        """
        reasons: list[str] = []
        name = rx.medication_name or ""
        dosage = rx.dosage_amount or ""
        frequency = rx.frequency or ""

        suggested_name = PrescriptionNormalizer.suggest_medication_name(name)
        if suggested_name and suggested_name != name:
            rx.suggested_medication_name = suggested_name
            reasons.append(
                f"Prescription name may be OCR text: '{name}'. Suggested review value: '{suggested_name}'"
            )

        suggested_dosage = PrescriptionNormalizer.suggest_dosage(dosage)
        if suggested_dosage and suggested_dosage != dosage:
            rx.suggested_dosage_amount = suggested_dosage
            reasons.append(
                f"Prescription dosage may be OCR text: '{dosage}'. Suggested review value: '{suggested_dosage}'"
            )

        normalized_frequency = PrescriptionNormalizer.normalize_frequency(frequency)
        if normalized_frequency:
            rx.normalized_frequency = normalized_frequency

        return reasons

    @staticmethod
    def suggest_medication_name(name: str) -> Optional[str]:
        stripped = name.strip()
        upper = stripped.upper()
        if upper in PrescriptionNormalizer.MEDICATION_SUGGESTIONS:
            return PrescriptionNormalizer.MEDICATION_SUGGESTIONS[upper]
        return None

    @staticmethod
    def suggest_dosage(dosage: str) -> Optional[str]:
        stripped = dosage.strip()
        if not stripped:
            return None

        # Common OCR issue: leading S misread before a dosage, e.g. S5mg -> 5mg.
        match = re.fullmatch(r"[sS](\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?))", stripped)
        if match:
            return match.group(1)

        # Common OCR issue: O/l/I used in place of zero/one inside compact dosage strings.
        compact = stripped.replace(" ", "")
        if re.fullmatch(r"[0-9OlI]+(?:mg|mcg|g|ml)", compact, flags=re.I):
            translated = compact.translate(str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1"}))
            if translated != compact:
                return translated

        return None

    @staticmethod
    def normalize_frequency(frequency: str) -> Optional[str]:
        normalized = re.sub(r"\s+", " ", frequency.strip().lower())
        if not normalized:
            return None
        return PrescriptionNormalizer.FREQUENCY_NORMALIZATION.get(normalized)
