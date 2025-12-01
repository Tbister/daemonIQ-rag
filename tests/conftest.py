import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app, client as qdrant_client, COLLECTION


@pytest.fixture(scope="module")
def test_collection_name() -> str:
    """Use a separate test collection to avoid polluting production data"""
    return "bas_docs_test"


@pytest.fixture(scope="module")
def test_data_dir() -> Generator[str, None, None]:
    """Create a temporary directory with sample test documents"""
    temp_dir = tempfile.mkdtemp(prefix="daemoniq_test_")

    # Create fixtures directory path
    fixtures_dir = Path(__file__).parent / "fixtures"

    # Copy fixture files if they exist, otherwise create minimal test files
    if fixtures_dir.exists():
        for file in fixtures_dir.glob("*.txt"):
            shutil.copy(file, temp_dir)
    else:
        # Fallback: create minimal test file
        test_file = Path(temp_dir) / "test_doc.txt"
        test_file.write_text("This is a test document for BAS testing.")

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def setup_test_environment(test_collection_name: str, test_data_dir: str):
    """
    Setup test environment with test collection and data directory.
    This runs once per test module.
    """
    # Override environment variables for testing
    os.environ["QDRANT_COLLECTION"] = test_collection_name
    os.environ["DATA_DIR"] = test_data_dir

    yield

    # Cleanup: delete test collection after all tests complete
    try:
        qdrant_client.delete_collection(test_collection_name)
        print(f"\nCleaned up test collection: {test_collection_name}")
    except Exception as e:
        print(f"\nWarning: Could not delete test collection {test_collection_name}: {e}")


@pytest.fixture
async def async_client(setup_test_environment) -> AsyncGenerator[AsyncClient, None]:
    """
    Async test client for FastAPI using httpx.
    Creates a new client for each test function.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_ollama_generate():
    """
    Mock Ollama API responses to avoid real LLM calls during tests.
    Returns a context manager that patches the Ollama client.
    """
    def _mock_generate(*args, **kwargs):
        # Mock response for Ollama.generate()
        mock_response = MagicMock()
        mock_response.text = "This is a mocked LLM response based on the BAS documentation context."
        return mock_response

    with patch("llama_index.llms.ollama.Ollama.complete") as mock_complete:
        mock_complete.return_value = _mock_generate()
        yield mock_complete


@pytest.fixture
def mock_ollama_stream():
    """
    Mock Ollama streaming responses for chat-stream endpoint.
    """
    def _mock_stream(*args, **kwargs):
        # Mock streaming response
        mock_response = MagicMock()
        mock_response.response_gen = iter(["This ", "is ", "a ", "mocked ", "streaming ", "response."])
        return mock_response

    with patch("llama_index.llms.ollama.Ollama.stream_complete") as mock_stream:
        mock_stream.return_value = _mock_stream()
        yield mock_stream


@pytest.fixture
def mock_ollama_http():
    """
    Mock HTTP requests to Ollama for /test-ollama endpoint.
    """
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "model": "llama3.1",
            "response": "OK",
            "done": True
        }
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture(autouse=True)
def reset_index_cache():
    """
    Reset the global index cache before each test.
    This ensures tests don't interfere with each other.
    """
    from app import main
    main._index_cache = None
    yield
    main._index_cache = None
