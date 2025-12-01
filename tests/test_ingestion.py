import pytest
import os
import tempfile
import shutil
from pathlib import Path
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_empty_directory(async_client: AsyncClient):
    """Test POST /ingest with empty data directory"""
    # Create empty temporary directory
    empty_dir = tempfile.mkdtemp(prefix="empty_test_")
    os.environ["DATA_DIR"] = empty_dir

    try:
        response = await async_client.post(
            "/ingest",
            json={"force_rebuild": False}
        )

        # Should return 400 because no files found
        assert response.status_code == 400
        assert "No PDF, TXT, or MD files found" in response.json()["detail"]
    finally:
        shutil.rmtree(empty_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_ingest_with_sample_files(async_client: AsyncClient, test_data_dir: str):
    """Test POST /ingest with sample PDF/TXT files"""
    # Use the test_data_dir fixture which has sample files
    os.environ["DATA_DIR"] = test_data_dir

    response = await async_client.post(
        "/ingest",
        json={"force_rebuild": True}
    )

    assert response.status_code == 200

    data = response.json()
    assert "files_indexed" in data
    assert "total_vectors" in data
    assert "mode" in data

    assert data["files_indexed"] > 0
    assert data["total_vectors"] > 0
    assert data["mode"] == "full_rebuild"


@pytest.mark.asyncio
async def test_incremental_ingestion(async_client: AsyncClient, test_data_dir: str):
    """Test incremental ingestion - second call doesn't re-index existing files"""
    os.environ["DATA_DIR"] = test_data_dir

    # First ingestion (force rebuild)
    response1 = await async_client.post(
        "/ingest",
        json={"force_rebuild": True}
    )
    assert response1.status_code == 200
    data1 = response1.json()
    initial_vectors = data1["total_vectors"]

    # Second ingestion (incremental - should skip already indexed files)
    response2 = await async_client.post(
        "/ingest",
        json={"force_rebuild": False}
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # Should be incremental mode
    assert data2["mode"] == "incremental"
    # Vector count should remain the same (no new files added)
    assert data2["total_vectors"] == initial_vectors


@pytest.mark.asyncio
async def test_force_rebuild_reindexes(async_client: AsyncClient, test_data_dir: str):
    """Test force_rebuild=true re-indexes everything"""
    os.environ["DATA_DIR"] = test_data_dir

    # First ingestion
    response1 = await async_client.post(
        "/ingest",
        json={"force_rebuild": True}
    )
    assert response1.status_code == 200
    data1 = response1.json()

    # Force rebuild
    response2 = await async_client.post(
        "/ingest",
        json={"force_rebuild": True}
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # Should be full_rebuild mode
    assert data2["mode"] == "full_rebuild"
    # Vector counts should be similar (same files re-indexed)
    assert abs(data2["total_vectors"] - data1["total_vectors"]) < 10


@pytest.mark.asyncio
async def test_ingest_nonexistent_directory(async_client: AsyncClient):
    """Test /ingest with nonexistent data directory"""
    os.environ["DATA_DIR"] = "/nonexistent/directory/path"

    response = await async_client.post(
        "/ingest",
        json={"force_rebuild": False}
    )

    assert response.status_code == 400
    assert "Data directory not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_ingest_new_file_incremental(async_client: AsyncClient, test_data_dir: str):
    """Test incremental ingestion when a new file is added"""
    os.environ["DATA_DIR"] = test_data_dir

    # First ingestion
    response1 = await async_client.post(
        "/ingest",
        json={"force_rebuild": True}
    )
    assert response1.status_code == 200
    initial_vectors = response1.json()["total_vectors"]

    # Add a new file
    new_file = Path(test_data_dir) / "new_test_file.txt"
    new_file.write_text("This is a new test document with additional BAS content for incremental testing.")

    # Incremental ingestion should pick up the new file
    response2 = await async_client.post(
        "/ingest",
        json={"force_rebuild": False}
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # Should have more vectors now
    assert data2["total_vectors"] > initial_vectors
    assert data2["mode"] == "incremental"

    # Cleanup
    new_file.unlink()
