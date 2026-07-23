from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentSection(BaseModel):
    section_type: str = "page"
    title: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    text: str
    char_count: int


class LabResult(BaseModel):
    test_name: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: Optional[str] = None
    test_date: Optional[date] = None
    source_page: Optional[int] = None
    source_text: Optional[str] = None


class Prescription(BaseModel):
    medication_name: str
    dosage_amount: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    instructions: Optional[str] = None
    source_page: Optional[int] = None
    source_text: Optional[str] = None
    suggested_medication_name: Optional[str] = None
    suggested_dosage_amount: Optional[str] = None
    normalized_frequency: Optional[str] = None


class MedicalRecord(BaseModel):
    patient_name: Optional[str] = None
    dob: Optional[date] = None
    date_of_service: Optional[date] = None
    facility_name: Optional[str] = None
    provider_name: Optional[str] = None
    lab_results: List[LabResult] = Field(default_factory=list)
    prescriptions: List[Prescription] = Field(default_factory=list)
    document_sections: List[DocumentSection] = Field(default_factory=list)
    raw_summary: str
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    analysis_status: str = "not_analyzed"
    review_required: bool = True
    review_reasons: List[str] = Field(default_factory=list)
