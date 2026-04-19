# Deployment Hardening Guide

Secure your Darwin-MCP Brain Droplet with Nginx, SSL, and environment-variable secrets.

---

## Prerequisites

- Ubuntu 22.04 LTS Droplet ($5/month)
- Domain name pointed at the Droplet IP (e.g. `brain.yourdomain.com`)
- Darwin-MCP deployed to `/opt/mcp-evolution-core` and running via `darwin.service`

---

## Step 1 — Install Nginx and Certbot

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

---

## Step 2 — Configure the Reverse Proxy

Copy the Nginx template into the sites directory and substitute your domain:

```bash
sudo cp /opt/mcp-evolution-core/brain/config/nginx.conf.template \
        /etc/nginx/sites-available/darwin-mcp

# Replace DOMAIN_NAME with your actual domain
sudo sed -i 's/DOMAIN_NAME/brain.yourdomain.com/g' \
        /etc/nginx/sites-available/darwin-mcp

# Enable the site
sudo ln -s /etc/nginx/sites-available/darwin-mcp \
           /etc/nginx/sites-enabled/

# Verify config
sudo nginx -t
sudo systemctl reload nginx
```

---

## Step 3 — Obtain an SSL Certificate (Certbot)

```bash
sudo certbot --nginx -d brain.yourdomain.com
```

Certbot will automatically:
- Obtain a Let's Encrypt certificate
- Update the Nginx config with correct `ssl_certificate` paths
- Add an HTTP → HTTPS redirect block

**Auto-renewal** is already set up by the Certbot package via a systemd timer.
Verify it with:

```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

---

## Step 4 — Harden the Bearer Token

> **Never hardcode `MCP_BEARER_TOKEN` in source code or `darwin.service`.**
> It must live exclusively in the environment file.

### Create the environment file

```bash
# Generate a secure random token
python3 -c "import secrets; print('MCP_BEARER_TOKEN=' + secrets.token_hex(32))"

# Write it to the env file (readable by the darwin user only)
sudo touch /opt/mcp-evolution-core/.env
sudo chown darwin:darwin /opt/mcp-evolution-core/.env
sudo chmod 600 /opt/mcp-evolution-core/.env

# Add the token
echo "MCP_BEARER_TOKEN=<your-generated-token>" | sudo tee /opt/mcp-evolution-core/.env
```

### Verify the service picks it up

```bash
sudo systemctl daemon-reload
sudo systemctl restart darwin
sudo systemctl status darwin

# Confirm the token is NOT visible in the process list
ps aux | grep uvicorn   # should NOT show the token
```

---

## Step 5 — Restart and Verify

```bash
sudo systemctl restart darwin
sudo systemctl status darwin

# Test the SSE endpoint through Nginx (HTTPS)
curl -N \
  -H "Authorization: Bearer <your-token>" \
  "https://brain.yourdomain.com/sse"
```

You should receive a `data:` line with the tool list JSON.

---

## Step 6 — Install the Self-Healing Crontab

```bash
sudo -u darwin bash /opt/mcp-evolution-core/brain/scripts/install_cron.sh
```

This installs an hourly cron that:
1. Checks port 8000 and restarts `darwin.service` if unresponsive
2. Removes stale `.git/index.lock` files from a crashed mutation
3. Runs `git submodule update --remote` to sync the vault

Logs are written to `/var/log/darwin_sanity.log`.

---

## MCP Client Configuration (Cursor / Claude Desktop)

Update your MCP client to use the secure HTTPS endpoint:

```json
{
  "mcpServers": {
    "darwin-brain": {
      "url": "https://brain.yourdomain.com/sse",
      "headers": {
        "Authorization": "Bearer <your-token>"
      }
    }
  }
}
```

---

## Security Checklist

| Item | Command |
|------|---------|
| UFW: allow only 22, 80, 443 | `sudo ufw allow 22 80 443 && sudo ufw enable` |
| Port 8000 blocked externally | `sudo ufw deny 8000` |
| .env file permissions | `sudo chmod 600 /opt/mcp-evolution-core/.env` |
| Certbot auto-renewal active | `sudo systemctl status certbot.timer` |
| darwin.service using uvicorn (not raw python) | `sudo systemctl cat darwin` |
| Self-healing crontab installed | `crontab -l -u darwin` |
