"""
Role:   HTTP layer: FastAPI application exposing corpus, retrieval, graph, chat and eval.
Input:  none
Output: create_app() re-exported for the CLI and the tests.
Flow:   Package marker; the application factory lives in app.py.
"""

from rag_lab_generator.api.app import create_app

__all__ = ["create_app"]
