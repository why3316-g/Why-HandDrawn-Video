"""Read-only Volcengine Doubao Speech voice catalog tool."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any

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


class DoubaoVoiceCatalog(BaseTool):
    """Query account-visible Doubao TTS voices through ListSpeakers."""

    name = "doubao_voice_catalog"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts_voice_catalog"
    provider = "doubao"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = ["env:VOLC_ACCESSKEY", "env:VOLC_SECRETKEY"]
    install_instructions = (
        "Set VOLC_ACCESSKEY and VOLC_SECRETKEY to Volcengine IAM credentials "
        "that can call speech_saas_prod ListSpeakers."
    )
    agent_skills = ["doubao-tts"]
    capabilities = [
        "list_tts_voices",
        "validate_voice_id",
        "filter_by_resource_id",
    ]
    supports = {
        "read_only": True,
        "pagination": True,
        "resource_filtering": True,
        "voice_type_filtering": True,
    }
    best_for = [
        "validating a Doubao voice ID before paid synthesis",
        "listing account-visible voices for seed-tts-1.0 or seed-tts-2.0",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "resource_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "default": ["seed-tts-2.0"],
            },
            "voice_types": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 30,
            },
            "all_pages": {"type": "boolean", "default": False},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "resource_ids": {"type": "array"},
            "voice_types": {"type": "array"},
            "total": {"type": "integer"},
            "speakers": {"type": "array"},
            "request_ids": {"type": "array"},
        },
    }
    artifact_schema = {"type": "array", "items": {"type": "string"}}

    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=128,
        vram_mb=0,
        disk_mb=0,
        network_required=True,
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=1.0,
        retryable_errors=["timeout", "InternalError"],
    )
    idempotency_key_fields = [
        "resource_ids",
        "voice_types",
        "page",
        "limit",
        "all_pages",
    ]
    side_effects = [
        "calls the read-only Volcengine ListSpeakers API",
    ]
    user_visible_verification = [
        "Confirm every selected voice has the expected VoiceType and ResourceID",
    ]

    HOST = "open.volcengineapi.com"
    REGION = "cn-beijing"
    SERVICE = "speech_saas_prod"
    ACTION = "ListSpeakers"
    API_VERSION = "2025-05-20"
    ALGORITHM = "HMAC-SHA256"

    def get_status(self) -> ToolStatus:
        if os.environ.get("VOLC_ACCESSKEY") and os.environ.get("VOLC_SECRETKEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        access_key = os.environ.get("VOLC_ACCESSKEY")
        secret_key = os.environ.get("VOLC_SECRETKEY")
        if not access_key or not secret_key:
            return ToolResult(
                success=False,
                error=(
                    "VOLC_ACCESSKEY or VOLC_SECRETKEY not set. "
                    + self.install_instructions
                ),
            )

        resource_ids = list(inputs.get("resource_ids") or ["seed-tts-2.0"])
        voice_types = list(inputs.get("voice_types") or [])
        page = int(inputs.get("page", 1))
        limit = int(inputs.get("limit", 30))
        all_pages = bool(inputs.get("all_pages", False))
        if not resource_ids:
            return ToolResult(
                success=False,
                error="resource_ids must contain at least one resource id",
            )
        if page < 1 or not 1 <= limit <= 100:
            return ToolResult(
                success=False,
                error="page must be >= 1 and limit must be between 1 and 100",
            )

        import requests

        speakers: list[dict[str, Any]] = []
        request_ids: list[str] = []
        total = 0
        current_page = page

        try:
            while True:
                body_dict = self._build_body(
                    resource_ids=resource_ids,
                    voice_types=voice_types,
                    page=current_page,
                    limit=limit,
                )
                body = json.dumps(
                    body_dict,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                query = {
                    "Action": self.ACTION,
                    "Version": self.API_VERSION,
                }
                headers = self._sign(
                    "POST",
                    "/",
                    query,
                    body,
                    access_key,
                    secret_key,
                )
                url = (
                    f"https://{self.HOST}/?"
                    + urllib.parse.urlencode(sorted(query.items()))
                )
                response = requests.post(
                    url,
                    data=body,
                    headers=headers,
                    timeout=30,
                )
                payload = self._json_or_raise(response)
                self._check_response(response.status_code, payload)

                response_metadata = payload.get("ResponseMetadata") or {}
                request_id = response_metadata.get("RequestId")
                if request_id:
                    request_ids.append(str(request_id))
                result = payload.get("Result") or {}
                page_speakers = result.get("Speakers") or []
                if not isinstance(page_speakers, list):
                    raise RuntimeError("ListSpeakers returned a non-list Speakers field")
                speakers.extend(page_speakers)
                total = int(result.get("Total") or len(speakers))

                if (
                    not all_pages
                    or not page_speakers
                    or len(speakers) >= total
                ):
                    break
                current_page += 1
                if current_page - page > 100:
                    raise RuntimeError(
                        "ListSpeakers pagination exceeded the 100-page safety limit"
                    )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Doubao voice catalog failed: {self._safe_error(exc)}",
                cost_usd=0.0,
            )

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "operation": self.ACTION,
                "resource_ids": resource_ids,
                "voice_types": voice_types,
                "total": total,
                "speakers": speakers,
                "request_ids": request_ids,
            },
            cost_usd=0.0,
        )

    @staticmethod
    def _build_body(
        *,
        resource_ids: list[str],
        voice_types: list[str],
        page: int,
        limit: int,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "ResourceIDs": resource_ids,
            "Page": page,
            "Limit": limit,
        }
        if voice_types:
            body["VoiceTypes"] = voice_types
        return body

    @classmethod
    def _sign(
        cls,
        method: str,
        path: str,
        query_params: dict[str, str],
        body: bytes,
        access_key: str,
        secret_key: str,
    ) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        x_date = now.strftime("%Y%m%dT%H%M%SZ")
        short_date = x_date[:8]
        body_hash = hashlib.sha256(body).hexdigest()

        signed_headers = {
            "host": cls.HOST,
            "x-content-sha256": body_hash,
            "x-date": x_date,
        }
        signed_names = sorted(signed_headers)
        canonical_headers = "".join(
            f"{name}:{signed_headers[name]}\n" for name in signed_names
        )
        signed_names_text = ";".join(signed_names)
        canonical_query = "&".join(
            (
                f"{urllib.parse.quote(str(key), safe='')}="
                f"{urllib.parse.quote(str(value), safe='')}"
            )
            for key, value in sorted(query_params.items())
        )
        canonical_request = "\n".join(
            [
                method.upper(),
                path,
                canonical_query,
                canonical_headers,
                signed_names_text,
                body_hash,
            ]
        )
        credential_scope = (
            f"{short_date}/{cls.REGION}/{cls.SERVICE}/request"
        )
        string_to_sign = "\n".join(
            [
                cls.ALGORITHM,
                x_date,
                credential_scope,
                hashlib.sha256(
                    canonical_request.encode("utf-8")
                ).hexdigest(),
            ]
        )

        key_date = hmac.new(
            secret_key.encode("utf-8"),
            short_date.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        key_region = hmac.new(
            key_date,
            cls.REGION.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        key_service = hmac.new(
            key_region,
            cls.SERVICE.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        key_signing = hmac.new(
            key_service,
            b"request",
            hashlib.sha256,
        ).digest()
        signature = hmac.new(
            key_signing,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "Host": cls.HOST,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Date": x_date,
            "X-Content-Sha256": body_hash,
            "Authorization": (
                f"{cls.ALGORITHM} Credential={access_key}/{credential_scope}, "
                f"SignedHeaders={signed_names_text}, Signature={signature}"
            ),
        }

    @staticmethod
    def _json_or_raise(response: Any) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                "Non-JSON response from ListSpeakers: "
                f"HTTP {response.status_code}"
            ) from exc

    @staticmethod
    def _check_response(
        http_status: int,
        payload: dict[str, Any],
    ) -> None:
        metadata = payload.get("ResponseMetadata") or {}
        error = metadata.get("Error") or {}
        if http_status < 400 and not error and "Result" in payload:
            return
        request_id = metadata.get("RequestId")
        code = error.get("Code") or "unknown"
        message = error.get("Message") or "unknown error"
        raise RuntimeError(
            f"HTTP {http_status}, code={code}, message={message}, "
            f"request_id={request_id or 'unknown'}"
        )

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = str(exc)
        for variable in ("VOLC_ACCESSKEY", "VOLC_SECRETKEY"):
            value = os.environ.get(variable, "")
            if value:
                message = message.replace(value, "[redacted]")
        return message
