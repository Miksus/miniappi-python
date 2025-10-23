import pytest
from miniappi.core import App
from miniappi.core.connection.mock import MockClient

@pytest.fixture
def mock_server():
    App.conn_client = MockClient()

    yield mock_server
