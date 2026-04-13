import datetime as dt
import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import HTTPException

from app.core.basic_chat import generate_basic_response
from app.core.database import get_service_client, supabase

import time

logger = logging.getLogger(__name__)


rate_limit_cache: Dict[str, List[float]] = {}


def check_and_update_rate_limit(
    user_id: str, max_requests: int = 10, window_seconds: int = 60
) -> None:
    current_time = time.time()

    stale_cutoff = current_time - window_seconds
    for uid in list(rate_limit_cache.keys()):
        recent = [t for t in rate_limit_cache[uid] if t > stale_cutoff]
        if recent:
            rate_limit_cache[uid] = recent
        else:
            del rate_limit_cache[uid]

    user_requests = [t for t in rate_limit_cache.get(user_id, []) if t > stale_cutoff]
    if len(user_requests) >= max_requests:
        raise ValueError(
            "Too many requests. Please wait before sending another message."
        )

    user_requests.append(current_time)
    rate_limit_cache[user_id] = user_requests


def clear_rate_limit_cache() -> None:
    rate_limit_cache.clear()


def _store_assistant_message(
    client: Any,
    conversation_id: str,
    content: str,
    sources_data: list[Any],
    enhanced_metadata: dict[str, Any],
) -> None:
    assistant_message_data = {
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": content,
        "created_at": datetime.now(dt.UTC).isoformat(),
    }

    attempts = [
        {
            **assistant_message_data,
            "sources": sources_data,
            "metadata": enhanced_metadata,
        },
        {**assistant_message_data, "sources": sources_data},
        {**assistant_message_data, "metadata": enhanced_metadata},
        assistant_message_data,
    ]

    assistant_message_response = None
    last_error = None

    for index, attempt_data in enumerate(attempts):
        try:
            assistant_message_response = (
                client.table("messages").insert(attempt_data).execute()
            )
            if assistant_message_response.data:
                if index > 0:
                    logger.warning(
                        "Message stored using fallback attempt %s (some columns may be missing from database)",
                        index + 1,
                    )
                break
        except Exception as attempt_error:
            last_error = attempt_error
            if index < len(attempts) - 1:
                error_msg = str(attempt_error).lower()
                if (
                    "column" in error_msg
                    or "metadata" in error_msg
                    or "sources" in error_msg
                ):
                    logger.debug(
                        "Attempt %s failed due to missing column, trying next approach",
                        index + 1,
                    )
                    continue
            break

    if not assistant_message_response or not assistant_message_response.data:
        raise Exception(
            "Failed to store assistant message after all attempts. "
            f"Last error: {str(last_error)}"
        )


