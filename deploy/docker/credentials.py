"""Generate local credentials once, each in the volume of the only services that need it.

/rustfs   root credentials of RustFS (RustFS, storage-init)
/websites operator password, MCP token, preview key, read-write storage user (websites, builder)
/child    read-only storage user (child)

Existing files are kept: restarting the composition never rotates credentials.
"""

import secrets
from pathlib import Path


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o755)
    if not path.exists():
        path.write_text(value)
        # Readable by the unprivileged users of the services mounting this volume.
        path.chmod(0o644)


write("/rustfs/access", "root" + secrets.token_hex(6))
write("/rustfs/secret", secrets.token_urlsafe(32))
write("/websites/storage_access", "websites" + secrets.token_hex(6))
# Storage secrets are command-line arguments of `mc admin user add`: hex never starts with "-".
write("/websites/storage_secret", secrets.token_hex(32))
write("/websites/token", secrets.token_urlsafe(32))
write("/websites/operator_password", secrets.token_urlsafe(12))
write("/websites/preview_secret", secrets.token_hex(32))
write("/child/storage_access", "child" + secrets.token_hex(6))
write("/child/storage_secret", secrets.token_hex(32))
print("credentials ready", flush=True)
