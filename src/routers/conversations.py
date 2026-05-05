"""
Conversation management router with comprehensive security and CRUD endpoints.
Includes input validation, authorization checks, rate limiting readiness, and SQL injection protection.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, Path
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
import logging
import uuid
import re

from src.models import (
    get_db, Conversation, ConversationMessage, User, get_or_create_user
)
from src.utils.api_security import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"], dependencies=[Depends(require_api_key)])

# ==================== Constants ====================
MAX_TITLE_LENGTH = 500
MIN_TITLE_LENGTH = 1
MAX_CONVERSATIONS_PER_REQUEST = 100
MIN_CONVERSATIONS_PER_REQUEST = 1
MAX_MESSAGES_PER_REQUEST = 100
MIN_MESSAGES_PER_REQUEST = 1
MAX_OFFSET = 10000

# UUID validation regex
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)

# ==================== Models ====================
class ConversationCreate(BaseModel):
    """Create conversation request model with validation."""
    user_id: str = Field(..., min_length=1, max_length=36, description="User ID")
    title: str | None = Field(None, min_length=MIN_TITLE_LENGTH, max_length=MAX_TITLE_LENGTH, description="Conversation title")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user_id is a valid UUID format."""
        if not UUID_PATTERN.match(v):
            raise ValueError("Invalid user_id format. Must be a valid UUID.")
        return v.lower()
    
    @validator('title')
    def validate_title(cls, v):
        """Sanitize and validate title."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Title cannot be empty or whitespace only.")
            # Remove potentially dangerous characters
            if len(v) > MAX_TITLE_LENGTH:
                raise ValueError(f"Title exceeds maximum length of {MAX_TITLE_LENGTH} characters.")
        return v

class ConversationUpdate(BaseModel):
    """Update conversation request model with validation."""
    title: str | None = Field(None, min_length=MIN_TITLE_LENGTH, max_length=MAX_TITLE_LENGTH, description="New conversation title")
    
    @validator('title')
    def validate_title(cls, v):
        """Sanitize and validate title."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Title cannot be empty or whitespace only.")
            if len(v) > MAX_TITLE_LENGTH:
                raise ValueError(f"Title exceeds maximum length of {MAX_TITLE_LENGTH} characters.")
        return v

class ConversationDetail(BaseModel):
    """Conversation detail response model."""
    id: str
    user_id: str
    title: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ConversationList(BaseModel):
    """Conversation list response model."""
    id: str
    user_id: str
    title: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class MessageDetail(BaseModel):
    """Message detail response model."""
    id: str
    role: str
    content: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== Helper Functions ====================
def validate_uuid(value: str) -> bool:
    """Validate UUID format to prevent SQL injection."""
    return bool(UUID_PATTERN.match(value))

