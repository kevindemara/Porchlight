import asyncio
import json

import httpx
import pytest
from porchlight.ai.ollama import Ollama
from porchlight.api.contracts import ApiError
from porchlight.config import Config


@pytest.mark.parametrize(
    "capabilities,remote,expected",
    [
        (["completion", "vision"], False, True),
        (["completion"], False, False),
        (["completion", "vision"], True, False),
    ],
)
def test_synthetic_inference_requires_actual_local_vision_metadata(
    config: Config, capabilities: list[str], remote: bool, expected: bool
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        route = request.url.path
        calls.append(route)
        if route == "/api/version":
            return httpx.Response(200, json={"version": "synthetic"})
        if route == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "innocent-alias", "digest": "synthetic", "size": 123}]},
            )
        if route == "/api/show":
            return httpx.Response(
                200,
                json={
                    "capabilities": capabilities,
                    "details": {"format": "gguf"},
                    "remote_host": "cloud.example" if remote else None,
                },
            )
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["messages"][0]["images"]
        assert "tools" not in body
        return httpx.Response(200, json={"message": {"content": '{"left":"red","right":"blue"}'}})

    async def exercise() -> None:
        client = Ollama(config, httpx.MockTransport(handler))
        try:
            if expected:
                assert (await client.smoke_test("innocent-alias")).passed
            else:
                with pytest.raises(ApiError) as error:
                    await client.smoke_test("innocent-alias")
                assert error.value.code == "VISION_MODEL_REQUIRED"
                assert "/api/chat" not in calls
        finally:
            await client.close()

    asyncio.run(exercise())


def test_model_http_redirect_is_never_followed(config: Config) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"Location": "https://cloud.example"})

    async def exercise() -> None:
        client = Ollama(config, httpx.MockTransport(handler))
        try:
            with pytest.raises(ApiError):
                await client.models()
            assert len(calls) == 1
        finally:
            await client.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("size", [1024, True, -1, None])
def test_resource_status_is_read_only_and_rejects_invalid_memory(
    config: Config, size: object
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method + " " + request.url.path)
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "selected", "size_vram": size},
                    {"name": "another", "size_vram": 2048},
                ]
            },
        )

    async def exercise() -> None:
        client = Ollama(config, httpx.MockTransport(handler))
        try:
            result = await client.resources("selected")
            assert result.available is (type(size) is int and size >= 0)
            if result.available:
                assert result.loaded_models == 2 and result.other_loaded_models == 1
                assert result.selected_loaded and result.contention_possible
                assert result.loaded_vram_bytes == 3072
            assert calls == ["GET /api/ps"]
        finally:
            await client.close()

    asyncio.run(exercise())


def test_resource_endpoint_requires_owner(authenticated) -> None:
    client, _headers = authenticated
    response = client.get("/api/v1/ollama/resources")
    assert response.status_code == 200
    assert set(response.json()) == {
        "available",
        "loaded_models",
        "other_loaded_models",
        "loaded_vram_bytes",
        "selected_loaded",
        "inference_busy",
        "contention_possible",
    }
    client.cookies.clear()
    assert client.get("/api/v1/ollama/resources").status_code == 401
