# Pascal Web Logger — Raspberry Pi Deployment

This guide covers deploying Pascal Web Logger to a Raspberry Pi on your home network.

## Prerequisites

- Raspberry Pi 4 (or newer), 2GB+ RAM
- 64-bit Raspberry Pi OS (Bookworm or newer)
- Ethernet connection (preferred) or Wi-Fi configured
- SSH enabled

## Quick Start

### 1. Flash Raspberry Pi OS

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Select **Raspberry Pi OS Lite (64-bit)** — no desktop needed
3. Click the gear icon to configure:
   - Set hostname: `pascal`
   - Enable SSH with password authentication
   - Set username/password (e.g., `pi` / your-password)
   - Configure Wi-Fi if not using Ethernet
   - Set timezone to your local timezone
4. Flash to SD card and boot the Pi

### 2. Connect to the Pi

Wait 1-2 minutes after boot, then:

```bash
# Find the Pi on your network
ping pascal.local

# SSH in
ssh pi@pascal.local
```

If `pascal.local` doesn't resolve, find the IP via your router or use:
```bash
# On Mac/Linux
arp -a | grep -i raspberry
```

### 3. Clone and Install

```bash
# Clone the repository
sudo git clone https://github.com/YOUR_USERNAME/pascal-monitor.git /opt/pascal-web

# Run the install script
cd /opt/pascal-web
sudo bash web/deploy/install_on_pi.sh
```

The script will:
- Install Python, SQLite, and other dependencies
- Create a `pascal` service user
- Set up the Python virtual environment
- Run database migrations
- Install and start the systemd service

### 4. Verify Installation

From another device on your network:

```bash
# Health check
curl http://pascal.local:8000/healthz

# Or open in browser
open http://pascal.local:8000
```

## Configuration

Edit `/etc/pascal-web.env` to customize:

```bash
sudo nano /etc/pascal-web.env
```

Available settings:
- `DATABASE_URL` — Database connection string
- `PORT` — Server port (default: 8000)
- `TIMEZONE` — Display timezone (default: America/New_York)
- `CSV_EXPORT_DIR` — Where to save CSV exports
- `LOG_USERS` — Comma-separated list of user names

After editing, restart the service:
```bash
sudo systemctl restart pascal-web
```

## Daily Operations

### View Logs

```bash
# Follow logs in real-time
journalctl -u pascal-web -f

# Last 100 lines
journalctl -u pascal-web -n 100

# Logs since boot
journalctl -u pascal-web -b
```

### Service Management

```bash
# Check status
sudo systemctl status pascal-web

# Restart
sudo systemctl restart pascal-web

# Stop
sudo systemctl stop pascal-web

# Start
sudo systemctl start pascal-web
```

### Upgrading

From your development machine, push changes to the repo. Then on the Pi:

```bash
ssh pi@pascal.local
cd /opt/pascal-web
git pull
sudo systemctl restart pascal-web
```

Or as a one-liner from your Mac:
```bash
ssh pi@pascal.local 'cd /opt/pascal-web && git pull && sudo systemctl restart pascal-web'
```

### Pulling CSV Exports to Mac

From the `web/` directory on your Mac:

```bash
make pull-csvs
```

Or manually:
```bash
rsync -avz pi@pascal.local:/opt/pascal-web/exports/*.csv ../data/
```

## Database Backup

The database is stored at `/opt/pascal-web/web/pascal.db`.

### Manual Backup

```bash
ssh pi@pascal.local
cp /opt/pascal-web/web/pascal.db /opt/pascal-web/backups/pascal-$(date +%Y-%m-%d).db
```

### Automated Daily Backup (Optional)

Add a cron job:

```bash
sudo crontab -e
```

Add this line (backs up at 3 AM daily, keeps last 30 days):
```
0 3 * * * cp /opt/pascal-web/web/pascal.db /opt/pascal-web/backups/pascal-$(date +\%Y-\%m-\%d).db && find /opt/pascal-web/backups -name "pascal-*.db" -mtime +30 -delete
```

### Restore from Backup

```bash
sudo systemctl stop pascal-web
cp /opt/pascal-web/backups/pascal-YYYY-MM-DD.db /opt/pascal-web/web/pascal.db
sudo chown pascal:pascal /opt/pascal-web/web/pascal.db
sudo systemctl start pascal-web
```

## Troubleshooting

### Service won't start

```bash
# Check logs for errors
journalctl -u pascal-web -n 50 --no-pager

# Verify the venv is set up
ls -la /opt/pascal-web/web/.venv/bin/uvicorn

# Test manually
cd /opt/pascal-web/web
sudo -u pascal .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Can't connect from other devices

1. Check the Pi's firewall:
   ```bash
   sudo ufw status
   # If active, allow port 8000:
   sudo ufw allow 8000
   ```

2. Verify the service is listening:
   ```bash
   ss -tlnp | grep 8000
   ```

3. Check the Pi's IP address:
   ```bash
   hostname -I
   ```

### mDNS (pascal.local) not working

Install/enable Avahi:
```bash
sudo apt-get install avahi-daemon
sudo systemctl enable avahi-daemon
sudo systemctl start avahi-daemon
```

### Permission errors

```bash
# Fix ownership
sudo chown -R pascal:pascal /opt/pascal-web
```

## Public Access (Optional)

To access Pascal from outside your home network without opening router ports, use Cloudflare Tunnel.

1. Install cloudflared on the Pi:
   ```bash
   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -o /usr/local/bin/cloudflared
   chmod +x /usr/local/bin/cloudflared
   ```

2. Authenticate with Cloudflare:
   ```bash
   cloudflared tunnel login
   ```

3. Create a tunnel:
   ```bash
   cloudflared tunnel create pascal
   ```

4. See `cloudflared.example.yml` for configuration.

## File Locations

| Item | Location |
|------|----------|
| Application | `/opt/pascal-web/` |
| Virtual environment | `/opt/pascal-web/web/.venv/` |
| Database | `/opt/pascal-web/web/pascal.db` |
| Configuration | `/etc/pascal-web.env` |
| Service file | `/etc/systemd/system/pascal-web.service` |
| CSV exports | `/opt/pascal-web/exports/` |
| Backups | `/opt/pascal-web/backups/` |
| Logs | `journalctl -u pascal-web` |
