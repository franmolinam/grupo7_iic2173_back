import pytest
from unittest.mock import patch


# evita que los tests le peguen de verdad a backend.quackpackagemo.me/events/emit
# (create_and_send_package emite eventos SSE por HTTP, no solo en memoria)
@pytest.fixture(autouse=True)
def _mock_emit_event():
    with patch("src.services.package_service.requests.post") as mock_post:
        yield mock_post
