# Prometheus & Grafana Integration for SDS Nexus Platform

This document summarizes the Prometheus and Grafana monitoring integration, including multi-environment configuration and alert suppression during maintenance.

## What's New

### 1. Prometheus Metrics Instrumentation

**File**: `app/core/metrics.py`

Comprehensive metrics instrumentation including:
- **HTTP Metrics**: Request count, duration, in-progress requests
- **Ceph Cluster Metrics**: Health status, capacity, utilization
- **OSD Metrics**: Total, up, down, in, out counts
- **MON Metrics**: Total MONs, quorum status
- **Placement Group Metrics**: Total, active+clean, degraded, undersized, etc.
- **Node Metrics**: CPU, memory, load average, temperature
- **RGW Metrics**: Buckets, objects, user operations
- **Alert Metrics**: Total alerts, alert creation counters
- **Chargeback Metrics**: Monthly costs, tenant usage
- **Worker Metrics**: Job execution count, duration, last success timestamp

All metrics are automatically exposed at `/api/v1/metrics` in Prometheus format.

### 2. Multi-Environment Configuration

**Files**: 
- `app/core/environment.py`
- `.env.development`
- `.env.staging`
- `.env.production.example`

Supports three deployment environments with environment-specific configuration:

| Environment | Use Case | Config File |
|---|---|---|
| Development | Local development, testing | `.env.development` |
| Staging | Pre-production testing | `.env.staging` or `/etc/sds-nexus/staging.env` |
| Production | Production deployment | `/etc/sds-nexus/production.env` |

**Configuration Precedence**:
1. Environment variables (highest priority)
2. Environment-specific `.env` file
3. Base `.env` file
4. Default values in code (lowest priority)

**Switch environments**:
```bash
export APP_ENV=production
# or
docker-compose --env-file .env.production up -d
```

### 3. Maintenance Windows & Alert Suppression

**Files**:
- `app/core/maintenance.py`
- `app/models/settings.py` (added MaintenanceWindow model)

Schedule maintenance windows to suppress alerts during planned system changes:

```python
from datetime import datetime, timedelta
from app.core.maintenance import create_maintenance_window

# Create a 4-hour maintenance window
window = create_maintenance_window(
    cluster_id=1,
    start_time=datetime.utcnow(),
    end_time=datetime.utcnow() + timedelta(hours=4),
    reason="Upgrade Ceph OSDs",
    suppress_alert_sources="osd,node",  # or "*" for all
)
```

**Features**:
- Scheduled, emergency, and testing maintenance types
- Selective alert suppression by source type
- Automatic cleanup of expired windows
- Prometheus metric tracking (`sds_nexus_maintenance_window_active`)

### 4. Prometheus & Grafana Docker Integration

**Files**:
- `docker/docker-compose.yml` (updated)
- `docker/prometheus/prometheus.yml`
- `docker/prometheus/rules/sds_nexus_alerts.yml`
- `docker/grafana/provisioning/datasources/prometheus.yml`
- `docker/grafana/provisioning/dashboards/default.yml`

**Docker stack includes**:
- PostgreSQL 16
- SDS Nexus API
- Prometheus (with 30-day retention)
- Grafana (with pre-configured data source)

**Start the full stack**:
```bash
cd docker
docker-compose up -d
```

**Access**:
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin/admin)
- Metrics Endpoint: `http://localhost:8000/api/v1/metrics`

### 5. Alert Rules

**File**: `docker/prometheus/rules/sds_nexus_alerts.yml`

Pre-configured alert rules for:
- **Cluster Health**: Unhealthy cluster, near-full capacity, critically full
- **OSD Health**: OSD down, multiple OSDs down, OSD out
- **MON Health**: Quorum lost
- **Placement Groups**: Degraded PGs, undersized PGs
- **Node Health**: High CPU, high memory, high temperature
- **Platform Health**: High API response time, worker failures, DB pool exhaustion
- **RGW**: Rapid bucket growth

All alerts respect maintenance windows when configured.

## Quick Start

### Development Environment

1. **Start the development stack**:
```bash
cd docker
docker-compose up -d
```

2. **Run database migrations**:
```bash
docker-compose --profile migrate up migrations
```

