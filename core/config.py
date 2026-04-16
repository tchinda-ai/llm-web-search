"""
core/config.py — centralised environment variable resolution.

Imported by every core sub-module. Neither app.py nor api.py should read
os.environ directly — they always get values through this module.
"""

import os

NVIDIA_API_KEY: str = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_MODEL: str = os.environ.get("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
SEARXNG_URL: str = os.environ.get("SEARXNG_URL", "http://localhost:8080")
