## SDS Nexus Infrastructure Topology (OSNexus QuantaStor -- ue-south-1)

**Corrected traffic flow (Load Balancer is IN FRONT of Object Gateways):**

```
S3 Client / Platform --> Load Balancer VIP --> Object Gateway (RGW) --> Storage Nodes
```

| GUI Section | Count | What It Is | How Platform Connects |
|---|---|---|---|
| **Load Balancers** | 12/12 | Reverse proxy VIP -- S3 entry point | ALL S3 + Admin API calls go HERE |
| **Object Gateways** | 9/12 | RGW daemons behind the LB | Never connect directly -- LB handles this |
| **Storage Nodes** | 12 | dbr-gbch-sds01..sds12 | ALL SSH Ceph CLI + node metrics go HERE |

**Cluster:** `ue-south-1` | **Health:** `HEALTH_OK` | **OSDs:** 287/287 | **MONs:** 7/7 | **Free:** 509 TB

**Rule of thumb:**
- S3 / Admin API traffic  -->  **Load Balancer VIP** (Load Balancer tab in QuantaStor GUI)
- SSH / CLI / metrics     -->  **Node hostnames directly** (`dbr-gbch-sds01` .. `sds12`)
- Never SSH to Load Balancers or Object Gateways

---


## Module 1 — Cluster Health

| Item | Value |
|---|---|
| Auth method | SSH as `sds-monitor` (read-only local account) |
| Connect to | `dbr-gbch-sds01` (admin/MON node) — direct SSH |
| All nodes | `dbr-gbch-sds01` → `dbr-gbch-sds12` |
| Do NOT SSH to | Object Gateways or Load Balancers |
| Key location | `/etc/sds-nexus/keys/sds_monitor_ed25519` |
| Commands | `ceph status`, `ceph df`, `ceph osd tree/df`, `ceph mon/mgr/pg stat` |
| Expected: OSDs | 287 total (matching GUI `287/287 OSDs Up`) |
| Expected: MONs | 7 in quorum (matching GUI `7/7 MONs in Quorum`) |
| Collection interval | Every 5 minutes (capacity: 1 hour) |
| Worker | `app/workers/cluster_monitor.py` |
| Service | `app/services/cluster_health/health_service.py` |

**Confirm before starting:** `sudo ceph status --format json` on `dbr-gbch-sds01` returns `HEALTH_OK` with 287 OSDs

---

## Module 2 — Node Monitoring

| Item | Value |
|---|---|
| Auth method | SSH as `sds-monitor` (same key) |
| Nodes to monitor | `dbr-gbch-sds01` through `dbr-gbch-sds12` (all 12) |
| Do NOT SSH to | Object Gateways or Load Balancers |
| Node discovery | Parse `ceph osd tree` → `dbr-gbch-sds01..12` hostnames |
| Expected OSDs/node | ~23–24 OSDs per node (287 ÷ 12) |
| CPU/Memory | `/proc/stat`, `/proc/meminfo`, `/proc/loadavg` via SSH |
| Temperatures | `sudo sensors -j` (requires sudoers.d rule on each node) |
| SMART | `sudo smartctl -a --json /dev/sdX` (requires sudoers.d rule) |
| Collection interval | Metrics: 5 min / SMART: 30 min |
| Worker | `app/workers/node_monitor.py` |
| Service | `app/services/node_monitoring/node_service.py` |

**Confirm before starting:** `sudo sensors -j` returns temperature data on at least one node

---

## Module 3 — Object Storage

| Item | Value |
|---|---|
| Auth method | RGW Admin REST API (HTTP, AWS Sig V4) |
| Connect to | **Load Balancer VIP** (not individual Gateway node IPs) |
| LB endpoint | Visible in SDS Nexus GUI → Load Balancer section |
| RGW user | `sds-nexus-monitor` (local RGW account, read caps only) |
| Caps required | `users=read;buckets=read;metadata=read;usage=read;zone=read` |
| Signing library | `botocore.auth.SigV4Auth` + `requests` |
| Admin endpoint | `http://<Load-Balancer-VIP>:7480/admin` |
| S3 endpoint | `http://<Load-Balancer-VIP>:7480` |
| Collection interval | Every 1 hour |
| Worker | `app/workers/storage_monitor.py` |
| Client | `app/services/object_storage/rgw_admin_client.py` |

**Confirm before starting:** `radosgw-admin user info --uid sds-nexus-monitor` shows correct caps

---

## Module 4 — Reporting

| Item | Value |
|---|---|
| Email library | `aiosmtplib` (async SMTP) |
| Templates | Jinja2 HTML in `app/templates/email/` |
| Excel library | `openpyxl` |
| Charts | `matplotlib` (PNG) embedded in Excel + emails |
| Schedule | Daily 07:00, 6-hourly, Monthly 1st 06:00 |
| Output path | `/var/sds-nexus/reports/` |
| Worker | `app/workers/report_worker.py` |

**Email layout rule:** Use inline CSS + table-based HTML. Avoid `<style>` blocks (Outlook strips them).

---

## Module 5 — Chargeback

| Item | Value |
|---|---|
| Billing method | Average GB per month (configurable: avg or peak) |
| Currencies | GBP (primary) + USD (secondary via exchange rate) |
| VAT | 20% UK VAT (configurable) |
| Billing day | 1st of month (configurable) |
| Data source | `tenant_usage` table (populated by Module 3) |
| Calculator | Pure Python, no DB access, fully unit-testable |
| Forecast method | Linear regression via `numpy.polyfit` |

**Rate change procedure:** Update `settings` table (category=chargeback) — no redeploy needed.

---

## Module 6 — Dashboard

| Item | Value |
|---|---|
| Backend | Existing FastAPI v1 API + new aggregation endpoints |
| Auth | JWT Bearer token (POST `/api/v1/auth/token`) |
| Ops dashboard | GET `/api/v1/dashboard/ops` — cluster + OSD + alerts |
| Management dashboard | GET `/api/v1/dashboard/management` — costs + trends |
| Tenant portal | GET `/api/v1/dashboard/tenant` — self-service (own data only) |
| Frontend option A | Plotly Dash (Python, port 8050) |
| Frontend option B | React/Vue SPA consuming FastAPI (recommended) |

---

## Read-Only Account Summary

| Account | Type | Where Created | Used By | Connects Via |
|---|---|---|---|---|
| `sds-monitor` | Linux local user | Each **Node** | Modules 1 & 2 (SSH) | Direct SSH to Node IPs |
| `client.sds-monitor` | Ceph auth keyring | Ceph cluster (on admin Node) | Module 1 (ceph CLI via sudo) | SSH → Node → sudo |
| `sds-nexus-monitor` | RGW local user | SDS Nexus RGW (via admin Node) | Module 3 (Admin API) | HTTP → **Load Balancer VIP** |
| `sds-nexus` | Platform Linux user | Platform server | Runs the Python app | — |
| `sds_nexus_user` | PostgreSQL user | PostgreSQL | All modules (DB writes) | TCP 5432 |

**Do NOT create `sds-monitor` Linux accounts on the Gateway or Load Balancer nodes.**  
**Do NOT point `RGW_ENDPOINT` at a Gateway node IP — always use the Load Balancer VIP.**
