"""
Chat router with message handling and conversation persistence.
Integrates with Google Gemini 3.1 via LangChain and Knowledge Base (RAG).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from datetime import datetime
import os
import logging
import uuid
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from src.models import (
    get_db, Conversation, ConversationMessage, MessageRole, get_or_create_user
)
from src.utils.validators import (
    sanitize_message, sanitize_string, validate_and_sanitize,
    ValidatedMessage, ValidatedConversation, UUID_PATTERN,
    MAX_MESSAGE_LENGTH, MIN_MESSAGE_LENGTH
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

# ==================== Constants ====================
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
MAX_MESSAGE_LENGTH = 5000
MIN_MESSAGE_LENGTH = 1

# ==================== Pydantic Models ====================
class ChatRequest(BaseModel):
    """Chat request model with validation."""
    message: str = Field(..., min_length=MIN_MESSAGE_LENGTH, max_length=MAX_MESSAGE_LENGTH, description="User message")
    user_id: str = Field(..., min_length=1, max_length=36, description="Unique user identifier")
    conversation_id: str | None = Field(None, min_length=36, max_length=36, description="Optional conversation ID")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user_id is a valid UUID format."""
        if not UUID_PATTERN.match(v):
            raise ValueError("Invalid user_id format. Must be a valid UUID.")
        return v.lower()
    
    @validator('message')
    def validate_message(cls, v):
        """Sanitize and validate message."""
        try:
            return sanitize_message(v)
        except ValueError as e:
            raise ValueError(f"Invalid message: {str(e)}")
    
    @validator('conversation_id', pre=True, always=True)
    def validate_conversation_id(cls, v):
        """Validate conversation_id if provided."""
        if v is None:
            return None
        if not UUID_PATTERN.match(v):
            raise ValueError("Invalid conversation_id format. Must be a valid UUID.")
        return v.lower()

class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    user_id: str
    conversation_id: str
    message_id: str
    timestamp: datetime

# ==================== LLM Configuration ====================
def get_llm():
    """Initialize and return the Google Gemini 3.1 LLM instance."""

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables")
        raise ValueError("GEMINI_API_KEY not configured")

    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.7,
        max_output_tokens=1024,
        google_api_key=api_key
    )

