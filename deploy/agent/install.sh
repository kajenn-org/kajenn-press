#!/bin/sh
# Prepares a Debian or Ubuntu host to serve published sites behind nginx, Caddy or
# Traefik (N7b): the site server as a container, the server agent as a service.
#
#   sh install.sh <nginx|caddy|traefik> <kajenn-press wheel or source directory>
#
# Run as root. The proxy and Docker are installed and running already: this script
# installs neither. It starts nothing; it prints what is left to fill in.
set -eu

PROXY=${1:-}
SOURCE=${2:-}
HERE=$(cd "$(dirname "$0")" && pwd)

case "$PROXY" in
nginx | caddy | traefik) ;;
*)
	echo "usage: sh install.sh <nginx|caddy|traefik> <kajenn-press wheel or source directory>" >&2
	exit 2
	;;
esac
[ -n "$SOURCE" ] || { echo "Give the kajenn-press wheel or source directory." >&2; exit 2; }
[ "$(id -u)" = 0 ] || { echo "Run as root." >&2; exit 1; }

# The agent: its own user, never root; root only through the sudoers lines of its proxy.
id kpress-agent >/dev/null 2>&1 ||
	useradd --system --home-dir /opt/kpress-agent --shell /usr/sbin/nologin kpress-agent
install -d -m 755 /opt/kpress-agent
python3 -m venv /opt/kpress-agent/venv
/opt/kpress-agent/venv/bin/pip install --quiet "$SOURCE"
install -m 644 "$HERE/agent.py" /opt/kpress-agent/agent.py
install -m 644 "$HERE/kpress-agent.service" /etc/systemd/system/kpress-agent.service

install -d -g kpress-agent -m 750 /etc/kpress-agent
if [ ! -f /etc/kpress-agent/token ]; then
	# The manager keeps the same value in <agent_tokens>/<server name>.token.
	python3 -c 'import secrets; print(secrets.token_urlsafe(32))' >/etc/kpress-agent/token
fi
chown root:kpress-agent /etc/kpress-agent/token
chmod 640 /etc/kpress-agent/token

case "$PROXY" in
nginx) grep -E 'nginx|certbot' "$HERE/sudoers-kpress-agent" >/tmp/kpress-sudoers ;;
caddy) grep -E 'caddy' "$HERE/sudoers-kpress-agent" >/tmp/kpress-sudoers ;;
traefik) : >/tmp/kpress-sudoers ;;
esac
if [ -s /tmp/kpress-sudoers ]; then
	visudo -cf /tmp/kpress-sudoers
	install -m 440 /tmp/kpress-sudoers /etc/sudoers.d/kpress-agent
fi
rm -f /tmp/kpress-sudoers

ENV=/etc/kpress-agent/agent.env
if [ ! -f "$ENV" ]; then
	{
		echo "AGENT_DRIVER=$PROXY"
		echo "AGENT_TOKEN_FILE=/etc/kpress-agent/token"
		echo "# The manager's address; the firewall must allow it too."
		echo "AGENT_ALLOWED="
		echo "AGENT_PORT=8890"
		echo "AGENT_TLS_CERT="
		echo "AGENT_TLS_KEY="
		echo "AGENT_UPSTREAM=http://127.0.0.1:8877"
	} >"$ENV"
	case "$PROXY" in
	nginx)
		install -d -o kpress-agent -m 755 /etc/nginx/kpress.d
		install -d -m 755 /var/www/kpress-acme
		{
			echo "AGENT_NGINX_DIR=/etc/nginx/kpress.d"
			echo "AGENT_ACME_WEBROOT=/var/www/kpress-acme"
			echo "AGENT_ACME_EMAIL="
		} >>"$ENV"
		;;
	traefik)
		install -d -o kpress-agent -m 755 /etc/traefik/kpress
		{
			echo "AGENT_TRAEFIK_DIR=/etc/traefik/kpress"
			echo "AGENT_TRAEFIK_ENTRYPOINT=websecure"
			echo "AGENT_TRAEFIK_RESOLVER=letsencrypt"
		} >>"$ENV"
		;;
	esac
	chmod 640 "$ENV"
	chown root:kpress-agent "$ENV"
fi

# The site server: the kajenn-child image, published on the loopback for the proxy.
install -d -m 755 /etc/kpress-site
# The container runs as uid 10003 (Dockerfile.child): it must read the secrets.
install -d -o 10003 -m 700 /etc/kpress-site/secrets
if [ ! -f /etc/kpress-site/site.env ]; then
	{
		echo "SITE_SERVER_NAME="
		echo "RELEASE_S3_ENDPOINT="
		echo "RELEASE_S3_BUCKET="
		echo "RELEASE_S3_ACCESS_FILE=/secrets/storage_access"
		echo "RELEASE_S3_SECRET_FILE=/secrets/storage_secret"
		echo "PRIVATE_LINK_SECRET_FILE=/secrets/private_link"
		echo "# The proxy reaches the container through the Docker bridge."
		echo "SITE_FORWARDED_ALLOW_IPS=172.16.0.0/12"
	} >/etc/kpress-site/site.env
	chmod 640 /etc/kpress-site/site.env
fi
install -m 644 "$HERE/kpress-site.service" /etc/systemd/system/kpress-site.service
systemctl daemon-reload

cat <<EOF
Installed for $PROXY. Left to do:
  1. /etc/kpress-agent/agent.env: AGENT_ALLOWED, AGENT_TLS_CERT, AGENT_TLS_KEY$([ "$PROXY" = nginx ] && echo ", AGENT_ACME_EMAIL").
  2. /etc/kpress-site/site.env: SITE_SERVER_NAME (the name given to server_add) and the release bucket.
     /etc/kpress-site/secrets, owned by uid 10003: storage_access, storage_secret
     (read-only keys of the release bucket), private_link.
  3. Load the kajenn-child image (docker load, or build deploy/docker/Dockerfile.child).
  4. Copy /etc/kpress-agent/token to the manager as <agent_tokens>/<server name>.token.
EOF
case "$PROXY" in
nginx) echo "  5. nginx.conf, http block: include /etc/nginx/kpress.d/*.conf;" ;;
caddy) echo "  5. Caddy: use $HERE/Caddyfile." ;;
traefik) echo "  5. Traefik: file provider with directory /etc/traefik/kpress and watch true." ;;
esac
cat <<EOF
  6. Firewall: 80 and 443 open; port 8890 only from the manager.
  7. systemctl enable --now kpress-site kpress-agent
EOF
