# SDS Nexus Platform - Production Deployment Checklist

## Quick Start

Follow **PRODUCTION_DEPLOYMENT_GUIDE.md** for detailed step-by-step instructions.

This checklist ensures all deployment steps are completed successfully.

---

## Pre-Deployment (Complete Before Starting)

### Server Requirements
- [ ] RHEL 10 server provisioned
- [ ] Minimum 4 CPU cores
- [ ] Minimum 8GB RAM
- [ ] Minimum 100GB disk space
- [ ] Root/sudo access available
- [ ] Network connectivity verified

### Access & Credentials Prepared
- [ ] Ceph cluster IP addresses
- [ ] Ceph SSH key (read-only access)
- [ ] RGW endpoint URL
- [ ] RGW access/secret keys (read-only)
- [ ] Database password generated
- [ ] SMTP server details
- [ ] SMTP credentials
- [ ] Firewall change requests approved

---

## Deployment Steps

### Step 1: System Preparation ☐
- [ ] System packages updated
- [ ] Python 3.12 installed
- [ ] PostgreSQL client libraries installed
- [ ] Application user `sds-nexus` created
- [ ] Required directories created (`/opt/sds-nexus`, `/etc/sds-nexus`, `/var/log/sds-nexus`)
- [ ] Directory permissions set correctly
- [ ] Firewall rules added (ports 8000, 9090, 3000)
- [ ] Firewall reloaded

**Verification**:
```bash
id sds-nexus
ls -ld /opt/sds-nexus /etc/sds-nexus /var/log/sds-nexus
sudo firewall-cmd --list-ports
```

---

### Step 2: PostgreSQL Installation ☐
- [ ] PostgreSQL 16 installed
- [ ] PostgreSQL initialized
- [ ] PostgreSQL service enabled
- [ ] PostgreSQL service started
- [ ] Database `sds_nexus` created
- [ ] Database user `sds_nexus_user` created
- [ ] User granted permissions
- [ ] `pg_hba.conf` configured for local access
- [ ] PostgreSQL restarted

**Verification**:
```bash
sudo systemctl status postgresql
psql -h localhost -U sds_nexus_user -d sds_nexus -c "SELECT version();"
```

---

### Step 3: Application Deployment ☐
- [ ] Repository cloned to `/opt/sds-nexus`
- [ ] Python virtual environment created
- [ ] Requirements installed from `requirements.txt`
- [ ] Production environment file created at `/etc/sds-nexus/production.env`
- [ ] All required variables configured (see below)
- [ ] Secrets generated (32+ char random strings)
- [ ] File permissions set to 600
- [ ] File owned by `sds-nexus` user
- [ ] SSH keys copied to `/etc/sds-nexus/keys/`
- [ ] SSH key permissions set to 600
- [ ] Database migrations applied (`alembic upgrade head`)

**Required Environment Variables**:
```
✓ APP_ENV=production
✓ APP_SECRET_KEY=<32_char_secret>
✓ JWT_SECRET_KEY=<32_char_secret>
✓ DB_HOST=localhost
✓ DB_PORT=5432
✓ DB_NAME=sds_nexus
✓ DB_USER=sds_nexus_user
✓ DB_PASSWORD=<your_password>
✓ CEPH_CLUSTER_NAME=<your_cluster>
✓ CEPH_MONITOR_HOST=<ceph_ip>
✓ CEPH_ADMIN_NODE=<ceph_admin_node>
✓ CEPH_SSH_KEY_PATH=/etc/sds-nexus/keys/sds_monitor_key
✓ RGW_ENDPOINT=<rgw_url>
✓ RGW_ACCESS_KEY=<rgw_access_key>
✓ RGW_SECRET_KEY=<rgw_secret_key>
✓ SMTP_HOST=<smtp_server>
✓ SMTP_USER=<smtp_user>
✓ SMTP_PASSWORD=<smtp_password>
✓ SMTP_FROM_ADDRESS=<from_email>
```

**Verification**:
```bash
source /opt/sds-nexus/venv/bin/activate
python -c "from app.main import app; print('✓ App imports successfully')"
alembic current
```

---

### Step 4: Prometheus Installation ☐
- [ ] Prometheus binary downloaded
- [ ] Prometheus installed to `/usr/local/bin/prometheus`
- [ ] `promtool` installed to `/usr/local/bin/promtool`
- [ ] Configuration directory created (`/etc/prometheus`)
- [ ] Data directory created (`/var/lib/prometheus`)
- [ ] `prometheus.yml` copied and configured
- [ ] Alert rules copied to `/etc/prometheus/rules/`
- [ ] Target updated to `localhost:8000` (not `api:8000`)
- [ ] Prometheus user created
- [ ] Directory permissions set
- [ ] Systemd service created
- [ ] Service enabled
- [ ] Service started

