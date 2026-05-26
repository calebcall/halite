# backend/src/halite/inventory/__init__.py
"""Fleet inventory — periodically collects per-minion data (packages, etc.)
into the Halite database for fleet-wide search and version queries.

Phase 1 ships the schema + version-comparison utilities. Subsequent phases
layer on collectors, the search API, the UI, and a background scheduler.
"""