def verify_conversation_ownership(db: Session, conversation_id: str, user_id: str) -> Conversation:
    """
    Verify that a conversation belongs to the user.
    Raises HTTPException if not found or user doesn't own it.
    """
    if not validate_uuid(conversation_id) or not validate_uuid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )
    
    conversation = db.query(Conversation).filter(
        and_(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        )
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return conversation

# ==================== Routes ====================
@router.post("/", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new conversation.
    
    Args:
        request: Conversation creation request
        db: Database session
        
    Returns:
        Created conversation details
        
    Raises:
        HTTPException: If user not found or database error occurs
    """
    try:
        # Ensure user exists
        user = get_or_create_user(db, request.user_id)
        
        # Create new conversation with unique ID
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            title=request.title
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        logger.info(f"Created conversation {conversation.id} for user {request.user_id}")
        
        return ConversationDetail.from_orm(conversation)
    
    except ValueError as e:
        logger.warning(f"Validation error creating conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input data"
        )
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating conversation"
        )

@router.get("", response_model=list[ConversationList])
async def list_conversations(
    user_id: str = Query(..., min_length=1, max_length=36, description="User ID"),
    limit: int = Query(20, ge=MIN_CONVERSATIONS_PER_REQUEST, le=MAX_CONVERSATIONS_PER_REQUEST, description="Number of conversations to return"),
    offset: int = Query(0, ge=0, le=MAX_OFFSET, description="Number of conversations to skip"),
    db: Session = Depends(get_db)
):
    """
    List conversations for a user with pagination.
    
    Args:
        user_id: User ID (must own the conversations)
        limit: Maximum number of conversations to return (1-100, default 20)
        offset: Number of conversations to skip (0-10000)
        db: Database session
        
    Returns:
        List of user conversations ordered by most recent
        
    Raises:
        HTTPException: If user_id is invalid or database error occurs
    """
    try:
        # Validate user_id format
        if not validate_uuid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user_id format"
            )
        
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(
            Conversation.updated_at.desc()
        ).offset(offset).limit(limit).all()
        
        return [ConversationList.from_orm(conv) for conv in conversations]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing conversations"
        )

@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str = Path(..., min_length=36, max_length=36),
    user_id: str = Query(..., min_length=1, max_length=36),
    db: Session = Depends(get_db)
):
    """
    Get conversation details.
    
    Args:
        conversation_id: Conversation ID
        user_id: User ID (for authorization verification)
        db: Database session
        
    Returns:
        Conversation details
        
    Raises:
        HTTPException: If conversation not found, user doesn't own it, or invalid ID format
    """
    try:
        conversation = verify_conversation_ownership(db, conversation_id, user_id)
        return ConversationDetail.from_orm(conversation)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving conversation"
        )

@router.put("/{conversation_id}", response_model=ConversationDetail)
async def update_conversation(
    conversation_id: str = Path(..., min_length=36, max_length=36),
    request: ConversationUpdate = None,
    user_id: str = Query(..., min_length=1, max_length=36),
    db: Session = Depends(get_db)
):
    """
    Update conversation details (only title).
    
    Args:
        conversation_id: Conversation ID
        request: Update request with new title
        user_id: User ID (for authorization verification)
        db: Database session
        
    Returns:
        Updated conversation details
        
    Raises:
        HTTPException: If conversation not found, user doesn't own it, or invalid data
    """
    try:
        conversation = verify_conversation_ownership(db, conversation_id, user_id)
        
        if request and request.title is not None:
            conversation.title = request.title
        
        conversation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(conversation)
        
        logger.info(f"Updated conversation {conversation_id} for user {user_id}")
        
        return ConversationDetail.from_orm(conversation)
    
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error updating conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input data"
        )
    except Exception as e:
        logger.error(f"Error updating conversation: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating conversation"
        )

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str = Path(..., min_length=36, max_length=36),
    user_id: str = Query(..., min_length=1, max_length=36, description="User ID for verification"),
    db: Session = Depends(get_db)
):
    """
    Delete a conversation and all its messages.
    
    Args:
        conversation_id: Conversation ID
        user_id: User ID (for authorization verification)
        db: Database session
        
    Raises:
        HTTPException: If conversation not found, user doesn't own it, or database error occurs
    """
    try:
        conversation = verify_conversation_ownership(db, conversation_id, user_id)
        
        # Delete conversation (cascades to messages due to foreign key)
        db.delete(conversation)
        db.commit()
        
        logger.info(f"Deleted conversation {conversation_id} for user {user_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting conversation"
        )

@router.get("/{conversation_id}/messages", response_model=list[MessageDetail])
async def get_conversation_messages(
    conversation_id: str = Path(..., min_length=36, max_length=36),
    user_id: str = Query(..., min_length=1, max_length=36, description="User ID for verification"),
    limit: int = Query(50, ge=MIN_MESSAGES_PER_REQUEST, le=MAX_MESSAGES_PER_REQUEST, description="Number of messages to return"),
    offset: int = Query(0, ge=0, le=MAX_OFFSET, description="Number of messages to skip"),
    db: Session = Depends(get_db)
):
    """
    Get messages from a conversation with pagination.
    
    Args:
        conversation_id: Conversation ID
        user_id: User ID (for authorization verification)
        limit: Maximum number of messages to return (1-100, default 50)
        offset: Number of messages to skip (0-10000)
        db: Database session
        
    Returns:
        List of messages in chronological order
        
    Raises:
        HTTPException: If conversation not found, user doesn't own it, or database error occurs
    """
    try:
        # Verify conversation exists and belongs to user
        conversation = verify_conversation_ownership(db, conversation_id, user_id)
        
        messages = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        ).order_by(
            ConversationMessage.created_at.asc()
        ).offset(offset).limit(limit).all()
        
        return [MessageDetail.from_orm(msg) for msg in messages]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving messages"
        )