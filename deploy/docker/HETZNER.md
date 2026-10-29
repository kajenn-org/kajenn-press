# kpress on the Hetzner host

Installs the websites manager at `https://kpress.genro.com`, behind the nginx already
running on the host. Only the manager runs: no `demo` profile, no public site served
from this host (step 7 describes what serving them needs).

Host facts (checked 2026-10-26): 46.62.203.133, x86_64, Ubuntu, nginx 1.24.0 on the
host listening on 80/443, certbot at `/usr/bin/certbot`, Docker with Compose,
port 8875 free. Other sites in `/etc/nginx/sites-enabled` are not touched.

Run every command as root on the host unless stated otherwise. Never run
`tests/docker` here: those tests delete the composition's volumes.

## 0. Prerequisites

- The deployment files are on `main` of `kajenn-org/kajenn-press`
  (`deploy/docker/compose.yaml` reading `.env`, `nginx-kpress.conf`).
- DNS: an A record `kpress.genro.com` pointing to `46.62.203.133` in the Route 53 zone
  `genro.com` (created 2026-10-26, TTL 300). The record `preview.kpress.genro.com`
  created the same day is no longer used. Check from any machine:

```bash
dig +short kpress.genro.com
```

It must print `46.62.203.133` before step 3.

## 1. Checkout

```bash
git clone https://github.com/kajenn-org/kajenn-press.git /opt/kpress
```

## 2. Configuration and first start

```bash
cat > /opt/kpress/deploy/docker/.env <<'EOF'
KPRESS_SCHEME=https
KPRESS_MANAGEMENT_HOST=kpress.genro.com
KPRESS_TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
KPRESS_S3_ENDPOINT=https://fsn1.your-objectstorage.com
KPRESS_S3_BUCKET=kpress-releases
KPRESS_S3_CREDENTIALS_DIR=/opt/kpress-secrets
EOF
chmod 600 /opt/kpress/deploy/docker/.env
```

Releases go to the private Hetzner Object Storage bucket `kpress-releases`
(Falkenstein, created 2026-10-26), not to RustFS. Object Storage keys are valid for
every bucket of the project; the host already holds a pair for the Sourcerer
backup. Copy it into the two files the composition mounts, without printing it:

```bash
install -d -m 700 /opt/kpress-secrets
(set -a; . /opt/sourcerer-backup/aws.env; umask 077; printf '%s\n' "$AWS_ACCESS_KEY_ID" > /opt/kpress-secrets/access; printf '%s\n' "$AWS_SECRET_ACCESS_KEY" > /opt/kpress-secrets/secret)
ls -l /opt/kpress-secrets
```

The files must be readable by uid 10002 (websites):

```bash
chown -R 10002:10002 /opt/kpress-secrets
```

nginx connects to `127.0.0.1:8875`; Docker forwards the connection, so websites sees
it coming from the gateway of the composition network, an address in Docker's
private ranges. Port 8875 is published on `127.0.0.1` only, so only host processes
and the composition's own containers reach it.

```bash
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml up -d --build
```

```bash
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml ps
```

`websites` must be running and `secrets` exited with code 0; `rustfs` and `storage-init`
are not started. websites starts only after its release storage qualification accepted
the bucket; a refused bucket stops it with an error in `docker compose ... logs websites`.

## 3. Certificates

nginx must answer the certbot challenge on port 80 before the 443 blocks exist.
Install the port-80 block alone first:

```bash
mkdir -p /var/www/kpress-acme
sed -n '1,/^}/p' /opt/kpress/deploy/docker/nginx-kpress.conf > /etc/nginx/sites-available/kpress
ln -s /etc/nginx/sites-available/kpress /etc/nginx/sites-enabled/kpress
nginx -t && systemctl reload nginx
```

```bash
certbot certonly --webroot -w /var/www/kpress-acme -d kpress.genro.com
```

The certificate lands in `/etc/letsencrypt/live/kpress.genro.com/`, the path used by
`nginx-kpress.conf`. Renewal uses the same webroot through the host's certbot timer.

## 4. Full nginx configuration

```bash
cp /opt/kpress/deploy/docker/nginx-kpress.conf /etc/nginx/sites-available/kpress
nginx -t && systemctl reload nginx
```

## 5. Check

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://kpress.genro.com/admin/
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' http://kpress.genro.com/admin/
```

Expected: `200`; `301 https://kpress.genro.com/admin/`.

