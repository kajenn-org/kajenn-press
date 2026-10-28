"""Domain errors and the server-owned access policy."""

from copy import deepcopy


class DomainError(Exception):
    def __init__(self, code, message, *, resource_id=None, block=None, details=None):
        super().__init__(message)
        self.code = code
        self.resource_id = resource_id
        self.block = block
        self.details = details

    def as_dict(self):
        return {
            "code": self.code,
            "message": str(self),
            "resource_id": self.resource_id,
            "block": self.block,
            "details": self.details,
        }


class AccessPolicy:
    """Trusted deployment policy: identity -> scope -> permission names.

    Scopes are installation, library, site:<stable ID> or administrator wildcard *.
    Permissions include read, write, use, create_site, build, preview_grant and publish;
    write does not imply read/use/build/preview_grant/publish.
    Configuration is private and supplied by the host, never by an API payload.
    """

    def __init__(self, grants):
        self.grants = deepcopy(grants)

    def allows(self, identity, scope, permission):
        rules = self.grants.get(identity, {})
        return permission in rules.get(scope, ()) or permission in rules.get("*", ())

    def require(self, identity, scope, permission):
        if not identity:
            raise DomainError("unauthenticated", "An authenticated principal is required")
        if not self.allows(identity, scope, permission):
            raise DomainError("forbidden", f"Missing {permission} grant in {scope}")
