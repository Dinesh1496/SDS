# SDS Nexus Platform - Operational Runbook

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Incident Response](#incident-response)
3. [Backup & Recovery](#backup--recovery)
4. [Performance Tuning](#performance-tuning)
5. [Capacity Management](#capacity-management)
6. [Security Operations](#security-operations)
7. [Change Management](#change-management)
8. [Disaster Recovery](#disaster-recovery)
9. [On-Call Procedures](#on-call-procedures)
10. [Escalation Procedures](#escalation-procedures)

---

## 1. Daily Operations

### Daily Health Check Checklist

**Time Required**: 15-20 minutes  
**Frequency**: Every business day at 9:00 AM

#### Platform Health
```bash
# 1. Check API is responding
curl -f http://localhost:8000/api/v1/health/live || echo "API DOWN!"

# 2. Check database connectivity
docker-compose exec api python3 -c "from app.db.session import check_db_connectivity; print('DB OK' if check_db_connectivity() else 'DB FAILED')"

# 3. Check Prometheus scraping
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="sds-nexus-api") | .health'

# 4. Check worker jobs executed
curl -s http://localhost:8000/api/v1/metrics | grep sds_nexus_worker_job_last_success_timestamp

# 5. Check for active alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'
```

#### Ceph Cluster Health
```bash
# Check cluster health status
ssh sds-monitor@dbr-gbch-sds01 'sudo ceph status --format json' | jq '.health.status'

# Expected: "HEALTH_OK"
# If HEALTH_WARN or HEALTH_ERR, investigate immediately

# Check OSD status
ssh sds-monitor@dbr-gbch-sds01 'sudo ceph osd stat' | grep -E 'up|in'

# Expected: "287 osds: 287 up, 287 in"
```

#### Review Dashboards
1. Open Grafana: http://your-server:3000
2. Check "Ceph Cluster Overview" dashboard
3. Check "Tenant Usage & Chargeback" dashboard
4. Look for red/orange indicators
5. Review any anomalies in graphs

#### Log Review
```bash
# Check for errors in last 24 hours
docker-compose logs --since 24h api | grep -i error | tail -20

# Check for warnings
docker-compose logs --since 24h api | grep -i warn | tail -20

# Check database logs
docker-compose logs --since 24h postgres | grep -i error
```

#### Action Items
- [ ] Platform responding normally
- [ ] No active critical alerts
- [ ] Ceph cluster health is OK
- [ ] All OSDs up and in
- [ ] No errors in logs
- [ ] Dashboards show normal metrics
- [ ] Worker jobs running on schedule

**If any checks fail**, proceed to [Incident Response](#incident-response)

---

## 2. Incident Response

### Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| **SEV1 - Critical** | Platform down, data loss risk | 15 minutes | Immediate |
| **SEV2 - High** | Degraded service, alerts firing | 1 hour | If not resolved in 2h |
| **SEV3 - Medium** | Performance issues, warnings | 4 hours | If not resolved in 8h |
| **SEV4 - Low** | Cosmetic issues, no impact | 1 business day | Not required |

### Common Incidents

#### INCIDENT: API Not Responding

**Symptoms**: Health check fails, 502/503 errors

**Diagnosis**:
```bash
# Check if container is running
docker-compose ps api

# Check container logs
docker-compose logs --tail=100 api

# Check resource usage
docker stats --no-stream api

# Check port binding
netstat -tlnp | grep 8000
```

**Resolution**:
```bash
# Restart API container
docker-compose restart api

# If that fails, full restart
docker-compose down
docker-compose up -d

# Check health after 30 seconds
sleep 30
curl http://localhost:8000/api/v1/health/live
```

**Root Cause Analysis**:
- Check logs for error before crash
- Review resource metrics in Grafana
- Document findings in incident log

---

#### INCIDENT: Cluster Health Degraded

**Symptoms**: Ceph status shows HEALTH_WARN or HEALTH_ERR

**Diagnosis**:
```bash
# Get detailed health info
ssh sds-monitor@dbr-gbch-sds01 'sudo ceph health detail'

# Check OSD status
ssh sds-monitor@dbr-gbch-sds01 'sudo ceph osd tree'

# Check PG status
ssh sds-monitor@dbr-gbch-sds01 'sudo ceph pg stat'

# Check MON quorum
ssh sds-monitor@dbr-gbch-sds01 'sudo ceph mon stat'
```

**Common Issues**:

1. **OSDs Down**
   ```bash
   # Identify down OSDs
   ssh sds-monitor@dbr-gbch-sds01 'sudo ceph osd tree | grep down'
   
   # Check node where OSD is located
   # SSH to that node and investigate
   ssh sds-monitor@dbr-gbch-sds0X 'sudo systemctl status ceph-osd@<id>'
   ```

2. **PGs Degraded**
   ```bash
   # Wait for recovery (if ongoing maintenance)
   # Check recovery progress
   ssh sds-monitor@dbr-gbch-sds01 'sudo ceph status'
   
   # Look for "recovering" or "backfilling" in output
   ```

3. **MON Quorum Lost**
   ```bash
   # Check MON status on each node
   for i in {01..07}; do
     ssh sds-monitor@dbr-gbch-sds${i} 'sudo systemctl status ceph-mon@*'
   done
   ```

**Escalation**: If unable to resolve in 30 minutes, escalate to Ceph SME

---

#### INCIDENT: High Database Load

**Symptoms**: Slow queries, connection pool exhausted

**Diagnosis**:
```bash
# Check active connections
docker-compose exec postgres psql -U sds_nexus_user -d sds_nexus -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Check slow queries
docker-compose exec postgres psql -U sds_nexus_user -d sds_nexus -c \
  "SELECT pid, now() - query_start as duration, query 
   FROM pg_stat_activity 
   WHERE state = 'active' AND now() - query_start > interval '5 seconds'
   ORDER BY duration DESC;"

# Check table sizes
docker-compose exec postgres psql -U sds_nexus_user -d sds_nexus -c \
  "SELECT schemaname, tablename, 
   pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables 
   WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC 
   LIMIT 10;"
```

**Resolution**:
```bash
# Increase connection pool (temporary)
# Edit .env and restart
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=50
docker-compose restart api

# Vacuum analyze (if fragmentation suspected)
docker-compose exec postgres psql -U sds_nexus_user -d sds_nexus -c "VACUUM ANALYZE;"

# Kill long-running query (last resort)
docker-compose exec postgres psql -U sds_nexus_user -d sds_nexus -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE state = 'active' AND now() - query_start > interval '30 minutes';"
```

---

#### INCIDENT: Disk Space Low

**Symptoms**: "No space left on device" errors

**Diagnosis**:
```bash
# Check disk usage
df -h

# Check which directory is full
du -sh /* | sort -h

# Check Docker volumes
docker system df

# Check Prometheus data
du -sh /var/lib/prometheus

# Check logs
du -sh /var/log/sds-nexus
```

**Resolution**:
```bash
# Clean up old Docker images/containers
docker system prune -a --volumes

# Rotate logs manually
docker-compose exec api logrotate -f /etc/logrotate.d/sds-nexus

# Clean old Prometheus data (caution: data loss)
# Only if critically low on space
sudo systemctl stop prometheus
sudo rm -rf /var/lib/prometheus/data/*
sudo systemctl start prometheus

# Increase disk size (long-term solution)
# Follow your infrastructure team's procedures
```

---

## 3. Backup & Recovery

### Backup Strategy

**Backup Schedule**:
- **Database**: Daily at 2:00 AM (automated)
- **Configuration**: Weekly (automated)
- **Prometheus data**: Not backed up (30-day retention acceptable)
- **Grafana dashboards**: Backed up in Git repository

### Database Backup

#### Automated Daily Backup
```bash
# Create backup script
cat > /opt/sds-nexus/scripts/backup-db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/sds-nexus/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/sds_nexus_${DATE}.sql.gz"

# Create backup
docker-compose exec -T postgres pg_dump -U sds_nexus_user sds_nexus | gzip > "${BACKUP_FILE}"

# Keep only last 30 days
find ${BACKUP_DIR} -name "sds_nexus_*.sql.gz" -mtime +30 -delete

echo "Backup completed: ${BACKUP_FILE}"
EOF

chmod +x /opt/sds-nexus/scripts/backup-db.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/sds-nexus/scripts/backup-db.sh >> /var/log/sds-nexus/backup.log 2>&1") | crontab -
```

#### Manual Backup
```bash
# Create immediate backup
docker-compose exec postgres pg_dump -U sds_nexus_user sds_nexus > backup_$(date +%Y%m%d).sql

# Compressed backup
docker-compose exec postgres pg_dump -U sds_nexus_user sds_nexus | gzip > backup_$(date +%Y%m%d).sql.gz
```

#### Restore Database
```bash
# Stop API first
docker-compose stop api

# Restore from backup
gunzip < backup_20240115.sql.gz | docker-compose exec -T postgres psql -U sds_nexus_user -d sds_nexus

# Restart API
docker-compose start api

# Verify
curl http://localhost:8000/api/v1/health/live
```

### Configuration Backup

#### Backup Configuration Files
```bash
# Automated configuration backup
cat > /opt/sds-nexus/scripts/backup-config.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/sds-nexus/backups/config"
DATE=$(date +%Y%m%d_%H%M%S)
ARCHIVE="${BACKUP_DIR}/config_${DATE}.tar.gz"

mkdir -p ${BACKUP_DIR}

# Backup configuration
tar czf ${ARCHIVE} \
  /etc/sds-nexus/*.env \
  /etc/sds-nexus/keys/ \
  /etc/prometheus/prometheus.yml \
  /etc/prometheus/rules/ \
  /etc/grafana/grafana.ini \
  /opt/sds-nexus/docker-compose.yml

# Keep last 90 days
find ${BACKUP_DIR} -name "config_*.tar.gz" -mtime +90 -delete

echo "Config backup completed: ${ARCHIVE}"
EOF

chmod +x /opt/sds-nexus/scripts/backup-config.sh

# Run weekly
(crontab -l 2>/dev/null; echo "0 3 * * 0 /opt/sds-nexus/scripts/backup-config.sh >> /var/log/sds-nexus/backup.log 2>&1") | crontab -
```

### Recovery Testing

**Frequency**: Quarterly

**Procedure**:
1. Create test environment
2. Restore latest backup
3. Verify all services start
4. Verify data integrity
5. Document test results
6. Update recovery procedures if needed

---

## 4. Performance Tuning

### Database Performance

#### Query Performance Analysis
```sql
-- Find slowest queries
SELECT 
  calls,
  total_time,
  mean_time,
  query
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Find most frequently called queries
SELECT 
  calls,
  total_time,
  query
FROM pg_stat_statements
ORDER BY calls DESC
LIMIT 10;
```

#### Index Optimization
```sql
-- Find missing indexes
SELECT 
  schemaname,
  tablename,
  attname,
  n_distinct,
  correlation
FROM pg_stats
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
  AND n_distinct > 100
ORDER BY n_distinct DESC;

-- Check index usage
SELECT 
  schemaname,
  tablename,
  indexname,
  idx_scan,
  idx_tup_read,
  idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```

#### Connection Pool Tuning
```bash
# Monitor connection pool metrics
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_db_connection_pool

# Adjust pool size if needed
# In .env file:
DB_POOL_SIZE=20        # Increase if exhaustion occurs
DB_MAX_OVERFLOW=40     # Double the pool size
DB_POOL_RECYCLE=1800   # Recycle connections every 30 min
```

### API Performance

#### Monitor Response Times
```bash
# Check 95th percentile response time
curl -s http://localhost:9090/api/v1/query --data-urlencode \
  'query=histogram_quantile(0.95, rate(sds_nexus_http_request_duration_seconds_bucket[5m]))' \
  | jq '.data.result[0].value[1]'

# If > 5 seconds, investigate
```

#### Worker Job Performance
```bash
# Check job execution times
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_worker_job_duration_seconds

# Check for failed jobs
curl http://localhost:8000/api/v1/metrics | grep 'sds_nexus_worker_job_execution_total.*failed'
```

### Prometheus Performance

#### Data Retention
```bash
# Check Prometheus disk usage
du -sh /var/lib/prometheus

# Adjust retention if needed (in prometheus.yml)
--storage.tsdb.retention.time=30d
--storage.tsdb.retention.size=50GB
```

---

## 5. Capacity Management

### Monitoring Capacity

#### Database Growth
```sql
-- Check database size growth
SELECT 
  date_trunc('day', now()) as date,
  pg_size_pretty(pg_database_size('sds_nexus')) as size;

-- Historical growth (if tracking)
SELECT 
  recorded_at,
  table_name,
  pg_size_pretty(table_size) as size
FROM table_sizes
WHERE table_name IN ('buckets', 'nodes', 'clusters')
ORDER BY recorded_at DESC
LIMIT 30;
```

#### Storage Growth Forecast
```bash
# Get growth rate from Grafana
# Navigate to "Tenant Usage & Chargeback" dashboard
# Review "Storage Growth Rate" panel

# Calculate time to capacity
AVAILABLE_TB=500
GROWTH_GB_PER_DAY=100
DAYS_TO_FULL=$((AVAILABLE_TB * 1024 / GROWTH_GB_PER_DAY))
echo "Days until 85% full: $((DAYS_TO_FULL * 85 / 100))"
```

### Capacity Planning Actions

#### When to Add Capacity

| Metric | Threshold | Action |
|--------|-----------|--------|
| Cluster utilization | > 75% | Plan capacity addition in 3 months |
| Cluster utilization | > 85% | Add capacity immediately |
| Database size | > 50 GB | Consider partitioning |
| Prometheus data | > 80 GB | Reduce retention or add disk |

#### Capacity Addition Procedure
1. Calculate required capacity
2. Create change request
3. Schedule maintenance window
4. Add storage nodes (Ceph team)
5. Verify cluster rebalancing
6. Update capacity metrics
7. Document changes

---

## 6. Security Operations

### Security Monitoring

#### Daily Security Checks
```bash
# Check for failed authentication attempts
docker-compose logs --since 24h api | grep -i "authentication failed"

# Check for suspicious API calls
docker-compose logs --since 24h api | grep -E "(401|403)" | tail -20

# Check for unusual access patterns
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_http_requests_total | grep -E "40[13]"
```

#### Weekly Security Review
- Review user access logs
- Check for unauthorized access attempts
- Review firewall logs
- Update security patches
- Review SSL certificate expiry

### Security Incident Response

#### INCIDENT: Unauthorized Access Detected

**Immediate Actions**:
1. Block source IP at firewall
2. Revoke compromised credentials
3. Force password rotation
4. Review access logs for extent of breach
5. Notify security team

```bash
# Block IP address
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="<IP>" reject'
sudo firewall-cmd --reload

# Check access from that IP
docker-compose logs api | grep "<IP>"

# Revoke JWT tokens (restart API)
docker-compose restart api
```

### Certificate Management

#### Check Certificate Expiry
```bash
# Check SSL certificate
echo | openssl s_client -servername your-domain.com -connect your-domain.com:443 2>/dev/null | openssl x509 -noout -dates

# Set reminder 30 days before expiry
EXPIRY_DATE=$(echo | openssl s_client -servername your-domain.com -connect your-domain.com:443 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
echo "Certificate expires: $EXPIRY_DATE"
```

---

## 7. Change Management

### Change Request Process

#### Change Categories

| Type | Approval Required | Testing Required | Maintenance Window |
|------|-------------------|------------------|-------------------|
| **Emergency** | Post-implementation | Minimal | Immediate |
| **Standard** | Change board | Full | Scheduled |
| **Minor** | Team lead | Unit tests | No downtime |

### Pre-Change Checklist

- [ ] Change request documented
- [ ] Risk assessment completed
- [ ] Rollback plan prepared
- [ ] Backup completed
- [ ] Testing completed in staging
- [ ] Stakeholders notified
- [ ] Maintenance window scheduled
- [ ] Documentation updated

### Post-Change Verification

```bash
# Run health checks
./scripts/health-check.sh

# Verify metrics
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_app_info

# Check dashboards
open http://localhost:3000

# Review logs for errors
docker-compose logs --since 10m api | grep -i error

# Monitor for 24 hours
# Set calendar reminder to verify stability
```

---

## 8. Disaster Recovery

### DR Strategy

**RPO (Recovery Point Objective)**: 24 hours  
**RTO (Recovery Time Objective)**: 4 hours

### DR Scenarios

#### Scenario 1: Complete Platform Failure

**Recovery Steps**:
1. Deploy new server with same specifications
2. Install RHEL 10 and prerequisites
3. Restore configuration from backup
4. Restore database from latest backup
5. Start services
6. Verify connectivity to Ceph cluster
7. Verify dashboards and metrics

**Estimated Time**: 2-3 hours

#### Scenario 2: Database Corruption

**Recovery Steps**:
1. Stop API
2. Backup corrupted database
3. Restore from latest backup
4. Run migrations if needed
5. Start API
6. Verify data integrity

**Estimated Time**: 30 minutes

#### Scenario 3: Ceph Cluster Disaster

**Note**: Ceph cluster DR is handled by infrastructure team

**Platform Actions**:
1. Platform will show alerts
2. Historical data preserved in database
3. Wait for cluster restoration
4. Verify connectivity after restoration
5. Resume normal operations

---

## 9. On-Call Procedures

### On-Call Rotation

**Schedule**: 24x7 coverage  
**Shift Duration**: 1 week  
**Handoff**: Monday 9:00 AM

### On-Call Responsibilities

- Respond to alerts within SLA
- Perform incident triage
- Escalate when necessary
- Document all incidents
- Perform daily health checks
- Complete handoff documentation

### Alert Handling

#### Alert Priority Matrix

| Alert | Severity | Response Time | Action |
|-------|----------|---------------|--------|
| Platform Down | SEV1 | 15 minutes | Immediate investigation |
| Cluster Unhealthy | SEV1 | 15 minutes | Check Ceph status |
| OSDs Down | SEV2 | 1 hour | Monitor recovery |
| High Memory | SEV3 | 4 hours | Review metrics |
| High Temperature | SEV2 | 1 hour | Check cooling |

### Handoff Template

```markdown
# On-Call Handoff - [Date]

## Incidents During Shift
- [List any incidents and their resolution]

## Ongoing Issues
- [List any unresolved issues]

## Scheduled Maintenance
- [List any upcoming maintenance]

## Notes
- [Any other relevant information]

## Action Items for Next On-Call
- [List any follow-up actions needed]
```

---

## 10. Escalation Procedures

### Escalation Matrix

| Level | Role | Contact | Escalation Criteria |
|-------|------|---------|---------------------|
| **L1** | On-Call Engineer | PagerDuty | Initial alert |
| **L2** | Senior Engineer | Phone | Not resolved in 1 hour |
| **L3** | Team Lead | Phone | Not resolved in 2 hours |
| **L4** | Platform Manager | Phone | SEV1 >4 hours |
| **L5** | Infrastructure Team | Ticket | Ceph cluster issues |

### When to Escalate

**Escalate to L2 if**:
- Unable to diagnose issue within 30 minutes
- Issue requires expertise beyond your level
- Multiple systems affected
- Data loss risk identified

**Escalate to L3 if**:
- SEV1 incident not resolved in 2 hours
- Requires change approval
- Involves other teams
- Customer communication needed

**Escalate to Infrastructure Team if**:
- Ceph cluster health degraded
- Storage node failures
- Network connectivity issues
- Hardware failures

### Escalation Process

1. Document current status
2. Gather all relevant information
3. Contact next level via designated method
4. Provide clear situation summary
5. Remain available for questions
6. Update incident ticket
7. Continue monitoring until handoff confirmed

---

## Appendix

### Useful Commands Quick Reference

```bash
# Platform status
docker-compose ps
docker-compose logs -f api
curl http://localhost:8000/api/v1/health/live

# Database
docker-compose exec postgres psql -U sds_nexus_user sds_nexus
docker-compose exec postgres pg_dump -U sds_nexus_user sds_nexus > backup.sql

# Metrics
curl http://localhost:8000/api/v1/metrics
curl http://localhost:9090/api/v1/targets

# Ceph
ssh sds-monitor@dbr-gbch-sds01 'sudo ceph status'
ssh sds-monitor@dbr-gbch-sds01 'sudo ceph health detail'

# Logs
tail -f /var/log/sds-nexus/app.log
journalctl -u sds-nexus-api -f
```

### Contact Information

| Role | Name | Phone | Email |
|------|------|-------|-------|
| On-Call Engineer | PagerDuty | - | oncall@company.com |
| Team Lead | [Name] | [Phone] | [Email] |
| Ceph SME | [Name] | [Phone] | [Email] |
| Database Admin | [Name] | [Phone] | [Email] |
| Infrastructure Team | - | - | infra@company.com |

---

**Document Version**: 1.0  
**Last Updated**: January 15, 2024  
**Next Review**: April 15, 2024  
**Owner**: Storage Operations Team
