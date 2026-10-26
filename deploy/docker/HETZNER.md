# kpress on the Hetzner host

Installs the websites manager at `https://kpress.genro.com`, with private previews at
`https://preview.kpress.genro.com`, behind the nginx already running on the host.
Only the manager runs: no `demo` profile, no public site served from this host.

Host facts (checked 2026-10-26): 46.62.203.133, x86_64, Ubuntu, nginx 1.24.0 on the
host listening on 80/443, certbot at `/usr/bin/certbot`, Docker with Compose,
port 8875 free. Other sites in `/etc/nginx/sites-enabled` are not touched.

Run every command as root on the host unless stated otherwise. Never run
`tests/docker` here: those tests delete the composition's volumes.

## 0. Prerequisites

- The deployment files are on `main` of `kajenn-org/kajenn-press`
  (`deploy/docker/compose.yaml` reading `.env`, `nginx-kpress.conf`).
- DNS: two A records pointing to `46.62.203.133` in the Route 53 zone `genro.com`
  (created 2026-10-26, TTL 300): `kpress.genro.com` and `preview.kpress.genro.com`.
  Check from any machine:

```bash
dig +short kpress.genro.com preview.kpress.genro.com
```

Both lines must print `46.62.203.133` before step 3.

## 1. Checkout

```bash
git clone https://github.com/kajenn-org/kajenn-press.git /opt/kpress
```

## 2. Configuration and first start

```bash
cat > /opt/kpress/deploy/docker/.env <<'EOF'
KPRESS_SCHEME=https
KPRESS_MANAGEMENT_HOST=kpress.genro.com
KPRESS_PREVIEW_HOST=preview.kpress.genro.com
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
certbot certonly --webroot -w /var/www/kpress-acme -d preview.kpress.genro.com
```

Each certificate lands in `/etc/letsencrypt/live/<name>/`, the paths used by
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
curl -s https://preview.kpress.genro.com/admin/
```

Expected: `200`; `301 https://kpress.genro.com/admin/`; `Preview unavailable`.

The operator password:

```bash
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml exec websites cat /secrets/operator_password
```

Sign in at `https://kpress.genro.com/admin/` as `operator`.

## Update

```bash
cd /opt/kpress && git pull --ff-only && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml up -d --build
```

If `nginx-kpress.conf` changed, repeat step 4.

## Restart and stop

`docker compose ... restart` and `down` (without `-v`) keep catalog and credentials.
`down -v` deletes the catalog and the generated credentials; the next `up` starts an
empty catalog. Releases already exported stay in the bucket.

## Manual backup

The catalog and the generated credentials live in the named volumes
`kajenn-websites_websites-data` and `kajenn-websites_websites-secrets`. Releases are in
the bucket and can be exported again from the catalog with `release_export`.

```bash
mkdir -p /opt/kpress-backup && cd /opt/kpress && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml stop websites
for v in websites-data websites-secrets; do docker run --rm -v kajenn-websites_$v:/v:ro -v /opt/kpress-backup:/b python:3.12-slim tar czf /b/$v-$(date +%F).tgz -C /v .; done
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml start websites
```

The archives contain credentials: keep `/opt/kpress-backup` private.
