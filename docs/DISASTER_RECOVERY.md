# OnePay Disaster Recovery Procedures

**Version:** 1.0  
**Last Updated:** April 10, 2026  
**Owner:** Operations Team

---

## Overview

This document outlines the procedures for recovering OnePay services from various disaster scenarios. All operations staff should be familiar with these procedures and participate in quarterly DR drills.

---

## Backup Strategy

### Database Backups

- **Frequency:** Daily full backups at 2 AM UTC
- **Retention Policy:**
  - 7 daily backups
  - 4 weekly backups
  - 12 monthly backups
- **Storage:** S3 with encryption at rest
- **Backup Tool:** `pg_dump` for PostgreSQL
- **Verification:** Automated verification runs daily at 3 AM UTC via `scripts/verify_backup.py`

### Application Configuration

- **Frequency:** Nightly snapshots of configuration files
- **Storage:** Encrypted S3 bucket
- **Retention:** 30 days

### Static Assets

- **Frequency:** Weekly backups
- **Storage:** CDN with origin failover
- **Retention:** 90 days

---

## Restore Procedures

### Database Restore

#### Prerequisites
- Access to backup storage (S3)
- Database credentials
- Target database server ready

#### Steps

1. **Stop Application Services**
   ```bash
   # Stop the application
   sudo systemctl stop onepay
   # Or if using Docker
   docker-compose down
   ```

2. **Download Latest Backup**
   ```bash
   # List available backups
   aws s3 ls s3://onepay-backups/database/
   
   # Download the latest backup
   aws s3 cp s3://onepay-backups/database/latest.dump /tmp/latest.dump
   ```

3. **Restore from Backup**
   ```bash
   # Restore to database
   pg_restore -d onepay -U onepay_user -h localhost /tmp/latest.dump
   
   # Or with connection string
   PGPASSWORD=your_password pg_restore -d onepay /tmp/latest.dump
   ```

4. **Verify Data Integrity**
   ```bash
   # Run verification script
   python scripts/verify_backup.py
   ```

5. **Run Database Migrations (if needed)**
   ```bash
   # Apply any pending migrations
   alembic upgrade head
   ```

6. **Start Application Services**
   ```bash
   # Start the application
   sudo systemctl start onepay
   # Or if using Docker
   docker-compose up -d
   ```

7. **Verify Application Health**
   ```bash
   # Check health endpoint
   curl https://api.onepay.com/health
   
   # Check metrics
   curl https://api.onepay.com/metrics
   ```

### Application Restore

#### Prerequisites
- Docker image repository access
- Configuration backups
- Environment variables

#### Steps

1. **Deploy from Docker Image**
   ```bash
   # Pull the latest image
   docker pull onepay/app:latest
   
   # Or deploy to production
   kubectl apply -f k8s/production/
   ```

2. **Restore Configuration**
   ```bash
   # Download configuration backup
   aws s3 cp s3://onepay-backups/config/.env.production /tmp/.env.production
   
   # Copy to application directory
   cp /tmp/.env.production /opt/onepay/.env.production
   ```

3. **Restore Secrets** (if using secret manager)
   ```bash
   # Restore from AWS Secrets Manager
   aws secretsmanager restore-secret --secret-id onepay/production
   ```

4. **Start Services**
   ```bash
   # Start application
   sudo systemctl start onepay
   ```

5. **Verify Health Checks**
   ```bash
   # Monitor logs
   tail -f /var/log/onepay/app.log
   
   # Check health endpoint
   curl https://api.onepay.com/health
   ```

---

## Failover Procedures

### Database Failover

#### Scenario: Primary Database Failure

**Prerequisites:**
- Standby database configured and in replication
- DNS access for updating records

**Steps:**

1. **Verify Standby Health**
   ```bash
   # Check replication status on standby
   psql -h standby-db -U onepay_user -d onepay -c "SELECT pg_is_in_recovery();"
   
   # Check replication lag
   psql -h standby-db -U onepay_user -d onepay -c "SELECT now() - pg_last_xact_replay_timestamp();"
   ```

2. **Promote Standby to Primary**
   ```bash
   # Connect to standby and promote
   psql -h standby-db -U onepay_user -d onepay -c "SELECT pg_promote();"
   ```

3. **Update Application Connection Strings**
   ```bash
   # Update environment variable
   export DATABASE_URL="postgresql://onepay_user:password@standby-db:5432/onepay"
   
   # Or update in config management system
   ```

