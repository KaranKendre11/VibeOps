"""FastAPI backend for VibeOps.

Wraps the existing LangGraph orchestrator + services behind an HTTP/SSE API and (in production)
serves the built React frontend. Replaces the Streamlit UI during the frontend migration.
"""
