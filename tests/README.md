# Cross-service tests

Service-local fast tests live beside their applications (`backend/tests` and, when introduced, `frontend` tests). This directory is reserved for Docker-backed integration and end-to-end tests that exercise more than one service.

Phase 1 uses the Compose health checks and documented HTTP smoke checks as its cross-service verification. Business end-to-end fixtures will be added with the first family/identity vertical slice.

