# kpress on the Hetzner host

Installs the websites manager at `https://kpress.genro.org`, with private previews at
`https://preview.kpress.genro.org`, behind the nginx already running on the host.
Only the manager runs: no `demo` profile, no public site served from this host.

Host facts (checked 2026-10-26): 46.62.203.133, x86_64, Ubuntu, nginx 1.24.0 on the
host listening on 80/443, certbot at `/usr/bin/certbot`, Docker with Compose,
port 8875 free. Other sites in `/etc/nginx/sites-enabled` are not touched.

Run every command as root on the host unless stated otherwise. Never run
`tests/docker` here: those tests delete the composition's volumes.

## 0. Prerequisites

- The deployment files are on `main` of `kajenn-org/kajenn-press`
  (`deploy/docker/compose.yaml` reading `.env`, `nginx-kpress.conf`).
- DNS: two A records pointing to `46.62.203.133`, created in the genro.org zone:
  `kpress.genro.org` and `preview.kpress.genro.org`. Check from any machine:

```bash
dig +short kpress.genro.org preview.kpress.genro.org
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
KPRESS_MANAGEMENT_HOST=kpress.genro.org
KPRESS_PREVIEW_HOST=preview.kpress.genro.org
KPRESS_TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
EOF
chmod 600 /opt/kpress/deploy/docker/.env
```

nginx connects to `127.0.0.1:8875`; Docker forwards the connection, so websites sees
it coming from the gateway of the composition network, an address in Docker's
private ranges. Port 8875 is published on `127.0.0.1` only, so only host processes
and the composition's own containers reach it.

```bash
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml up -d --build
```

```bash
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml ps
```

`websites` and `rustfs` must be running; `secrets` and `storage-init` exited with code 0.

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
certbot certonly --webroot -w /var/www/kpress-acme -d kpress.genro.org
certbot certonly --webroot -w /var/www/kpress-acme -d preview.kpress.genro.org
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
curl -s -o /dev/null -w '%{http_code}\n' https://kpress.genro.org/admin/
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' http://kpress.genro.org/admin/
curl -s https://preview.kpress.genro.org/admin/
```

Expected: `200`; `301 https://kpress.genro.org/admin/`; `Preview unavailable`.

The operator password:

```bash
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml exec websites cat /secrets/operator_password
```

Sign in at `https://kpress.genro.org/admin/` as `operator`.

## Update

```bash
cd /opt/kpress && git pull --ff-only && docker compose -f deploy/docker/compose.yaml up -d --build
```

If `nginx-kpress.conf` changed, repeat step 4.

## Restart and stop

`docker compose ... restart` and `down` (without `-v`) keep catalog, releases and
credentials. `down -v` deletes all of them; the next `up` starts empty with new
credentials.

## Manual backup

The state lives in named volumes: `kajenn-websites_websites-data` (catalog),
`kajenn-websites_rustfs-data` (releases), and the three secrets volumes.

```bash
mkdir -p /opt/kpress-backup && cd /opt/kpress && docker compose -f deploy/docker/compose.yaml stop websites rustfs
for v in websites-data rustfs-data websites-secrets rustfs-secrets child-secrets; do docker run --rm -v kajenn-websites_$v:/v:ro -v /opt/kpress-backup:/b python:3.12-slim tar czf /b/$v-$(date +%F).tgz -C /v .; done
cd /opt/kpress && docker compose -f deploy/docker/compose.yaml start rustfs websites
```

The archives contain credentials: keep `/opt/kpress-backup` private.
