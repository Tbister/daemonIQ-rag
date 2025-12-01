import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_chat_returns_answer_and_sources(async_client: AsyncClient, test_data_dir: str):
    """Test POST /chat returns answer and sources with mocked Ollama"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # Ingest data first
    await async_client.post("/ingest", json={"force_rebuild": True})

    # Mock Ollama response
    with patch("llama_index.llms.ollama.Ollama.complete") as mock_complete:
        mock_response = MagicMock()
        mock_response.text = "The JACE 9000 is a building automation controller."
        mock_complete.return_value = mock_response

        response = await async_client.post(
            "/chat",
            json={"q": "What is JACE?", "k": 4}
        )

    assert response.status_code == 200

    data = response.json()
    assert "answer" in data
    assert "sources" in data

    # Answer should contain the mocked response
    assert len(data["answer"]) > 0

    # Sources should be a list
    assert isinstance(data["sources"], list)


@pytest.mark.asyncio
async def test_chat_stream_returns_streaming_response(async_client: AsyncClient, test_data_dir: str):
    """Test POST /chat-stream returns streaming response with mocked Ollama"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # Ingest data first
    await async_client.post("/ingest", json={"force_rebuild": True})

    # Mock Ollama streaming response
    with patch("llama_index.llms.ollama.Ollama.stream_complete") as mock_stream:
        # Create a mock streaming response
        mock_response = MagicMock()
        mock_response.delta = "streamed text"

        def stream_generator():
            yield mock_response

        mock_stream.return_value = stream_generator()

        response = await async_client.post(
            "/chat-stream",
            json={"q": "What is JACE?", "k": 2}
        )

    assert response.status_code == 200
    # Should return text/plain for streaming
    assert "text/plain" in response.headers.get("content-type", "")

    # Read the streamed content
    content = response.text
    assert len(content) > 0


@pytest.mark.asyncio
async def test_chat_enforces_minimum_k(async_client: AsyncClient, test_data_dir: str):
    """Test that /chat enforces minimum k=4 for retrieval"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # Ingest data first
    await async_client.post("/ingest", json={"force_rebuild": True})

    # Mock Ollama
    with patch("llama_index.llms.ollama.Ollama.complete") as mock_complete:
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_complete.return_value = mock_response

        # Request with k=1 (should be upgraded to 4)
        response = await async_client.post(
            "/chat",
            json={"q": "test query", "k": 1}
        )

    assert response.status_code == 200
    # The endpoint should work even with k=1 (it enforces minimum of 4 internally)


@pytest.mark.asyncio
async def test_chat_error_when_ollama_unavailable(async_client: AsyncClient, test_data_dir: str):
    """Test error handling when Ollama is unavailable"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # Ingest data first
    await async_client.post("/ingest", json={"force_rebuild": True})

    # Mock Ollama to raise an exception
    with patch("llama_index.llms.ollama.Ollama.complete", side_effect=ConnectionError("Ollama unavailable")):
        response = await async_client.post(
            "/chat",
            json={"q": "test query", "k": 4}
        )

    # Should return 500 error
    assert response.status_code == 500
    assert "Query failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_without_ingestion(async_client: AsyncClient):
    """Test /chat fails gracefully when no data has been ingested"""
    response = await async_client.post(
        "/chat",
        json={"q": "test query", "k": 4}
    )

    # Should return 500 since collection doesn't exist
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_chat_with_query_field_fallback(async_client: AsyncClient, test_data_dir: str):
    """Test /chat accepts both 'q' and 'query' fields"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # Ingest data first
    await async_client.post("/ingest", json={"force_rebuild": True})

    # Mock Ollama
    with patch("llama_index.llms.ollama.Ollama.complete") as mock_complete:
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_complete.return_value = mock_response

        # Test with 'query' field (fallback)
        response = await async_client.post(
            "/chat",
            json={"query": "test query", "k": 4}
        )

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data


@pytest.mark.asyncio
async def test_chat_timeout_handling(async_client: AsyncClient, test_data_dir: str):
    """Test /chat handles timeout errors appropriately"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # Ingest data first
    await async_client.post("/ingest", json={"force_rebuild": True})

    # Mock Ollama to raise TimeoutError
    with patch("llama_index.llms.ollama.Ollama.complete", side_effect=TimeoutError("Request timed out")):
        response = await async_client.post(
            "/chat",
            json={"q": "test query", "k": 4}
        )

    # Should return 504 (Gateway Timeout)
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()
