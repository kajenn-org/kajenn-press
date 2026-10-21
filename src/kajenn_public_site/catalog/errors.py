"""Persistence errors shared with future service adapters."""


class CatalogError(Exception):
    """Base persistence failure."""


class Conflict(CatalogError):
    """The supplied generation or idempotency input is stale/inconsistent."""


class OwnershipError(CatalogError):
    """Another coordinator already owns this catalog."""


class IntegrityError(CatalogError):
    """Stored schema, references or bytes do not match their declared identity."""


class UnsupportedProfile(CatalogError):
    """The local profile cannot provide its required filesystem primitives."""


class CommitUncertain(CatalogError):
    """Stop writes and reopen; recovery must determine whether publication happened."""
