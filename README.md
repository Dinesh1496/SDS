# SDS Nexus Storage Operations & Chargeback Platform

Enterprise-grade monitoring and chargeback platform for Ceph-based object storage infrastructure.

**🚀 NEW:** Now includes comprehensive **Prometheus** and **Grafana** integration for real-time monitoring, multi-environment configuration management, and maintenance window support for alert suppression. See [PROMETHEUS_GRAFANA_SETUP.md](PROMETHEUS_GRAFANA_SETUP.md) for details.

## Features

- **Cluster Health Monitoring**: Real-time MON, MGR, OSD, PG status tracking
- **Node Monitoring**: CPU, Memory, Disk, Temperature, SMART, Network metrics
- **Object Storage Monitoring**: Tenant, bucket, quota, and growth tracking
- **Automated Reporting**: Daily/6-hour email alerts, monthly Excel/PDF reports
- **Chargeback**: Multi-currency (GBP/USD) cost calculation and forecasting
- **Dashboard**: Operations, management, and customer portals
- **Historical Database**: Long-term trend analysis and capacity planning
- **🆕 Prometheus Metrics**: Comprehensive instrumentation for all components
- **🆕 Grafana Dashboards**: Pre-built dashboards for visualization
- **🆕 Multi-Environment**: Development, staging, and production configurations
- **🆕 Maintenance Windows**: Scheduled alert suppression during system changes
- **🆕 Alert Rules**: Proactive monitoring with customizable alert thresholds

## Technology Stack

- **Backend**: Python 3.12+, FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic
- **SSH Access**: Paramiko
- **Object Storage API**: Boto3
- **Reporting**: OpenPyXL, Matplotlib, Plotly, Jinja2
- **Data Processing**: Pandas
- **Validation**: Pydantic
- **Logging**: Loguru
- **Containerization**: Docker
- **🆕 Monitoring**: Prometheus + Grafana
- **🆕 Metrics**: prometheus-client

## Project Structure

```
sds-nexus-platform/
├── alembic/                    # Database migrations
├── app/
│   ├── api/                    # FastAPI routes
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   └── __init__.py
│   │   └── deps.py
│   ├── core/                   # Core configuration
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── security.py
│   │   └── __init__.py
│   ├── db/                     # Database
│   │   ├── base.py
│   │   ├── session.py
│   │   └── __init__.py
│   ├── models/                 # SQLAlchemy models
│   │   ├── cluster.py
│   │   ├── node.py
│   │   ├── storage.py
│   │   ├── monitoring.py
│   │   ├── reporting.py
│   │   ├── chargeback.py
│   │   ├── user.py
│   │   └── __init__.py
│   ├── schemas/                # Pydantic schemas
│   │   ├── cluster.py
│   │   ├── node.py
│   │   ├── storage.py
│   │   ├── monitoring.py
│   │   └── __init__.py
│   ├── repositories/           # Data access layer
│   │   ├── base.py
│   │   ├── cluster.py
│   │   ├── node.py
│   │   └── __init__.py
│   ├── services/               # Business logic layer
│   │   ├── cluster_health/
│   │   ├── node_monitoring/
│   │   ├── object_storage/
│   │   ├── reporting/
│   │   ├── chargeback/
│   │   └── __init__.py
│   ├── utils/                  # Utility functions
│   │   ├── ssh_client.py
│   │   ├── ceph_client.py
│   │   ├── email_client.py
│   │   ├── retry.py
│   │   └── __init__.py
│   ├── workers/                # Background tasks
│   │   ├── cluster_monitor.py
│   │   ├── node_monitor.py
│   │   ├── storage_monitor.py
│   │   └── __init__.py
│   └── main.py                 # Application entry point
├── tests/                      # Test suite
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── scripts/                    # Utility scripts
│   ├── init_db.py
│   └── seed_data.py
├── config/                     # Configuration files
│   ├── development.env
│   ├── production.env
│   └── logging.yaml
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
├── docs/                       # Documentation
├── .env.example
├── .gitignore
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Installation

### Quick Start - Production Deployment

**⚡ For production deployment, use the streamlined guide:**

📘 **[PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md)** - Complete step-by-step deployment (2-3 hours)

**Prerequisites:**
- RHEL 10 server (4 CPU, 8GB RAM, 100GB disk)
- Root access
- Ceph cluster access credentials

**Deployment Steps:**
1. System preparation (15 min)
2. PostgreSQL installation (10 min)
3. Application deployment (20 min)
4. Prometheus installation (15 min)
5. Grafana installation (15 min)
6. Service configuration (10 min)
7. Automated tasks setup (10 min)
8. Verification & testing (15 min)

### Development Environment (Docker)

```bash
# Start the full stack (API, PostgreSQL, Prometheus, Grafana)
cd docker
docker-compose up -d

