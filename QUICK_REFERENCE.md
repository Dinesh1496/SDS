# SDS Nexus Platform - Quick Reference Card

## Access URLs

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| API Documentation | http://localhost:8000/docs | - |
| Prometheus Metrics | http://localhost:8000/api/v1/metrics | - |
| Prometheus UI | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin / admin |
| Alertmanager | http://localhost:9093 | - |

## Docker Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f prometheus
docker-compose logs -f grafana

# Stop all services
docker-compose down

# Restart a service
docker-compose restart api

# Run database migrations
docker-compose --profile migrate up migrations

# Remove all volumes (DANGER: data loss)
docker-compose down -v

# View running containers
docker-compose ps

# Execute command in container
docker-compose exec api bash
docker-compose exec postgres psql -U sds_nexus_user sds_nexus
```

## Environment Management

```bash
# Set environment
export APP_ENV=production

# Load specific environment file
docker-compose --env-file .env.production up -d

# Validate environment configuration
python3 -c "from app.core.environment import validate_environment_config; print(validate_environment_config())"

# Get environment info
python3 -c "from app.core.environment import get_environment_info; print(get_environment_info())"
```

## Metrics Queries

### View Raw Metrics
```bash
# All metrics
curl http://localhost:8000/api/v1/metrics

# Filter specific metrics
curl http://localhost:8000/api/v1/metrics | grep ceph_cluster

# Cluster health status
curl http://localhost:8000/api/v1/metrics | grep ceph_cluster_health_status
```

### Prometheus Queries
```bash
# Query Prometheus API
curl 'http://localhost:9090/api/v1/query?query=ceph_cluster_health_status'

# Check target status
curl http://localhost:9090/api/v1/targets | python3 -m json.tool

# Query with time range
curl 'http://localhost:9090/api/v1/query_range?query=ceph_cluster_utilization_percent&start=2024-01-01T00:00:00Z&end=2024-01-01T23:59:59Z&step=1h'
```

### Common PromQL Queries
```promql
# Cluster utilization percentage
ceph_cluster_utilization_percent{cluster_name="ue-south-1"}

# Number of OSDs down
ceph_osd_down{cluster_name="ue-south-1"}

# Top 5 nodes by CPU usage
topk(5, ceph_node_cpu_usage_percent)

# API request rate (req/sec)
rate(sds_nexus_http_requests_total[5m])

# Failed worker jobs in last hour
increase(sds_nexus_worker_job_execution_total{status="failed"}[1h])

# Active maintenance windows
sds_nexus_maintenance_window_active == 1

# Average API response time (95th percentile)
histogram_quantile(0.95, rate(sds_nexus_http_request_duration_seconds_bucket[5m]))
```

## Maintenance Windows

### Create Maintenance Window (Python)
```python
from datetime import datetime, timedelta
from app.core.maintenance import create_maintenance_window, MaintenanceType
from app.db.session import get_db

# Schedule 4-hour maintenance window
window = create_maintenance_window(
    cluster_id=1,
    start_time=datetime.utcnow(),
    end_time=datetime.utcnow() + timedelta(hours=4),
    reason="OSD firmware upgrades on nodes sds08-sds12",
    maintenance_type=MaintenanceType.SCHEDULED,
    created_by="ops-team",
    suppress_alert_sources="osd,node",  # or "*" for all
    db=next(get_db()),
)
print(f"Created maintenance window {window.id}")
```

### Create Maintenance Window (SQL)
```sql
-- Insert maintenance window
INSERT INTO maintenance_windows (
    cluster_id, start_time, end_time, reason, 
    maintenance_type, created_by, suppress_alert_sources, is_active
) VALUES (
    1,
    datetime('now'),
    datetime('now', '+4 hours'),
    'Scheduled OSD upgrades',
    'scheduled',
    'ops-team',
    'osd,node',
    1
);
```

### Check Active Maintenance
```python
from app.core.maintenance import is_maintenance_active
from app.db.session import get_db

