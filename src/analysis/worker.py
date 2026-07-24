import json
import time
import logging
import os
from typing import List, Dict, Any, Optional

from src.analysis.queue import (
    get_next_task, 
    update_task_status, 
    get_queue_depth
)
from src.analysis.llm_engine import LLMEngine
from src.analysis.extractor import EntityExtractor
from src.analysis.schema import MedicalRecord

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Worker")

# Configuration
MAX_LOCAL_QUEUE_DEPTH = 3  # Threshold to trigger overflow
LOCAL_LLM_MODEL = "unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL"
REMOTE_LLM_MODEL = "gpt-4o"  # Example remote model

class TMRWorker:
    def __init__(self):
        self.local_engine = LLMEngine()
        # Note: In a real production system, the RemoteLLM_Engine 
        # would be initialized here as well.
        self.is_running = True

    def run(self):
        """Main worker loop."""
        logger.info("Worker started. Monitoring queue...")
        
        while self.is_running:
            tasks = get_next_task(batch_size=1)
            
            if not tasks:
                time.sleep(1)  # Sleep briefly if queue is empty
                continue
            
            task_data = tasks[0]
            task_id = task_data['id']
            task_type = task_data['task_type']
            payload_str = task_data['payload']
            source_doc_id = task_data['source_doc_id']
            
            # Parse the payload (which contains the text chunk and doc_id)
            try:
                payload = json.loads(payload_str)
                context_text = payload.get("payload", "") # The TriageEngine puts the text here
            except Exception as e:
                logger.error(f"Failed to parse payload for task {task_id}: {e}")
                update_task_status(task_id, "failed")
                continue

            logger.info(f"Processing {task_type} (Task ID: {task_id})")
            
            # Determine routing based on queue depth
            depth = get_queue_depth()
            use_remote = depth > MAX_LOCAL_QUEUE_DEPTH
            provider = "remote_api" if use_remote else "local_llm"
            
            logger.info(f"Queue Depth: {depth} | Routing to: {provider}")

            try:
                # Here we would call the appropriate engine
                # For now, we route to the local engine as a base implementation
                # and log the "Remote" intent.
                
                # Simulate extraction logic
                # In reality, this calls the LLM and updates the MedicalRecord
                # For this demo, we'll just simulate a successful completion
                
                # response = self.local_engine.generate(...)
                # ... logic to update MedicalRecord ...
                
                time.sleep(1) # Simulate work
                
                update_task_status(task_id, "completed", provider=provider)
                logger.info(f"Successfully completed task {task_id} via {provider}")
                
            except Exception as e:
                logger.error(f"Error processing task {task_id}: {e}")
                update_task_status(task_id, "failed", retries=1)

if __name__ == "__main__":
    worker = TMRWorker()
    worker.run()
