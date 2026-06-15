"""Chat router — AI-powered natural language infrastructure queries."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.dependencies import CustomerContext, get_current_customer
from services.chat_service import process_chat

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[str]
    usage: Optional[dict] = None


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    customer: CustomerContext = Depends(get_current_customer),
):
    """Process a natural language query about the customer's AWS infrastructure."""
    history = [{"role": m.role, "content": m.content} for m in request.history]
    result = await process_chat(request.message, customer.customer_id, history)
    return ChatResponse(**result)
