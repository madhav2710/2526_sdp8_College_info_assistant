"""
Basic chat responses without RAG implementation.
Used for prototype when RAG is not available.
"""

from app.core.database import get_service_client
from typing import Dict


async def generate_basic_response(query: str, college_id: str) -> Dict:
    """
    Generate basic responses without RAG.
    
    Args:
        query: User's question
        college_id: College ID for filtering
        
    Returns:
        Dictionary with response text and sources
    """
    client = get_service_client()
    
    # Check if documents are available
    try:
        doc_count_response = client.table("documents").select("id", count="exact").eq("college_id", college_id).eq("status", "completed").execute()
        doc_count = doc_count_response.count if hasattr(doc_count_response, 'count') else 0
    except Exception:
        doc_count = 0
    
    if doc_count == 0:
        return {
            "response": "Our knowledge base is currently being set up. Please check back later or contact your college administration.",
            "sources": [],
            "chunks_used": 0
        }
    
    # Keyword-based responses for prototype
    query_lower = query.lower()
    
    if any(word in query_lower for word in ["syllabus", "course", "subject", "curriculum"]):
        return {
            "response": "I can help you with course and syllabus information. Please check our course catalog or contact your department for specific details.",
            "sources": [],
            "chunks_used": 0
        }
    elif any(word in query_lower for word in ["placement", "job", "career", "internship"]):
        return {
            "response": "For placement and career information, please refer to our placement office or check the official placement reports.",
            "sources": [],
            "chunks_used": 0
        }
    elif any(word in query_lower for word in ["admission", "enrollment", "apply", "application"]):
        return {
            "response": "For admission and enrollment information, please visit our admissions office or check the official admission guidelines on our website.",
            "sources": [],
            "chunks_used": 0
        }
    elif any(word in query_lower for word in ["fee", "tuition", "payment", "cost"]):
        return {
            "response": "For fee structure and payment information, please contact the accounts office or refer to the official fee schedule.",
            "sources": [],
            "chunks_used": 0
        }
    else:
        return {
            "response": "Thank you for your question. We're currently processing documents to provide you with accurate answers. Please try again later or contact your college administration for immediate assistance.",
            "sources": [],
            "chunks_used": 0
        }