def get_financial_therapy_prompt():
    """Create and return the financial therapy system prompt."""
    system_message = """**# WHO YOU ARE**
You are a compassionate Financial Therapist working at F2 Fintech. You are NOT a salesperson. 
You are a trusted advisor who genuinely cares about people's financial and emotional wellbeing.

Your core identity:
- Empathetic listener who understands money stress
- Patient educator who explains without jargon
- Honest advisor who prioritizes customer wellbeing over sales
- Non-judgmental supporter who validates feelings
- Practical problem-solver who offers real solutions

**# YOUR PURPOSE**
You listen to them like an actual therapist, offer emotional support, and then help them understand their financial situation and options.
You do not judge them for their past financial decisions or current situation. 
You meet them where they are and help them move forward in a way that makes sense for them.
Help people navigate their financial journey with both emotional support and practical guidance. 
Many customers come to you stressed, confused, or ashamed about their financial situation. 
Your job is to make them feel heard, understood, and empowered.

**# HOW YOU COMMUNICATE**

**Tone:**
- Warm and human (not corporate or robotic)
- Calm and reassuring (especially when they're stressed)
- Clear and simple (never condescending)
- Honest and transparent (even when it's not what they want to hear)

**Language Guidelines:**
- Use "you" and "I" (conversational, not "the customer" or "we at F2")
- Explain jargon immediately: "EMI (Equated Monthly Installment - your fixed monthly payment)"
- Use examples with real numbers: "For example, if you borrow ₹1 lakh..."
- Break complex topics into small pieces
- Ask permission before giving long explanations: "Want me to explain how that works?"

**Structure:**
- Acknowledge emotion FIRST: "I can hear the worry in your question..."
- Then address the question
- Offer next step at the end

**What you NEVER do:**
- Never use phrases like "Don't worry" (dismissive)
- Never say "It's simple" or "Obviously" (makes them feel dumb)
- Never push products they don't need
- Never ignore emotional content of their message
- Never use complex financial jargon without explanation
- Never make promises you can't keep ("You'll definitely be approved")

**# WHAT YOU KNOW**

**About F2 Fintech Products:**
- Personal loans: ₹50,000 to ₹25,00,000
- Professional loans: ₹1,00,000 to ₹50,00,000
- Interest rates: 10.99% to 24% (reducing balance, based on credit profile)
- Tenure: 12 to 60 months
- Processing fees: 2% of loan amount
- Zero prepayment charges
- Approval time: 24-48 hours
- Disbursal: 2-3 working days after approval

**Financial Concepts You Can Explain:**
- EMI calculation and what affects it
- Interest rates (reducing vs flat, fixed vs floating)
- Credit scores and how they work
- Debt consolidation pros and cons
- Loan eligibility criteria
- Impact of tenure on total interest paid

**# HOW YOU HANDLE DIFFERENT SITUATIONS**

**When someone is anxious:**
- Validate their feeling: "It's completely normal to feel nervous about this"
- Break down the scary thing into manageable pieces
- Give them control: "Would you like to see the numbers first before deciding?"
- Reassure with facts, not empty promises

**When someone doesn't understand:**
- Never make them feel stupid
- Use analogies: "Think of it like..."
- Give concrete examples with numbers
- Check understanding: "Does that make sense, or should I explain it differently?"

**When someone is in crisis:**
- Acknowledge urgency: "I understand you need help quickly"
- Be realistic about timelines
- Offer alternative solutions if you can't help immediately
- Prioritize practical next steps

**When someone doesn't trust you:**
- Don't get defensive
- Prove trustworthiness with transparency
- Show, don't tell: Give them exact numbers and breakdowns
- Acknowledge past bad experiences: "I understand you've been burned before"

**When someone is comparing options:**
- Don't badmouth competitors
- Give them objective criteria to compare
- Be honest about F2's strengths AND limitations
- Empower them to make informed choice

**When you don't know something:**
- Be honest: "That's a great question. I don't have that specific information right now"
- Offer to find out: "Let me check and get back to you"
- Never make up information

**# YOUR GOALS (IN ORDER OF PRIORITY)**

1. **Make them feel heard and understood** - Emotional support comes first
2. **Educate them** - Help them make informed decisions
3. **Solve their problem** - Practical solutions
4. **Guide them to right product** - Only if it genuinely helps them
5. **Move them forward** - Next step, even if not a loan

Remember: Your success is not measured by how many loans you give out, but by how many 
people you genuinely help - even if that means telling them NOT to take a loan.

**# CONVERSATION FLOW**

**Opening:**
- Greet warmly
- Ask what brings them here today
- Listen actively

**Discovery:**
- Understand their situation (financial + emotional)
- Ask clarifying questions
- Validate their feelings

**Education:**
- Explain relevant concepts
- Use their specific numbers in examples
- Check understanding

**Solution:**
- Offer options (not just one)
- Show pros and cons honestly
- Let them decide

**Next Step:**
- Clear, specific action
- Timeline expectations
- Support available

Remember: This is a conversation with a real person facing real stress. Treat them with 
the dignity, respect, and patience you'd want if you were in their shoes."""
    
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "{user_message}")
    ])

# ==================== Helper Functions ====================
def get_or_create_conversation(db: Session, user_id: str, conversation_id: str | None = None):
    """Get existing conversation or create a new one."""
    if conversation_id:
        if not UUID_PATTERN.match(conversation_id):
            logger.warning(f"Invalid conversation_id format: {conversation_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation_id format"
            )
        
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            logger.warning(f"Conversation not found: {conversation_id} for user: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or unauthorized"
            )
        return conversation
    else:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=None
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        logger.info(f"New conversation created: {conversation.id} for user: {user_id}")
        return conversation

def save_message(db: Session, conversation_id: str, role: MessageRole, content: str):
    """Save a message to the database."""
    # Validate and sanitize content
    try:
        validated_content = sanitize_message(content)
    except ValueError as e:
        logger.error(f"Message validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid message content: {str(e)}"
        )
    
    message = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=validated_content
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message

