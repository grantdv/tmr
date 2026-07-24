import json
import re
from typing import List, Dict, Any
from src.analysis.queue import add_task

class TriageEngine:
    """
    The Triage Engine performs a high-speed, low-cost pass over document text 
    to identify 'easy' extractions and queue 'complex' extractions.
    """

    # Categories for extraction
    # Easy: Can be extracted with high confidence via regex or small local models
    # Complex: Require deep reasoning (multi-line, messy OCR, ambiguous values)
    EXTRACTION_MAP = {
        "PATIENT_INFO": {
            "easy": ["patient_name", "dob"],
            "complex": []
        },
        "ENCOUNTER_METADATA": {
            "easy": ["facility_name", "provider_name"],
            "complex": ["date_of_service"]
        },
        "LAB_RESULTS": {
            "easy": [],
            "complex": ["lab_results"]
        },
        "PRESCRIPTIONS": {
            "easy": [],
            "complex": ["prescriptions"]
        }
    }

    @classmethod
    def triage_document(cls, doc_id: str, full_text: str) -> List[Dict[str, Any]]:
        """
        Analyzes the text and returns a list of tasks to be added to the queue.
        """
        tasks_to_queue = []

        # 1. Fast-scan for Patient Info
        # If we find clear patterns, we could process them now, 
        # but for the Triage model, we put them in the queue for consistency.
        tasks_to_queue.append({
            "type": "PATIENT_INFO",
            "payload": full_text,
            "priority": 1,
            "doc_id": doc_id
        })

        # 2. Fast-scan for Encounter Metadata
        tasks_to_queue.append({
            "type": "ENCOUNTER_METADATA",
            "payload": full_text,
            "priority": 2,
            "doc_id": doc_id
        })

        # 3. Complex Lab Results
        # We look for "Lab" keywords to decide if this document even needs a lab pass
        if any(kw in full_text.lower() for kw in ["lab", "test result", "glucose", "hba1c"]):
            tasks_to_queue.append({
                "type": "LAB_RESULTS",
                "payload": full_text,
                "priority": 3,
                "doc_id": doc_id
            })

        # 4. Complex Prescriptions
        if any(kw in full_text.lower() for kw in ["medication", "rx", "prescription", "mg"]):
            tasks_to_queue.append({
                "type": "PRESCRIPTIONS",
                "payload": full_text,
                "priority": 3,
                "doc_id": doc_id
            })

        # Add to our SQLite queue
        for task in tasks_to_queue:
            add_task(
                task_type=task["type"],
                payload=json.dumps(task), # Payload contains the chunk of text to analyze
                source_doc_id=task["doc_id"],
                priority=task["priority"]
            )

        return tasks_to_queue

# Example usage:
# TriageEngine.triage_document("doc_123", "Patient: Smith, Doe. Lab results: Glucose 110...")
