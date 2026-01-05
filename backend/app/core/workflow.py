"""
Workflow validation and status management utilities.
"""

def validate_status_transition(current_status: str, new_status: str) -> bool:
    """
    Validate that status transition is allowed.
    
    Valid transitions:
    - uploaded → pending_approval
    - pending_approval → approved, rejected
    - approved → processing
    - processing → completed, failed
    - rejected → [] (terminal state)
    - completed → [] (terminal state)
    - failed → processing (can retry)
    
    Args:
        current_status: Current document status
        new_status: Desired new status
        
    Returns:
        True if transition is valid, False otherwise
    """
    valid_transitions = {
        'uploaded': ['pending_approval'],
        'pending_approval': ['approved', 'rejected'],
        'approved': ['processing'],
        'processing': ['completed', 'failed'],
        'rejected': [],  # Terminal state
        'completed': [],  # Terminal state
        'failed': ['processing']  # Can retry
    }
    
    allowed = valid_transitions.get(current_status, [])
    return new_status in allowed

def log_status_change(
    client,
    document_id: str,
    old_status: str,
    new_status: str,
    changed_by: str,
    comments: str = None
):
    """
    Log a status change to the document_status_history table.
    
    Args:
        client: Supabase client
        document_id: Document UUID
        old_status: Previous status
        new_status: New status
        changed_by: User ID who made the change
        comments: Optional comments about the change
    """
    try:
        client.table("document_status_history").insert({
            "document_id": document_id,
            "old_status": old_status,
            "new_status": new_status,
            "changed_by": changed_by,
            "comments": comments
        }).execute()
    except Exception as e:
        # Log error but don't fail the operation
        print(f"Warning: Failed to log status change: {str(e)}")

