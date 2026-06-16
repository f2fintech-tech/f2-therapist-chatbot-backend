"""
Database models and configuration for Financial Therapist Chatbot.
Uses SQLAlchemy ORM with PostgreSQL backend.
"""

from sqlalchemy import create_engine, Column, String, DateTime, Integer, Float, ForeignKey, Text, Enum as SQLEnum, JSON, inspect, text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os
import enum
import logging

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

# ==================== Database Configuration ====================
def get_database_url():
    """Get database URL with fallback for development."""
    # Check individual PostgreSQL connection parameters first
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USERNAME")
    db_pass = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_DATABASE")

    if db_host and db_user and db_pass and db_name:
        # Construct postgresql connection URL
        return f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

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
    phone = Column(String(32), nullable=True)
    location = Column(String(255), nullable=True)
    occupation = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    hearts = Column(Integer, default=50, nullable=False)
    is_guest = Column(String(5), default="true")
    wellness_score = Column(Integer, default=50, nullable=False)
    wellness_tier = Column(String(32), default="Building", nullable=False)
    momentum_score = Column(Integer, default=50, nullable=False)
    financial_goal = Column(String(255), nullable=True)
    financial_stress = Column(String(255), nullable=True)
    risk_tolerance = Column(String(255), nullable=True)
    monthly_income = Column(String(255), nullable=True)
    therapy_style = Column(String(255), nullable=True)
    goals = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    consolidated_profile = relationship("UserConsolidatedProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

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


class TestResult(Base):
    """Stored result for a completed financial wellness test."""

    __tablename__ = "test_results"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    test_type = Column(String(64), nullable=False, index=True)
    raw_score = Column(Float, nullable=False)
    normalized_score = Column(Float, nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    insights = Column(JSON, nullable=True)
    category_breakdown = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MoodLiveState(Base):
    """Latest live mood sample captured from chat."""

    __tablename__ = "mood_live_state"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True, index=True)
    stress = Column(Integer, default=50, nullable=False)
    urgency = Column(Integer, default=50, nullable=False)
    openness = Column(Integer, default=50, nullable=False)
    willingness = Column(Integer, default=50, nullable=False)
    emotion = Column(Integer, default=50, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MoodTrendState(Base):
    """Smoothed emotional trend state used by the wellness engine."""

    __tablename__ = "mood_trend_state"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True, index=True)
    stress_trend = Column(Integer, default=50, nullable=False)
    urgency_trend = Column(Integer, default=50, nullable=False)
    openness_trend = Column(Integer, default=50, nullable=False)
    willingness_trend = Column(Integer, default=50, nullable=False)
    emotion_trend = Column(Integer, default=50, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class WellnessBreakdown(Base):
    """Current calculated wellness breakdown for a user."""

    __tablename__ = "wellness_breakdown"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True, index=True)
    money_iq = Column(Integer, default=50, nullable=False)
    debt_health = Column(Integer, default=50, nullable=False)
    financial_safety = Column(Integer, default=50, nullable=False)
    credit_health = Column(Integer, default=50, nullable=False)
    loan_comfort = Column(Integer, default=50, nullable=False)
    mood_health = Column(Integer, default=50, nullable=False)
    overall_score = Column(Integer, default=50, nullable=False)
    wellness_tier = Column(String(32), default="Building", nullable=False)
    momentum_score = Column(Integer, default=50, nullable=False)
    insights = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserConsolidatedProfile(Base):
    """Consolidated profile containing user settings, page activities, calculator history, and chatbot interactions in JSON format."""
    __tablename__ = "user_consolidated_profiles"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True, index=True)
    data = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="consolidated_profile")

    def __repr__(self):
        return f"<UserConsolidatedProfile(user_id={self.user_id})>"


class UserCreditReport(Base):
    """Stores fetched credit score reports (JSON + PDF link) mapped to users."""
    __tablename__ = "user_credit_reports"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    bureau = Column(String(32), nullable=False) # "cibil" or "experian"
    score = Column(Integer, nullable=False)
    report_data = Column(JSON, nullable=False)  # The normalized JSON report (cached result)
    raw_bureau_json = Column(JSON, nullable=True)  # The raw API response from the bureau — used to re-parse on demand
    pdf_url = Column(Text, nullable=True)       # The download link/URL for the PDF report
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserLoanCalculatorActivity(Base):
    """Stores user activity logs on the loan calculator tools."""
    __tablename__ = "user_loan_calculator_activities"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    calculator_type = Column(String(32), nullable=False, index=True)  # "emi", "compare", "prepayment", "eligibility"
    loan_type = Column(String(32), nullable=True)  # "home", "business", etc.
    inputs = Column(JSON, nullable=False)  # Map of all input values filled by the user
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<UserLoanCalculatorActivity(id={self.id}, user_id={self.user_id}, calculator_type={self.calculator_type})>"


