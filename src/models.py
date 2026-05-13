"""
Database models and configuration for Financial Therapist Chatbot.
Uses SQLAlchemy ORM with PostgreSQL backend.
"""

from sqlalchemy import create_engine, Column, String, DateTime, Integer, ForeignKey, Text, Enum as SQLEnum, JSON, inspect, text
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
    hashed_password = Column(String(255), nullable=True)
    hearts = Column(Integer, default=50, nullable=False)
    is_guest = Column(String(5), default="true")
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
    mood = Column(JSON, nullable=True)  # Store mood analysis data as JSON
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
        _ensure_users_columns()
        _ensure_conversation_message_mood_column()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise


def _ensure_users_columns():
    """Add missing users-table columns for backward compatibility in existing DBs."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    alter_statements: list[str] = []

    if "hashed_password" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255)")
    if "hearts" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN hearts INTEGER NOT NULL DEFAULT 50")
    if "is_guest" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN is_guest VARCHAR(5) DEFAULT 'true'")
    if "created_at" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN created_at DATETIME")
    if "updated_at" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN updated_at DATETIME")

    if not alter_statements:
        return

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))

        # Backfill non-null/default expectations for legacy rows.
        connection.execute(text("UPDATE users SET hearts = 50 WHERE hearts IS NULL"))
        connection.execute(text("UPDATE users SET is_guest = 'true' WHERE is_guest IS NULL"))
        connection.execute(text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        connection.execute(text("UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))

    logger.info("Ensured users schema compatibility columns are present")


def _ensure_conversation_message_mood_column():
    """Add the mood column to existing databases if it is missing."""
    inspector = inspect(engine)
    if "conversation_messages" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("conversation_messages")}
    if "mood" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE conversation_messages ADD COLUMN mood JSON"))
        logger.info("Added missing mood column to conversation_messages")

def get_db():
    """Dependency for getting database session in FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================== Helper Functions ====================
def get_or_create_user(db, user_id: str, email: str = None, name: str = None):
    """Get existing user or create a new one. New guests get 50 hearts on creation."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(
            id=user_id,
            email=email,
            name=name or "Guest",
            hashed_password=None,
            hearts=50,
            is_guest="true",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Auto-created guest user %s with 50 hearts", user_id)
    return user
