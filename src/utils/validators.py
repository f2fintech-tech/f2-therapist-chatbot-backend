"""
Input validation and sanitization utilities.
Protects against common security vulnerabilities and data quality issues.
"""

import re
from typing import Optional
from pydantic import BaseModel, Field, validator, ValidationError
import logging

logger = logging.getLogger(__name__)

# ==================== Validation Constants ====================
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{3,32}$')
PHONE_PATTERN = re.compile(r'^\+?1?\d{9,15}$')

MAX_NAME_LENGTH = 100
MIN_NAME_LENGTH = 2
MAX_EMAIL_LENGTH = 255
MAX_MESSAGE_LENGTH = 5000
MIN_MESSAGE_LENGTH = 1
MAX_TITLE_LENGTH = 200

# ==================== Sanitization Functions ====================
def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize string input.
    - Remove leading/trailing whitespace
    - Remove special characters (keep letters, numbers, common punctuation)
    - Limit length
    
    Args:
        text: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not isinstance(text, str):
        raise ValueError("Input must be a string")
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t\r')
    
    # Apply max length if specified
    if max_length and len(text) > max_length:
        text = text[:max_length].strip()
    
    return text

def sanitize_email(email: str) -> str:
    """
    Sanitize and validate email address.
    
    Args:
        email: Email address to sanitize
        
    Returns:
        Sanitized email (lowercase)
        
    Raises:
        ValueError: If email is invalid
    """
    email = sanitize_string(email, MAX_EMAIL_LENGTH)
    
    if not EMAIL_PATTERN.match(email):
        raise ValueError("Invalid email format")
    
    return email.lower()

def sanitize_name(name: str) -> str:
    """
    Sanitize user name.
    Allows letters, numbers, spaces, hyphens, apostrophes.
    
    Args:
        name: Name to sanitize
        
    Returns:
        Sanitized name
        
    Raises:
        ValueError: If name is invalid
    """
    name = sanitize_string(name, MAX_NAME_LENGTH)
    
    if len(name) < MIN_NAME_LENGTH:
        raise ValueError(f"Name must be at least {MIN_NAME_LENGTH} characters")
    
    # Allow letters, numbers, spaces, hyphens, apostrophes
    if not re.match(r"^[a-zA-Z0-9\s\-']+$", name):
        raise ValueError("Name contains invalid characters")
    
    return name

def sanitize_message(message: str) -> str:
    """
    Sanitize chat message.
    
    Args:
        message: Message to sanitize
        
    Returns:
        Sanitized message
        
    Raises:
        ValueError: If message is invalid
    """
    message = sanitize_string(message, MAX_MESSAGE_LENGTH)
    
    if len(message) < MIN_MESSAGE_LENGTH:
        raise ValueError("Message cannot be empty")
    
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH}")
    
    return message

def sanitize_title(title: str) -> str:
    """
    Sanitize conversation title.
    
    Args:
        title: Title to sanitize
        
    Returns:
        Sanitized title
        
    Raises:
        ValueError: If title is invalid
    """
    title = sanitize_string(title, MAX_TITLE_LENGTH)
    
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"Title exceeds maximum length of {MAX_TITLE_LENGTH}")
    
    return title

# ==================== Validation Models ====================
class ValidatedUser(BaseModel):
    """Validated user model."""
    id: str = Field(..., description="User UUID")
    email: Optional[str] = Field(None, description="User email")
    name: Optional[str] = Field(None, description="User name")
    
    @validator('id')
    def validate_id(cls, v):
        """Validate user ID is valid UUID."""
        if not UUID_PATTERN.match(v):
            raise ValueError("Invalid user ID format")
        return v.lower()
    
    @validator('email', pre=True, always=True)
    def validate_email(cls, v):
        """Validate and sanitize email."""
        if v is None:
            return None
        try:
            return sanitize_email(v)
        except ValueError as e:
            raise ValueError(f"Invalid email: {str(e)}")
    
    @validator('name', pre=True, always=True)
    def validate_name(cls, v):
        """Validate and sanitize name."""
        if v is None:
            return None
        try:
            return sanitize_name(v)
        except ValueError as e:
            raise ValueError(f"Invalid name: {str(e)}")

class ValidatedMessage(BaseModel):
    """Validated message model."""
    content: str = Field(..., min_length=MIN_MESSAGE_LENGTH, max_length=MAX_MESSAGE_LENGTH)
    
    @validator('content')
    def validate_content(cls, v):
        """Validate and sanitize message content."""
        try:
            return sanitize_message(v)
        except ValueError as e:
            raise ValueError(f"Invalid message: {str(e)}")

class ValidatedConversation(BaseModel):
    """Validated conversation model."""
    id: str = Field(..., description="Conversation UUID")
    title: Optional[str] = Field(None, max_length=MAX_TITLE_LENGTH)
    user_id: str = Field(..., description="User UUID")
    
    @validator('id', 'user_id')
    def validate_uuid(cls, v):
        """Validate UUID format."""
        if not UUID_PATTERN.match(v):
            raise ValueError("Invalid UUID format")
        return v.lower()
    
    @validator('title', pre=True, always=True)
    def validate_title(cls, v):
        """Validate and sanitize title."""
        if v is None:
            return None
        try:
            return sanitize_title(v)
        except ValueError as e:
            raise ValueError(f"Invalid title: {str(e)}")

# ==================== Validation Helper Function ====================
def validate_and_sanitize(data: dict, validation_model: BaseModel) -> dict:
    """
    Validate and sanitize data using a Pydantic model.
    
    Args:
        data: Dictionary of data to validate
        validation_model: Pydantic model class to validate against
        
    Returns:
        Validated data as dictionary
        
    Raises:
        ValidationError: If validation fails
    """
    try:
        validated = validation_model(**data)
        return validated.dict()
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise