"""LLM service for MiniMax API integration."""
import json
import os
from typing import List, AsyncGenerator, Dict

import httpx
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class MiniMaxLLMService:
    """Service for calling MiniMax API."""

    def __init__(self):
        self.api_key = os.environ.get("MINIMAX_API_KEY", "") or os.getenv("MINIMAX_API_KEY", "")
        self.api_url = os.environ.get("MINIMAX_API_URL", "") or os.getenv("MINIMAX_API_URL", "")
        self.model = os.environ.get("MINIMAX_MODEL", "") or os.getenv("MINIMAX_MODEL", "")

        # Use defaults if not set
        if not self.api_url:
            self.api_url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        if not self.model:
            self.model = "abab6.5s-chat"

        print(f"[DEBUG] MiniMax API URL: {self.api_url}")
        print(f"[DEBUG] MiniMax Model: {self.model}")
        print(f"[DEBUG] MiniMax API Key set: {bool(self.api_key)}")

        self.client = httpx.AsyncClient(timeout=120.0)

    async def close(self):
        await self.client.aclose()

    async def call(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 2048) -> str:
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY is not set. Please configure it in .env file.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_output_tokens": max_tokens
        }

        print(f"[DEBUG] Sending request to {self.api_url}")

        try:
            response = await self.client.post(self.api_url, headers=headers, json=payload)
            print(f"[DEBUG] Response status: {response.status_code}")

            response.raise_for_status()
            result = response.json()
            print(f"[DEBUG] Response keys: {result.keys()}")

            # MiniMax response format
            if "base_resp" in result:
                if result["base_resp"]["status_code"] == 0:
                    return result["choices"][0]["message"]["content"]
                else:
                    raise ValueError(f"API error: {result['base_resp']['status_msg']}")
            elif "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                raise ValueError(f"Unexpected API response: {result}")

        except httpx.HTTPError as e:
            print(f"[ERROR] HTTP Error: {e}")
            raise ConnectionError(f"API request failed: {e}")

    async def stream_call(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY is not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }

        async with self.client.stream("POST", self.api_url, headers=headers, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue


# Global LLM service instance
llm_service = MiniMaxLLMService()


async def get_llm_response(messages: List[BaseMessage], temperature: float = 0.7) -> str:
    api_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            api_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            api_messages.append({"role": "assistant", "content": msg.content})

    return await llm_service.call(api_messages, temperature=temperature)


async def stream_llm_response(messages: List[BaseMessage], temperature: float = 0.7) -> AsyncGenerator[str, None]:
    api_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            api_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            api_messages.append({"role": "assistant", "content": msg.content})

    async for chunk in llm_service.stream_call(api_messages, temperature=temperature):
        yield chunk
