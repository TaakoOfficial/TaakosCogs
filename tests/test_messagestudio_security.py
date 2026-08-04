"""Security regression tests for MessageStudio remote text URLs."""

from messagestudio.messagestudio import MessageStudio


def test_normalizes_exact_pastebin_host_to_raw_path() -> None:
    assert MessageStudio._normalize_text_host_url("https://pastebin.com/abc123") == "https://pastebin.com/raw/abc123"
    assert MessageStudio._normalize_text_host_url("https://www.pastebin.com/abc123?x=1") == (
        "https://www.pastebin.com/raw/abc123?x=1"
    )


def test_does_not_trust_lookalike_pastebin_hosts() -> None:
    malicious = "https://pastebin.com.attacker.example/pastebin.com/abc123"
    assert MessageStudio._normalize_text_host_url(malicious) == malicious


def test_normalizes_exact_gist_host_only() -> None:
    assert MessageStudio._normalize_text_host_url("https://gist.github.com/user/id") == ("https://gist.github.com/user/id/raw")
    malicious = "https://gist.github.com.attacker.example/user/id"
    assert MessageStudio._normalize_text_host_url(malicious) == malicious
