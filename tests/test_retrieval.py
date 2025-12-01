import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_retrieve_returns_chunks(async_client: AsyncClient, test_data_dir: str):
    """Test POST /retrieve returns chunks with scores and metadata"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # First ingest some data
    ingest_response = await async_client.post(
        "/ingest",
        json={"force_rebuild": True}
    )
    assert ingest_response.status_code == 200

    # Now retrieve
    response = await async_client.post(
        "/retrieve",
        json={"q": "JACE controller", "k": 4}
    )

    assert response.status_code == 200

    data = response.json()
    assert "count" in data
    assert "results" in data

    # Should return some results (at least 1)
    assert data["count"] > 0
    assert len(data["results"]) > 0

    # Check structure of first result
    first_result = data["results"][0]
    assert "score" in first_result
    assert "text" in first_result
    assert "metadata" in first_result


@pytest.mark.asyncio
async def test_retrieve_scores_valid_range(async_client: AsyncClient, test_data_dir: str):
    """Test similarity scores are in valid range (0.0-1.0)"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # Ingest data first
    await async_client.post("/ingest", json={"force_rebuild": True})

    # Retrieve
    response = await async_client.post(
        "/retrieve",
        json={"q": "controller", "k": 4}
    )

    assert response.status_code == 200
    data = response.json()

    # Check all scores are in valid range
    for result in data["results"]:
        score = result["score"]
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_retrieve_with_no_matching_documents(async_client: AsyncClient, test_data_dir: str):
    """Test POST /retrieve with query unlikely to match"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # Ingest data first
    await async_client.post("/ingest", json={"force_rebuild": True})

    # Query with random unrelated text
    response = await async_client.post(
        "/retrieve",
        json={"q": "quantum physics nuclear reactor spacecraft", "k": 4}
    )

    assert response.status_code == 200
    data = response.json()

    # Should still return results (vector search always returns top-k)
    # but scores should be lower
    assert "count" in data
    assert "results" in data

    # If there are results, they should have low similarity scores
    if data["count"] > 0:
        for result in data["results"]:
            # Scores should be relatively low for unrelated content
            # (though this depends on the actual test data)
            assert result["score"] >= 0.0


@pytest.mark.asyncio
async def test_retrieve_respects_k_parameter(async_client: AsyncClient, test_data_dir: str):
    """Test that retrieve respects the k parameter"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # Ingest data first
    await async_client.post("/ingest", json={"force_rebuild": True})

    # Retrieve with k=2
    response = await async_client.post(
        "/retrieve",
        json={"q": "controller", "k": 2}
    )

    assert response.status_code == 200
    data = response.json()

    # Should return at most k results
    assert data["count"] <= 2
    assert len(data["results"]) <= 2


@pytest.mark.asyncio
async def test_retrieve_without_ingestion(async_client: AsyncClient):
    """Test /retrieve fails gracefully when no data has been ingested"""
    response = await async_client.post(
        "/retrieve",
        json={"q": "test query", "k": 4}
    )

    # Should return 500 since collection doesn't exist
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_retrieve_with_query_field_fallback(async_client: AsyncClient, test_data_dir: str):
    """Test /retrieve accepts both 'q' and 'query' fields"""
    import os
    os.environ["DATA_DIR"] = test_data_dir

    # Ingest data first
    await async_client.post("/ingest", json={"force_rebuild": True})

    # Test with 'query' field (fallback)
    response = await async_client.post(
        "/retrieve",
        json={"query": "controller", "k": 2}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0
