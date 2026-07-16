# 🚀 START HERE - SDS Nexus Platform

## What is This?

The **SDS Nexus Platform** is an enterprise monitoring and chargeback system for Ceph object storage. It provides:

- Real-time cluster health monitoring
- Tenant usage tracking and cost analysis
- Automated backups and health checks
- Beautiful Grafana dashboards
- Comprehensive alerting

---

## ⚡ Quick Deploy to Production

### Time Required: **2-3 hours**

### Prerequisites
- RHEL 10 server (4 CPU, 8GB RAM, 100GB disk)
- Root access
- Ceph cluster access (SSH key, RGW credentials)
- SMTP server for email notifications

### Follow This Guide

📘 **[PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md)**

This guide walks you through:
1. System preparation (15 min)
2. PostgreSQL setup (10 min)
3. Application deployment (20 min)
4. Prometheus installation (15 min)
5. Grafana installation (15 min)
6. Service configuration (10 min)
7. Automated tasks (10 min)
8. Verification (15 min)

**All commands are provided. Just copy-paste and execute.**

---

## 📋 Deployment Checklist

Use this to verify your deployment:

📋 **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)**

---

## 🎯 What You Get

After deployment, you'll have:

| Service | Access |
|---------|--------|
| **REST API** | `http://YOUR_SERVER:8000` |
| **API Documentation** | `http://YOUR_SERVER:8000/docs` |
| **Prometheus** | `http://YOUR_SERVER:9090` |
| **Grafana Dashboards** | `http://YOUR_SERVER:3000` |

### Pre-Built Dashboards

1. **Ceph Cluster Overview** - Health, capacity, OSDs, MONs, placement groups
2. **Tenant Usage & Chargeback** - Historical usage, costs, billing analysis (30 days)

### Automated Features

- ✅ Metrics collection every 5 minutes
- ✅ Database backups daily at 2 AM
- ✅ Health checks every 15 minutes
- ✅ Log rotation automatically managed
- ✅ Alert suppression during maintenance

---

## 📖 Documentation Structure

### For Deployment
- **START_HERE.md** (this file) - Quick overview
- **QUICK_START.md** - Condensed deployment commands
- **PRODUCTION_DEPLOYMENT_GUIDE.md** - Complete step-by-step guide ⭐
- **DEPLOYMENT_CHECKLIST.md** - Verification checklist

### For Operations
- **docs/OPERATIONAL_RUNBOOK.md** - Daily operations and incident response
- **docs/TENANT_CHARGEBACK_DASHBOARD.md** - Dashboard usage guide
- **docs/MONITORING_INTEGRATION.md** - External system integrations
- **OPERATIONAL_COMPLETENESS_CHECKLIST.md** - Production readiness

### For Reference
- **README.md** - Project overview and features
- **DEPLOYMENT_SUMMARY.md** - What was done and file cleanup
- **docs/** - Additional guides and documentation

---

## 🛠️ Common Commands

```bash
# Check service status
sudo systemctl status sds-nexus-api

# View logs
sudo journalctl -u sds-nexus-api -f

# Run health check
/usr/local/bin/health_check.sh --verbose

# Manual backup
/usr/local/bin/backup_database.sh

# Restart services
sudo systemctl restart sds-nexus-api
```

---

## ❓ Need Help?

### During Deployment
- **Troubleshooting**: See PRODUCTION_DEPLOYMENT_GUIDE.md (Section 10)
- **Common Issues**: Database connection, firewall, permissions

### After Deployment
- **Daily Operations**: docs/OPERATIONAL_RUNBOOK.md
- **Dashboard Help**: docs/TENANT_CHARGEBACK_DASHBOARD.md
- **Alert Configuration**: docker/prometheus/rules/sds_nexus_alerts.yml

---

## 🎓 Training

### For Operations Team
1. Review **PRODUCTION_DEPLOYMENT_GUIDE.md**
2. Read **docs/OPERATIONAL_RUNBOOK.md**
3. Explore Grafana dashboards
4. Practice incident response procedures

### For Managers
1. Review **README.md** (features overview)
2. Check **OPERATIONAL_COMPLETENESS_CHECKLIST.md** (what's included)
3. Access Grafana at `http://YOUR_SERVER:3000`
4. Review dashboards for business insights

---

## 📊 What's Monitored

### Cluster Health
- MON quorum status
- OSD up/down/in/out status
- Placement group health
- Cluster capacity and utilization
- Recovery and rebalancing

### Node Performance
- CPU usage per node
- Memory utilization
- Disk I/O
- Temperature sensors
- Network metrics

### Object Storage (RGW)
- Bucket sizes and object counts
- Tenant usage tracking
- Growth rates
- Cost calculations (GBP/USD)

### Platform Health
- API response times
- Worker job execution
- Database connection pool
- Error rates

---

## 🚦 Deployment Flow

```
1. Read PRODUCTION_DEPLOYMENT_GUIDE.md
          ↓
2. Execute all 10 steps in order
          ↓
3. Verify with DEPLOYMENT_CHECKLIST.md
          ↓
4. Access Grafana and review dashboards
          ↓
5. Read docs/OPERATIONAL_RUNBOOK.md
          ↓
6. Monitor for 24 hours
          ↓
7. Sign off on DEPLOYMENT_CHECKLIST.md
          ↓
8. PRODUCTION READY ✅
```

---

## ⏱️ Time Estimates

| Task | Time | Difficulty |
|------|------|------------|
| **First-time deployment** | 4-5 hours | Medium (reading + doing) |
| **Experienced admin** | 2-3 hours | Easy (following guide) |
| **Quick deploy** | 2 hours | Easy (using QUICK_START.md) |

---

## 🔒 Security Notes

- Change Grafana admin password immediately
- Store all passwords in secure vault
- Restrict firewall access to internal network
- Use SSH keys (not passwords) for Ceph access
- Review security section in deployment guide

---

## ✅ Production Ready

This platform is **complete and ready for production** with:

- ✅ Comprehensive monitoring (40+ metrics)
- ✅ Pre-built Grafana dashboards
- ✅ Automated backups and health checks
- ✅ Multi-environment support
- ✅ Complete documentation (10,000+ lines)
- ✅ Operational runbooks
- ✅ Simple 2-3 hour deployment

---

## 🚀 Ready to Deploy?

### Step 1: Open This Guide
📘 **[PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md)**

### Step 2: Follow All Steps

### Step 3: Verify with Checklist
📋 **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)**

### Step 4: Start Monitoring!
🎯 Access Grafana at `http://YOUR_SERVER:3000`

---

## 💡 Pro Tips

1. **Read the full guide first** before starting deployment
2. **Prepare all credentials** before beginning (saves time)
3. **Use the checklist** to track progress
4. **Test the backup** immediately after deployment
5. **Monitor for 24 hours** before declaring success

---

## 📞 Support

- **Documentation**: All guides in this repository
- **Logs**: `/var/log/sds-nexus/` and `journalctl`
- **Health Check**: `/usr/local/bin/health_check.sh --verbose`
- **Runbook**: `docs/OPERATIONAL_RUNBOOK.md`

---

**Version**: 1.0.0  
**Last Updated**: January 2024  
**Status**: Production Ready ✅

**👉 Start with: [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md)**