**Verification**:
```bash
curl http://localhost:9090/-/healthy
sudo systemctl status prometheus
```

---

### Step 5: Grafana Installation ☐
- [ ] Grafana repository added
- [ ] Grafana installed
- [ ] Service enabled
- [ ] Service started
- [ ] Prometheus data source added
- [ ] Data source verified (test connection succeeds)
- [ ] Ceph Cluster Overview dashboard imported
- [ ] Tenant Usage & Chargeback dashboard imported
- [ ] Admin password changed from default

**Verification**:
```bash
curl http://localhost:3000/api/health
# Access http://YOUR_SERVER:3000 and verify dashboards exist
```

---

### Step 6: Application Service ☐
- [ ] Systemd service file created (`/etc/systemd/system/sds-nexus-api.service`)
- [ ] Service configured with correct paths
- [ ] Worker count set (default 4)
- [ ] Service enabled
- [ ] Service started
- [ ] Health check passes (liveness endpoint)
- [ ] Health check passes (readiness endpoint)
- [ ] Metrics endpoint accessible

**Verification**:
```bash
sudo systemctl status sds-nexus-api
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready
curl http://localhost:8000/api/v1/metrics | head -10
```

---

### Step 7: Automated Tasks ☐
- [ ] Backup script copied to `/usr/local/bin/backup_database.sh`
- [ ] Backup script made executable
- [ ] Backup script configured with correct paths
- [ ] Health check script copied to `/usr/local/bin/health_check.sh`
- [ ] Health check script made executable
- [ ] Cron jobs configured for `sds-nexus` user
- [ ] Database backup scheduled (daily 2 AM)
- [ ] Health check scheduled (every 15 minutes)
- [ ] Log rotation configured (`/etc/logrotate.d/sds-nexus`)

**Verification**:
```bash
sudo crontab -u sds-nexus -l
/usr/local/bin/health_check.sh --verbose
ls -la /etc/logrotate.d/sds-nexus
```

---

### Step 8: SELinux Configuration (If Enabled) ☐
- [ ] Port 8000 added to `http_port_t` context
- [ ] Database connections allowed
- [ ] Network connections allowed
- [ ] SELinux booleans set persistently

**Verification**:
```bash
getenforce  # Check if SELinux is enforcing
getsebool httpd_can_network_connect_db
getsebool httpd_can_network_connect
```

---

## Verification & Testing

### Service Status ☐
- [ ] API service running
- [ ] Prometheus service running
- [ ] Grafana service running
- [ ] PostgreSQL service running
- [ ] No service errors in logs

**Commands**:
```bash
sudo systemctl status sds-nexus-api prometheus grafana-server postgresql
```

---

### API Functionality ☐
- [ ] Liveness endpoint returns 200 OK
- [ ] Readiness endpoint returns 200 OK
- [ ] Metrics endpoint returns Prometheus format
- [ ] Metrics include `sds_nexus_app_info`
- [ ] Metrics include `ceph_cluster_health_status`
- [ ] API docs accessible (if not disabled)

**Commands**:
```bash
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_app_info
```

---

### Prometheus Verification ☐
- [ ] Prometheus UI accessible at port 9090
- [ ] `sds-nexus-api` target shows as UP
- [ ] Target health is "up" in status
- [ ] Alert rules loaded successfully
- [ ] Can query `up{job="sds-nexus-api"}` returns 1
- [ ] Can query `sds_nexus_app_info`

**Commands**:
```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="sds-nexus-api")'
curl -s 'http://localhost:9090/api/v1/query?query=up{job="sds-nexus-api"}' | jq
```

---

### Grafana Verification ☐
- [ ] Grafana UI accessible at port 3000
- [ ] Can login with admin credentials
- [ ] Prometheus data source configured
- [ ] Data source test connection succeeds
- [ ] "Ceph Cluster Overview" dashboard exists
- [ ] "Tenant Usage & Chargeback" dashboard exists
- [ ] Dashboards display data (not "No Data")
- [ ] Time range selector works
- [ ] Refresh functionality works

**Access**: `http://YOUR_SERVER:3000`

---

