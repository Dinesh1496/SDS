#!/bin/bash
################################################################################
# SDS Nexus Platform - Automated Health Check Script
################################################################################
# Description: Performs comprehensive health checks on all platform components
# Usage: ./scripts/health_check.sh [--verbose] [--alert-only]
# Exit Codes: 0=All OK, 1=Warning, 2=Critical
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VERBOSE=false
ALERT_ONLY=false
EXIT_CODE=0

# Parse arguments
for arg in "$@"; do
    case $arg in
        --verbose) VERBOSE=true ;;
        --alert-only) ALERT_ONLY=true ;;
    esac
done

# Helper functions
log_info() {
    if [[ "$ALERT_ONLY" == "false" ]]; then
        echo -e "${BLUE}[INFO]${NC} $1"
    fi
}

log_success() {
    if [[ "$ALERT_ONLY" == "false" ]]; then
        echo -e "${GREEN}[OK]${NC} $1"
    fi
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    [[ $EXIT_CODE -lt 1 ]] && EXIT_CODE=1
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    EXIT_CODE=2
}

check_status() {
    local description=$1
    local command=$2
    
    if [[ "$VERBOSE" == "true" ]]; then
        log_info "Checking: $description"
    fi
    
    if eval "$command" >/dev/null 2>&1; then
        log_success "$description"
        return 0
    else
        log_error "$description"
        return 1
    fi
}

################################################################################
# Health Checks
################################################################################

log_info "==================== SDS Nexus Health Check ===================="
log_info "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
log_info ""

# 1. Docker Services
log_info "--- Checking Docker Services ---"
if command -v docker-compose &> /dev/null; then
    SERVICES=(api postgres prometheus grafana)
    for service in "${SERVICES[@]}"; do
        if docker-compose ps -q $service &> /dev/null; then
            STATUS=$(docker-compose ps $service | grep $service | awk '{print $4}')
            if [[ "$STATUS" == "running" ]] || [[ "$STATUS" == "Up" ]]; then
                log_success "Service $service is running"
            else
                log_error "Service $service is not running (status: $STATUS)"
            fi
        else
            log_error "Service $service not found"
        fi
    done
else
    log_warning "docker-compose not found, skipping Docker service checks"
fi

echo ""

# 2. API Health
log_info "--- Checking API Health ---"
check_status "API liveness endpoint" \
    "curl -sf http://localhost:8000/api/v1/health/live"

check_status "API readiness endpoint" \
    "curl -sf http://localhost:8000/api/v1/health/ready"

