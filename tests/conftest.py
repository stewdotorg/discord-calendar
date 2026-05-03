"""Pytest configuration — VCR integration tests and custom options."""

import os

import pytest


def pytest_addoption(parser):
    """Add custom CLI options for pytest."""
    parser.addoption(
        "--record",
        action="store_true",
        default=False,
        help="Re-record VCR cassettes against the live Google Calendar API",
    )


def _vcr_record_mode(request) -> str:
    """Return VCR record mode based on --record flag.

    Default: 'none' (play back cassettes, no network).
    --record: 'all' (re-record all cassettes from live API).
    """
    if request.config.getoption("--record"):
        return "all"
    return "none"


def _strip_auth_headers(request):
    """Remove Authorization headers from VCR cassettes for security."""
    if "Authorization" in request.headers:
        del request.headers["Authorization"]
    return request


@pytest.fixture(scope="function")
def vcr(request):
    """Pytest fixture that provides a configured VCR instance.

    Cassettes are stored in tests/cassettes/ with the test function name.
    Authorization headers are stripped before recording.

    When a cassette file does not exist and --record is not set, the test
    is skipped so the full suite can run without live credentials.
    """
    import vcr as vcr_lib

    cassette_name = request.node.name
    record_mode = _vcr_record_mode(request)

    cassette_path = os.path.join(
        "tests", "cassettes", cassette_name
    )

    if record_mode == "none" and not os.path.exists(cassette_path):
        pytest.skip(
            f"Cassette '{cassette_name}' not found. "
            "Run with --record to create it."
        )

    my_vcr = vcr_lib.VCR(
        cassette_library_dir="tests/cassettes",
        record_mode=record_mode,
        match_on=["method", "scheme", "host", "port", "path", "query"],
        before_record_request=_strip_auth_headers,
        decode_compressed_response=True,
    )

    return my_vcr