4. **Update DNS Records** (if using DNS-based routing)
   ```bash
   # Update DNS to point to standby
   # This depends on your DNS provider
   ```

5. **Restart Application Services**
   ```bash
   # Restart to pick up new connection string
   sudo systemctl restart onepay
   ```

6. **Verify Replication** (if setting up new standby)
   ```bash
   # Set up replication from new primary to new standby
   # Follow standard PostgreSQL replication setup
   ```

### Application Failover

#### Scenario: Application Server Failure

**Prerequisites:**
- Multiple application servers behind load balancer
- Health checks configured

**Steps:**

1. **Verify Load Balancer Health**
   ```bash
   # Check which servers are healthy
   # This depends on your load balancer (AWS ALB, HAProxy, etc.)
   ```

2. **Remove Failed Server from Rotation**
   ```bash
   # Deregister from load balancer
   aws elbv2 deregister-targets --target-group-arn <tg-arn> --targets Id=<instance-id>
   ```

3. **Deploy New Instance**
   ```bash
   # Launch new instance from AMI
   aws ec2 run-instances --image-id <ami-id> --instance-type t3.medium
   
   # Or deploy new container
   kubectl rollout restart deployment/onepay-app
   ```

4. **Verify New Instance Health**
   ```bash
   # Wait for health checks to pass
   # This may take several minutes
   ```

5. **Add New Instance to Rotation**
   ```bash
   # Register with load balancer
   aws elbv2 register-targets --target-group-arn <tg-arn> --targets Id=<instance-id>
   ```

---

## Recovery Time Objectives (RTO) and Recovery Point Objectives (RPO)

| Component | RTO | RPO |
|-----------|-----|-----|
| Database | 4 hours | 24 hours |
| Application | 1 hour | 0 hours (stateless) |
| Configuration | 30 minutes | 24 hours |
| Static Assets | 2 hours | 7 days |

---

## Testing Procedures

### Quarterly DR Drills

1. **Schedule:** First Sunday of each quarter
2. **Scope:** Full disaster recovery simulation
3. **Participants:** Operations team, DevOps team
4. **Procedure:**
   - Simulate primary database failure
   - Execute failover procedures
   - Verify application functionality
   - Document any issues
   - Update procedures based on findings

### Monthly Backup Verification

- Automated verification runs daily via `scripts/verify_backup.py`
- Monthly manual verification by operations team
- Verify backup restoration to test environment
- Document results in operations log

---

## Contact Information

### Primary Contacts

| Role | Name | Email | Phone |
|------|------|-------|-------|
| Operations Lead | - | ops@onepay.com | - |
| Database Admin | - | dba@onepay.com | - |
| DevOps Engineer | - | devops@onepay.com | - |

### Emergency Contacts

| Severity | Contact Method |
|----------|---------------|
| Critical (P0) | PagerDuty + SMS |
| High (P1) | Slack #oncall + Email |
| Medium (P2) | Slack #ops |
| Low (P3) | Email |

### External Vendors

| Service | Contact |
|---------|---------|
| AWS Support | AWS Console |
| Database Provider | Vendor Support Portal |
| DNS Provider | Provider Dashboard |

---

## Incident Response Checklist

### During Incident

- [ ] Assess severity and impact
- [ ] Notify relevant team members
- [ ] Activate incident response channel
- [ ] Begin documentation
- [ ] Execute recovery procedures
- [ ] Communicate with stakeholders

### Post-Incident

- [ ] Conduct post-mortem meeting
- [ ] Document root cause
- [ ] Create action items
- [ ] Update procedures if needed
- [ ] Share lessons learned

---

## Appendix

### Useful Commands

```bash
# Check database size
psql -d onepay -c "SELECT pg_size_pretty(pg_database_size('onepay'));"

# Check table sizes
psql -d onepay -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Check active connections
psql -d onepay -c "SELECT count(*) FROM pg_stat_activity;"

# Check replication lag
psql -d onepay -c "SELECT now() - pg_last_xact_replay_timestamp();"

# List recent backups
aws s3 ls s3://onepay-backups/database/ --recursive | sort

# Check application logs
tail -f /var/log/onepay/app.log

# Check service status
sudo systemctl status onepay
```

### Related Documentation

- [Backup Policy](BACKUP_POLICY.md)
- [Incident Response Plan](INCIDENT_RESPONSE.md)
- [Security Procedures](SECURITY_PROCEDURES.md)
- [Monitoring Guide](MONITORING_GUIDE.md)

---

**Document History**

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | April 10, 2026 | Initial document | Operations Team |
