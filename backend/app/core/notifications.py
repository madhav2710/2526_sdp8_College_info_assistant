from uuid import UUID
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.core.database import get_service_client
from app.models.notification import (
    Notification,
    NotificationCreate,
    NotificationUpdate,
    NotificationFilters,
    NotificationType
)
import httpx
import os


class NotificationManager:
    """Manages notification CRUD operations and business logic"""
    
    def __init__(self):
        self.client = get_service_client()
        self.supabase_url = os.getenv("supabase_url")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    async def create_notification(self, notification_data: NotificationCreate) -> Notification:
        """Create a new notification"""
        try:
            # Validate notification type
            if not isinstance(notification_data.type, NotificationType):
                raise ValueError(f"Invalid notification type: {notification_data.type}")
            
            # Prepare data for insertion
            insert_data = {
                "recipient_id": str(notification_data.recipient_id),
                "type": notification_data.type.value,
                "title": notification_data.title,
                "content": notification_data.content,
                "metadata": notification_data.metadata
            }
            
            # Use direct HTTP to ensure service key is used
            db_url = f"{self.supabase_url}/rest/v1/notifications"
            headers = {
                "Authorization": f"Bearer {self.service_key}",
                "ApiKey": self.service_key,
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    db_url, 
                    json=insert_data, 
                    headers=headers, 
                    timeout=10.0
                )
                
                if response.status_code not in [200, 201]:
                    raise Exception(f"Database error: {response.text}")
                
                result = response.json()
                if not result:
                    raise Exception("Failed to create notification")
                
                notification_record = result[0] if isinstance(result, list) else result
                return Notification(**notification_record)
                
        except Exception as e:
            raise Exception(f"Failed to create notification: {str(e)}")
    
    async def get_notifications(
        self, 
        user_id: UUID, 
        filters: Optional[NotificationFilters] = None
    ) -> List[Notification]:
        """Get notifications for a user with optional filtering"""
        try:
            # Build query parameters
            params = {
                "recipient_id": f"eq.{user_id}",
                "order": "created_at.desc"
            }
            
            if filters:
                if filters.unread_only:
                    params["is_read"] = "eq.false"
                
                if filters.notification_type:
                    params["type"] = f"eq.{filters.notification_type.value}"
                
                if filters.limit:
                    params["limit"] = str(filters.limit)
                
                if filters.offset:
                    params["offset"] = str(filters.offset)
            
            # Use direct HTTP to ensure service key is used
            db_url = f"{self.supabase_url}/rest/v1/notifications"
            headers = {
                "Authorization": f"Bearer {self.service_key}",
                "ApiKey": self.service_key,
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(
                    db_url,
                    params=params,
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    raise Exception(f"Database error: {response.text}")
                
                notifications_data = response.json()
                return [Notification(**notification) for notification in notifications_data]
                
        except Exception as e:
            raise Exception(f"Failed to get notifications: {str(e)}")
    
    async def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user"""
        try:
            params = {
                "recipient_id": f"eq.{user_id}",
                "is_read": "eq.false",
                "select": "count"
            }
            
            db_url = f"{self.supabase_url}/rest/v1/notifications"
            headers = {
                "Authorization": f"Bearer {self.service_key}",
                "ApiKey": self.service_key,
                "Content-Type": "application/json",
                "Prefer": "count=exact"
            }
            
            async with httpx.AsyncClient() as http_client:
                response = await http_client.head(
                    db_url,
                    params=params,
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    raise Exception(f"Database error: {response.text}")
                
                # Extract count from Content-Range header
                content_range = response.headers.get("Content-Range", "")
                if content_range:
                    # Format: "0-24/25" or "*/0"
                    count_part = content_range.split("/")[-1]
                    return int(count_part) if count_part.isdigit() else 0
                
                return 0
                
        except Exception as e:
            raise Exception(f"Failed to get unread count: {str(e)}")
    
    async def mark_as_read(self, notification_id: UUID, user_id: UUID) -> bool:
        """Mark a notification as read"""
        try:
            update_data = {
                "is_read": True,
                "read_at": datetime.utcnow().isoformat()
            }
            
            # Use direct HTTP to ensure service key is used
            db_url = f"{self.supabase_url}/rest/v1/notifications"
            params = {
                "id": f"eq.{notification_id}",
                "recipient_id": f"eq.{user_id}"
            }
            headers = {
                "Authorization": f"Bearer {self.service_key}",
                "ApiKey": self.service_key,
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as http_client:
                response = await http_client.patch(
                    db_url,
                    params=params,
                    json=update_data,
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code not in [200, 204]:
                    raise Exception(f"Database error: {response.text}")
                
                return True
                
        except Exception as e:
            raise Exception(f"Failed to mark notification as read: {str(e)}")
    
    async def delete_notification(self, notification_id: UUID, user_id: UUID) -> bool:
        """Delete a notification"""
        try:
            # Use direct HTTP to ensure service key is used
            db_url = f"{self.supabase_url}/rest/v1/notifications"
            params = {
                "id": f"eq.{notification_id}",
                "recipient_id": f"eq.{user_id}"
            }
            headers = {
                "Authorization": f"Bearer {self.service_key}",
                "ApiKey": self.service_key,
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as http_client:
                response = await http_client.delete(
                    db_url,
                    params=params,
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code not in [200, 204]:
                    raise Exception(f"Database error: {response.text}")
                
                return True
                
        except Exception as e:
            raise Exception(f"Failed to delete notification: {str(e)}")
    
    async def create_document_notification(
        self,
        recipient_ids: List[UUID],
        notification_type: NotificationType,
        document_id: UUID,
        document_filename: str,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Notification]:
        """Create document-related notifications for multiple recipients"""
        notifications = []
        
        # Define notification content based on type
        content_templates = {
            NotificationType.DOCUMENT_UPLOADED: {
                "title": "New Document Uploaded",
                "content": f'Document "{document_filename}" has been uploaded and is awaiting approval.'
            },
            NotificationType.DOCUMENT_APPROVED: {
                "title": "Document Approved", 
                "content": f'Your document "{document_filename}" has been approved for processing.'
            },
            NotificationType.DOCUMENT_REJECTED: {
                "title": "Document Rejected",
                "content": f'Your document "{document_filename}" has been rejected.'
            },
            NotificationType.DOCUMENT_PROCESSED: {
                "title": "Document Processing Complete",
                "content": f'Your document "{document_filename}" has been successfully processed and is now available for queries.'
            },
            NotificationType.DOCUMENT_FAILED: {
                "title": "Document Processing Failed",
                "content": f'Processing failed for document "{document_filename}". Please check the error details and try again.'
            }
        }
        
        template = content_templates.get(notification_type)
        if not template:
            raise ValueError(f"Unsupported notification type: {notification_type}")
        
        # Create base metadata
        metadata = {
            "document_id": str(document_id),
            "document_filename": document_filename
        }
        if additional_metadata:
            metadata.update(additional_metadata)
        
        # Create notifications for all recipients
        for recipient_id in recipient_ids:
            try:
                notification_data = NotificationCreate(
                    recipient_id=recipient_id,
                    type=notification_type,
                    title=template["title"],
                    content=template["content"],
                    metadata=metadata
                )
                
                notification = await self.create_notification(notification_data)
                notifications.append(notification)
                
            except Exception as e:
                # Log error but continue with other recipients
                print(f"Failed to create notification for recipient {recipient_id}: {str(e)}")
        
        return notifications


# Global instance for use across the application
notification_manager = NotificationManager()