### End-to-End Workflow ☐
- [ ] API exposes metrics
- [ ] Prometheus scrapes metrics successfully
- [ ] Grafana queries Prometheus successfully
- [ ] Dashboard panels display metrics
- [ ] Alerts can be triggered (test threshold)
- [ ] Health check script passes all checks

**Command**:
```bash
/usr/local/bin/health_check.sh --verbose
```

---

## Post-Deployment Configuration

### Security Hardening ☐
- [ ] Firewall rules restrict access to internal network only
- [ ] Grafana admin password changed
- [ ] Passwords stored in secure vault
- [ ] TLS/SSL configured (if required)
- [ ] SELinux policies verified (if using SELinux)

---

### Documentation ☐
- [ ] Server IP/hostname documented
- [ ] All passwords stored in secure vault
- [ ] SSH key locations documented
- [ ] Configuration file locations documented
- [ ] Operations team trained
- [ ] Runbook reviewed

---

### Operational Readiness ☐
- [ ] Backup script tested manually
- [ ] Backup retention verified (30 days)
- [ ] Restore procedure tested
- [ ] Log rotation tested
- [ ] Alert rules reviewed and tuned
- [ ] On-call team notified
- [ ] Escalation procedures documented

---

## Access Summary

After deployment, document these URLs:

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| API | `http://YOUR_SERVER:8000` | None (internal network) |
| API Docs | `http://YOUR_SERVER:8000/docs` | N/A |
| Prometheus | `http://YOUR_SERVER:9090` | None (restrict via firewall) |
| Grafana | `http://YOUR_SERVER:3000` | admin / <changed_password> |
| Metrics | `http://YOUR_SERVER:8000/api/v1/metrics` | None (for Prometheus) |

---

## Common Issues & Solutions

### ❌ API Won't Start
```bash
# Check logs
sudo journalctl -u sds-nexus-api -n 50 --no-pager

# Common fixes:
# 1. Database connection - verify credentials in /etc/sds-nexus/production.env
# 2. Port in use - check: sudo lsof -i :8000
# 3. Permissions - check: ls -la /opt/sds-nexus
```

### ❌ Prometheus Not Scraping
```bash
# Check Prometheus logs
sudo journalctl -u prometheus -n 50 --no-pager

# Common fixes:
# 1. Verify API is accessible: curl http://localhost:8000/api/v1/metrics
# 2. Check prometheus.yml has correct target (localhost:8000)
# 3. Restart Prometheus: sudo systemctl restart prometheus
```

### ❌ Grafana No Data
```bash
# Check data source
curl http://localhost:3000/api/datasources -u admin:your_password | jq

# Common fixes:
# 1. Verify Prometheus is accessible: curl http://localhost:9090/api/v1/query?query=up
# 2. Check data source URL is correct (http://localhost:9090)
# 3. Test query in Prometheus UI first
```

### ❌ Database Connection Errors
```bash
# Test connection
psql -h localhost -U sds_nexus_user -d sds_nexus

# Common fixes:
# 1. Check PostgreSQL is running: sudo systemctl status postgresql
# 2. Verify pg_hba.conf has correct entry
# 3. Check password in /etc/sds-nexus/production.env
```

---

## Final Sign-Off

### Development Team
- [ ] Code deployed
- [ ] Database migrations applied
- [ ] Configuration verified
- [ ] All services started
- [ ] Health checks passing

### Operations Team
- [ ] Access credentials received
- [ ] Runbook reviewed
- [ ] Monitoring dashboards accessible
- [ ] Alert rules understood
- [ ] Backup procedures documented

### Management
- [ ] Deployment approved
- [ ] Resources allocated
- [ ] Support procedures in place
- [ ] Go-live authorized

---

## Deployment Complete ✅

**Deployment Date**: ___________________

**Deployed By**: ___________________

**Verified By**: ___________________

**Sign-Off**: ___________________

---

## Next Steps

1. ✅ Monitor system for 24 hours
2. ✅ Review Grafana dashboards daily
3. ✅ Verify backups are running
4. ✅ Test restore procedure
5. ✅ Train additional team members
6. ✅ Schedule quarterly review

---

## Support Contacts

**Primary Contact**: Storage Operations Team  
**Documentation**: `/opt/sds-nexus/docs/`  
**Runbook**: `docs/OPERATIONAL_RUNBOOK.md`  
**Troubleshooting**: `PRODUCTION_DEPLOYMENT_GUIDE.md`

---

**Version**: 1.0.0  
**Last Updated**: January 2024
