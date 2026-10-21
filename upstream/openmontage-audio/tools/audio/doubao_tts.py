"""Doubao Speech text-to-speech provider tool."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from tools.audio.doubao_voice_catalog import DoubaoVoiceCatalog
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class DoubaoRequestError(RuntimeError):
    """A provider or preflight failure with safe diagnostic context."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


class DoubaoTTS(BaseTool):
    name = "doubao_tts"
    version = "0.2.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "doubao"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:DOUBAO_SPEECH_API_KEY"]
    install_instructions = (
        "Set DOUBAO_SPEECH_API_KEY to a Volcengine Doubao Speech API Key.\n"
        "Optional: set DOUBAO_SPEECH_VOICE_TYPE to the default speaker voice.\n"
        "Use the new console API key flow; do not pass app id/access token as the API key."
    )
    fallback = "google_tts"
    fallback_tools = ["google_tts", "elevenlabs_tts", "openai_tts", "piper_tts"]
    agent_skills = ["doubao-tts", "text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "multilingual",
        "timestamp_alignment",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "timestamps": True,
        "long_text_async": True,
    }
    best_for = [
        "natural Mandarin narration",
        "Chinese explainer voiceovers with character-level timestamps",
        "long-form narration that needs subtitle alignment",
    ]
    not_good_for = [
        "fully offline production",
        "voice clone matching",
        "real-time interactive speech playback",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "voice_id": {
                "type": "string",
                "description": "Doubao speaker/voice_type. Defaults to DOUBAO_SPEECH_VOICE_TYPE.",
            },
            "resource_id": {
                "type": "string",
                "default": "seed-tts-2.0",
                "description": "Volcengine resource id. Use seed-tts-2.0 for Doubao Speech 2.0 voices.",
            },
            "voice_validation": {
                "type": "string",
                "enum": ["auto", "required", "skip"],
                "default": "auto",
                "description": (
                    "Validate voice_id with ListSpeakers before synthesis. "
                    "auto validates when VOLC_ACCESSKEY/VOLC_SECRETKEY exist; "
                    "required fails closed; skip bypasses validation."
                ),
            },
            "format": {
                "type": "string",
                "default": "mp3",
                "enum": ["mp3", "ogg_opus", "pcm"],
            },
            "sample_rate": {
                "type": "integer",
                "default": 24000,
                "enum": [8000, 16000, 22050, 24000, 32000, 44100, 48000],
            },
            "speech_rate": {
                "type": "integer",
                "default": 0,
                "minimum": -50,
                "maximum": 100,
                "description": "Doubao speech rate. 0=normal, 100=2x, -50=0.5x.",
            },
            "enable_timestamp": {
                "type": "boolean",
                "default": True,
                "description": "Return sentence/word timing metadata when supported by the selected endpoint.",
            },
            "disable_markdown_filter": {
                "type": "boolean",
                "default": False,
                "description": "Pass through Doubao markdown filtering behavior. Defaults to API-safe false.",
            },
            "return_usage": {
                "type": "boolean",
                "default": True,
                "description": "Request usage token data from Volcengine when available.",
            },
            "output_path": {"type": "string"},
            "metadata_path": {
                "type": "string",
                "description": "Where to save the full query JSON. Defaults next to output_path.",
            },
            "poll_interval_seconds": {
                "type": "number",
                "default": 2.0,
                "minimum": 0.5,
            },
            "timeout_seconds": {
                "type": "integer",
                "default": 300,
                "minimum": 30,
            },
            "max_transient_query_retries": {
                "type": "integer",
                "default": 12,
                "minimum": 0,
                "description": (
                    "Maximum retries for transient async query failures such as "
                    "provider code 55000000. Does not retry auth, permission, "
                    "quota, or malformed-request failures."
                ),
            },
            "max_download_retries": {
                "type": "integer",
                "default": 3,
                "minimum": 0,
                "description": (
                    "Maximum retries for transient signed-audio download errors "
                    "after the async task has completed."
                ),
            },
            "allow_overwrite": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Allow replacing an existing output only when explicitly "
                    "requested. Concurrent writes are always rejected."
                ),
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "metadata_path": {"type": "string"},
            "task_id": {"type": "string"},
            "audio_duration_seconds": {"type": ["number", "null"]},
            "sentences": {"type": "array"},
            "usage": {"type": ["object", "null"]},
        },
    }
    artifact_schema = {
        "type": "array",
        "items": {"type": "string"},
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["timeout", "rate_limit", "quota exceeded for types: concurrency"],
    )
    idempotency_key_fields = ["text", "voice_id", "resource_id", "speech_rate", "sample_rate"]
    side_effects = [
        "writes audio file to output_path",
        "writes Doubao query metadata JSON next to output_path",
        "calls Volcengine Doubao Speech API",
    ]
    user_visible_verification = [
        "Listen to generated audio for Mandarin naturalness and pacing",
        "Check timestamp JSON before building subtitles",
    ]
    quality_score = 0.88
    latency_p50_seconds = 8.0

    SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/tts/submit"
    QUERY_URL = "https://openspeech.bytedance.com/api/v3/tts/query"
    DEFAULT_RESOURCE_ID = "seed-tts-2.0"
    DEFAULT_VOICE_ENV = "DOUBAO_SPEECH_VOICE_TYPE"
    DEFAULT_MAX_TRANSIENT_QUERY_RETRIES = 12
    MAX_TRANSIENT_QUERY_BACKOFF_SECONDS = 15.0
    TRANSIENT_QUERY_CODES = {55000000}
    TRANSIENT_QUERY_HTTP_STATUSES = {429, 500, 502, 503, 504}
    DEFAULT_MAX_DOWNLOAD_RETRIES = 3
    MAX_DOWNLOAD_BACKOFF_SECONDS = 8.0

    def get_status(self) -> ToolStatus:
        if os.environ.get("DOUBAO_SPEECH_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Volcengine bills Doubao Speech 2.0 by characters. Keep this conservative
        # and prefer provider-returned usage when available.
        return round(len(inputs.get("text", "")) * 0.000015, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        self._artifact_lock_path: Path | None = None
        api_key = os.environ.get("DOUBAO_SPEECH_API_KEY")
        if not api_key:
            return ToolResult(success=False, error="No Doubao Speech API key. " + self.install_instructions)

        voice_id = inputs.get("voice_id") or os.environ.get(self.DEFAULT_VOICE_ENV)
        if not voice_id:
            return ToolResult(
                success=False,
                error=(
                    "No Doubao voice_id provided. Pass voice_id or set "
                    f"{self.DEFAULT_VOICE_ENV} in the environment."
                ),
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key=api_key, voice_id=voice_id)
        except DoubaoRequestError as exc:
            safe_message = self._safe_error(exc)
            metadata_path = self._write_failure_metadata(
                inputs,
                voice_id=voice_id,
                error=safe_message,
                details=exc.details,
            )
            data = {"error_context": exc.details}
            if metadata_path:
                data["metadata_path"] = str(metadata_path)
            return ToolResult(
                success=False,
                error=f"Doubao TTS failed: {safe_message}",
                data=data,
                cost_usd=0.0,
            )
        except Exception as exc:
            safe_message = self._safe_error(exc)
            details = {"stage": "unknown"}
            metadata_path = self._write_failure_metadata(
                inputs,
                voice_id=voice_id,
                error=safe_message,
                details=details,
            )
            data = {"error_context": details}
            if metadata_path:
                data["metadata_path"] = str(metadata_path)
            return ToolResult(
                success=False,
                error=f"Doubao TTS failed: {safe_message}",
                data=data,
                cost_usd=0.0,
            )
        finally:
            self._release_artifact_lock()

        result.duration_seconds = round(time.time() - start, 2)
        if not result.cost_usd:
            result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], *, api_key: str, voice_id: str) -> ToolResult:
        import requests

        text = inputs["text"]
        fmt = inputs.get("format", "mp3")
        resource_id = inputs.get("resource_id", self.DEFAULT_RESOURCE_ID)
        voice_validation = self._validate_voice(
            inputs,
            voice_id=voice_id,
            resource_id=resource_id,
        )
        output_path = Path(inputs.get("output_path", f"doubao_tts.{self._extension_for_format(fmt)}"))
        metadata_path = Path(
            inputs.get("metadata_path") or output_path.with_suffix(output_path.suffix + ".json")
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self._acquire_artifact_lock(
            output_path,
            metadata_path,
            allow_overwrite=bool(inputs.get("allow_overwrite", False)),
        )

        req_id = str(uuid.uuid4())
        headers = self._headers(
            api_key=api_key,
            resource_id=resource_id,
            request_id=req_id,
            return_usage=bool(inputs.get("return_usage", True)),
        )
        body = self._submit_body(inputs, voice_id=voice_id, request_id=req_id)

        submit_response = requests.post(self.SUBMIT_URL, headers=headers, json=body, timeout=(10, 60))
        submit_data = self._json_or_raise(submit_response)
        self._raise_for_doubao_error(
            submit_response.status_code,
            submit_data,
            stage="submit",
            request_id=req_id,
        )

        task_id = submit_data.get("data", {}).get("task_id")
        if not task_id:
            raise DoubaoRequestError(
                "Doubao submit succeeded but did not return data.task_id "
                f"(stage=submit, request_id={req_id})",
                details={
                    "stage": "submit",
                    "request_id": req_id,
                    "provider_response": submit_data,
                },
            )

        query_data, query_trace = self._poll_query(
            requests_module=requests,
            api_key=api_key,
            resource_id=resource_id,
            task_id=task_id,
            return_usage=bool(inputs.get("return_usage", True)),
            poll_interval=float(inputs.get("poll_interval_seconds", 2.0)),
            timeout_seconds=int(inputs.get("timeout_seconds", 300)),
            max_transient_query_retries=int(
                inputs.get(
                    "max_transient_query_retries",
                    self.DEFAULT_MAX_TRANSIENT_QUERY_RETRIES,
                )
            ),
        )
        query_data = dict(query_data)
        request_trace = {
            "submit_request_id": req_id,
            "task_id": task_id,
            "query_attempt_count": len(query_trace),
            "transient_query_retry_count": sum(
                1 for item in query_trace if item.get("action") == "retry"
            ),
            "attempts": query_trace,
        }
        # Keep the provider response shape intact while adding a safe,
        # secret-free audit trail. This is essential when an async provider
        # returns a transient server error that later recovers.
        query_data["openmontage_request_trace"] = request_trace
        data = query_data.get("data", {})
        audio_url = data.get("audio_url")
        if not audio_url:
            raise DoubaoRequestError(
                "Doubao task completed but did not return data.audio_url "
                f"(stage=query, task_id={task_id})",
                details={
                    "stage": "query",
                    "task_id": task_id,
                    "provider_response": query_data,
                },
            )

        download_trace: list[dict[str, Any]] = []
        max_download_retries = max(
            0,
            int(inputs.get("max_download_retries", self.DEFAULT_MAX_DOWNLOAD_RETRIES)),
        )
        audio_response = None
        for download_attempt in range(1, max_download_retries + 2):
            try:
                audio_response = requests.get(audio_url, timeout=(10, 120))
                audio_response.raise_for_status()
                download_trace.append(
                    {
                        "attempt": download_attempt,
                        "action": "success",
                        "http_status": audio_response.status_code,
                        "observed_at_epoch": time.time(),
                    }
                )
                break
            except Exception as exc:
                download_trace.append(
                    {
                        "attempt": download_attempt,
                        "action": "retry" if download_attempt <= max_download_retries else "fail",
                        "error": str(exc),
                        "observed_at_epoch": time.time(),
                    }
                )
                if download_attempt > max_download_retries:
                    request_trace["download_attempts"] = download_trace
                    raise DoubaoRequestError(
                        f"Doubao audio download failed after {download_attempt} attempts: {exc} "
                        f"(stage=download, task_id={task_id})",
                        details={
                            "stage": "download",
                            "task_id": task_id,
                            "provider_response": query_data,
                            "request_trace": request_trace,
                        },
                    ) from exc
                time.sleep(
                    min(2 ** (download_attempt - 1), self.MAX_DOWNLOAD_BACKOFF_SECONDS)
                )
        request_trace["download_attempts"] = download_trace
        query_data["openmontage_request_trace"] = request_trace
        output_path.write_bytes(audio_response.content)
        metadata_path.write_text(json.dumps(query_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        audio_duration = self._audio_duration(output_path)
        usage = data.get("usage")
        cost = self._cost_from_usage(usage) or self.estimate_cost(inputs)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": resource_id,
                "resource_id": resource_id,
                "voice_id": voice_id,
                "format": fmt,
                "sample_rate": inputs.get("sample_rate", 24000),
                "speech_rate": inputs.get("speech_rate", 0),
                "text_length": len(text),
                "task_id": task_id,
                "task_status": data.get("task_status"),
                "req_text_length": data.get("req_text_length"),
                "synthesize_text_length": data.get("synthesize_text_length"),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
                "metadata_path": str(metadata_path),
                "sentences": data.get("sentences", []),
                "usage": usage,
                "url_expire_time": data.get("url_expire_time"),
                "voice_validation": voice_validation,
                "request_trace": request_trace,
            },
            artifacts=[str(output_path), str(metadata_path)],
            cost_usd=cost,
            model=resource_id,
        )

    def _headers(
        self,
        *,
        api_key: str,
        resource_id: str,
        request_id: str,
        return_usage: bool,
    ) -> dict[str, str]:
        headers = {
            "X-Api-Key": api_key,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": request_id,
            "Content-Type": "application/json",
        }
        if return_usage:
            headers["X-Control-Require-Usage-Tokens-Return"] = "true"
        return headers

    def _submit_body(self, inputs: dict[str, Any], *, voice_id: str, request_id: str) -> dict[str, Any]:
        audio_params = {
            "format": inputs.get("format", "mp3"),
            "sample_rate": inputs.get("sample_rate", 24000),
            "speech_rate": inputs.get("speech_rate", 0),
            "enable_timestamp": bool(inputs.get("enable_timestamp", True)),
        }
        additions = {
            "disable_markdown_filter": bool(inputs.get("disable_markdown_filter", False)),
        }
        return {
            "user": {"uid": inputs.get("user_id", "openmontage")},
            "unique_id": request_id,
            "req_params": {
                "text": inputs["text"],
                "speaker": voice_id,
                "audio_params": audio_params,
                "additions": json.dumps(additions, ensure_ascii=False),
            },
        }

    def _poll_query(
        self,
        *,
        requests_module: Any,
        api_key: str,
        resource_id: str,
        task_id: str,
        return_usage: bool,
        poll_interval: float,
        timeout_seconds: int,
        max_transient_query_retries: int,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        deadline = time.time() + timeout_seconds
        base_poll_interval = max(0.5, poll_interval)
        next_delay = base_poll_interval
        transient_retry_count = 0
        attempt = 0
        trace: list[dict[str, Any]] = []
        while time.time() < deadline:
            delay_before_query = min(next_delay, max(0.0, deadline - time.time()))
            if delay_before_query > 0:
                time.sleep(delay_before_query)
            attempt += 1
            query_request_id = str(uuid.uuid4())
            headers = self._headers(
                api_key=api_key,
                resource_id=resource_id,
                request_id=query_request_id,
                return_usage=return_usage,
            )
            response = requests_module.post(self.QUERY_URL, headers=headers, json={"task_id": task_id}, timeout=(10, 60))
            query_data = self._json_or_raise(response)
            provider_code = query_data.get("code")
            provider_message = query_data.get("message", "")
            data = query_data.get("data") or {}
            task_status = data.get("task_status")
            is_transient = self._is_transient_query_error(
                response.status_code,
                provider_code,
                provider_message,
            )
            trace_item = {
                "attempt": attempt,
                "request_id": query_request_id,
                "task_id": task_id,
                "http_status": response.status_code,
                "provider_code": provider_code,
                "provider_message": provider_message,
                "task_status": task_status,
                "delay_before_seconds": round(delay_before_query, 3),
                "observed_at_epoch": time.time(),
                "action": "retry" if is_transient else "continue",
            }
            trace.append(trace_item)
            if is_transient:
                if transient_retry_count >= max(0, max_transient_query_retries):
                    raise DoubaoRequestError(
                        "Doubao query transient errors exhausted: "
                        f"HTTP {response.status_code}, code {provider_code}: "
                        f"{provider_message} (stage=query, task_id={task_id})",
                        details={
                            "stage": "query",
                            "task_id": task_id,
                            "http_status": response.status_code,
                            "provider_response": query_data,
                            "request_trace": trace,
                            "transient_query_retry_count": transient_retry_count,
                        },
                    )
                transient_retry_count += 1
                next_delay = min(
                    max(base_poll_interval * (2**transient_retry_count), base_poll_interval),
                    self.MAX_TRANSIENT_QUERY_BACKOFF_SECONDS,
                )
                continue
            self._raise_for_doubao_error(
                response.status_code,
                query_data,
                stage="query",
                request_id=query_request_id,
                task_id=task_id,
            )
            if task_status == 2:
                return query_data, trace
            if task_status == 3:
                raise DoubaoRequestError(
                    "Doubao task failed: "
                    f"{query_data.get('message', 'unknown error')} "
                    f"(stage=query, request_id={query_request_id}, "
                    f"task_id={task_id})",
                    details={
                        "stage": "query",
                        "request_id": query_request_id,
                        "task_id": task_id,
                        "provider_response": query_data,
                        "request_trace": trace,
                    },
                )
            # A normal pending response should use the base cadence; only
            # transient failures increase the backoff.
            next_delay = base_poll_interval
        raise DoubaoRequestError(
            f"Doubao task did not finish within {timeout_seconds} seconds "
            f"(stage=query, task_id={task_id})",
            details={
                "stage": "query",
                "task_id": task_id,
                "timeout_seconds": timeout_seconds,
                "request_trace": trace,
            },
        )

    @classmethod
    def _is_transient_query_error(
        cls,
        http_status: int,
        provider_code: Any,
        provider_message: Any,
    ) -> bool:
        """Return whether a query response is safe to retry on the same task."""

        if http_status in cls.TRANSIENT_QUERY_HTTP_STATUSES:
            return True
        if provider_code in cls.TRANSIENT_QUERY_CODES:
            return True
        message = str(provider_message or "").lower()
        return any(
            marker in message
            for marker in (
                "server error",
                "internal server error",
                "服务端错误",
                "服务暂时不可用",
                "temporarily unavailable",
            )
        )

    @staticmethod
    def _json_or_raise(response: Any) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"Non-JSON response from Doubao API: HTTP {response.status_code}") from exc

    def _raise_for_doubao_error(
        self,
        http_status: int,
        payload: dict[str, Any],
        *,
        stage: str | None = None,
        request_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        code = payload.get("code")
        if http_status < 400 and code == 20000000:
            return
        message = payload.get("message", "unknown error")
        hint = self._diagnostic_hint(message)
        context = []
        if stage:
            context.append(f"stage={stage}")
        if request_id:
            context.append(f"request_id={request_id}")
        if task_id:
            context.append(f"task_id={task_id}")
        suffix = f" ({', '.join(context)})" if context else ""
        raise DoubaoRequestError(
            f"HTTP {http_status}, code {code}: {message}{hint}{suffix}",
            details={
                "stage": stage,
                "request_id": request_id,
                "task_id": task_id,
                "http_status": http_status,
                "provider_response": payload,
            },
        )

    def _validate_voice(
        self,
        inputs: dict[str, Any],
        *,
        voice_id: str,
        resource_id: str,
    ) -> dict[str, Any]:
        mode = inputs.get("voice_validation", "auto")
        if mode == "skip":
            return {"status": "skipped", "mode": mode}

        catalog = DoubaoVoiceCatalog()
        if catalog.get_status() != ToolStatus.AVAILABLE:
            if mode == "required":
                raise DoubaoRequestError(
                    "voice_validation requires VOLC_ACCESSKEY and "
                    "VOLC_SECRETKEY (stage=voice_validation)",
                    details={
                        "stage": "voice_validation",
                        "voice_id": voice_id,
                        "resource_id": resource_id,
                        "reason": "catalog_credentials_unavailable",
                    },
                )
            return {
                "status": "skipped",
                "mode": mode,
                "reason": "catalog_credentials_unavailable",
            }

        catalog_result = catalog.execute(
            {
                "resource_ids": [resource_id],
                "voice_types": [voice_id],
                "page": 1,
                "limit": 30,
            }
        )
        if not catalog_result.success:
            raise DoubaoRequestError(
                "voice_validation failed before synthesis: "
                f"{catalog_result.error} (stage=voice_validation)",
                details={
                    "stage": "voice_validation",
                    "voice_id": voice_id,
                    "resource_id": resource_id,
                    "provider_response": catalog_result.data,
                },
            )

        speakers = catalog_result.data.get("speakers") or []
        matching = [
            speaker
            for speaker in speakers
            if speaker.get("VoiceType") == voice_id
            and speaker.get("ResourceID") == resource_id
        ]
        if not matching:
            raise DoubaoRequestError(
                f"voice_validation rejected voice_id={voice_id!r} for "
                f"resource_id={resource_id!r}; ListSpeakers returned no "
                "exact match (stage=voice_validation)",
                details={
                    "stage": "voice_validation",
                    "voice_id": voice_id,
                    "resource_id": resource_id,
                    "provider_response": catalog_result.data,
                },
            )
        speaker = matching[0]
        return {
            "status": "validated",
            "mode": mode,
            "voice_type": speaker.get("VoiceType"),
            "name": speaker.get("Name"),
            "resource_id": speaker.get("ResourceID"),
            "request_ids": catalog_result.data.get("request_ids", []),
        }

    def _write_failure_metadata(
        self,
        inputs: dict[str, Any],
        *,
        voice_id: str,
        error: str,
        details: dict[str, Any],
    ) -> Path | None:
        metadata_value = inputs.get("metadata_path")
        output_value = inputs.get("output_path")
        if metadata_value:
            metadata_path = Path(metadata_value)
        elif output_value:
            output_path = Path(output_value)
            metadata_path = output_path.with_suffix(output_path.suffix + ".json")
        else:
            return None
        payload = {
            "success": False,
            "provider": self.provider,
            "model": inputs.get("resource_id", self.DEFAULT_RESOURCE_ID),
            "voice_id": voice_id,
            "stage": details.get("stage", "unknown"),
            "error": error,
            **details,
        }
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if metadata_path.exists():
            metadata_path = metadata_path.with_name(
                f"{metadata_path.name}.failure-{int(time.time())}.json"
            )
        metadata_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return metadata_path

    def _acquire_artifact_lock(
        self,
        output_path: Path,
        metadata_path: Path,
        *,
        allow_overwrite: bool,
    ) -> None:
        """Prevent late/concurrent tasks from overwriting narration evidence."""

        if not allow_overwrite and (output_path.exists() or metadata_path.exists()):
            raise DoubaoRequestError(
                "Refusing to overwrite an existing narration artifact; use a new "
                "versioned output path or explicitly set allow_overwrite=true "
                "(stage=artifact_lock)",
                details={
                    "stage": "artifact_lock",
                    "output_path": str(output_path),
                    "metadata_path": str(metadata_path),
                    "reason": "existing_artifact",
                },
            )

        lock_path = Path(str(output_path) + ".lock")
        lock_payload = {
            "pid": os.getpid(),
            "created_at_epoch": time.time(),
            "output_path": str(output_path),
            "metadata_path": str(metadata_path),
        }
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise DoubaoRequestError(
                "Narration output is already locked by another task; do not "
                "start a duplicate synthesis (stage=artifact_lock)",
                details={
                    "stage": "artifact_lock",
                    "lock_path": str(lock_path),
                    "output_path": str(output_path),
                    "reason": "concurrent_or_stale_lock",
                },
            ) from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(lock_payload, handle, ensure_ascii=False)
                handle.write("\n")
        except Exception:
            lock_path.unlink(missing_ok=True)
            raise
        self._artifact_lock_path = lock_path

    def _release_artifact_lock(self) -> None:
        lock_path = getattr(self, "_artifact_lock_path", None)
        if lock_path is not None:
            Path(lock_path).unlink(missing_ok=True)
            self._artifact_lock_path = None

    @staticmethod
    def _diagnostic_hint(message: str) -> str:
        lowered = message.lower()
        if "load grant" in lowered or "requested grant not found" in lowered:
            return " (check DOUBAO_SPEECH_API_KEY and use the new-console X-Api-Key flow)"
        if "speaker permission denied" in lowered or "access denied" in lowered:
            return " (check voice_id/DOUBAO_SPEECH_VOICE_TYPE and voice authorization)"
        if "quota exceeded" in lowered:
            return " (check quota, concurrency, or remaining character package)"
        if "unsupported additions explicit language" in lowered:
            return " (do not pass additions.explicit_language for this endpoint)"
        return ""

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        # Avoid ever echoing request headers or secrets in user-visible errors.
        message = str(exc)
        for variable in (
            "DOUBAO_SPEECH_API_KEY",
            "VOLC_ACCESSKEY",
            "VOLC_SECRETKEY",
        ):
            value = os.environ.get(variable, "")
            if value:
                message = message.replace(value, "[redacted]")
        return message

    @staticmethod
    def _extension_for_format(fmt: str) -> str:
        if fmt == "ogg_opus":
            return "ogg"
        if fmt == "pcm":
            return "pcm"
        return "mp3"

    @staticmethod
    def _audio_duration(path: Path) -> float | None:
        try:
            from tools.analysis.audio_probe import probe_duration

            return probe_duration(path)
        except Exception:
            return None

    @staticmethod
    def _cost_from_usage(usage: Any) -> float | None:
        if not isinstance(usage, dict):
            return None
        text_words = usage.get("text_words")
        if not isinstance(text_words, (int, float)):
            return None
        return round(float(text_words) * 0.000015, 4)
