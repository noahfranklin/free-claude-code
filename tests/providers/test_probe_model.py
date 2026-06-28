"""Unit tests for the streaming health-probe (`probe_model`) contract.

The proactive model-health probe relies on `probe_model` mirroring real usage:
stream a tiny completion and (a) return on the first chunk = healthy, (b) raise on
an upstream error (e.g. 404), and (c) raise when the stream yields nothing. These
back the `healthy_only` model picker, so the contract is locked in here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest
from httpx import Request, Response

from providers.exceptions import APIError


@pytest.mark.asyncio
async def test_probe_model_healthy_on_first_chunk(nim_provider):
    """A model that streams a chunk within the timeout is healthy (no raise)."""

    async def mock_stream():
        yield MagicMock()

    with patch.object(
        nim_provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()
        # Returns None (healthy); must not raise.
        assert await nim_provider.probe_model("good-model", timeout=5.0) is None
        # Probed via streaming, bypassing the rate limiter.
        await_args = mock_create.await_args
        assert await_args is not None
        assert await_args.kwargs["stream"] is True


@pytest.mark.asyncio
async def test_probe_model_raises_on_upstream_error(nim_provider):
    """A 4xx/5xx from the provider raises so the probe records unhealthy."""
    not_found = openai.NotFoundError(
        message="not found for account",
        response=Response(404, request=Request("POST", "https://x/v1/chat")),
        body=None,
    )
    with (
        patch.object(
            nim_provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=not_found,
        ),
        pytest.raises(openai.NotFoundError),
    ):
        await nim_provider.probe_model("dead-model", timeout=5.0)


@pytest.mark.asyncio
async def test_probe_model_raises_on_empty_stream(nim_provider):
    """A stream that yields nothing is unhealthy (raises)."""

    async def empty_stream():
        return
        yield  # pragma: no cover - makes this an async generator

    with patch.object(
        nim_provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = empty_stream()
        with pytest.raises(APIError, match="streamed no content"):
            await nim_provider.probe_model("silent-model", timeout=5.0)
