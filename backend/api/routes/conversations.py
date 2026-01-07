"""Conversation API routes for managing chat sessions."""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import uuid

from api.database import get_database
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/conversations", tags=["Conversations"])


# ============ Models ============

class MessageCreate(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    model_used: Optional[str] = None
    provider_used: Optional[str] = None
    tokens_used: Optional[int] = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    timestamp: str
    model_used: Optional[str] = None
    provider_used: Optional[str] = None
    tokens_used: Optional[int] = None


class ConversationCreate(BaseModel):
    title: str = "New Repo"
    user_id: str = "default"
    provider: str = "glm"
    model_name: str = "glm-4.6"
    system_prompt: Optional[str] = None
    metadata: Optional[str] = None  # JSON string for github_repo, pull_requests, etc.


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None
    metadata: Optional[str] = None  # JSON string for github_repo, pull_requests, etc.


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    provider: str
    model_name: str
    system_prompt: Optional[str] = None
    metadata: Optional[str] = None  # JSON string for github_repo, pull_requests, etc.
    messages: List[MessageResponse] = []


class ConversationListItem(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    provider: str
    model_name: str
    message_count: int


# ============ Routes ============

@router.get("", response_model=List[ConversationListItem])
async def list_conversations(user_id: str = "default") -> List[ConversationListItem]:
    """List all conversations for a user."""
    db = get_database()
    conversations = db.get_all_conversations(user_id)

    return [
        ConversationListItem(
            id=conv["id"],
            user_id=conv["user_id"],
            title=conv["title"],
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
            provider=conv["provider"],
            model_name=conv["model_name"],
            message_count=conv.get("message_count", 0)
        )
        for conv in conversations
    ]


@router.post("", response_model=ConversationResponse)
async def create_conversation(data: ConversationCreate) -> ConversationResponse:
    """Create a new conversation."""
    db = get_database()
    conv_id = str(uuid.uuid4())

    conv = db.create_conversation(conv_id, {
        "user_id": data.user_id,
        "title": data.title,
        "provider": data.provider,
        "model_name": data.model_name,
        "system_prompt": data.system_prompt,
        "metadata": data.metadata,
    })

    logger.info(f"Created conversation: {conv_id}")

    return ConversationResponse(
        id=conv["id"],
        user_id=conv["user_id"],
        title=conv["title"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        provider=conv["provider"],
        model_name=conv["model_name"],
        system_prompt=conv.get("system_prompt"),
        metadata=conv.get("metadata"),
        messages=[]
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str) -> ConversationResponse:
    """Get a conversation with all its messages."""
    db = get_database()
    conv = db.get_conversation(conversation_id)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = db.get_messages(conversation_id)

    return ConversationResponse(
        id=conv["id"],
        user_id=conv["user_id"],
        title=conv["title"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        provider=conv["provider"],
        model_name=conv["model_name"],
        system_prompt=conv.get("system_prompt"),
        metadata=conv.get("metadata"),
        messages=[MessageResponse(**msg) for msg in messages]
    )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(conversation_id: str, data: ConversationUpdate) -> ConversationResponse:
    """Update a conversation."""
    db = get_database()

    if not db.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    updates = {"updated_at": datetime.utcnow().isoformat()}
    if data.title is not None:
        updates["title"] = data.title
    if data.provider is not None:
        updates["provider"] = data.provider
    if data.model_name is not None:
        updates["model_name"] = data.model_name
    if data.system_prompt is not None:
        updates["system_prompt"] = data.system_prompt
    if data.metadata is not None:
        updates["metadata"] = data.metadata

    conv = db.update_conversation(conversation_id, updates)
    messages = db.get_messages(conversation_id)

    return ConversationResponse(
        id=conv["id"],
        user_id=conv["user_id"],
        title=conv["title"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        provider=conv["provider"],
        model_name=conv["model_name"],
        system_prompt=conv.get("system_prompt"),
        metadata=conv.get("metadata"),
        messages=[MessageResponse(**msg) for msg in messages]
    )


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict:
    """Delete a conversation."""
    db = get_database()

    if not db.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    logger.info(f"Deleted conversation: {conversation_id}")
    return {"success": True, "message": "Conversation deleted"}


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def add_message(conversation_id: str, data: MessageCreate) -> MessageResponse:
    """Add a message to a conversation."""
    db = get_database()

    if not db.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    message_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    message = {
        "id": message_id,
        "conversation_id": conversation_id,
        "role": data.role,
        "content": data.content,
        "timestamp": now,
        "model_used": data.model_used,
        "provider_used": data.provider_used,
        "tokens_used": data.tokens_used,
    }

    result = db.add_message(conversation_id, message)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to add message")

    return MessageResponse(**result)


class MessageUpdate(BaseModel):
    content: str


@router.patch("/{conversation_id}/messages/{message_id}", response_model=MessageResponse)
async def update_message(conversation_id: str, message_id: str, data: MessageUpdate) -> MessageResponse:
    """Update a message's content."""
    db = get_database()

    if not db.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    updated_msg = db.update_message(conversation_id, message_id, data.content)
    if updated_msg:
        return MessageResponse(**updated_msg)

    raise HTTPException(status_code=404, detail="Message not found")