The operator password:

```bash
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml exec websites cat /secrets/operator_password
```

Sign in at `https://kpress.genro.com/admin/` as `operator`.

## 6. Site sources

Site sources (N3) live in a separate private bucket, `kpress-sources`, with S3
versioning enabled: every save is a version. Publishing page by page (N4) writes to
`kpress-releases`, which then needs versioning too: each page object and each site
index is a version. Without `KPRESS_SOURCES_BUCKET` the site operations answer
`unavailable` and the rest of kpress works as before.

1. Create the bucket `kpress-sources` in the Hetzner console, in the same project
   and location as `kpress-releases` (Falkenstein), private.
2. Enable versioning on both buckets from the websites container, which already holds
   the project keys and s3fs. The command prints the state read back for each:

```bash
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml exec -T websites python -c "
import os, s3fs
from pathlib import Path
fs = s3fs.S3FileSystem(key=Path(os.environ['RELEASE_S3_ACCESS_FILE']).read_text().strip(), secret=Path(os.environ['RELEASE_S3_SECRET_FILE']).read_text().strip(), client_kwargs={'endpoint_url': os.environ['RELEASE_S3_ENDPOINT']})
for bucket in ('kpress-sources', 'kpress-releases'):
    fs.call_s3('put_bucket_versioning', Bucket=bucket, VersioningConfiguration={'Status': 'Enabled'})
    print(bucket, fs.call_s3('get_bucket_versioning', Bucket=bucket).get('Status'))"
```

   Expected: `kpress-sources Enabled` and `kpress-releases Enabled`. Versioning cannot
   be turned off afterwards, only suspended. The releases already exported by the old
   path stay readable.
3. Add the bucket to the server `.env` and update:

```bash
printf 'KPRESS_SOURCES_BUCKET=kpress-sources\n' >> /opt/kpress/deploy/docker/.env
cd /opt/kpress && git pull --ff-only && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml up -d --build
```

   At startup websites refuses a source or release bucket whose versioning is not enabled.

Object Storage keys are valid for every bucket of the project, so these keys can read
the sources. They must never be given to a child: when published sites are served
from this host, children need keys limited to the release bucket. Whether Hetzner
offers bucket-limited keys is not verified.

## 7. Serving published sites from this host

Not applied yet: the owner decided that this host runs the manager only, and public
serving comes later. When it does, a site server (`deploy/docker/site_server.py`, the
`site-server` service of the demo) runs with:

- read-only keys limited to `kpress-releases`, including `GetObjectVersion` and
  `ListBucketVersions`, since pages are read by pinned version. Hetzner project keys
  read every bucket, so they cannot be used here; bucket-limited keys are not verified;
- the private-link secret of websites (`/secrets/private_link` in the websites
  volume), mounted read-only and named by `PRIVATE_LINK_SECRET_FILE`;
- an nginx server block per public domain, as in step 4, proxying to the site server
  on port 8877 with `Host`, and a certificate per domain.

The site server reads `bindings.json` from `kpress-releases`: a site gets its address
from the public origin of its root page (SEO tab) at its next Publish, with no restart.

## Update

```bash
cd /opt/kpress && git pull --ff-only && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml up -d --build
```

If `nginx-kpress.conf` changed, repeat step 4. The version of 2026-10-29 drops the
`preview.kpress.genro.com` server block; its certificate can be removed with
`certbot delete --cert-name preview.kpress.genro.com`.

## Restart and stop

`docker compose ... restart` and `down` (without `-v`) keep working copies and
credentials. `down -v` deletes the working copies not yet saved and the generated
credentials. Site sources and published pages stay in their buckets.

## Manual backup

The working copies and the generated credentials live in the named volumes
`kajenn-websites_websites-data` and `kajenn-websites_websites-secrets`. Site sources and
published pages are versioned in their buckets.

```bash
mkdir -p /opt/kpress-backup && cd /opt/kpress && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml stop websites
for v in websites-data websites-secrets; do docker run --rm -v kajenn-websites_$v:/v:ro -v /opt/kpress-backup:/b python:3.12-slim tar czf /b/$v-$(date +%F).tgz -C /v .; done
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml start websites
```

The archives contain credentials: keep `/opt/kpress-backup` private.
