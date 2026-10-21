
import os
from typing import Any

import requests


class ChatbotAPIError(Exception):
    """Represent readable errors returned by the chatbot API client."""


def _content_to_text(content: Any) -> str:
    """Convert OpenAI-compatible message content into plain text."""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    parts.append(str(text))

        return "\n".join(parts)

    return str(content or "")


def chat_completion(
    messages: list[dict[str, str]],
    ui_user_id: str,
    ui_chat_id: str,
) -> str:
    """
    Send conversation messages to the existing FastAPI chatbot.

    The API key remains on the Streamlit server and is never
    embedded in frontend HTML or JavaScript.
    """

    api_key = os.getenv("CHATBOT_API_KEY", "").strip()

    base_url = os.getenv(
        "CHATBOT_API_BASE_URL",
        "http://127.0.0.1:8100",
    ).rstrip("/")

    model = os.getenv("CHATBOT_MODEL", "sms-assistant")

    if not api_key:
        raise ChatbotAPIError(
            "CHATBOT_API_KEY was not found. "
            "Check the existing .env file in the project root."
        )

    payload = {
        "model": model,
        "messages": messages[-40:],
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-OpenWebUI-User-Id": ui_user_id,
        "X-OpenWebUI-Chat-Id": ui_chat_id,
        "X-OpenWebUI-User-Name": "Streamlit User",
    }

    try:
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=(5, 120),
            allow_redirects=False,
        )

    except requests.RequestException as exc:
        raise ChatbotAPIError(
            "Could not connect to the FastAPI server. "
            "Make sure the server is running on port 8100."
        ) from exc

    if response.status_code != 200:
        try:
            error_data = response.json()
            detail = error_data.get("detail", "Unknown API error")
        except ValueError:
            detail = response.text[:300] or "Unknown API error"

        if response.status_code in (401, 403):
            raise ChatbotAPIError(
                "The FastAPI server rejected the request. "
                "Check the CHATBOT_API_KEY and authentication settings."
            )

        if response.status_code == 429:
            raise ChatbotAPIError(
                "The request limit has been reached. "
                "Please wait a moment and try again."
            )

        raise ChatbotAPIError(
            f"FastAPI returned an error "
            f"({response.status_code}): {detail}"
        )

    try:
        data = response.json()
        choices = data.get("choices", [])

        if not choices:
            raise ChatbotAPIError(
                "The FastAPI response did not contain an assistant answer."
            )

        message = choices[0].get("message", {})
        answer = _content_to_text(message.get("content", ""))

        if not answer.strip():
            raise ChatbotAPIError(
                "The chatbot returned an empty response."
            )

        return answer.strip()

    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise ChatbotAPIError(
            "The FastAPI server returned an unexpected response format."
        ) from exc
