"""Per-request context for the API adapter.

``RequestContext`` carries the identity that flows through a single API request.
Today that is just the session id; it is intentionally minimal. When auth lands
(Phase 8), authenticated-user identity will be added here as NEW fields without
reshaping handler signatures — handlers already receive the context instead of
reaching into the raw request ad hoc, so the extension point is in one place.

Deliberately absent: ``tenant_id``. V1 has no multi-tenancy — that is a V2
concern, addable later via a migration. Do not add a tenant field here.

This type lives in the API adapter only. The framework-agnostic core (``nixus/``)
never imports it; handlers pass plain values (e.g. ``ctx.session_id``) across the
boundary, so rule 1 (one-way dependency direction) stays intact.

Note: session identity currently arrives in the request body, so the context is
built at handler entry via :meth:`RequestContext.for_session`. When identity
moves to a header / auth token, this can become a FastAPI ``Depends`` provider
without changing the handlers that already take ``ctx.session_id``.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    """Immutable per-request identity. session_id only in V1."""

    session_id: str

    @classmethod
    def for_session(cls, session_id: str | None) -> "RequestContext":
        """Build a context, generating a session id when the caller didn't supply one.

        Mirrors the previous inline ``req.session_id or str(uuid.uuid4())`` exactly.
        """
        return cls(session_id=session_id or str(uuid.uuid4()))