# Run database migrations
docker-compose --profile migrate up migrations

# Access services:
# - API: http://localhost:8000/docs
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
# - Metrics: http://localhost:8000/api/v1/metrics
```

### Local Development (Without Docker)

1. Create virtual environment:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.development.example` to `.env` and configure
4. Run application:
   ```bash
   uvicorn app.main:app --reload
   ```

## Configuration

Configuration is managed through environment variables with multi-environment support.

### Environment Files

- **Development**: `.env.development` (local development)
- **Staging**: `.env.staging` (pre-production testing)
- **Production**: `/etc/sds-nexus/production.env` (production deployment)

See `.env.production.example` for all available options.

### Key Configuration Areas

- Database connection
- Ceph cluster credentials
- Email settings
- Chargeback rates
- Monitoring intervals
- Prometheus/Grafana endpoints
- Alert thresholds

### Switch Environments

```bash
# Set environment
export APP_ENV=production

# Or in Docker
docker-compose --env-file .env.production up -d
```

See [docs/PROMETHEUS_GRAFANA_GUIDE.md](docs/PROMETHEUS_GRAFANA_GUIDE.md) for configuration management details.

## Modules

### Module 1: Cluster Health Monitoring
Monitor MON, MGR, OSD, PG status, recovery, rebalancing, and capacity.

### Module 2: Node Monitoring
Track CPU, memory, disk, temperature, SMART status, and network metrics.

### Module 3: Object Storage Monitoring
Monitor tenants, buckets, object counts, quotas, and growth trends.

### Module 4: Reporting
Generate daily emails, 6-hour alerts, monthly Excel/PDF reports with graphs.

### Module 5: Chargeback
Calculate costs in GBP/USD, generate monthly invoices, forecast future costs.

### Module 6: Dashboard
Provide operations, management, and customer-facing dashboards.

### Module 7: Prometheus & Grafana Monitoring
Comprehensive metrics collection and visualization:
- Real-time cluster health metrics
- Node performance monitoring
- RGW bucket and user metrics
- Platform health (API, workers, database)
- **Pre-built Grafana dashboards:**
  - **Ceph Cluster Overview** - Cluster health, capacity, OSDs, MONs, PGs
  - **Tenant Usage & Chargeback** - Historical tenant usage, cost tracking, billing analysis
- Alert rules with maintenance window support

See [PROMETHEUS_GRAFANA_SETUP.md](PROMETHEUS_GRAFANA_SETUP.md) for setup instructions and [docs/TENANT_CHARGEBACK_DASHBOARD.md](docs/TENANT_CHARGEBACK_DASHBOARD.md) for tenant chargeback dashboard guide.

## API Documentation

Once running, access interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Prometheus Metrics: http://localhost:8000/api/v1/metrics

## Monitoring Stack

Access the monitoring tools:
- **Prometheus**: http://localhost:9090 - Metrics collection and alerting
- **Grafana**: http://localhost:3000 - Dashboards and visualization (default: admin/admin)
- **Alertmanager**: http://localhost:9093 - Alert routing (optional)

## Development

### Running Tests

```bash
pytest
pytest --cov=app tests/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Code Quality

```bash
# Format
black app/
isort app/

# Lint
pylint app/
mypy app/

