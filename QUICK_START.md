# SDS Nexus Platform - Quick Start Guide

## 🚀 Deploy to Production in 2-3 Hours

### Prerequisites Checklist
- ✅ RHEL 10 server (4 CPU, 8GB RAM, 100GB disk)
- ✅ Root/sudo access
- ✅ Ceph cluster IP and SSH key
- ✅ RGW endpoint and credentials
- ✅ SMTP server details
- ✅ Database password ready

---

## Step-by-Step Deployment

### 1. System Setup (15 min)
```bash
# Install packages
sudo dnf5 install -y python3.12 postgresql16-server

# Create user and directories
sudo useradd -r -m -s /bin/bash sds-nexus
sudo mkdir -p /opt/sds-nexus /etc/sds-nexus /var/log/sds-nexus

# Configure firewall
sudo firewall-cmd --permanent --add-port={8000,9090,3000}/tcp
sudo firewall-cmd --reload
```

### 2. Database Setup (10 min)
```bash
# Initialize PostgreSQL
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql

# Create database
sudo -u postgres psql << EOF
CREATE DATABASE sds_nexus;
CREATE USER sds_nexus_user WITH PASSWORD 'YOUR_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE sds_nexus TO sds_nexus_user;
EOF
```

### 3. Deploy Application (20 min)
```bash
# Clone and install
cd /opt/sds-nexus
# Copy your project files here
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
sudo cp .env.production.example /etc/sds-nexus/production.env
sudo vi /etc/sds-nexus/production.env  # Edit configuration

# Run migrations
export APP_ENV=production
alembic upgrade head
```

### 4. Install Monitoring (30 min)
```bash
# Install Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.48.0/prometheus-2.48.0.linux-amd64.tar.gz
tar xzf prometheus-2.48.0.linux-amd64.tar.gz
sudo cp prometheus-2.48.0.linux-amd64/prometheus /usr/local/bin/

# Install Grafana
sudo dnf5 install -y grafana

# Configure and start services
# (See PRODUCTION_DEPLOYMENT_GUIDE.md for details)
```

### 5. Start Services (10 min)
```bash
# Create and start API service
sudo systemctl enable --now sds-nexus-api

# Start monitoring
sudo systemctl enable --now prometheus grafana-server

# Verify
curl http://localhost:8000/api/v1/health/live
```

### 6. Import Dashboards (5 min)
```bash
# Import Grafana dashboards
curl -X POST http://localhost:3000/api/dashboards/db \
  -u admin:admin \
  -d @docker/grafana/dashboards/ceph-cluster-overview.json

curl -X POST http://localhost:3000/api/dashboards/db \
  -u admin:admin \
  -d @docker/grafana/dashboards/tenant-usage-chargeback.json
```

### 7. Configure Backups (10 min)
```bash
# Set up automated backups
sudo crontab -e -u sds-nexus
# Add:
# 0 2 * * * /usr/local/bin/backup_database.sh
```

---

## Access Your Platform

| Service | URL | Credentials |
|---------|-----|-------------|
| **API** | http://YOUR_SERVER:8000 | None |
| **API Docs** | http://YOUR_SERVER:8000/docs | N/A |
| **Prometheus** | http://YOUR_SERVER:9090 | None |
| **Grafana** | http://YOUR_SERVER:3000 | admin/admin (change!) |

---

## Verify Deployment

```bash
# Run health check
/usr/local/bin/health_check.sh --verbose

# Check all services
sudo systemctl status sds-nexus-api prometheus grafana-server

# Verify metrics
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_app_info
```

---

## Essential Configuration

Edit `/etc/sds-nexus/production.env`:

```bash
# Application
APP_ENV=production
APP_SECRET_KEY=<generate-32-char-secret>
JWT_SECRET_KEY=<generate-32-char-secret>

# Database
DB_HOST=localhost
DB_PASSWORD=<your-db-password>

# Ceph
CEPH_MONITOR_HOST=<ceph-ip>
CEPH_SSH_KEY_PATH=/etc/sds-nexus/keys/sds_monitor_key

# RGW
RGW_ENDPOINT=<rgw-url>
RGW_ACCESS_KEY=<rgw-key>
RGW_SECRET_KEY=<rgw-secret>

# Email
SMTP_HOST=<smtp-server>
SMTP_USER=<smtp-user>
SMTP_PASSWORD=<smtp-password>
```

Generate secrets:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Troubleshooting

### API Won't Start
```bash
sudo journalctl -u sds-nexus-api -n 50
# Check database connection and environment file
```

### No Metrics in Grafana
```bash
# Verify Prometheus is scraping
curl http://localhost:9090/api/v1/targets | jq

# Check API metrics endpoint
curl http://localhost:8000/api/v1/metrics
```

### Database Connection Error
```bash
# Test connection
psql -h localhost -U sds_nexus_user -d sds_nexus

# Check PostgreSQL is running
sudo systemctl status postgresql
```

---

## Next Steps

1. ✅ Change Grafana admin password
2. ✅ Review dashboards
3. ✅ Test backup script
4. ✅ Configure alerts
5. ✅ Review operational runbook

---

## Complete Documentation

For detailed instructions, see:

📘 **[PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md)** - Complete deployment guide

📋 **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Verification checklist

📖 **[docs/OPERATIONAL_RUNBOOK.md](docs/OPERATIONAL_RUNBOOK.md)** - Daily operations guide

---

## Support

- **Documentation**: `/opt/sds-nexus/docs/`
- **Logs**: `/var/log/sds-nexus/`
- **Service Logs**: `sudo journalctl -u sds-nexus-api -f`
- **Health Check**: `/usr/local/bin/health_check.sh --verbose`

---

**Deployment Time**: 2-3 hours  
**Version**: 1.0.0  
**Status**: Production Ready ✅
