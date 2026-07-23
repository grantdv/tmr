"""Client for the local OpenAI-compatible inference server."""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import requests


class LLMEngineError(RuntimeError):
    """Raised when the configured LLM cannot produce a valid extraction."""


class LLMEngine:
    CACHE_SCHEMA_VERSION = "1.0"
    CACHE_DIR = Path("data/output/llm_cache")
    SYSTEM_PROMPT = "You extract medical records. Return only valid JSON, with no markdown or explanation."

    def __init__(
        self,
        provider: str = "local",
        base_url: str = "http://localhost:8080",
        timeout: int = 180,
        max_context_chars: int = 24000,
        use_cache: bool = True,
    ):
        if provider != "local":
            raise ValueError("Only the local LLM provider is supported")
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_context_chars = max_context_chars
        self.use_cache = use_cache
        self.model: Optional[str] = os.getenv("TMR_LLM_MODEL")

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            response.raise_for_status()
            body = response.json()
            models = body.get("data") or body.get("models") or []
            if not models:
                raise LLMEngineError("Local LLM returned no models")
            model = models[0]
            self.model = model.get("id") or model.get("model") or model.get("name")
            if not self.model:
                raise LLMEngineError("Could not determine model identifier")
            return self.model
        except LLMEngineError:
            raise
        except Exception as exc:
            raise LLMEngineError(f"Unable to contact LLM model endpoint: {exc}") from exc

    def query(self, prompt: str, context: str) -> Dict[str, object]:
        model = self._resolve_model()
        context = context[-self.max_context_chars:]
        print(
            f"[DEBUG] LLM server ONLINE; model={model}; timeout={self.timeout}s; "
            f"cache={self.use_cache}"
        )

        if self.use_cache:
            cached = self._load_cache(model, prompt, context)
            if cached is not None:
                print(f"[DEBUG] LLM Cache HIT: {cached['cache_path']}")
                return cached["parsed_response"]
            print("[DEBUG] LLM Cache MISS")

        parsed, raw_content = self._query_local_llm(model, prompt, context)
        if self.use_cache:
            cache_path = self._write_cache(model, prompt, context, parsed, raw_content)
            print(f"[DEBUG] LLM Cache WROTE: {cache_path}")
        return parsed

    def _query_local_llm(
        self, model: str, prompt: str, context: str
    ) -> tuple[Dict[str, object], str]:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"{prompt}\n\nDOCUMENT TEXT:\n{context}"},
            ],
            "temperature": 0.0,
            "max_tokens": 2500,
            "reasoning_effort": "low",
            "stream": False,
        }
        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=(5, self.timeout),
            )
            response.raise_for_status()
            data = response.json()
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            if not content:
                raise LLMEngineError(
                    f"LLM returned no content (finish_reason={choice.get('finish_reason')})"
                )
            print(f"[DEBUG] Raw LLM content: {content[:1000]}")
            return self._parse_json(content), content
        except LLMEngineError:
            raise
        except Exception as exc:
            raise LLMEngineError(f"LLM request failed: {exc}") from exc

    def _cache_key(self, model: str, prompt: str, context: str) -> str:
        payload = {
            "cache_schema_version": self.CACHE_SCHEMA_VERSION,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": model,
            "system_prompt": self.SYSTEM_PROMPT,
            "prompt": prompt,
            "context": context,
            "temperature": 0.0,
            "max_tokens": 2500,
            "reasoning_effort": "low",
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _cache_path(self, model: str, prompt: str, context: str) -> Path:
        key = self._cache_key(model, prompt, context)
        safe_model = re.sub(r"[^A-Za-z0-9._-]+", "_", model)[:80]
        return self.CACHE_DIR / f"{safe_model}.{key[:24]}.llm.json"

    def _load_cache(self, model: str, prompt: str, context: str):
        cache_path = self._cache_path(model, prompt, context)
        if not cache_path.exists():
            return None
        try:
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("cache_schema_version") != self.CACHE_SCHEMA_VERSION:
                return None
            parsed_response = payload.get("parsed_response")
            if not isinstance(parsed_response, dict):
                return None
            return {
                "cache_path": cache_path,
                "parsed_response": parsed_response,
            }
        except Exception as exc:
            print(f"[DEBUG] Ignoring unreadable LLM cache: {exc}")
            return None

    def _write_cache(
        self,
        model: str,
        prompt: str,
        context: str,
        parsed_response: Dict[str, object],
        raw_content: str,
    ) -> Path:
        cache_path = self._cache_path(model, prompt, context)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cache_schema_version": self.CACHE_SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provider": self.provider,
            "base_url": self.base_url,
            "model": model,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
            "parsed_response": parsed_response,
            "raw_content": raw_content,
        }
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return cache_path

    @staticmethod
    def _parse_json(content: str) -> Dict[str, object]:
        clean = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content.strip(), flags=re.I)
        try:
            parsed = json.loads(clean)
        except json.JSONDecodeError as exc:
            match = re.search(r"\{.*\}", clean, flags=re.S)
            if not match:
                raise LLMEngineError(f"LLM returned invalid JSON: {exc}") from exc
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError as nested_exc:
                raise LLMEngineError(f"LLM returned invalid JSON: {nested_exc}") from nested_exc
        if not isinstance(parsed, dict):
            raise LLMEngineError("LLM response must be a JSON object")
        return parsed
