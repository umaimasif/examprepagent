"""Vercel Python serverless entry point.

Vercel's @vercel/python runtime detects the module-level `app` ASGI callable.
Local dev:  uvicorn api.index:app --reload
"""
import os
import sys

# Make the project root importable when Vercel runs this file in isolation.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routes import app  # noqa: E402

__all__ = ["app"]
