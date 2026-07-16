# SDS Nexus Platform - Production Deployment Guide

## Quick Overview

This guide provides a **simple, end-to-end procedure** for deploying the SDS Nexus Platform in production. Follow these steps in order for a successful deployment.

**Estimated Time**: 2-3 hours  
**Prerequisites**: RHEL 10 server with root access

---

## Pre-Deployment Checklist

Before you begin, ensure you have:

- [ ] RHEL 10 server (minimum 4 CPU, 8GB RAM, 100GB disk)
- [ ] Root or sudo access
- [ ] Network access to Ceph cluster
- [ ] SSH key for Ceph cluster access (read-only)
- [ ] Database credentials (PostgreSQL)
- [ ] SMTP server details for email notifications
- [ ] Firewall rules approved for ports: 8000, 9090, 3000

---

## Step 1: System Preparation (15 minutes)

### 1.1 Update System
```bash
sudo dnf5 update -y
sudo dnf5 install -y git python3.12 python3.12-pip python3.12-devel \
  postgresql-devel gcc openssl-devel libffi-devel
```

### 1.2 Create Application User
```bash
sudo useradd -r -m -s /bin/bash sds-nexus
sudo mkdir -p /opt/sds-nexus
sudo mkdir -p /etc/sds-nexus
sudo mkdir -p /var/log/sds-nexus
sudo mkdir -p /var/sds-nexus/backups
sudo chown -R sds-nexus:sds-nexus /opt/sds-nexus /etc/sds-nexus /var/log/sds-nexus /var/sds-nexus
```

### 1.3 Configure Firewall
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp  # API
sudo firewall-cmd --permanent --add-port=9090/tcp  # Prometheus
sudo firewall-cmd --permanent --add-port=3000/tcp  # Grafana
sudo firewall-cmd --reload
```

---

## Step 2: Install PostgreSQL (10 minutes)

### 2.1 Install PostgreSQL 16
```bash
sudo dnf5 install -y postgresql16-server postgresql16-contrib
sudo postgresql-setup --initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### 2.2 Create Database
```bash
sudo -u postgres psql << EOF
CREATE DATABASE sds_nexus;
CREATE USER sds_nexus_user WITH PASSWORD 'YOUR_SECURE_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE sds_nexus TO sds_nexus_user;
\c sds_nexus
GRANT ALL ON SCHEMA public TO sds_nexus_user;
EOF
```

### 2.3 Configure PostgreSQL Access
```bash
# Edit /var/lib/pgsql/16/data/pg_hba.conf
sudo vi /var/lib/pgsql/16/data/pg_hba.conf
# Add this line:
# host    sds_nexus    sds_nexus_user    127.0.0.1/32    scram-sha-256

sudo systemctl restart postgresql
```

---

## Step 3: Deploy Application (20 minutes)

### 3.1 Clone Repository
```bash
sudo -u sds-nexus bash
cd /opt/sds-nexus
git clone <YOUR_REPO_URL> .
# Or copy files from your development machine
```

### 3.2 Create Python Virtual Environment
```bash
cd /opt/sds-nexus
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.3 Configure Environment
```bash
# Copy production template
sudo cp .env.production.example /etc/sds-nexus/production.env
sudo chown sds-nexus:sds-nexus /etc/sds-nexus/production.env
sudo chmod 600 /etc/sds-nexus/production.env

# Edit configuration
sudo vi /etc/sds-nexus/production.env
```

**Required Configuration** (edit these values):
```bash
APP_ENV=production
APP_SECRET_KEY=<GENERATE_32_CHAR_SECRET>
JWT_SECRET_KEY=<GENERATE_32_CHAR_SECRET>

DB_HOST=localhost
DB_PORT=5432
DB_NAME=sds_nexus
DB_USER=sds_nexus_user
DB_PASSWORD=<YOUR_DATABASE_PASSWORD>

CEPH_CLUSTER_NAME=<YOUR_CLUSTER_NAME>
CEPH_MONITOR_HOST=<YOUR_CEPH_MONITOR_IP>
CEPH_ADMIN_NODE=<YOUR_CEPH_ADMIN_NODE>
CEPH_SSH_KEY_PATH=/etc/sds-nexus/keys/sds_monitor_key