async def create_chat_response(
    message: Any, current_user: dict[str, Any]
) -> dict[str, Any]:
    user_id_str = str(message.user_id)
    authenticated_user_id = str(current_user["user_id"])

    if authenticated_user_id != user_id_str:
        logger.warning(
            "User %s attempted to send message as user %s",
            authenticated_user_id,
            message.user_id,
        )
        raise HTTPException(
            status_code=403,
            detail="Not authorized to send messages for this user",
        )

    try:
        check_and_update_rate_limit(authenticated_user_id)
    except ValueError as exc:
        logger.warning("Rate limit exceeded for user %s", authenticated_user_id)
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    logger.info(
        "Processing chat message from user %s in conversation %s",
        user_id_str,
        message.conversation_id,
    )

    try:
        client = get_service_client()

        try:
            profile = (
                client.table("profiles")
                .select("college_id, role")
                .eq("id", user_id_str)
                .execute()
            )
            if not profile.data:
                logger.error("User profile not found for user_id: %s", message.user_id)
                raise HTTPException(status_code=404, detail="User profile not found")

            college_id = profile.data[0]["college_id"]
            user_role = profile.data[0]["role"]

            if not college_id:
                logger.error(
                    "User %s is not associated with a college", message.user_id
                )
                raise HTTPException(
                    status_code=400, detail="User is not associated with a college"
                )

        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Error during user authentication: %s", str(exc))
            raise HTTPException(status_code=500, detail="Authentication error") from exc

        try:
            conv_check = (
                client.table("conversations")
                .select("id, user_id, college_id")
                .eq("id", str(message.conversation_id))
                .execute()
            )

            if not conv_check.data:
                conversation_data = {
                    "id": str(message.conversation_id),
                    "user_id": user_id_str,
                    "college_id": college_id,
                    "title": message.content[:50]
                    + ("..." if len(message.content) > 50 else ""),
                    "created_at": datetime.now(dt.UTC).isoformat(),
                }
                client.table("conversations").insert(conversation_data).execute()
                logger.info(
                    "Created new conversation %s for user %s",
                    message.conversation_id,
                    message.user_id,
                )
            else:
                existing_conv = conv_check.data[0]
                if existing_conv["user_id"] != user_id_str:
                    logger.warning(
                        "User %s attempted to access conversation %s owned by %s",
                        message.user_id,
                        message.conversation_id,
                        existing_conv["user_id"],
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="Not authorized to access this conversation",
                    )

                if existing_conv["college_id"] != college_id:
                    logger.warning(
                        "College ID mismatch for conversation %s",
                        message.conversation_id,
                    )
                    raise HTTPException(
                        status_code=403, detail="College access violation"
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "Error managing conversation %s: %s",
                message.conversation_id,
                str(exc),
            )
            raise HTTPException(
                status_code=500, detail="Conversation management error"
            ) from exc

        try:
            user_message_data = {
                "conversation_id": str(message.conversation_id),
                "role": "user",
                "content": message.content,
                "created_at": datetime.now(dt.UTC).isoformat(),
            }
            user_message_response = (
                client.table("messages").insert(user_message_data).execute()
            )

            if not user_message_response.data:
                raise Exception("Failed to store user message")
        except Exception as exc:
            logger.error("Error storing user message: %s", str(exc))
            raise HTTPException(
                status_code=500, detail="Failed to store message"
            ) from exc

        rag_result = None
        response_metadata: dict[str, Any] = {
            "rag_used": False,
            "fallback_used": False,
            "processing_time": 0.0,
            "error_details": None,
        }
        start_time = time.time()

        generate_rag_response = None
        try:
            from app.core.rag import (
                EmbeddingServiceError,
                RAGError,
                VectorStoreError,
                generate_rag_response,
            )

            rag_available = True
        except (ImportError, ModuleNotFoundError) as import_error:
            logger.warning("RAG module not available: %s", str(import_error))
            rag_available = False
            EmbeddingServiceError = None
            VectorStoreError = None
            RAGError = None

        try:
            if not rag_available:
                raise ImportError("RAG module dependencies not installed")
            if generate_rag_response is None:
                raise ImportError("RAG response generator not available")

            conversation_history = []
            try:
                history_response = (
                    client.table("messages")
                    .select("role, content, created_at")
                    .eq("conversation_id", str(message.conversation_id))
                    .order("created_at", desc=False)
                    .limit(10)
                    .execute()
                )

                if history_response.data:
                    conversation_history = [
                        {
                            "role": history_message["role"],
                            "content": history_message["content"],
                            "created_at": history_message["created_at"],
                        }
                        for history_message in history_response.data
                    ]
            except Exception as history_error:
                logger.warning(
                    "Failed to retrieve conversation history: %s", str(history_error)
                )

            rag_result = await generate_rag_response(
                query=message.content,
                college_id=college_id,
                conversation_history=conversation_history,
            )

            response_metadata["rag_used"] = True
            response_metadata["processing_time"] = time.time() - start_time

            if rag_result.get("fallback_used", False):
                response_metadata["fallback_used"] = True
            else:
                logger.info(
                    "RAG response generated successfully using %s chunks from %s sources",
                    rag_result.get("chunks_used", 0),
                    len(rag_result.get("sources", [])),
                )
        except (ImportError, ModuleNotFoundError) as import_error:
            logger.warning("RAG not available, using basic chat: %s", str(import_error))
            rag_result = await generate_basic_response(
                query=message.content,
                college_id=college_id,
            )
            response_metadata["fallback_used"] = True
            response_metadata["rag_used"] = False
            response_metadata["processing_time"] = time.time() - start_time
        except Exception as exc:
            if (
                rag_available
                and EmbeddingServiceError
                and isinstance(exc, EmbeddingServiceError)
            ):
                response_metadata["error_details"] = f"AI service error: {str(exc)}"
            elif (
                rag_available and VectorStoreError and isinstance(exc, VectorStoreError)
            ):
                response_metadata["error_details"] = (
                    f"Document search error: {str(exc)}"
                )
            elif rag_available and RAGError and isinstance(exc, RAGError):
                response_metadata["error_details"] = f"RAG system error: {str(exc)}"
            else:
                response_metadata["error_details"] = f"Unexpected error: {str(exc)}"

            try:
                rag_result = await generate_basic_response(
                    query=message.content,
                    college_id=college_id,
                )
                response_metadata["fallback_used"] = True
                response_metadata["processing_time"] = time.time() - start_time
            except Exception as fallback_error:
                logger.error("All fallback mechanisms failed: %s", str(fallback_error))
                raise HTTPException(
                    status_code=503,
                    detail="All chat services are temporarily unavailable",
                ) from fallback_error

        if not rag_result or not rag_result.get("response"):
            logger.error("No valid response generated for user %s", message.user_id)
            raise HTTPException(status_code=500, detail="Failed to generate response")

        sources_data = rag_result.get("sources", [])
        source_details = rag_result.get("source_details", [])
        chunks_used = rag_result.get("chunks_used", 0)
        quality_score = rag_result.get("quality_score", 0.0)
        conversation_context_used = rag_result.get("conversation_context_used", False)
        enhanced_metadata = {
            "rag_used": response_metadata["rag_used"],
            "fallback_used": response_metadata["fallback_used"],
            "chunks_used": chunks_used,
            "processing_time": response_metadata["processing_time"],
            "user_role": user_role,
            "college_id": college_id,
            "quality_score": quality_score,
            "conversation_context_used": conversation_context_used,
            "source_details": source_details,
        }

        try:
            _store_assistant_message(
                client=client,
                conversation_id=str(message.conversation_id),
                content=rag_result["response"],
                sources_data=sources_data,
                enhanced_metadata=enhanced_metadata,
            )
        except Exception as exc:
            logger.error("Error storing assistant message: %s", str(exc))
            raise HTTPException(
                status_code=500, detail="Failed to store response"
            ) from exc

        response_data = {
            "status": "success",
            "message": "Message processed successfully",
            "role": "assistant",
            "content": rag_result["response"],
            "sources": sources_data,
            "conversation_id": str(message.conversation_id),
            "metadata": {
                "chunks_used": chunks_used,
                "rag_enabled": response_metadata["rag_used"],
                "fallback_used": response_metadata["fallback_used"],
                "processing_time_ms": round(
                    response_metadata["processing_time"] * 1000, 2
                ),
                "response_type": "rag"
                if response_metadata["rag_used"]
                and not response_metadata["fallback_used"]
                else "fallback",
                "college_id": college_id,
                "timestamp": datetime.now(dt.UTC).isoformat(),
                "quality_score": quality_score,
                "conversation_context_used": conversation_context_used,
                "source_details": source_details,
            },
        }

        return response_data
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error processing chat message for user %s: %s",
            message.user_id,
            str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "message": "An unexpected error occurred while processing your message",
                "timestamp": datetime.now(dt.UTC).isoformat(),
            },
        ) from exc


