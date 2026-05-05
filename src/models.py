"""
Database models and configuration for Financial Therapist Chatbot.
Uses SQLAlchemy ORM with PostgreSQL backend.
"""

from sqlalchemy import create_engine, Column, String, DateTime, Integer, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os
import enum
import logging

logger = logging.getLogger(__name__)

# ==================== Database Configuration ====================
def get_database_url():
    """Get database URL with fallback for development."""
    url = os.getenv("DATABASE_URL")

    if not url:
        logger.warning("DATABASE_URL not set, using SQLite for development")
        url = "sqlite:///./test.db"

    return url

DATABASE_URL = get_database_url()
logger.info(f"Database connection configured: {DATABASE_URL}")

# Create engine and session
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==================== Enums ====================
class MessageRole(str, enum.Enum):
    """Enum for message roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

# ==================== Models ====================
class User(Base):
    """User model for storing user information."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"

class Conversation(Base):
    """Conversation model for storing conversation sessions."""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    message_count = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title={self.title})>"

class ConversationMessage(Base):
    """ConversationMessage model for storing individual messages in a conversation."""
    __tablename__ = "conversation_messages"

    id = Column(String(36), primary_key=True, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)  # For tracking token usage
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<ConversationMessage(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"

# ==================== Database Initialization ====================
def init_db():
    """Initialize the database by creating all tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def get_db():
    """Dependency for getting database session in FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================== Helper Functions ====================
def get_or_create_user(db, user_id: str, email: str = None, name: str = None):
    """Get existing user or create a new one."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(id=user_id, email=email, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
