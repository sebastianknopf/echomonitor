# EchoMonitor

Minimal Streamlit client for the EchoGTFS monitoring API. Fully AI based setup for demonstration purposes, so there's no license on this project.

## Requirements

- Python 3.12+
- Streamlit

All runtime dependencies are declared in `pyproject.toml`.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
streamlit run src/echomonitor/app.py
```

## Login

The login screen accepts an API base URL, username, and password.

Enter only the base URL, for example:

```text
https://api.example.com
```

EchoMonitor adds the API paths from the OpenAPI specification itself. The login request is therefore sent to:

```text
https://api.example.com/api/auth/token
```

using the OAuth2 password flow.

## Streamlit Community Cloud

Use `src/echomonitor/app.py` as the application entry point.

The project uses a standard `src` layout and keeps the runtime dependency set intentionally minimal.
