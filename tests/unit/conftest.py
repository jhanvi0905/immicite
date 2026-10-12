import pytest
from pytest_socket import disable_socket, enable_socket


@pytest.fixture(autouse=True)
def no_network():
    """Unit tests never touch the network (docs/architecture.md, section 8)."""
    # Unix sockets stay allowed: the asyncio event loop needs one internally.
    disable_socket(allow_unix_socket=True)
    yield
    enable_socket()
