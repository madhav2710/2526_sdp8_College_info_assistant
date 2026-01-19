"""
Enhanced basic chat responses with improved fallback mechanisms.
Used when RAG is not available or fails, providing graceful degradation.
"""

from app.core.database import get_service_client
from typing import Dict
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


async def generate_basic_response(query: str, college_id: str) -> Dict:
    """
    Generate enhanced basic responses without RAG, with improved fallback mechanisms
    and better user experience during service failures.
    
    Args:
        query: User's question
        college_id: College ID for filtering
        
    Returns:
        Dictionary with response text, sources, and fallback metadata
    """
    client = get_service_client()
    
    # Enhanced logging for fallback usage
    logger.info(f"Generating basic fallback response for query: '{query[:50]}...' (college: {college_id})")
    
    # Check if documents are available with enhanced error handling
    doc_count = 0
    doc_status_info = {}
    
    try:
        # Get document statistics for better user feedback
        doc_stats_response = client.table("documents").select(
            "status", count="exact"
        ).eq("college_id", college_id).execute()
        
        if hasattr(doc_stats_response, 'count'):
            doc_count = doc_stats_response.count
        else:
            doc_count = len(doc_stats_response.data) if doc_stats_response.data else 0
        
        # Get status breakdown for more informative responses
        if doc_stats_response.data:
            for doc in doc_stats_response.data:
                status = doc.get("status", "unknown")
                doc_status_info[status] = doc_status_info.get(status, 0) + 1
        
        logger.info(f"Document availability check: {doc_count} total documents, status breakdown: {doc_status_info}")
        
    except Exception as e:
        logger.warning(f"Failed to check document availability: {str(e)}")
        doc_count = 0
        doc_status_info = {}
    
    # Enhanced responses based on document availability and query content
    query_lower = query.lower()
    
    # If no documents are available at all
    if doc_count == 0:
        return {
            "response": "Our knowledge base is currently being set up. Please check back later or contact your college administration for immediate assistance.",
            "sources": [],
            "chunks_used": 0,
            "fallback_used": True,
            "fallback_reason": "No documents available",
            "quality_score": 0.3,
            "doc_status": "no_documents"
        }
    
    # If documents exist but none are completed (processed)
    completed_docs = doc_status_info.get("completed", 0)
    if completed_docs == 0:
        processing_docs = doc_status_info.get("processing", 0)
        pending_docs = doc_status_info.get("pending_approval", 0) + doc_status_info.get("approved", 0)
        
        if processing_docs > 0:
            return {
                "response": f"We're currently processing {processing_docs} document(s) to build our knowledge base. This usually takes a few minutes. Please try again shortly, or contact your college administration for immediate assistance.",
                "sources": [],
                "chunks_used": 0,
                "fallback_used": True,
                "fallback_reason": "Documents still processing",
                "quality_score": 0.4,
                "doc_status": "processing",
                "processing_count": processing_docs
            }
        elif pending_docs > 0:
            return {
                "response": f"We have {pending_docs} document(s) awaiting approval and processing. Once approved, they'll be available for questions. Please contact your college administration for immediate assistance.",
                "sources": [],
                "chunks_used": 0,
                "fallback_used": True,
                "fallback_reason": "Documents pending approval",
                "quality_score": 0.4,
                "doc_status": "pending",
                "pending_count": pending_docs
            }
    
    # Enhanced keyword-based responses with more helpful information
    response_templates = {
        "syllabus": {
            "keywords": ["syllabus", "course", "subject", "curriculum", "program", "degree"],
            "response": "I can help you with course and syllabus information. While I'm currently unable to search through our documents, I recommend checking your college's official course catalog, student portal, or contacting your academic department directly for the most up-to-date syllabus and course information."
        },
        "placement": {
            "keywords": ["placement", "job", "career", "internship", "employment", "recruit"],
            "response": "For placement and career information, I recommend visiting your college's placement office or career services center. You can also check the official placement reports and statistics on your college website, or contact the placement coordinator directly for current opportunities and guidance."
        },
        "admission": {
            "keywords": ["admission", "enrollment", "apply", "application", "eligibility", "entrance"],
            "response": "For admission and enrollment information, please visit your college's admissions office or check the official admission guidelines on the college website. The admissions team can provide you with detailed information about eligibility criteria, application procedures, and important dates."
        },
        "fee": {
            "keywords": ["fee", "tuition", "payment", "cost", "expense", "scholarship"],
            "response": "For fee structure and payment information, please contact the accounts office or finance department. You can also refer to the official fee schedule on your college website. If you're looking for scholarship information, the student affairs office can provide details about available financial aid options."
        },
        "exam": {
            "keywords": ["exam", "test", "assessment", "evaluation", "grade", "result"],
            "response": "For examination schedules, results, and assessment information, please check your student portal or contact the examination office. Your academic department can also provide specific information about course assessments and grading policies."
        },
        "library": {
            "keywords": ["library", "book", "resource", "study", "research"],
            "response": "For library services and resources, please visit the college library or check their online catalog. The library staff can help you find books, research materials, and provide information about study spaces and borrowing policies."
        },
        "hostel": {
            "keywords": ["hostel", "accommodation", "residence", "room", "boarding"],
            "response": "For hostel and accommodation information, please contact the hostel office or student affairs department. They can provide details about room availability, facilities, fees, and application procedures for campus housing."
        }
    }
    
    # Find the best matching response template
    best_match = None
    max_matches = 0
    
    for category, template in response_templates.items():
        matches = sum(1 for keyword in template["keywords"] if keyword in query_lower)
        if matches > max_matches:
            max_matches = matches
            best_match = template
    
    # Use specific response if we found good keyword matches
    if best_match and max_matches > 0:
        return {
            "response": best_match["response"],
            "sources": [],
            "chunks_used": 0,
            "fallback_used": True,
            "fallback_reason": "RAG service unavailable - keyword-based response",
            "quality_score": 0.6,
            "doc_status": "available_but_rag_failed",
            "keyword_matches": max_matches,
            "completed_docs": completed_docs
        }
    
    # Generic helpful response for unmatched queries
    generic_responses = [
        f"Thank you for your question. While I'm currently unable to search through our {completed_docs} processed document(s) due to a technical issue, I'm here to help. Please try rephrasing your question or contact your college administration for immediate assistance.",
        
        f"I understand you're looking for information. Although I can't access our document database right now, your college administration or the relevant department can provide you with accurate and up-to-date information about your query.",
        
        f"I apologize, but I'm experiencing technical difficulties accessing our knowledge base of {completed_docs} document(s). For immediate assistance with your question, please contact your college's help desk or the appropriate department directly."
    ]
    
    # Rotate through generic responses based on time to provide variety
    response_index = int(time.time() / 3600) % len(generic_responses)  # Change every hour
    selected_response = generic_responses[response_index]
    
    return {
        "response": selected_response,
        "sources": [],
        "chunks_used": 0,
        "fallback_used": True,
        "fallback_reason": "RAG service unavailable - generic helpful response",
        "quality_score": 0.5,
        "doc_status": "available_but_rag_failed",
        "completed_docs": completed_docs,
        "total_docs": doc_count,
        "doc_status_breakdown": doc_status_info,
        "timestamp": datetime.utcnow().isoformat()
    }

