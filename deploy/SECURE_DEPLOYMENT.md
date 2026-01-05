# Secure deployment guide (VPS / Docker)

This project includes a local dashboard. Treat it as **sensitive** (it can expose strategy state, positions, etc.).

## 1) Minimum safe defaults (no public exposure)

Run the dashboard bound to localhost only:

```bash
python run_with_dashboard.py --dry-run --port 8888 --bind 127.0.0.1
```

## 2) Firewall (UFW example)

Allow only SSH + HTTPS publicly:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Do **NOT** open 8888 publicly.

## 3) Reverse proxy (nginx) + Basic Auth + HTTPS

### Install nginx + certbot

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx apache2-utils
```

### Create HTTP basic auth file

```bash
sudo htpasswd -c /etc/nginx/.htpasswd youruser
```

### Configure nginx

Copy `deploy/nginx_polymarket_arb.conf` to:

- `/etc/nginx/sites-available/polymarket-arb`
- symlink to `/etc/nginx/sites-enabled/polymarket-arb`

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Get a TLS certificate (Let's Encrypt)

```bash
sudo certbot --nginx -d dashboard.example.com
```

## 4) App-level token (recommended defense-in-depth)

Set a long random token:

```bash
python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
```

Export it (or put in `.env`):

```bash
export DASHBOARD_TOKEN="..."
export DASHBOARD_ALLOWED_ORIGINS="https://dashboard.example.com"
```

When accessing directly (without nginx basic auth), you can pass:
- HTTP: `Authorization: Bearer <token>` or `?token=<token>`
- WebSocket: `?token=<token>` (the dashboard JS can be adjusted if you want token injection)

If you use nginx basic auth, you may not need the app token, but keeping both is safer.

## 5) Docker deployment (recommended)

- Build and run app bound to **localhost only** (nginx publishes 443):

```bash
cp .env.example .env
# edit .env and set DASHBOARD_TOKEN + DASHBOARD_ALLOWED_ORIGINS
docker compose -f deploy/docker-compose.yml up -d --build
```

## 6) Operational hardening tips

- Run the service under a dedicated OS user.
- Store API keys in a secrets manager (not in config files).
- Enable automatic security updates on the VPS.
- Use fail2ban for SSH and/or nginx auth endpoints if exposed.
- Monitor logs and set alerting for repeated auth failures / connection spikes.
