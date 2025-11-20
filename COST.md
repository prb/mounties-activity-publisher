# Cost & Billing Expectations

## Objective
This project is architected to run within the **Google Cloud Free Tier** or at negligible cost (cents per month). All architectural decisions and infrastructure changes must align with this goal.

## Free Tier Constraints
To maintain zero/low cost, the project adheres to the following limits (as of 2025):

### Compute (Cloud Functions / Cloud Run)
- **Constraint**: Keep invocations and compute time low.
- **Free Tier Limit**: 
    - 2 million requests/month
    - 360,000 GB-seconds of memory, 180,000 vCPU-seconds
- **Current Usage**: The publisher runs infrequently (scheduled), well below these limits.

### Database (Firestore)
- **Constraint**: Minimize unnecessary reads/writes.
- **Free Tier Limit**:
    - 1 GB storage
    - 50,000 reads/day
    - 20,000 writes/day
- **Current Usage**: Activity volume is low.

### Observability (Logging & Monitoring)
- **Constraint**: Use Log-based alerts (free) rather than custom metrics (paid).
- **Free Tier Limit**:
    - **Logging**: 50 GB logs ingestion/month (Free).
    - **Alerting**: Log-based alerts are free (no separate charge from ingestion).
    - **Notification Channels**: Email notifications are free.

## Review Policy
Any Pull Request that modifies `infrastructure/` or changes data access patterns must be reviewed for potential cost impacts.
- **Avoid**: High-frequency polling loops, large log volumes, or expensive resources like Cloud SQL or Load Balancers.
- **Prefer**: Event-driven architecture, Firestore, and standard Cloud Logging.

## Budget Alerts
(Optional but Recommended)
Set up a Google Cloud Budget Alert for **$1.00/month** to receive immediate notification if costs spike unexpectedly.
