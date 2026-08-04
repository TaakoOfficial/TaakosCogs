"""Security regression tests for WHMCS API authentication."""

import pytest

from whmcs.whmcs_api import WHMCSAPIClient, WHMCSAuthenticationError


def test_whmcs_uses_api_identifier_and_secret() -> None:
    client = WHMCSAPIClient("https://billing.example.com")
    client.set_api_credentials("identifier", "secret", "access-key")
    payload = client._build_request_data("GetClients", {"limitnum": 10})
    assert payload == {
        "action": "GetClients",
        "responsetype": "json",
        "identifier": "identifier",
        "secret": "secret",
        "accesskey": "access-key",
        "limitnum": 10,
    }


def test_whmcs_rejects_requests_without_api_credentials() -> None:
    client = WHMCSAPIClient("https://billing.example.com")
    with pytest.raises(WHMCSAuthenticationError, match="No authentication credentials"):
        client._build_request_data("GetClients")
    assert not hasattr(client, "set_admin_credentials")
