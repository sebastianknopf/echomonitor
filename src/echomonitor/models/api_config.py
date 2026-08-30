"""Models used by the API integration."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ApiConfig:
    """Configuration required to connect to the EchoGTFS API."""

    base_url: str

    def __post_init__(self) -> None:
        """Validate and normalize the configured base URL."""
        normalized = self.base_url.strip().rstrip("/")
        parsed = urlparse(normalized)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("The API base URL must be an absolute HTTP(S) URL.")

        object.__setattr__(self, "base_url", normalized)


@dataclass(frozen=True, slots=True)
class TokenResponse:
    """OAuth token returned by the API."""

    access_token: str
    token_type: str