if is_maintenance_active(cluster_id=1, db=next(get_db())):
    print("Maintenance window is active")
```

### End Maintenance Early
```python
from app.core.maintenance import end_maintenance_window
from app.db.session import get_db

end_maintenance_window(window_id=123, db=next(get_db()))
```

### List Active Windows (SQL)
```sql
SELECT id, cluster_id, start_time, end_time, reason, suppress_alert_sources
FROM maintenance_windows
WHERE is_active = 1
  AND start_time <= datetime('now')
  AND end_time >= datetime('now');
```

## Database Operations

```bash
# Connect to database
docker-compose exec postgres psql -U sds_nexus_user sds_nexus

# Backup database
docker-compose exec postgres pg_dump -U sds_nexus_user sds_nexus > backup_$(date +%Y%m%d).sql

# Restore database
docker-compose exec -T postgres psql -U sds_nexus_user sds_nexus < backup_20240115.sql

# Run migrations
cd /opt/sds-nexus
source venv/bin/activate
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"

# Rollback one migration
alembic downgrade -1
```

## Grafana Operations

```bash
# Add Prometheus data source via API
curl -X POST http://localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "name": "Prometheus",
    "type": "prometheus",
    "url": "http://prometheus:9090",
    "access": "proxy",
    "isDefault": true
  }'

# List dashboards
curl http://localhost:3000/api/search -u admin:admin

# Import dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @docker/grafana/dashboards/ceph-cluster-overview.json

# Change admin password
curl -X PUT http://localhost:3000/api/user/password \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{"oldPassword":"admin","newPassword":"new_password","confirmNew":"new_password"}'
```

## Prometheus Operations

```bash
# Reload configuration (without restart)
curl -X POST http://localhost:9090/-/reload

# Check configuration
promtool check config /etc/prometheus/prometheus.yml

