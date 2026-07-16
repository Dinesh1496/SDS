# Tenant Usage & Chargeback Dashboard Guide

## Overview

The Tenant Usage & Chargeback dashboard provides comprehensive historical tracking of tenant storage usage and associated costs. This dashboard enables:

- **Historical usage tracking** - View usage trends over 30 days or custom time ranges
- **Cost visibility** - See monthly costs in both GBP and USD
- **Tenant comparison** - Compare usage and costs across tenants
- **Growth analysis** - Identify rapid growth trends
- **Bucket-level details** - Drill down to individual bucket usage
- **Cost projections** - Understand future cost implications

## Dashboard Access

**URL**: `http://your-grafana-server:3000/d/tenant-usage-chargeback`

**Default Credentials**: admin / admin (change in production!)

## Dashboard Sections

### 1. Tenant Overview (Top Row)

Four key statistics provide a snapshot of current state:

| Metric | Description |
|--------|-------------|
| **Total Tenants** | Number of unique tenants with storage usage |
| **Total Storage Used** | Aggregate storage consumption across all tenants |
| **Total Monthly Cost (GBP)** | Current month's projected cost in GBP |
| **Total Monthly Cost (USD)** | Current month's projected cost in USD |

**Color Coding:**
- Green: Normal usage
- Yellow: High usage (>1 TB total or >£1,000/month)
- Orange: Very high usage (>5 TB total or >£5,000/month)

---

### 2. Historical Usage Trends

#### Storage Usage by Tenant (30 Days)
- **Time Series Graph** showing storage consumption over time
- **Multiple Lines** - one per tenant (filtered by template variable)
- **Legend Statistics**: Last value, mean, and maximum usage
- **Use Case**: Identify usage patterns, seasonal variations, and anomalies

**Example Insights:**
- Steady linear growth = predictable cost
- Sudden spikes = investigate data ingestion or retention policies
- Declining usage = potential cost savings

#### Monthly Cost by Tenant - GBP (30 Days)
- **Time Series Graph** showing cost trends over time
- **Calculated** based on current pricing rates (£0.05/GB/month default)
- **Use Case**: Budget forecasting and variance analysis

**Cost Calculation:**
```
Monthly Cost (GBP) = (Storage in GB) × (£0.05/GB/month)
```

#### Storage Growth Rate by Tenant (7 Day Average)
- **Time Series Graph** showing rate of change (bytes per second)
- **7-day rolling average** to smooth out daily fluctuations
- **Use Case**: Capacity planning and infrastructure scaling decisions

**Interpretation:**
- Positive rate = Growing usage
- Negative rate = Decreasing usage (rare)
- Zero rate = Stable usage

#### Cost Growth Rate by Tenant - GBP (7 Day Average)
- **Time Series Graph** showing how quickly costs are increasing
- **Projected Monthly Change** = Rate × 30 days
- **Use Case**: Early warning for budget overruns

---

### 3. Tenant Details & Rankings

#### Top 10 Tenants by Storage Usage
- **Horizontal Bar Chart** showing largest consumers
- **Color Gradient**: Green (low) → Yellow (medium) → Red (high)
- **Sorted** by usage descending
- **Use Case**: Identify top storage consumers for optimization discussions

#### Top 10 Tenants by Monthly Cost (GBP)
- **Horizontal Bar Chart** showing highest costs
- **Real-time** cost calculation based on current usage
- **Use Case**: Focus cost optimization efforts on highest-impact tenants

#### Tenant Usage & Cost Table
- **Comprehensive Table** with sortable columns:
  - **Tenant**: Tenant identifier
  - **Storage Usage**: Current storage consumption in bytes (human-readable)
  - **Monthly Cost (GBP)**: Current month projection in GBP
  - **Monthly Cost (USD)**: Current month projection in USD
  - **Bucket Count**: Number of buckets owned by tenant

**Table Features:**
- **Sortable**: Click column headers to sort
- **Filterable**: Use tenant template variable to filter
- **Exportable**: Export to CSV for external analysis

---

### 4. Bucket-Level Details

#### Top 20 Buckets by Size
- **Table View** showing largest individual buckets
- **Columns**: Tenant, Bucket Name, Size, Object Count
- **Sorted** by size descending
- **Use Case**: Identify large buckets for archival or cleanup

