"""Minimal HTTP client for the EchoGTFS API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from echomonitor.models.api_config import ApiConfig

TOKEN_PATH = "/api/auth/token"
DEFAULT_TIMEOUT_SECONDS = 15.0
ROLLING_TOKEN_HEADER = "X-New-Token"


class ApiError(RuntimeError):
    """Raised when an API request fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class ApiClient:
    """Session-bound client for the EchoGTFS API."""

    config: ApiConfig
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    token: str | None = None

    def login(self, username: str, password: str) -> None:
        """Authenticate using the OAuth2 password flow."""
        request = Request(
            self._url(TOKEN_PATH),
            data=urlencode(
                {
                    "grant_type": "password",
                    "username": username,
                    "password": password,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = self._read_json_response(response)
                new_token = response.headers.get(ROLLING_TOKEN_HEADER)
        except HTTPError as exc:
            raise _login_error(exc) from exc
        except (URLError, TimeoutError) as exc:
            raise ApiError(
                "The API could not be reached. Check the base URL and network connection."
            ) from exc

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ApiError("The API returned an invalid token response.")

        self.token = new_token or access_token

    def get_json(self, path: str) -> dict[str, Any]:
        """Perform an authenticated GET request and return its JSON object."""
        if not self.token:
            raise ApiError("Authentication is required.", status_code=401)

        request = Request(
            self._url(path),
            headers={"Authorization": f"Bearer {self.token}"},
            method="GET",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = self._read_json_response(response)
                self._update_token(response.headers.get(ROLLING_TOKEN_HEADER))
                return payload
        except HTTPError as exc:
            if exc.code == 401:
                self.clear_token()
                raise ApiError(
                    "The authentication session is no longer valid.",
                    status_code=401,
                ) from exc

            raise ApiError(
                f"The API returned HTTP {exc.code}.",
                status_code=exc.code,
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise ApiError(
                "The API could not be reached. Check the base URL and network connection."
            ) from exc

    def clear_token(self) -> None:
        """Clear the current access token."""
        self.token = None

    def _update_token(self, new_token: str | None) -> None:
        if new_token:
            self.token = new_token

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}/{path.lstrip('/')}"

    @staticmethod
    def _read_json_response(response: Any) -> dict[str, Any]:
        try:
            payload = json.loads(response.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            raise ApiError("The API returned an invalid JSON response.") from exc

        if not isinstance(payload, dict):
            raise ApiError("The API returned an invalid JSON response.")

        return payload


def _login_error(error: HTTPError) -> ApiError:
    if error.code == 400:
        message = "The API rejected the login because the user is inactive."
    elif error.code == 401:
        message = "Invalid username or password."
    elif error.code == 422:
        message = "The API rejected the login data."
    else:
        message = f"The API returned HTTP {error.code}."

    return ApiError(message, status_code=error.code)
