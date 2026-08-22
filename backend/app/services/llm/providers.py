"""Small provider adapters for optional live structured extraction and RAG."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from app.config import Settings


def build_nvidia_text_payload(
    *, model: str, system_prompt: str, user_prompt: str
) -> dict[str, Any]:
    return {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }


def build_nvidia_vision_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    content: bytes,
    mime_type: str,
) -> dict[str, Any]:
    encoded = base64.b64encode(content).decode("ascii")
    return {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                    },
                ],
            },
        ],
    }


async def complete_nvidia_json(
    settings: Settings,
    *,
    system_prompt: str,
    user_prompt: str,
    content: bytes | None = None,
    mime_type: str | None = None,
) -> dict[str, Any]:
    if not settings.nvidia_api_key or not settings.nvidia_small_model:
        raise RuntimeError("NVIDIA small-model configuration is incomplete")
    if content is not None:
        if not settings.nvidia_vision_model:
            raise RuntimeError("NVIDIA vision capability is not configured")
        if not mime_type or not mime_type.startswith("image/"):
            raise RuntimeError("NVIDIA vision input must be an image")
        payload = build_nvidia_vision_payload(
            model=settings.nvidia_vision_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            content=content,
            mime_type=mime_type,
        )
    else:
        payload = build_nvidia_text_payload(
            model=settings.nvidia_small_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    url = f"{settings.nvidia_base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.nvidia_api_key}"},
            json=payload,
        )
        response.raise_for_status()
        return _json_from_text(response.json()["choices"][0]["message"]["content"])


def build_gemini_document_payload(
    *,
    system_prompt: str,
    user_prompt: str,
    content: bytes,
    mime_type: str,
) -> dict[str, Any]:
    """Build a Gemini generateContent request with inline document bytes."""
    return {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": user_prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64.b64encode(content).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }


async def complete_document_json(
    settings: Settings,
    *,
    system_prompt: str,
    user_prompt: str,
    content: bytes,
    mime_type: str,
) -> dict[str, Any]:
    """Extract structured data from an image/PDF through the configured vision provider."""
    if settings.vision_llm_provider != "gemini":
        raise RuntimeError(
            f"Unsupported vision LLM provider: {settings.vision_llm_provider}. "
            "Set VISION_LLM_PROVIDER=gemini for document vision."
        )
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_vision_model}:generateContent"
    )
    payload = build_gemini_document_payload(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        content=content,
        mime_type=mime_type,
    )
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            url,
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
    response_text = body["candidates"][0]["content"]["parts"][0]["text"]
    return _json_from_text(response_text)


def _json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return a JSON object")
    return json.loads(text[start : end + 1])


async def complete_groq_json(
    settings: Settings, *, system_prompt: str, user_prompt: str
) -> dict[str, Any]:
    """Call the Phase 3 heavy provider directly, independent of legacy settings."""
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    payload = {
        "model": settings.effective_groq_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return _json_from_text(response.json()["choices"][0]["message"]["content"])


async def complete_json(
    settings: Settings, *, system_prompt: str, user_prompt: str
) -> dict[str, Any]:
    provider = settings.text_llm_provider
    if provider == "groq":
        return await complete_groq_json(
            settings, system_prompt=system_prompt, user_prompt=user_prompt
        )

    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        payload = {
            "model": settings.openai_text_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return _json_from_text(response.json()["choices"][0]["message"]["content"])

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_text_model}:generateContent?key={settings.gemini_api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return _json_from_text(text)

    raise RuntimeError(f"Unsupported text LLM provider: {provider}")
