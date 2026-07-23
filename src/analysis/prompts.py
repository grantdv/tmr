PATIENT_INFO_PROMPT = """
Extract the patient's name and date of birth.
Return only this JSON shape:
{"patient_name": "string or null", "dob": "YYYY-MM-DD or null"}
Use null when the document does not provide a value. Do not guess.
"""

ENCOUNTER_METADATA_PROMPT = """
Extract encounter-level metadata from the document text.
Return only this JSON shape:
{"facility_name": "string or null", "provider_name": "string or null", "date_of_service": "YYYY-MM-DD or null"}
Use the visit date, encounter date, service date, or report date as date_of_service.
Use null when the document does not provide a value. Do not guess.
"""

LAB_RESULTS_PROMPT = """
Extract every laboratory result in the document text.
Return only this JSON shape:
{"lab_results": [{"test_name": "string", "numeric_value": 0.0, "unit": "string or null", "status": "string or null"}]}
Do not invent results. Use an empty list when no laboratory results are present.
"""

PRESCRIPTIONS_PROMPT = """
Extract every medication or prescription in the document text.
Return only this JSON shape:
{"prescriptions": [{"medication_name": "string", "dosage_amount": "string or null", "frequency": "string or null", "route": "string or null", "instructions": "string or null"}]}
Preserve uncertain OCR text rather than silently correcting it. Do not invent missing values.
"""