RGW_ENDPOINT=<YOUR_RGW_ENDPOINT>
RGW_ACCESS_KEY=<YOUR_RGW_ACCESS_KEY>
RGW_SECRET_KEY=<YOUR_RGW_SECRET_KEY>

SMTP_HOST=<YOUR_SMTP_SERVER>
SMTP_PORT=587
SMTP_USER=<YOUR_SMTP_USER>
SMTP_PASSWORD=<YOUR_SMTP_PASSWORD>
SMTP_FROM_ADDRESS=sds-nexus@yourdomain.com
```

**Generate secrets**:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.4 Set Up SSH Keys
```bash
sudo mkdir -p /etc/sds-nexus/keys
sudo cp your_ceph_ssh_key /etc/sds-nexus/keys/sds_monitor_key
sudo chmod 600 /etc/sds-nexus/keys/sds_monitor_key
sudo chown sds-nexus:sds-nexus /etc/sds-nexus/keys/sds_monitor_key
```

### 3.5 Run Database Migrations
```bash
cd /opt/sds-nexus
source venv/bin/activate
export APP_ENV=production
alembic upgrade head
```

---

## Step 4: Install Prometheus (15 minutes)

### 4.1 Download and Install
```bash
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.48.0/prometheus-2.48.0.linux-amd64.tar.gz
tar xzf prometheus-2.48.0.linux-amd64.tar.gz
sudo cp prometheus-2.48.0.linux-amd64/prometheus /usr/local/bin/
sudo cp prometheus-2.48.0.linux-amd64/promtool /usr/local/bin/
```

### 4.2 Configure Prometheus
```bash
sudo mkdir -p /etc/prometheus/rules
sudo mkdir -p /var/lib/prometheus

# Copy configuration files
sudo cp /opt/sds-nexus/docker/prometheus/prometheus.yml /etc/prometheus/
sudo cp /opt/sds-nexus/docker/prometheus/rules/*.yml /etc/prometheus/rules/

# Edit prometheus.yml - update API target
sudo vi /etc/prometheus/prometheus.yml
# Change: targets: ['api:8000'] to targets: ['localhost:8000']
```

### 4.3 Create Prometheus User and Service
```bash
sudo useradd --no-create-home --shell /bin/false prometheus
sudo chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus

# Create systemd service
sudo tee /etc/systemd/system/prometheus.service > /dev/null << 'EOF'
[Unit]
Description=Prometheus
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/prometheus \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/var/lib/prometheus \
    --web.listen-address=:9090 \
    --storage.tsdb.retention.time=30d \
    --web.console.templates=/etc/prometheus/consoles \
    --web.console.libraries=/etc/prometheus/console_libraries

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable prometheus
sudo systemctl start prometheus
```

### 4.4 Verify Prometheus
```bash
curl http://localhost:9090/-/healthy
# Should return: Prometheus is Healthy.
```

---

## Step 5: Install Grafana (15 minutes)

### 5.1 Add Grafana Repository
```bash
sudo tee /etc/yum.repos.d/grafana.repo << 'EOF'
[grafana]
name=grafana
baseurl=https://rpm.grafana.com
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://rpm.grafana.com/gpg.key
EOF
```

### 5.2 Install Grafana
```bash
sudo dnf5 install -y grafana
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

### 5.3 Configure Grafana Data Source
```bash
# Wait for Grafana to start
sleep 10

# Add Prometheus data source
curl -X POST http://localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "name": "Prometheus",
    "type": "prometheus",
    "url": "http://localhost:9090",
    "access": "proxy",
    "isDefault": true
  }'
```

### 5.4 Import Dashboards
```bash
# Import Ceph Cluster Overview Dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @/opt/sds-nexus/docker/grafana/dashboards/ceph-cluster-overview.json

# Import Tenant Usage & Chargeback Dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @/opt/sds-nexus/docker/grafana/dashboards/tenant-usage-chargeback.json
```

### 5.5 Change Grafana Admin Password
```bash
# Access Grafana at http://YOUR_SERVER:3000
# Login: admin / admin
# You will be prompted to change the password
```

---

## Step 6: Configure Application Service (10 minutes)

### 6.1 Create Systemd Service
```bash
sudo tee /etc/systemd/system/sds-nexus-api.service > /dev/null << 'EOF'
[Unit]
Description=SDS Nexus Platform API
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=sds-nexus
Group=sds-nexus
WorkingDirectory=/opt/sds-nexus
Environment="PATH=/opt/sds-nexus/venv/bin"
Environment="APP_ENV=production"
ExecStart=/opt/sds-nexus/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
EOF
```

### 6.2 Start Application
```bash
sudo systemctl daemon-reload
sudo systemctl enable sds-nexus-api
sudo systemctl start sds-nexus-api
```

### 6.3 Verify Application
```bash
# Check service status
sudo systemctl status sds-nexus-api

# Test API
curl http://localhost:8000/api/v1/health/live
# Should return: {"status":"ok"}

# Test metrics endpoint
curl http://localhost:8000/api/v1/metrics | head -20
```

---

## Step 7: Configure Automated Tasks (10 minutes)

### 7.1 Database Backup Script
```bash
sudo cp /opt/sds-nexus/scripts/backup_database.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/backup_database.sh

# Edit to set correct paths
sudo vi /usr/local/bin/backup_database.sh
```

### 7.2 Health Check Script
```bash
sudo cp /opt/sds-nexus/scripts/health_check.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/health_check.sh
```

### 7.3 Configure Cron Jobs
```bash
sudo crontab -e -u sds-nexus
```

Add these lines:
```cron
# Database backup - daily at 2 AM
0 2 * * * /usr/local/bin/backup_database.sh >> /var/log/sds-nexus/backup.log 2>&1

# Health check - every 15 minutes
*/15 * * * * /usr/local/bin/health_check.sh --alert-only >> /var/log/sds-nexus/health-check.log 2>&1
```

### 7.4 Configure Log Rotation
```bash
sudo cp /opt/sds-nexus/scripts/log_rotation.conf /etc/logrotate.d/sds-nexus
```

---

## Step 8: Configure SELinux (Optional, 10 minutes)

If SELinux is enabled:

```bash
# Allow API to bind to port 8000
sudo semanage port -a -t http_port_t -p tcp 8000

