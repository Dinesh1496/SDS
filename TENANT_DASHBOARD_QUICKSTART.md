# Tenant Usage & Chargeback Dashboard - Quick Start

## Access Dashboard

**URL**: http://localhost:3000 (or your Grafana server)  
**Login**: admin / admin (change in production)  
**Dashboard**: "SDS Nexus - Tenant Usage & Chargeback"

## What You'll See

### 📊 At a Glance (Top Row)
- **Total Tenants** - How many tenants have storage
- **Total Storage Used** - Aggregate usage across all tenants
- **Total Monthly Cost (GBP)** - Current month's projected cost
- **Total Monthly Cost (USD)** - Same cost in USD

### 📈 Historical Trends (30 Days Default)
- **Storage Usage by Tenant** - Line graph showing usage over time
- **Monthly Cost by Tenant** - Cost trends over time
- **Growth Rates** - How fast storage and costs are growing

### 🏆 Rankings
- **Top 10 Tenants by Usage** - Largest storage consumers
- **Top 10 Tenants by Cost** - Highest costs
- **Full Tenant Table** - Complete list with sortable columns

### 🪣 Bucket Details
- **Top 20 Buckets by Size** - Largest individual buckets
- **Bucket Growth Trends** - How buckets are growing over time

### 🥧 Cost Breakdown
- **Pie Charts** - Visual distribution of costs and storage
- Shows percentage contribution of each tenant

## Quick Actions

### View Specific Tenant
1. Click "tenant" dropdown at top
2. Select tenant name
3. Dashboard filters to show only that tenant

### Change Time Range
1. Click time range (top right)
2. Select:
   - Last 7 days (recent activity)
   - Last 30 days (monthly billing)
   - Last 90 days (quarterly review)
   - Custom range

### Export Billing Data
1. Scroll to "Tenant Usage & Cost Table"
2. Click table menu (three dots)
3. Select "Export to CSV"
4. Use in Excel or billing system

### Compare Multiple Tenants
1. Click "tenant" dropdown
2. Select multiple tenants (Ctrl+Click or Cmd+Click)
3. Dashboard shows comparison

## Key Metrics Explained

| Metric | What It Shows | How to Use It |
|--------|---------------|---------------|
| **Storage Usage** | Current storage consumption in GB/TB | Capacity planning |
| **Monthly Cost (GBP)** | Calculated as: (GB × £0.05/GB/month) | Budget tracking |
| **Monthly Cost (USD)** | Calculated as: (GB × $0.06/GB/month) | International reporting |
| **Growth Rate** | How fast usage is increasing | Trend forecasting |
| **Bucket Count** | Number of buckets per tenant | Resource utilization |

## Common Questions

### How is cost calculated?
```
Monthly Cost = (Storage in GB) × (Price per GB per month)

Default rates:
- GBP: £0.05 per GB per month
- USD: $0.06 per GB per month

Example:
- 1 TB (1,000 GB) = £50/month or $60/month
- 10 TB (10,000 GB) = £500/month or $600/month
```

### Why don't I see historical data?
- **New deployment**: Takes time to accumulate history
- **Prometheus retention**: Default is 30 days
- **Solution**: Wait for data to accumulate or extend retention

### How often is data updated?
- **Metrics collection**: Every 5 minutes
- **Prometheus scraping**: Every 15 seconds
- **Dashboard refresh**: Every 5 minutes (configurable)

### Can I change pricing rates?
Yes, update environment variables:
```bash
# In .env file or environment
CHARGEBACK_GBP_PER_GB_MONTH=0.08  # Change from 0.05 to 0.08
CHARGEBACK_USD_PER_GB_MONTH=0.10  # Change from 0.06 to 0.10

# Restart API
docker-compose restart api
```

### How do I add alerts?
See alert rules in `docker/prometheus/rules/sds_nexus_alerts.yml`

Example - Alert when tenant exceeds £1000/month:
```yaml
- alert: TenantHighCost
  expr: sds_nexus_chargeback_monthly_cost_gbp > 1000
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Tenant {{ $labels.tenant }} costs £{{ $value }}/month"
```

## Usage Scenarios

### 📅 Monthly Billing
1. Set time range to current month
2. Go to "Tenant Usage & Cost Table"
3. Export to CSV
4. Import into billing system

### 🔍 Investigate Cost Spike
1. Check "Monthly Cost by Tenant" graph
2. Identify which tenant spiked
3. Select that tenant
4. Review "Bucket Growth Trends"
5. Check "Top 20 Buckets" for culprits

### 📊 Capacity Planning
1. View "Storage Growth Rate"
2. Note daily/weekly growth rate
3. Calculate: Days to full = (Available Capacity) / (Growth Rate)
4. Plan infrastructure scaling

### 💰 Budget Review
1. Note "Total Monthly Cost"
2. Compare to budget
3. Check "Top 10 Tenants by Cost"
4. Focus optimization on top spenders

### 🏢 Internal Chargeback
1. View "Cost Distribution (GBP)" pie chart
2. Note each tenant's percentage
3. Apply percentages to shared costs
4. Generate internal invoices

## Tips & Tricks

### 💡 Use Annotations
Mark important events on graphs:
- Tenant onboarding
- Infrastructure changes
- Policy updates

### 📊 Create Custom Panels
Add your own calculations:
- Cost per object
- Cost per bucket
- Usage efficiency metrics

### 🔔 Set Up Alerting
Get notified when:
- Costs exceed threshold
- Growth rate is abnormal
- Tenant usage spikes

### 📈 Track Trends
Regular review schedule:
- **Daily**: Check growth rates
- **Weekly**: Review top consumers
- **Monthly**: Generate billing reports
- **Quarterly**: Analyze long-term trends

## Troubleshooting

### Dashboard Shows "No Data"
```bash
# Check metrics are being generated
curl http://localhost:8000/api/v1/metrics | grep chargeback

# Check Prometheus is scraping
curl http://localhost:9090/api/v1/targets | grep sds-nexus-api

# Verify worker is running
docker-compose logs -f api | grep chargeback
```

### Costs Look Wrong
```bash
# Check current pricing configuration
echo $CHARGEBACK_GBP_PER_GB_MONTH
echo $CHARGEBACK_USD_PER_GB_MONTH

# Verify metric values
curl http://localhost:8000/api/v1/metrics | grep chargeback_monthly_cost

# Manual calculation
# Cost = (Storage in GB) × (Rate per GB)
```

### Can't Select Tenant
- Ensure tenant has data in Prometheus
- Check template variable query in dashboard settings
- Verify metrics have "tenant" label

## Learn More

- **Full Guide**: [docs/TENANT_CHARGEBACK_DASHBOARD.md](docs/TENANT_CHARGEBACK_DASHBOARD.md)
- **Setup Guide**: [PROMETHEUS_GRAFANA_SETUP.md](PROMETHEUS_GRAFANA_SETUP.md)
- **API Docs**: http://localhost:8000/docs
- **Prometheus Queries**: http://localhost:9090

## Support

Need help?
1. Check full documentation
2. Review Prometheus metrics
3. Check application logs
4. Contact: Storage Operations Team

---

**Quick Access Links:**
- [Dashboard Documentation](docs/TENANT_CHARGEBACK_DASHBOARD.md)
- [Prometheus Setup](PROMETHEUS_GRAFANA_SETUP.md)
- [Alert Configuration](docker/prometheus/rules/sds_nexus_alerts.yml)
- [Worker Code](app/workers/chargeback_metrics_updater.py)