class Advisor(Base):
    """Advisor model representing the expert profile."""
    __tablename__ = "advisors"

    f2_fintech_id = Column(String(255), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    designation = Column(String(255), nullable=False)
    avatar_url = Column(String(1000), nullable=True)
    availability = Column(String(32), default="available", nullable=False)  # "available" or "unavailable"
    expertise = Column(JSON, nullable=True)  # List of strings
    strength = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True)
    rating = Column(Float, default=0.0, nullable=False)
    reviews_count = Column(Integer, default=0, nullable=False)
    next_slot = Column(String(255), nullable=True)
    category = Column(String(255), nullable=False)
    fee = Column(Integer, default=899, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    password_hash = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<Advisor(f2_fintech_id={self.f2_fintech_id}, name={self.name})>"


class AdvisorAppointment(Base):
    """AdvisorAppointment model representing consultations/bookings for advisors."""
    __tablename__ = "advisor_appointments"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    advisor_id = Column(String(255), ForeignKey("advisors.f2_fintech_id"), nullable=False, index=True)
    advisor_name = Column(String(255), nullable=False)
    date = Column(String(64), nullable=False)
    time = Column(String(64), nullable=False)
    notes = Column(Text, nullable=True)
    booked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    cancelled = Column(Boolean, default=False, nullable=False)
    rating = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)
    meet_url = Column(String(1000), nullable=True)
    joined = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<AdvisorAppointment(id={self.id}, user_id={self.user_id}, advisor_id={self.advisor_id})>"


# ==================== Database Initialization ====================
def init_db():
    """Initialize the database by creating all tables."""
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_users_columns()
        _ensure_conversation_message_mood_column()
        _ensure_user_wellness_columns()
        _ensure_credit_report_columns()
        _ensure_advisor_password_column()
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
    if "phone" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN phone VARCHAR(32)")
    if "location" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN location VARCHAR(255)")
    if "occupation" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN occupation VARCHAR(255)")
    if "bio" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN bio TEXT")
    if "hearts" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN hearts INTEGER NOT NULL DEFAULT 50")
    if "is_guest" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN is_guest VARCHAR(5) DEFAULT 'true'")
    if "financial_goal" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN financial_goal VARCHAR(255)")
    if "financial_stress" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN financial_stress VARCHAR(255)")
    if "risk_tolerance" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN risk_tolerance VARCHAR(255)")
    if "monthly_income" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN monthly_income VARCHAR(255)")
    if "therapy_style" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN therapy_style VARCHAR(255)")
    if "goals" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN goals JSON")
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


def _ensure_user_wellness_columns():
    """Add missing wellness columns to existing users tables."""

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    alter_statements: list[str] = []

    if "wellness_score" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN wellness_score INTEGER NOT NULL DEFAULT 50")
    if "wellness_tier" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN wellness_tier VARCHAR(32) NOT NULL DEFAULT 'Building'")
    if "momentum_score" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN momentum_score INTEGER NOT NULL DEFAULT 50")

    if not alter_statements:
        return

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))
        connection.execute(text("UPDATE users SET wellness_score = 50 WHERE wellness_score IS NULL"))
        connection.execute(text("UPDATE users SET wellness_tier = 'Building' WHERE wellness_tier IS NULL"))
        connection.execute(text("UPDATE users SET momentum_score = 50 WHERE momentum_score IS NULL"))

    logger.info("Ensured user wellness columns are present")


def _ensure_credit_report_columns():
    """Add raw_bureau_json column to user_credit_reports if it is missing (backward compatibility)."""
    inspector = inspect(engine)
    if "user_credit_reports" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("user_credit_reports")}
    if "raw_bureau_json" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE user_credit_reports ADD COLUMN raw_bureau_json JSON"))
        logger.info("Added raw_bureau_json column to user_credit_reports")

def _ensure_advisor_password_column():
    """Add password_hash column to advisors table if it is missing (backward compatibility)."""
    inspector = inspect(engine)
    if "advisors" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("advisors")}
    if "password_hash" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE advisors ADD COLUMN password_hash VARCHAR(255)"))
        logger.info("Added password_hash column to advisors")

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
            wellness_score=50,
            wellness_tier="Building",
            momentum_score=50,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Auto-created guest user %s with 50 hearts", user_id)
    return user
