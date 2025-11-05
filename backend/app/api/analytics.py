import json
import os
from collections import Counter
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Header

# Define the log file path
LOG_FILE = r"C:\Users\ravis\OneDrive\Desktop\PROJECTS\InsightSphere\backend\app\api\analytics_log.jsonl" 

router = APIRouter()

# --- Utility Functions for Logging ---

def read_logs() -> List[Dict[str, Any]]:
    """Reads and parses all logs from the JSONL file."""
    logs = []
    if not os.path.exists(LOG_FILE):
        return logs
    try:
        with open(LOG_FILE, 'r') as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip malformed lines to prevent crashing the dashboard
                    continue 
    except Exception as e:
        print(f"Error reading analytics log: {e}")
    return logs

def log_query(log_data: Dict[str, Any]):
    """Appends a query record to the log file."""
    # Ensure timestamp is current upon logging
    log_data['timestamp'] = datetime.now().isoformat()
    
    # The log file is created if it does not exist
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(log_data) + '\n')

# --- API Endpoint ---

@router.get("/dashboard/simple")
async def get_simple_analytics_dashboard() -> Dict[str, Any]:
    """Calculates and returns simple, core RAG system analytics."""
    
    logs = read_logs()

    if not logs:
        return {
            "total_queries": 0, "error_rate": "0.00%", "queries_per_user": {}, 
            "most_queried_documents": {}, "avg_response_time_ms": 0.0, 
        }

    # Data Collection & Aggregation
    total_queries = len(logs)
    error_count = sum(1 for log in logs if log.get("error") is True)
    
    # Filter for logs with a valid response time for averaging
    success_logs = [log for log in logs if log.get("error") is False and log.get("response_time_ms") is not None]
    
    # Calculate Metrics
    error_rate = f"{error_count / total_queries * 100:.2f}%"

    # 1. Queries Per User
    user_counts = Counter(log.get("user_id", "anonymous") for log in logs)
    
    # 2. Most Queried Documents (FIXED LOGIC)
    doc_sources = []
    for log in logs:
        # log.get("document_queried") is a list of dictionaries.
        # We must extract the 'source' string from the 'metadata' of each dictionary.
        if isinstance(log.get("document_queried"), list):
             for doc_chunk in log["document_queried"]:
                 # Safely access the nested 'source' property (which is the filename string)
                 if isinstance(doc_chunk, dict) and 'metadata' in doc_chunk and 'source' in doc_chunk['metadata']:
                     doc_sources.append(doc_chunk['metadata']['source'])
                 # Handle cases where the document_queried might have been logged as a simple string list
                 elif isinstance(doc_chunk, str):
                     doc_sources.append(doc_chunk)

    # Counter can now safely run on a list of strings
    document_counts = Counter(doc_sources)

    # 3. Average Response Time
    avg_response_time_ms = sum(log["response_time_ms"] for log in success_logs) / len(success_logs) if success_logs else 0.0

    return {
        "total_queries": total_queries,
        "error_rate": error_rate,
        "queries_per_user": dict(user_counts),
        "most_queried_documents": dict(document_counts.most_common(5)),
        "avg_response_time_ms": round(avg_response_time_ms, 2),
    }