3. **Access the services**:
   - API: http://localhost:8000/docs
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000

4. **Import dashboards**:
```bash
# Ceph Cluster Overview Dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @docker/grafana/dashboards/ceph-cluster-overview.json

# Tenant Usage & Chargeback Dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @docker/grafana/dashboards/tenant-usage-chargeback.json
```

5. **View metrics**:
```bash
curl http://localhost:8000/api/v1/metrics
```

### Production Deployment

1. **Copy environment template**:
```bash
sudo cp .env.production.example /etc/sds-nexus/production.env
sudo chmod 600 /etc/sds-nexus/production.env
sudo chown sds-nexus:sds-nexus /etc/sds-nexus/production.env
```

2. **Edit configuration**:
```bash
sudo vi /etc/sds-nexus/production.env
# Update all CHANGE_ME values
```

3. **Install Prometheus** (see `docs/PROMETHEUS_GRAFANA_GUIDE.md` for full instructions):
```bash
# Download and install
wget https://github.com/prometheus/prometheus/releases/download/v2.48.0/prometheus-2.48.0.linux-amd64.tar.gz
tar xzf prometheus-2.48.0.linux-amd64.tar.gz
sudo cp prometheus-2.48.0.linux-amd64/prometheus /usr/local/bin/

# Configure
sudo mkdir -p /etc/prometheus/rules
sudo cp docker/prometheus/prometheus.yml /etc/prometheus/
sudo cp docker/prometheus/rules/*.yml /etc/prometheus/rules/

# Create systemd service (see full guide)
sudo systemctl enable prometheus
sudo systemctl start prometheus
```

4. **Install Grafana**:
```bash
# Add Grafana repo
sudo tee /etc/yum.repos.d/grafana.repo << EOF
[grafana]
name=grafana
baseurl=https://rpm.grafana.com
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://rpm.grafana.com/gpg.key
EOF

sudo dnf5 install -y grafana
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

5. **Configure Grafana data source**:
```bash
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

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SDS Nexus Platform                       │
│                                                               │
│  ┌───────────────┐      ┌─────────────┐                     │
│  │   FastAPI     │      │  Workers    │                     │
│  │   (Port 8000) │      │  (APScheduler)                    │
│  └───────┬───────┘      └──────┬──────┘                     │
│          │                      │                             │
│          │  Exposes metrics     │  Updates metrics            │
│          │  at /api/v1/metrics  │                             │
│          v                      v                             │
│  ┌────────────────────────────────────────┐                 │
│  │      Prometheus Client Library         │                 │
│  │      (app/core/metrics.py)              │                 │
│  └────────────────────────────────────────┘                 │
└───────────────────────┬───────────────────────────────────┘
                        │
                        │  HTTP GET /api/v1/metrics
                        │  (every 15 seconds)
                        v
           ┌────────────────────────┐
           │     Prometheus         │
           │     (Port 9090)        │
           │                        │
           │  - Scrapes metrics     │
           │  - Evaluates alerts    │
           │  - 30-day retention    │
           └───────────┬────────────┘
                       │
                       │  PromQL queries
                       v
           ┌────────────────────────┐
           │       Grafana          │
           │       (Port 3000)      │
           │                        │
           │  - Dashboards          │
           │  - Visualizations      │
           │  - Alert annotations   │
           └────────────────────────┘
```

## Key Metrics Exposed

### Ceph Cluster
- `ceph_cluster_health_status` - 0=OK, 1=WARN, 2=ERR
- `ceph_cluster_total_bytes` - Total capacity
- `ceph_cluster_used_bytes` - Used capacity
- `ceph_cluster_utilization_percent` - Utilization %

### OSDs
- `ceph_osd_total` - Total OSDs
- `ceph_osd_up` - OSDs in UP state
- `ceph_osd_down` - OSDs in DOWN state

### Nodes
- `ceph_node_cpu_usage_percent{node_name="..."}` - CPU usage per node
- `ceph_node_memory_usage_percent{node_name="..."}` - Memory usage per node
- `ceph_node_temperature_celsius{node_name="...",sensor="..."}` - Temperature per sensor

### RGW
- `rgw_bucket_total` - Total buckets
- `rgw_bucket_size_bytes{bucket_name="...",tenant="..."}` - Bucket size
- `rgw_user_operations_total{user_id="...",operation_type="..."}` - User operations

### Platform
- `sds_nexus_http_requests_total{method="...",endpoint="...",status_code="..."}` - HTTP requests
- `sds_nexus_worker_job_execution_total{job_name="...",status="..."}` - Worker jobs
- `sds_nexus_alert_total{cluster_name="...",severity="...",status="..."}` - Alerts

## Example Prometheus Queries

```promql
# Cluster utilization over time
ceph_cluster_utilization_percent{cluster_name="ue-south-1"}