#### Bucket Growth Trends (Selected Tenant)
- **Time Series** showing individual bucket growth
- **Filtered** by selected tenant from template variable
- **One Line per Bucket**
- **Use Case**: Understand which buckets are driving tenant growth

---

### 5. Cost Breakdown & Projections

#### Cost Distribution (GBP) - Current Month
- **Pie Chart** showing percentage contribution of each tenant to total costs
- **Interactive**: Click slices to highlight
- **Legend**: Shows value and percentage
- **Use Case**: Visualize cost allocation for internal chargebacks

#### Cost Distribution (USD) - Current Month
- **Pie Chart** in USD currency
- **Exchange Rate**: Applied automatically (default 1 GBP = 1.27 USD)
- **Use Case**: International reporting or USD-based budgets

#### Storage Distribution - Current
- **Pie Chart** showing storage consumption by tenant
- **Use Case**: Capacity planning and tenant quota management

---

## Template Variables

### Cluster Selection
- **Variable**: `$cluster`
- **Type**: Dropdown (single select)
- **Purpose**: Select which Ceph cluster to view
- **Auto-populated** from Prometheus metrics

### Tenant Selection
- **Variable**: `$tenant`
- **Type**: Multi-select dropdown
- **Options**: 
  - `All` - Show all tenants (default)
  - Individual tenant names - Filter to specific tenants
- **Use Case**: Focus on specific tenants or compare subset

**Example Usage:**
1. Select cluster: `ue-south-1`
2. Select tenants: `tenant-finance`, `tenant-marketing`
3. Dashboard shows only those two tenants across all panels

---

## Time Range Selection

Dashboard defaults to **30 days** but can be adjusted:

| Time Range | Use Case |
|------------|----------|
| Last 7 days | Recent trends and troubleshooting |
| Last 30 days | Monthly billing cycle |
| Last 90 days | Quarterly review |
| Last 6 months | Long-term trend analysis |
| Custom range | Specific billing periods or incidents |

**How to Change:**
1. Click time range selector (top right)
2. Choose predefined range or enter custom dates
3. Dashboard updates all panels automatically

---

## Metrics Explained

### Source Metrics

All data comes from Prometheus metrics:

| Metric | Description | Labels |
|--------|-------------|--------|
| `sds_nexus_chargeback_tenant_usage_bytes` | Current storage usage per tenant | cluster_name, tenant |
| `sds_nexus_chargeback_monthly_cost_gbp` | Monthly cost in GBP | cluster_name, tenant |
| `sds_nexus_chargeback_monthly_cost_usd` | Monthly cost in USD | cluster_name, tenant |
| `rgw_bucket_size_bytes` | Individual bucket size | cluster_name, tenant, bucket_name |
| `rgw_bucket_objects` | Object count per bucket | cluster_name, tenant, bucket_name |
| `rgw_bucket_total` | Total bucket count | cluster_name, tenant |

### Calculated Metrics

Dashboard uses PromQL functions to derive insights:

```promql
# Storage growth rate (bytes per second)
rate(sds_nexus_chargeback_tenant_usage_bytes[7d])

# Cost growth rate (GBP per month)
rate(sds_nexus_chargeback_monthly_cost_gbp[7d]) * 86400 * 30

# Top 10 tenants by usage
topk(10, sds_nexus_chargeback_tenant_usage_bytes)

# Percentage of total usage
(sds_nexus_chargeback_tenant_usage_bytes / 
 sum(sds_nexus_chargeback_tenant_usage_bytes)) * 100
```

---

## Common Use Cases

### 1. Monthly Billing Report

**Goal**: Generate end-of-month billing report

**Steps:**
1. Set time range to current month (e.g., "Dec 1 - Dec 31")
2. Select cluster: `ue-south-1`
3. Select tenant: `All`
4. Navigate to "Tenant Usage & Cost Table"
5. Click "Export" → "CSV" to download
6. Import CSV into billing system or Excel

**Data Provided:**
- Tenant name
- Storage usage (GB)
- Monthly cost (GBP and USD)
- Bucket count

---

### 2. Investigate Cost Spike

**Goal**: Understand why costs increased suddenly