# Check alert rules
promtool check rules /etc/prometheus/rules/*.yml

# Query API
curl 'http://localhost:9090/api/v1/query?query=up'

# Get all targets
curl http://localhost:9090/api/v1/targets

# Get all alerts
curl http://localhost:9090/api/v1/alerts

# Get active alerts only
curl 'http://localhost:9090/api/v1/alerts?state=active'
```

## Health Checks

```bash
# API health
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready

# Prometheus health
curl http://localhost:9090/-/healthy
curl http://localhost:9090/-/ready

# Grafana health
curl http://localhost:3000/api/health

# Database connection
docker-compose exec postgres pg_isready -U sds_nexus_user
```

## Logs and Debugging

```bash
# View API logs
docker-compose logs -f api --tail=100

# View Prometheus logs
docker-compose logs -f prometheus --tail=100

# View Grafana logs
docker-compose logs -f grafana --tail=100

# View all logs
docker-compose logs -f

# Production logs (systemd)
journalctl -u sds-nexus-api -f
journalctl -u prometheus -f
journalctl -u grafana-server -f

# Application logs (if using file logging)
tail -f /var/log/sds-nexus/app.log
tail -f /var/log/prometheus/prometheus.log
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/unit/test_security.py

# Run specific test
pytest tests/unit/test_security.py::test_password_hash

# Run integration tests only
pytest tests/integration/
```

## Performance Monitoring

```bash
# Check API response time
curl -w "@-" -o /dev/null -s http://localhost:8000/api/v1/metrics <<'EOF'
    time_namelookup:  %{time_namelookup}\n
       time_connect:  %{time_connect}\n
    time_appconnect:  %{time_appconnect}\n
   time_pretransfer:  %{time_pretransfer}\n
      time_redirect:  %{time_redirect}\n
 time_starttransfer:  %{time_starttransfer}\n
                    ----------\n
         time_total:  %{time_total}\n
EOF

# Check database connection pool
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_db_connection_pool

# Check worker job durations
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_worker_job_duration

# Check HTTP request metrics
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_http_requests_total
```

## Alert Configuration

### Silence an Alert (Alertmanager)
```bash
# Create silence for 2 hours
curl -X POST http://localhost:9093/api/v1/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [
      {"name": "alertname", "value": "CephOSDDown", "isRegex": false}
    ],
    "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'",
    "endsAt": "'$(date -u -d '+2 hours' +%Y-%m-%dT%H:%M:%S.000Z)'",
    "createdBy": "ops-team",
    "comment": "Planned OSD maintenance"
  }'

# List active silences
curl http://localhost:9093/api/v1/silences

# Delete silence
curl -X DELETE http://localhost:9093/api/v1/silence/{silence_id}
```

## Troubleshooting Commands

```bash
# Check if metrics endpoint is working
curl -I http://localhost:8000/api/v1/metrics

# Check Prometheus scraping status
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .job, health: .health, lastError: .lastError}'

# Check Grafana data source status
curl http://localhost:3000/api/datasources -u admin:admin | jq

# Verify environment configuration
docker-compose exec api env | grep APP_ENV

# Check database connectivity
docker-compose exec api python3 -c "from app.db.session import check_db_connectivity; print(check_db_connectivity())"

# Test maintenance window logic
docker-compose exec api python3 -c "
from app.core.maintenance import is_maintenance_active
from app.db.session import get_db
print('Maintenance active:', is_maintenance_active(cluster_id=1, db=next(get_db())))
"
```

## Security

```bash
# Generate secure random key (for secrets)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Change Grafana admin password
docker-compose exec grafana grafana-cli admin reset-admin-password newpassword

# Rotate database password
# 1. Update .env file with new password
# 2. Update database: ALTER USER sds_nexus_user WITH PASSWORD 'new_password';
# 3. Restart services: docker-compose restart

# Check file permissions (production)
ls -la /etc/sds-nexus/
# Should show: -rw------- (600) for .env files
# Should show: drwxr-x--- (750) for directories
```

## Useful File Paths

| File | Location |
|------|----------|
| API logs (dev) | `./logs/app.log` |
| API logs (prod) | `/var/log/sds-nexus/app.log` |
| Environment config (dev) | `.env.development` |
| Environment config (prod) | `/etc/sds-nexus/production.env` |
| SSH keys (prod) | `/etc/sds-nexus/keys/` |
| Prometheus config | `/etc/prometheus/prometheus.yml` |
| Prometheus rules | `/etc/prometheus/rules/*.yml` |
| Grafana config | `/etc/grafana/grafana.ini` |
| Grafana dashboards | `/var/lib/grafana/dashboards/` |

## Emergency Procedures

### Disable Prometheus Scraping (if causing issues)
```bash
# Edit prometheus.yml and comment out sds-nexus-api job
vi /etc/prometheus/prometheus.yml
# Reload Prometheus
curl -X POST http://localhost:9090/-/reload
```

### Stop Alert Notifications
```bash
# Silence all alerts for 1 hour
curl -X POST http://localhost:9093/api/v1/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [{"name": "alertname", "value": ".*", "isRegex": true}],
    "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'",
    "endsAt": "'$(date -u -d '+1 hour' +%Y-%m-%dT%H:%M:%S.000Z)'",
    "createdBy": "emergency",
    "comment": "Emergency silence - all alerts"
  }'
```

### Rollback Database Migration
```bash
cd /opt/sds-nexus
source venv/bin/activate
alembic downgrade -1  # Rollback one migration
alembic current       # Check current version
```

---

For complete documentation, see:
- **[Implementation Guide](docs/IMPLEMENTATION_GUIDE.md)**
- **[Prometheus/Grafana Setup](PROMETHEUS_GRAFANA_SETUP.md)**
- **[Prometheus/Grafana Guide](docs/PROMETHEUS_GRAFANA_GUIDE.md)**
- **[Changes Summary](CHANGES_SUMMARY.md)**
- **[Implementation Checklist](IMPLEMENTATION_CHECKLIST.md)**