async def create_guest_chat_response(request: Any) -> dict[str, Any]:
    try:
        client = get_service_client()

        college_id = None
        if request.college_id:
            college_check = (
                client.table("colleges")
                .select("id")
                .eq("id", request.college_id)
                .limit(1)
                .execute()
            )
            if college_check.data:
                college_id = request.college_id

        if not college_id:
            colleges_resp = client.table("colleges").select("id").limit(1).execute()
            colleges = getattr(colleges_resp, "data", None) or colleges_resp.data
            if not colleges:
                return {
                    "content": "The system is not fully configured yet (no colleges found). Please contact the administrator.",
                    "sources": [],
                }
            college_id = colleges[0]["id"]

        try:
            from app.core.rag import generate_rag_response

            rag_result = await generate_rag_response(
                query=request.content,
                college_id=college_id,
                conversation_history=[],
            )
        except Exception as rag_error:
            logger.warning(
                "Guest chat RAG failed, falling back to basic response: %s",
                str(rag_error),
            )
            rag_result = await generate_basic_response(
                query=request.content,
                college_id=college_id,
            )
            rag_result["fallback_used"] = True
            rag_result["fallback_reason"] = f"Guest RAG failed: {str(rag_error)}"

        return {
            "content": rag_result.get("response", ""),
            "sources": rag_result.get("sources", []),
            "metadata": {
                "fallback_used": rag_result.get("fallback_used", False),
                "fallback_reason": rag_result.get("fallback_reason"),
                "chunks_used": rag_result.get("chunks_used", 0),
                "quality_score": rag_result.get("quality_score"),
            },
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Guest chat failed: {str(exc)}"
        ) from exc


async def get_chat_history_for_user(user_id: str) -> list[dict[str, Any]]:
    try:
        conv_response = (
            supabase.table("conversations")
            .select("id, title, created_at, updated_at, college_id")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return conv_response.data
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_conversation_messages_for_user(
    conversation_id: str, user_id: str
) -> dict[str, Any]:
    try:
        client = get_service_client()

        conv_check = (
            client.table("conversations")
            .select("user_id")
            .eq("id", conversation_id)
            .execute()
        )
        if not conv_check.data:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conv_check.data[0]["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this conversation"
            )

        messages_response = (
            client.table("messages")
            .select("id, role, content, created_at, metadata")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
        )

        return {
            "conversation_id": conversation_id,
            "messages": messages_response.data or [],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get conversation messages: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversation messages: {str(exc)}",
        ) from exc
