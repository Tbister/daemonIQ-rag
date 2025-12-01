import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    """Test that /health returns 200 and expected structure"""
    response = await async_client.get("/health")

    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert "data_dir" in data
    assert "qdrant_url" in data
    assert "model" in data


@pytest.mark.asyncio
async def test_health_cors_preflight(async_client: AsyncClient):
    """Test that /health supports OPTIONS for CORS preflight"""
    response = await async_client.options("/health")

    # OPTIONS should return 200
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_test_ollama_endpoint(async_client: AsyncClient, mock_ollama_http):
    """Test /test-ollama endpoint with mocked Ollama response"""
    response = await async_client.get("/test-ollama")

    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] == "success"
    assert "response" in data

    # Verify the mock was called
    mock_ollama_http.assert_called_once()


@pytest.mark.asyncio
async def test_test_ollama_connection_error(async_client: AsyncClient):
    """Test /test-ollama when Ollama is unavailable"""
    from unittest.mock import patch

    # Mock requests.post to raise an exception
    with patch("requests.post", side_effect=ConnectionError("Connection refused")):
        response = await async_client.get("/test-ollama")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Connection refused" in data["detail"]