# Check API response time
if RESPONSE_TIME=$(curl -o /dev/null -s -w '%{time_total}' http://localhost:8000/api/v1/health/live 2>/dev/null); then
    RESPONSE_MS=$(echo "$RESPONSE_TIME * 1000" | bc)
    if (( $(echo "$RESPONSE_TIME < 1.0" | bc -l) )); then
        log_success "API response time: ${RESPONSE_MS}ms"
    elif (( $(echo "$RESPONSE_TIME < 5.0" | bc -l) )); then
        log_warning "API response time slow: ${RESPONSE_MS}ms"
    else
        log_error "API response time critical: ${RESPONSE_MS}ms"
    fi
fi

echo ""

# 3. Database Connectivity
log_info "--- Checking Database ---"
if command -v docker-compose &> /dev/null; then
    check_status "PostgreSQL connection" \
        "docker-compose exec -T postgres pg_isready -U sds_nexus_user"
    
    # Check database size
    if DB_SIZE=$(docker-compose exec -T postgres psql -U sds_nexus_user -d sds_nexus -t -c "SELECT pg_size_pretty(pg_database_size('sds_nexus'));" 2>/dev/null | tr -d ' '); then
        log_success "Database size: $DB_SIZE"
    fi
    
    # Check active connections
    if CONNECTIONS=$(docker-compose exec -T postgres psql -U sds_nexus_user -d sds_nexus -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null | tr -d ' '); then
        if [[ $CONNECTIONS -lt 20 ]]; then
            log_success "Active DB connections: $CONNECTIONS"
        elif [[ $CONNECTIONS -lt 50 ]]; then
            log_warning "High DB connections: $CONNECTIONS"
        else
            log_error "Critical DB connections: $CONNECTIONS"
        fi
    fi
fi

echo ""

# 4. Prometheus
log_info "--- Checking Prometheus ---"
check_status "Prometheus health endpoint" \
    "curl -sf http://localhost:9090/-/healthy"

check_status "Prometheus ready endpoint" \
    "curl -sf http://localhost:9090/-/ready"

# Check if Prometheus is scraping targets
if TARGETS_UP=$(curl -s http://localhost:9090/api/v1/targets 2>/dev/null | grep -o '"health":"up"' | wc -l); then
    if [[ $TARGETS_UP -gt 0 ]]; then
        log_success "Prometheus scraping $TARGETS_UP targets"
    else
        log_error "No Prometheus targets up"
    fi
fi

# Check for firing alerts
if FIRING_ALERTS=$(curl -s http://localhost:9090/api/v1/alerts 2>/dev/null | grep -c '"state":"firing"'); then
    if [[ $FIRING_ALERTS -eq 0 ]]; then
        log_success "No firing alerts"
    else
        log_warning "$FIRING_ALERTS alert(s) firing"
        
        if [[ "$VERBOSE" == "true" ]]; then
            curl -s http://localhost:9090/api/v1/alerts 2>/dev/null | \
                jq -r '.data.alerts[] | select(.state=="firing") | "\(.labels.alertname): \(.annotations.summary)"' 2>/dev/null | \
                while read -r line; do
                    log_warning "  $line"
                done
        fi
    fi
fi

echo ""

# 5. Grafana
log_info "--- Checking Grafana ---"
check_status "Grafana health endpoint" \
    "curl -sf http://localhost:3000/api/health"

# Check if Grafana can reach Prometheus
if DATASOURCE_STATUS=$(curl -s http://localhost:3000/api/datasources -u admin:admin 2>/dev/null | grep -o '"type":"prometheus"'); then
    if [[ -n "$DATASOURCE_STATUS" ]]; then
        log_success "Grafana Prometheus datasource configured"
    else
        log_warning "Grafana Prometheus datasource not found"
    fi
fi

echo ""

# 6. Worker Jobs
log_info "--- Checking Worker Jobs ---"
if METRICS=$(curl -s http://localhost:8000/api/v1/metrics 2>/dev/null); then
    # Check last success timestamp for key workers
    WORKERS=("cluster_health" "chargeback_metrics_updater")
    CURRENT_TIME=$(date +%s)
    
    for worker in "${WORKERS[@]}"; do
        if LAST_SUCCESS=$(echo "$METRICS" | grep "sds_nexus_worker_job_last_success_timestamp{job_name=\"$worker\"}" | grep -oP '\d+\.?\d*$'); then
            TIME_DIFF=$((CURRENT_TIME - ${LAST_SUCCESS%.*}))
            
            if [[ $TIME_DIFF -lt 600 ]]; then  # Less than 10 minutes
                log_success "Worker '$worker' last ran $(($TIME_DIFF / 60)) minutes ago"
            elif [[ $TIME_DIFF -lt 3600 ]]; then  # Less than 1 hour
                log_warning "Worker '$worker' last ran $(($TIME_DIFF / 60)) minutes ago"
            else
                log_error "Worker '$worker' last ran $(($TIME_DIFF / 3600)) hours ago"
            fi
        else
            log_warning "Worker '$worker' has not run yet or metrics unavailable"
        fi
    done
fi

echo ""

# 7. Disk Space
log_info "--- Checking Disk Space ---"
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [[ $DISK_USAGE -lt 75 ]]; then
    log_success "Root disk usage: ${DISK_USAGE}%"
elif [[ $DISK_USAGE -lt 90 ]]; then
    log_warning "Root disk usage high: ${DISK_USAGE}%"
else
    log_error "Root disk usage critical: ${DISK_USAGE}%"
fi

# Check Docker volumes
if command -v docker &> /dev/null; then
    DOCKER_USAGE=$(docker system df --format '{{.Type}}\t{{.Size}}' 2>/dev/null | awk '$1=="Images" {print $2}')
    log_info "Docker images size: $DOCKER_USAGE"
fi

echo ""

# 8. Memory Usage
log_info "--- Checking Memory Usage ---"
if command -v free &> /dev/null; then
    MEM_USAGE=$(free | awk 'NR==2 {printf "%.0f", $3/$2 * 100}')
    if [[ $MEM_USAGE -lt 75 ]]; then
        log_success "Memory usage: ${MEM_USAGE}%"
    elif [[ $MEM_USAGE -lt 90 ]]; then
        log_warning "Memory usage high: ${MEM_USAGE}%"
    else
        log_error "Memory usage critical: ${MEM_USAGE}%"
    fi
fi

echo ""

# 9. Ceph Cluster (if accessible)
log_info "--- Checking Ceph Cluster ---"
if command -v ssh &> /dev/null && [[ -f /etc/sds-nexus/keys/sds_monitor_ed25519 ]]; then
    SSH_KEY="/etc/sds-nexus/keys/sds_monitor_ed25519"
    CEPH_ADMIN_NODE="${CEPH_ADMIN_NODE:-dbr-gbch-sds01}"
    
    if CEPH_STATUS=$(ssh -i $SSH_KEY -o ConnectTimeout=5 -o BatchMode=yes sds-monitor@$CEPH_ADMIN_NODE 'sudo ceph status --format json' 2>/dev/null); then
        HEALTH=$(echo "$CEPH_STATUS" | jq -r '.health.status' 2>/dev/null)
        case $HEALTH in
            "HEALTH_OK")
                log_success "Ceph cluster health: $HEALTH"
                ;;
            "HEALTH_WARN")
                log_warning "Ceph cluster health: $HEALTH"
                ;;
            "HEALTH_ERR")
                log_error "Ceph cluster health: $HEALTH"
                ;;
            *)
                log_warning "Ceph cluster health unknown"
                ;;
        esac
        
        # Check OSDs
        OSDS_UP=$(echo "$CEPH_STATUS" | jq -r '.osdmap.num_up_osds' 2>/dev/null)
        OSDS_IN=$(echo "$CEPH_STATUS" | jq -r '.osdmap.num_in_osds' 2>/dev/null)
        OSDS_TOTAL=$(echo "$CEPH_STATUS" | jq -r '.osdmap.num_osds' 2>/dev/null)
        
        if [[ "$OSDS_UP" == "$OSDS_TOTAL" ]] && [[ "$OSDS_IN" == "$OSDS_TOTAL" ]]; then
            log_success "All OSDs up and in: $OSDS_UP/$OSDS_TOTAL"
        else
            log_error "OSDs issue: $OSDS_UP up, $OSDS_IN in, $OSDS_TOTAL total"
        fi
    else
        log_warning "Cannot connect to Ceph cluster (SSH may not be configured)"
    fi
else
    log_info "Skipping Ceph checks (SSH not configured)"
fi

echo ""

# 10. Recent Errors
log_info "--- Checking Recent Errors ---"
if command -v docker-compose &> /dev/null; then
    ERROR_COUNT=$(docker-compose logs --since 1h api 2>/dev/null | grep -ci error || echo 0)
    if [[ $ERROR_COUNT -eq 0 ]]; then
        log_success "No errors in last hour"
    elif [[ $ERROR_COUNT -lt 10 ]]; then
        log_warning "$ERROR_COUNT errors in last hour"
    else
        log_error "$ERROR_COUNT errors in last hour (check logs)"
    fi
fi

################################################################################
# Summary
################################################################################

echo ""
log_info "==================== Health Check Complete ===================="

case $EXIT_CODE in
    0)
        log_success "All checks passed - system healthy"
        ;;
    1)
        log_warning "Some checks returned warnings - review above"
        ;;
    2)
        log_error "Critical issues detected - immediate action required"
        ;;
esac

echo ""
exit $EXIT_CODE
