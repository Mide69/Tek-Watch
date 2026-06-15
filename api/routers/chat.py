"""Chat router — AI-powered natural language infrastructure queries."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from auth.dependencies import CustomerContext, get_current_customer
from rate_limit import limiter
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
@limiter.limit("10/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    customer: CustomerContext = Depends(get_current_customer),
):
    """Process a natural language query about the customer's AWS infrastructure.

    Limited to 10 requests/minute per IP to protect Anthropic API spend.
    """
    history = [{"role": m.role, "content": m.content} for m in body.history]
    result = await process_chat(body.message, customer.customer_id, history)
    return ChatResponse(**result)