# Allow connections to PostgreSQL
sudo setsebool -P httpd_can_network_connect_db 1

# Allow network connections
sudo setsebool -P httpd_can_network_connect 1
```

---

## Step 9: Verification & Testing (15 minutes)

### 9.1 Service Status
```bash
# Check all services
sudo systemctl status sds-nexus-api
sudo systemctl status prometheus
sudo systemctl status grafana-server
sudo systemctl status postgresql
```

### 9.2 API Health Checks
```bash
# Liveness
curl http://localhost:8000/api/v1/health/live

# Readiness
curl http://localhost:8000/api/v1/health/ready

# Metrics
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_app_info
```

### 9.3 Prometheus Verification
```bash
# Check Prometheus is scraping API
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="sds-nexus-api")'

# Should show "health": "up"
```

### 9.4 Grafana Verification
```bash
# Access Grafana web UI
# URL: http://YOUR_SERVER:3000
# Login with the password you set

# Navigate to Dashboards
# You should see:
# - Ceph Cluster Overview
# - Tenant Usage & Chargeback
```

### 9.5 Run Health Check Script
```bash
sudo -u sds-nexus /usr/local/bin/health_check.sh --verbose
```

---

## Step 10: Post-Deployment Configuration (10 minutes)

### 10.1 Configure Email Notifications (Optional)
If you want email alerts:
```bash
# Install and configure Alertmanager
# See docs/MONITORING_INTEGRATION.md for details
```

### 10.2 Create Initial Maintenance Window (Optional)
```bash
# Access Python shell
cd /opt/sds-nexus
source venv/bin/activate
python3

# In Python:
from datetime import datetime, timedelta
from app.core.maintenance import create_maintenance_window, MaintenanceType
from app.db.session import get_db