# Number of OSDs down
ceph_osd_down{cluster_name="ue-south-1"}

# Highest node CPU usage
topk(5, ceph_node_cpu_usage_percent)

# API request rate (requests/second)
rate(sds_nexus_http_requests_total[5m])

# Failed worker jobs in the last hour
increase(sds_nexus_worker_job_execution_total{status="failed"}[1h])

# Active maintenance windows
sds_nexus_maintenance_window_active == 1
```

## Maintenance Window Examples

### Create a Scheduled Maintenance Window

```python
from datetime import datetime, timedelta
from app.core.maintenance import create_maintenance_window, MaintenanceType
from app.db.session import get_db

# Schedule maintenance for tonight 2 AM - 6 AM
start = datetime(2024, 3, 15, 2, 0, 0)
end = datetime(2024, 3, 15, 6, 0, 0)

window = create_maintenance_window(
    cluster_id=1,
    start_time=start,
    end_time=end,
    reason="Scheduled firmware update on nodes sds08-sds12",
    maintenance_type=MaintenanceType.SCHEDULED,
    created_by="ops-team",
    suppress_alert_sources="node,osd",  # Suppress only node and OSD alerts
    db=next(get_db()),
)
```

### Check Active Maintenance

```python
from app.core.maintenance import is_maintenance_active
from app.db.session import get_db

if is_maintenance_active(cluster_id=1, db=next(get_db())):
    print("Maintenance window active - alerts suppressed")
```

### End Maintenance Early

```python
from app.core.maintenance import end_maintenance_window
from app.db.session import get_db

end_maintenance_window(window_id=123, db=next(get_db()))
```

## Configuration Files Summary

| File | Purpose |
|---|---|
| `app/core/metrics.py` | Prometheus metrics definitions |
| `app/core/environment.py` | Multi-environment configuration loader |
| `app/core/maintenance.py` | Maintenance window management |
| `app/api/v1/endpoints/metrics.py` | Metrics HTTP endpoint |
| `docker/prometheus/prometheus.yml` | Prometheus scrape configuration |
| `docker/prometheus/rules/sds_nexus_alerts.yml` | Alert rules |
| `docker/grafana/provisioning/datasources/prometheus.yml` | Grafana data source |
| `.env.development` | Development environment config |
| `.env.staging` | Staging environment config |
| `.env.production.example` | Production environment template |
| `docs/PROMETHEUS_GRAFANA_GUIDE.md` | Full installation guide |

## Documentation

- **Full Implementation Guide**: `docs/IMPLEMENTATION_GUIDE.md`
- **Prometheus & Grafana Setup**: `docs/PROMETHEUS_GRAFANA_GUIDE.md`
- **Module Quick Reference**: `docs/MODULE_QUICKREF.md`

## Support

For questions or issues:
1. Check `docs/PROMETHEUS_GRAFANA_GUIDE.md` for detailed setup instructions
2. Review `docker/prometheus/rules/sds_nexus_alerts.yml` for alert rule examples
3. Check Prometheus targets: `http://localhost:9090/targets`
4. View raw metrics: `http://localhost:8000/api/v1/metrics`

## Testing

```bash
# Test metrics endpoint
curl http://localhost:8000/api/v1/metrics | grep ceph_cluster_health_status

# Test Prometheus is scraping
curl http://localhost:9090/api/v1/targets | python3 -m json.tool

# Test Grafana connection to Prometheus
curl http://localhost:3000/api/datasources -u admin:admin | python3 -m json.tool

# Validate environment configuration
python3 -c "
from app.core.environment import validate_environment_config, get_environment_info
print('Valid:', validate_environment_config())
print('Info:', get_environment_info())
"
```
