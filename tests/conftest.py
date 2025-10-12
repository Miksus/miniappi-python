import pytest
from miniappi.core.stream import Streamer
from miniappi.testing.mock import MockClient

@pytest.fixture
def mock_server():
    Streamer.conn_client = MockClient()

    yield mock_server
