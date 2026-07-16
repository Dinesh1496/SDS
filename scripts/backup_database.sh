#!/bin/bash
################################################################################
# SDS Nexus Platform - Database Backup Script
################################################################################
# Description: Automated PostgreSQL database backup with retention management
# Usage: ./scripts/backup_database.sh [--retention-days 30]
# Schedule: Run daily at 2:00 AM via cron
################################################################################

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/var/sds-nexus/backups/database}"
RETENTION_DAYS="${1:-30}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/sds_nexus_${DATE}.sql.gz"
LOG_FILE="/var/log/sds-nexus/backup.log"

# Database configuration (from environment or defaults)
DB_USER="${DB_USER:-sds_nexus_user}"
DB_NAME="${DB_NAME:-sds_nexus}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handler
error_exit() {
    log "ERROR: $1"
    exit 1
}

################################################################################
# Main Backup Process
################################################################################

log "==================== Database Backup Started ===================="

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR" || error_exit "Cannot create backup directory"

# Check if Docker is available
if ! command -v docker-compose &> /dev/null; then
    error_exit "docker-compose not found"
fi

# Check if database is accessible
if ! docker-compose exec -T postgres pg_isready -U "$DB_USER" &> /dev/null; then
    error_exit "Database is not accessible"
fi

# Get database size before backup
DB_SIZE=$(docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));" | tr -d ' ')
log "Database size: $DB_SIZE"

# Perform backup
log "Creating backup: $BACKUP_FILE"
if docker-compose exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup completed successfully: $BACKUP_SIZE"
else
    error_exit "Backup failed"
fi

# Verify backup integrity
log "Verifying backup integrity..."
if gunzip -t "$BACKUP_FILE" &> /dev/null; then
    log "Backup verification passed"
else
    error_exit "Backup verification failed"
fi

# Cleanup old backups
log "Cleaning up backups older than $RETENTION_DAYS days..."
DELETED_COUNT=$(find "$BACKUP_DIR" -name "sds_nexus_*.sql.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
if [[ $DELETED_COUNT -gt 0 ]]; then
    log "Deleted $DELETED_COUNT old backup(s)"
else
    log "No old backups to delete"
fi

# List current backups
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "sds_nexus_*.sql.gz" | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "Total backups: $BACKUP_COUNT (Total size: $TOTAL_SIZE)"

# Optional: Upload to remote storage (uncomment and configure as needed)
# log "Uploading to remote storage..."
# aws s3 cp "$BACKUP_FILE" s3://your-backup-bucket/sds-nexus/ || log "WARNING: Remote upload failed"

log "==================== Database Backup Completed ===================="

# Send success notification (optional)
# curl -X POST "https://your-monitoring-service/webhook" \
#   -H "Content-Type: application/json" \
#   -d "{\"status\": \"success\", \"backup\": \"$BACKUP_FILE\", \"size\": \"$BACKUP_SIZE\"}"

exit 0
