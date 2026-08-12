# Quick Start: Deploy SDS Nexus on Kubernetes

## Prerequisites

✅ Docker Desktop with Kubernetes enabled
✅ kubectl installed
✅ Docker image built

---

## Step 1: Build Docker Image (5 minutes)

```bash
cd d:\SDS

# Build image
docker build -t sds-nexus:latest -f docker/Dockerfile .

# Verify
docker images | grep sds-nexus
```

---

## Step 2: Create Namespace (1 minute)

```bash
kubectl apply -f k8s/base/namespace.yaml

# Verify
kubectl get namespaces
```

---

## Step 3: Create Secrets (2 minutes)

```bash
# Generate secrets
$APP_SECRET = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
$JWT_SECRET = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

# Create secrets
kubectl create secret generic sds-nexus-secrets `
  --from-literal=app-secret-key=$APP_SECRET `
  --from-literal=jwt-secret-key=$JWT_SECRET `
  --from-literal=db-password=devpassword123 `
  --from-literal=ceph-ssh-key="" `
  --from-literal=rgw-access-key="" `
  --from-literal=rgw-secret-key="" `
  --from-literal=smtp-password="" `
  -n sds-nexus

# Verify
kubectl get secrets -n sds-nexus
```

---

## Step 4: Deploy Configuration (1 minute)

```bash
kubectl apply -f k8s/base/configmap.yaml

# Verify
kubectl get configmap -n sds-nexus
```

---

## Step 5: Deploy PostgreSQL (3 minutes)

```bash
# Create PVC
kubectl apply -f k8s/database/postgresql-pvc.yaml

# Deploy PostgreSQL
kubectl apply -f k8s/database/postgresql-deployment.yaml
kubectl apply -f k8s/database/postgresql-service.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=postgresql -n sds-nexus --timeout=120s

# Verify
kubectl get pods -n sds-nexus
kubectl get svc -n sds-nexus
```

---

## Step 6: Run Database Migrations (2 minutes)

```bash
# Run migrations in a one-time job
kubectl run -it --rm alembic-migrate --image=sds-nexus:latest --restart=Never -n sds-nexus -- sh -c "alembic upgrade head"

# Or manually
kubectl exec -it deployment/sds-nexus-api -n sds-nexus -- alembic upgrade head
```

---

## Step 7: Deploy API (3 minutes)

```bash
# Deploy API
kubectl apply -f k8s/api/api-deployment.yaml
kubectl apply -f k8s/api/api-service.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=sds-nexus-api -n sds-nexus --timeout=120s

# Verify
kubectl get pods -n sds-nexus
kubectl get svc -n sds-nexus
```

---

## Step 8: Access Services (1 minute)

### Option 1: LoadBalancer (Docker Desktop)

```bash
# Get external IP (should be localhost)
kubectl get svc sds-nexus-api -n sds-nexus

# Access API
curl http://localhost:8000/api/v1/health/live

# Access API docs
start http://localhost:8000/docs
```

### Option 2: Port Forward

```bash
# Port forward API
kubectl port-forward -n sds-nexus svc/sds-nexus-api 8000:8000

# In another terminal, test
curl http://localhost:8000/api/v1/health/live

# Access docs
start http://localhost:8000/docs
```

---

## Step 9: Deploy Monitoring (Optional, 5 minutes)

```bash
# Deploy Prometheus
kubectl apply -f k8s/monitoring/prometheus/

# Deploy Grafana
kubectl apply -f k8s/monitoring/grafana/

# Access Prometheus
kubectl port-forward -n sds-nexus svc/prometheus 9090:9090

# Access Grafana
kubectl port-forward -n sds-nexus svc/grafana 3000:3000

# Open in browser
start http://localhost:9090  # Prometheus
start http://localhost:3000  # Grafana (admin/admin)
```

---

## Step 10: Enable Auto-Scaling (Optional, 1 minute)

```bash
# Enable metrics server (if not already enabled)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Apply HPA
kubectl apply -f k8s/api/api-hpa.yaml

# Verify
kubectl get hpa -n sds-nexus
```

---

## Verification Checklist

```bash
# Check all resources
kubectl get all -n sds-nexus

# Check pods are running
kubectl get pods -n sds-nexus

# Check services
kubectl get svc -n sds-nexus

# Check API health
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready

# Check metrics
curl http://localhost:8000/api/v1/metrics | head -20

# View logs
kubectl logs -f deployment/sds-nexus-api -n sds-nexus
```

---

## Common Commands

```bash
# View all resources
kubectl get all -n sds-nexus

# View logs
kubectl logs -f deployment/sds-nexus-api -n sds-nexus

# Describe pod
kubectl describe pod <pod-name> -n sds-nexus

# Execute command in pod
kubectl exec -it deployment/sds-nexus-api -n sds-nexus -- sh

# Scale manually
kubectl scale deployment sds-nexus-api --replicas=3 -n sds-nexus

# Restart deployment
kubectl rollout restart deployment/sds-nexus-api -n sds-nexus

# Check HPA status
kubectl get hpa -n sds-nexus

# Delete everything
kubectl delete namespace sds-nexus
```

---

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n sds-nexus

# View pod details
kubectl describe pod <pod-name> -n sds-nexus

# Check logs
kubectl logs <pod-name> -n sds-nexus

# Check events
kubectl get events -n sds-nexus --sort-by='.lastTimestamp'
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
kubectl get pods -l app=postgresql -n sds-nexus

# Test database connection
kubectl exec -it deployment/postgresql -n sds-nexus -- psql -U sds_nexus_user -d sds_nexus -c "SELECT 1;"

# Check service
kubectl get svc postgresql -n sds-nexus
```

### API Not Accessible

```bash
# Check service
kubectl get svc sds-nexus-api -n sds-nexus

# Check endpoints
kubectl get endpoints sds-nexus-api -n sds-nexus

# Port forward to test
kubectl port-forward -n sds-nexus svc/sds-nexus-api 8000:8000
```

---

## Next Steps

1. ✅ Review logs: `kubectl logs -f deployment/sds-nexus-api -n sds-nexus`
2. ✅ Test auto-scaling: Generate load and watch HPA
3. ✅ Test rolling updates: `kubectl set image deployment/sds-nexus-api api=sds-nexus:v2 -n sds-nexus`
4. ✅ Set up monitoring: Deploy Prometheus and Grafana
5. ✅ Configure ingress: Set up nginx-ingress for external access

---

**Total Time**: ~20 minutes  
**Result**: SDS Nexus Platform running on Kubernetes! 🎉

