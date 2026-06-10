"""omics_backend — backend for the AI-assisted omics desktop application.

The backend is the only component that holds vendor credentials and the only path to
vendor models (the AI gateway). It validates config, runs Milestone-1 services, and
records provenance. See docs/SPEC.md (authoritative).
"""

__version__ = "0.1.0"