db = next(get_db())
window = create_maintenance_window(
    cluster_id=1,  # Adjust to your cluster ID
    start_time=datetime.utcnow() + timedelta(days=7),
    end_time=datetime.utcnow() + timedelta(days=7, hours=4),
    reason="Scheduled maintenance window",
    maintenance_type=MaintenanceType.SCHEDULED,
    created_by="admin",
    db=db,
)
print(f"Created maintenance window ID: {window.id}")
```

### 10.3 Document Your Deployment
Record these details:
- Server IP/hostname
- Database password (in secure vault)
- Grafana admin password (in secure vault)
- SSH key location
- RGW credentials
- SMTP credentials

---

## Access Information

After successful deployment, access the platform at:

| Service | URL | Credentials |
|---------|-----|-------------|
| **API** | `http://YOUR_SERVER:8000` | No auth (internal network) |
| **API Docs** | `http://YOUR_SERVER:8000/docs` | N/A |
| **Prometheus** | `http://YOUR_SERVER:9090` | No auth (restrict via firewall) |
| **Grafana** | `http://YOUR_SERVER:3000` | admin / <your_password> |
| **Metrics** | `http://YOUR_SERVER:8000/api/v1/metrics` | No auth (for Prometheus) |

---

## Common Commands

```bash
# Restart services
sudo systemctl restart sds-nexus-api
sudo systemctl restart prometheus
sudo systemctl restart grafana-server

# View logs
sudo journalctl -u sds-nexus-api -f
sudo journalctl -u prometheus -f
sudo journalctl -u grafana-server -f
tail -f /var/log/sds-nexus/app.log

# Check service status
sudo systemctl status sds-nexus-api

# Run health check
/usr/local/bin/health_check.sh --verbose

# Manual backup
/usr/local/bin/backup_database.sh

# View Prometheus targets
curl http://localhost:9090/api/v1/targets | jq

# Test API
curl http://localhost:8000/api/v1/health/live
```

---

## Troubleshooting

### API Won't Start
```bash
# Check logs
sudo journalctl -u sds-nexus-api -n 50

# Common issues:
# 1. Database connection - check credentials in /etc/sds-nexus/production.env
# 2. Port already in use - check: sudo lsof -i :8000
# 3. Permission issues - check: ls -la /opt/sds-nexus
```

### Prometheus Not Scraping
```bash
# Check Prometheus logs
sudo journalctl -u prometheus -n 50

# Check API is accessible from Prometheus
curl http://localhost:8000/api/v1/metrics

# Verify prometheus.yml has correct target
cat /etc/prometheus/prometheus.yml | grep targets
```

### Grafana No Data
```bash
# Check data source
curl http://localhost:3000/api/datasources -u admin:your_password

# Test Prometheus connection
curl http://localhost:9090/api/v1/query?query=up

# Check Grafana logs
sudo journalctl -u grafana-server -n 50
```

### Database Connection Errors
```bash
# Test PostgreSQL connection
psql -h localhost -U sds_nexus_user -d sds_nexus

# Check PostgreSQL is running
sudo systemctl status postgresql

# Check pg_hba.conf
sudo cat /var/lib/pgsql/16/data/pg_hba.conf | grep sds_nexus
```

---

## Security Hardening

After deployment, consider:

1. **Firewall**: Restrict port 8000, 9090, 3000 to internal network only
2. **TLS/SSL**: Configure HTTPS for all web interfaces
3. **Authentication**: Add API authentication (JWT)
4. **SELinux**: Ensure SELinux policies are properly configured
5. **Secrets**: Move sensitive data to Delinea or HashiCorp Vault
6. **Backups**: Verify backups are running and test restore procedure

---

## Next Steps

1. ✅ Review operational runbook: `docs/OPERATIONAL_RUNBOOK.md`
2. ✅ Set up alert notifications: `docs/MONITORING_INTEGRATION.md`
3. ✅ Configure tenant chargeback rates in database
4. ✅ Create maintenance windows for scheduled work
5. ✅ Train operations team on Grafana dashboards
6. ✅ Schedule quarterly recovery testing

---

## Support

For issues during deployment:

1. Check logs: `/var/log/sds-nexus/` and `journalctl`
2. Review troubleshooting section above
3. Consult documentation in `docs/` directory
4. Contact Storage Operations Team

---

**Deployment Time**: 2-3 hours  
**Tested On**: RHEL 10  
**Version**: 1.0.0  
**Last Updated**: January 2024