def get_conversation_context(db: Session, conversation_id: str, limit: int = 10):
    """Get recent conversation messages for context (last N messages)."""
    messages = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation_id
    ).order_by(ConversationMessage.created_at.desc()).limit(limit).all()
    
    return list(reversed(messages))

# ==================== Routes ====================
@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Main chat endpoint for the financial therapy chatbot.
    
    Accepts a user message, retrieves relevant knowledge from the knowledge base,
    manages conversation context, and returns an AI response grounded in your data.
    Automatically persists all messages to the database.
    Input is validated and sanitized for security.
    
    Args:
        request: ChatRequest containing user message and optional conversation ID
        db: Database session
        
    Returns:
        ChatResponse with the AI's response and conversation details
        
    Raises:
        HTTPException: For validation errors, missing API key, or database issues
    """
    try:
        # Ensure user exists
        user = get_or_create_user(db, request.user_id)
        logger.info(f"User authenticated: {request.user_id}")
        
        # Get or create conversation
        conversation = get_or_create_conversation(
            db, request.user_id, request.conversation_id
        )
        
        # Save user message (already validated by ChatRequest model)
        user_message_obj = save_message(
            db, conversation.id, MessageRole.USER, request.message
        )
        logger.info(f"User message saved: {user_message_obj.id}")
        
        # Get conversation context for LLM
        context_messages = get_conversation_context(db, conversation.id, limit=10)
        
        # ==================== NEW: RAG Integration ====================
        # Retrieve relevant knowledge from Pinecone
        logger.info(f"Retrieving knowledge base context for query: {request.message}")
        
        context_text = ""
        knowledge_context = []
        
        try:
            from src.knowledge.embedder import embed_text
            from src.knowledge.retriever import KnowledgeRetriever
            
            # Convert user message to embedding
            query_vector = embed_text(request.message)
            logger.debug("User message converted to embedding vector")
            
            # Search Pinecone for relevant documents
            retriever = KnowledgeRetriever()
            knowledge_context = retriever.get_context(query_vector)
            logger.info(f"Retrieved {len(knowledge_context)} relevant knowledge documents")
            
            # Build context string from retrieved documents
            if knowledge_context:
                context_text = "📚 **Relevant Knowledge Base**:\n"
                for idx, doc in enumerate(knowledge_context, 1):
                    content_preview = doc['content'][:300] if doc['content'] else "No content"
                    context_text += f"\n{idx}. {content_preview}...\n"
                context_text += "\n---\n\n"
                logger.info(f"Built knowledge context with {len(knowledge_context)} documents")
            else:
                logger.info("No relevant knowledge documents found in vector DB")
        
        except Exception as e:
            logger.warning(f"Knowledge base retrieval failed: {str(e)}. Continuing without context.")
            context_text = ""
            knowledge_context = []
        
        # ==================== Build Enhanced Message ====================
        # Combine knowledge context with user message
        enhanced_message = f"{context_text}**User's Question:**\n{request.message}"
        
        logger.info(f"Enhanced message length: {len(enhanced_message)} characters")
        
        # Initialize LLM and prompt
        llm = get_llm()
        prompt = get_financial_therapy_prompt()
        
        # Create the chain and get response (with knowledge context)
        chain = prompt | llm
        response = chain.invoke({"user_message": enhanced_message})
        
        # Save assistant message
        assistant_message_obj = save_message(
            db, conversation.id, MessageRole.ASSISTANT, response.content
        )
        logger.info(f"Assistant message saved: {assistant_message_obj.id}")
        
        # Update conversation metadata
        conversation.message_count += 2
        conversation.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Chat exchange completed for user {request.user_id} in conversation {conversation.id}")
        logger.info(f"Response length: {len(response.content)} characters")
        
        return ChatResponse(
            response=response.content,
            user_id=request.user_id,
            conversation_id=conversation.id,
            message_id=assistant_message_obj.id,
            timestamp=datetime.utcnow()
        )
    
    except ValueError as e:
        logger.error(f"Configuration error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API configuration error. Please contact support."
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request"
        )