**Steps:**
1. Look at "Monthly Cost by Tenant - GBP" graph
2. Identify which tenant(s) show spike
3. Select that tenant in template variable
4. Check "Storage Usage by Tenant" graph for correlation
5. Review "Bucket Growth Trends" to identify which buckets grew
6. Check "Top 20 Buckets by Size" for largest contributors

**Questions to Answer:**
- Did usage increase or just pricing change?
- Is growth from new buckets or existing buckets?
- Is growth pattern expected or anomalous?

---

### 3. Capacity Planning

**Goal**: Forecast when cluster will reach capacity

**Steps:**
1. Set time range to "Last 90 days"
2. Look at "Storage Usage by Tenant" graph
3. Identify linear growth patterns
4. Note current growth rate from "Storage Growth Rate" graph
5. Calculate time to capacity:
   ```
   Days to Capacity = (Available Capacity) / (Current Growth Rate)
   ```

**Example:**
- Available capacity: 500 TB
- Current growth rate: 100 GB/day
- Time to capacity: ~13.7 years (500,000 GB / 100 GB/day / 365 days)

---

### 4. Budget Variance Analysis

**Goal**: Compare actual costs to budget

**Steps:**
1. Set time range to fiscal month
2. Note "Total Monthly Cost (GBP)" from top stat panel
3. Compare to budgeted amount
4. If over budget:
   - Check "Top 10 Tenants by Monthly Cost"
   - Review growth rates for top consumers
   - Identify optimization opportunities

---

### 5. Tenant Cost Allocation

**Goal**: Allocate infrastructure costs to tenants

**Steps:**
1. Use "Cost Distribution (GBP)" pie chart
2. Note percentage for each tenant
3. Apply percentages to shared infrastructure costs
4. Generate internal chargeback invoices

**Example:**
- Total infrastructure cost: £10,000/month
- Tenant A uses 30% of storage = £3,000 allocation
- Tenant B uses 70% of storage = £7,000 allocation

---

## Alert Configuration

Set up alerts based on dashboard queries:

### High Cost Alert

**Alert Rule:**
```yaml
- alert: TenantHighMonthlyCost
  expr: sds_nexus_chargeback_monthly_cost_gbp > 1000
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Tenant {{ $labels.tenant }} monthly cost is £{{ $value }}"
```

### Rapid Growth Alert

**Alert Rule:**
```yaml
- alert: TenantRapidGrowth
  expr: rate(sds_nexus_chargeback_tenant_usage_bytes[7d]) > 1073741824
  for: 6h
  labels:
    severity: info
  annotations:
    summary: "Tenant {{ $labels.tenant }} growing by >1GB/day"
```

---

## Customization

### Adjust Pricing Rates

Pricing is calculated from database configuration. To change rates:

```sql
-- Update chargeback rates in settings table
UPDATE settings 
SET value = '0.08' 
WHERE category = 'chargeback' AND key = 'gbp_per_gb_month';

-- Or via environment variables
export CHARGEBACK_GBP_PER_GB_MONTH=0.08
export CHARGEBACK_USD_PER_GB_MONTH=0.10
```

After changing rates, restart the chargeback metrics updater:
```bash
docker-compose restart api
```

### Add Custom Panels

1. Click "Add Panel" at top of dashboard
2. Select visualization type
3. Add PromQL query
4. Configure display options
5. Save dashboard

**Example Custom Panel - Cost Per Object:**
```promql
(sds_nexus_chargeback_monthly_cost_gbp / 
 sum by (tenant) (rgw_bucket_objects))
```

### Modify Time Ranges

Edit dashboard JSON and change default time range:
```json
"time": {
  "from": "now-90d",  // Change from 30d to 90d
  "to": "now"
}
```

---

## Data Retention

### Prometheus Retention
- **Default**: 30 days
- **Location**: `/var/lib/prometheus`
- **To increase**:
  ```bash
  # Edit prometheus.yml or command args
  --storage.tsdb.retention.time=90d
  ```

### Database Historical Data
The platform stores historical data in PostgreSQL:
- **Bucket snapshots**: Retained indefinitely
- **Usage reports**: Configurable retention (default 365 days)
- **Query**: `SELECT * FROM buckets WHERE recorded_at > NOW() - INTERVAL '30 days'`

---

## Troubleshooting

### No Data Showing

**Check 1**: Verify metrics are being collected
```bash
curl http://localhost:8000/api/v1/metrics | grep chargeback_tenant_usage
```