# Security
bandit -r app/
```

## Documentation

### 🚀 Deployment Guides
- **[PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md)** - **START HERE** - Simple end-to-end deployment (2-3 hours)
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Deployment verification checklist
- **[PROMETHEUS_GRAFANA_SETUP.md](PROMETHEUS_GRAFANA_SETUP.md)** - Monitoring stack quick start

### 📖 Operational Documentation
- **[OPERATIONAL_RUNBOOK.md](docs/OPERATIONAL_RUNBOOK.md)** - Daily operations, incident response, procedures
- **[MONITORING_INTEGRATION.md](docs/MONITORING_INTEGRATION.md)** - Email, Slack, PagerDuty integrations
- **[TENANT_CHARGEBACK_DASHBOARD.md](docs/TENANT_CHARGEBACK_DASHBOARD.md)** - Tenant usage dashboard guide
- **[OPERATIONAL_COMPLETENESS_CHECKLIST.md](OPERATIONAL_COMPLETENESS_CHECKLIST.md)** - Production readiness assessment

### 📚 Reference Documentation
- **[Implementation Guide](docs/IMPLEMENTATION_GUIDE.md)** - Comprehensive RHEL 10 deployment guide
- **[Prometheus & Grafana Guide](docs/PROMETHEUS_GRAFANA_GUIDE.md)** - Detailed monitoring configuration
- **[Module Quick Reference](docs/MODULE_QUICKREF.md)** - Quick reference for all modules
- **[Delinea Integration](docs/DELINEA_INTEGRATION.md)** - Secret management integration (optional)

## Monitoring & Alerts

### View Metrics

```bash
# Raw Prometheus metrics
curl http://localhost:8000/api/v1/metrics

# Query specific metric
curl 'http://localhost:9090/api/v1/query?query=ceph_cluster_health_status'

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | python3 -m json.tool
```

### Example Prometheus Queries

```promql
# Cluster utilization percentage
ceph_cluster_utilization_percent{cluster_name="ue-south-1"}

# Number of OSDs down
ceph_osd_down{cluster_name="ue-south-1"}

# Top 5 nodes by CPU usage
topk(5, ceph_node_cpu_usage_percent)

# API request rate (requests per second)
rate(sds_nexus_http_requests_total[5m])

# Failed worker jobs in last hour
increase(sds_nexus_worker_job_execution_total{status="failed"}[1h])
```

### Maintenance Windows

Schedule maintenance windows to suppress alerts during planned system changes:

```python
# Create maintenance window
from datetime import datetime, timedelta
from app.core.maintenance import create_maintenance_window, MaintenanceType

window = create_maintenance_window(
    cluster_id=1,
    start_time=datetime.utcnow(),
    end_time=datetime.utcnow() + timedelta(hours=4),
    reason="Scheduled OSD firmware upgrades",
    maintenance_type=MaintenanceType.SCHEDULED,
    created_by="ops-team",
    suppress_alert_sources="osd,node",  # or "*" for all alerts
)

# Check if maintenance is active
from app.core.maintenance import is_maintenance_active
if is_maintenance_active(cluster_id=1, db=db_session):
    print("Maintenance window active - alerts suppressed")

# End maintenance early
from app.core.maintenance import end_maintenance_window
end_maintenance_window(window_id=123, db=db_session)
```

See [PROMETHEUS_GRAFANA_SETUP.md](PROMETHEUS_GRAFANA_SETUP.md) for more examples and configuration options.

## Quick Commands

```bash
# Start full stack
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop all services
docker-compose down

# View metrics
curl http://localhost:8000/api/v1/metrics | grep ceph_cluster

# Access Grafana
open http://localhost:3000  # Login: admin/admin

# Query Prometheus
curl 'http://localhost:9090/api/v1/query?query=up'

# Run migrations
docker-compose --profile migrate up migrations

# Database backup
docker-compose exec postgres pg_dump -U sds_nexus_user sds_nexus > backup.sql
```

## License

Proprietary - Internal Use Only

## Support

Contact: Storage Operations Team