**Check 2**: Verify Prometheus is scraping
```bash
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="sds-nexus-api")'
```

**Check 3**: Verify worker is running
```bash
# Check if chargeback metrics updater ran recently
curl http://localhost:8000/api/v1/metrics | grep chargeback_metrics_updater
```

### Dashboard Shows "N/A"

**Cause**: No data for selected time range or tenant

**Solution**:
1. Widen time range
2. Select "All" tenants
3. Verify data exists in Prometheus: `/graph` page, query `sds_nexus_chargeback_tenant_usage_bytes`

### Costs Don't Match Expected

**Cause**: Pricing rates may be misconfigured

**Solution**:
1. Check current rates:
   ```bash
   curl http://localhost:8000/api/v1/metrics | grep chargeback_monthly_cost_gbp
   ```

2. Verify pricing configuration:
   ```sql
   SELECT * FROM settings WHERE category = 'chargeback';
   ```

3. Recalculate manually:
   ```
   Cost (GBP) = (Usage in GB) × (Rate per GB)
   Example: 1000 GB × £0.05/GB = £50.00
   ```

### Pie Chart Shows No Data

**Cause**: Query returns empty result

**Check**:
1. Are there active tenants? `SELECT COUNT(DISTINCT tenant) FROM buckets;`
2. Is Prometheus scraping? Check `/targets` in Prometheus UI
3. Is time range too narrow? Set to "Last 30 days"

---

## Best Practices

### 1. Regular Review Cadence

- **Daily**: Monitor "Cost Growth Rate" for anomalies
- **Weekly**: Review "Top 10 Tenants" for changes
- **Monthly**: Generate billing reports from table export
- **Quarterly**: Analyze long-term trends (90-day view)

### 2. Set Up Annotations

Mark significant events on graphs:

```bash
# Create annotation in Grafana
curl -X POST http://localhost:3000/api/annotations \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "dashboardId": 1,
    "time": '$(date +%s000)',
    "text": "Tenant onboarding: new-tenant-123",
    "tags": ["tenant", "onboarding"]
  }'
```

### 3. Export Regular Reports

Automate monthly report generation:

```bash
#!/bin/bash
# Export tenant costs to CSV monthly
YEAR_MONTH=$(date +%Y-%m)
curl -s 'http://localhost:9090/api/v1/query?query=sds_nexus_chargeback_monthly_cost_gbp' \
  | jq -r '.data.result[] | [.metric.tenant, .value[1]] | @csv' \
  > "tenant_costs_${YEAR_MONTH}.csv"
```

### 4. Maintain Documentation

Keep track of:
- Pricing rate changes (with effective dates)
- Tenant onboarding/offboarding events
- Storage quota allocations
- Cost optimization initiatives

---

## API Integration

Fetch tenant usage data programmatically:

### Python Example

```python
import requests
from datetime import datetime, timedelta

# Query Prometheus API
PROMETHEUS_URL = "http://localhost:9090"
query = "sds_nexus_chargeback_monthly_cost_gbp"

response = requests.get(
    f"{PROMETHEUS_URL}/api/v1/query",
    params={"query": query}
)

data = response.json()
for result in data['data']['result']:
    tenant = result['metric']['tenant']
    cost = float(result['value'][1])
    print(f"{tenant}: £{cost:.2f}")
```

### cURL Example

```bash
# Get current costs for all tenants
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=sds_nexus_chargeback_monthly_cost_gbp' \
  | jq '.data.result[] | {tenant: .metric.tenant, cost: .value[1]}'
```

---

## Related Dashboards

- **Ceph Cluster Overview** - Infrastructure health and capacity
- **Node Metrics** - Per-node performance and utilization
- **Platform Health** - API and worker job monitoring

Navigate between dashboards using links in the top navigation bar.

---

## Support

For questions or issues with this dashboard:

1. Check Prometheus metrics are being generated: `curl http://localhost:8000/api/v1/metrics`
2. Review worker logs: `docker-compose logs -f api | grep chargeback`
3. Check Grafana query inspector: Click panel title → Inspect → Query
4. Contact: Storage Operations Team

---

**Dashboard Version**: 1.0.0  
**Last Updated**: January 15, 2024  
**Maintained By**: Storage Operations Team
