# Operations Guide

This guide covers operational tasks for the Mountaineers Activities Discord Publisher.

> **Note:** This project uses Cloud Functions 2nd gen, which are built on Cloud Run. Function invocation requires proper IAM permissions and OIDC tokens.

## Related Documents
- [Architecture Specification](spec.md)
- [Cost & Billing Expectations](COST.md)

## Deployment

This project uses **Pulumi** for infrastructure management.

### Prerequisites
- [Pulumi CLI](https://www.pulumi.com/docs/install/)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- Python 3.11+

### Required Secrets
Before deploying, ensure the following files exist in the project root:
- `DISCORD_CHANNEL_ID.secret`: Contains the Discord Channel ID.
- `DISCORD_BOT_TOKEN.secret`: Contains the Discord Bot Token.

### Deploying Changes
1. Navigate to the infrastructure directory:
   ```bash
   cd infrastructure
   ```
2. Preview changes:
   ```bash
   pulumi preview
   ```
3. Deploy:
   ```bash
   pulumi up
   ```

## Manual Function Invocation

All Cloud Functions are deployed with IAM authentication required. To invoke them manually, you need to include an identity token in your requests.

### Deployed Functions

- `searcher` - Search for new activities (triggered by Cloud Scheduler)
- `scraper` - Scrape activity details (triggered by Cloud Tasks)
- `publisher` - Publish to Discord (triggered by Cloud Tasks)
- `publishing-catchup` - Retry failed publications (triggered by Cloud Scheduler)

### Prerequisites

- Ensure your user account has the `Cloud Run Invoker` role for the function.
- Have the `gcloud` CLI installed and authenticated.

### Method 1: Using curl with identity token (Recommended)

```bash
# Set your environment variables
export GCP_PROJECT=your-project-id
export GCP_REGION=us-central1

# Get function URLs
SEARCHER_URL=$(gcloud functions describe searcher \
  --region=$GCP_REGION \
  --gen2 \
  --format="value(serviceConfig.uri)")

PUBLISHING_CATCHUP_URL=$(gcloud functions describe publishing-catchup \
  --region=$GCP_REGION \
  --gen2 \
  --format="value(serviceConfig.uri)")

# Get an identity token for your authenticated user
TOKEN=$(gcloud auth print-identity-token)

# Invoke the searcher function
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"start_index": 0, "activity_type": "Backcountry Skiing"}' \
  $SEARCHER_URL

# Invoke the publishing catchup function
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  $PUBLISHING_CATCHUP_URL
```

**Note:** Identity tokens expire after 1 hour. If you get a 401 error, regenerate the token.

### Method 2: Using Cloud Scheduler to trigger

```bash
# Manually trigger the scheduled search job
gcloud scheduler jobs run search-scheduler \
  --location=$GCP_REGION

# Manually trigger the publishing catchup job
gcloud scheduler jobs run publishing-catchup-scheduler \
  --location=$GCP_REGION
```

This is the recommended way to test the full scheduled workflow, as it uses the same authentication method (OIDC) that automatic runs use.

## Monitoring and Debugging

### Cloud Logging (Stackdriver)

This project uses native Google Cloud Logging. You can view logs in the [Google Cloud Console](https://console.cloud.google.com/logs).

```bash
# View recent logs for a specific function
gcloud functions logs read searcher \
  --region=$GCP_REGION \
  --gen2 \
  --limit=50

# Follow logs in real-time
gcloud functions logs read searcher \
  --region=$GCP_REGION \
  --gen2 \
  --follow

# View logs for all functions
for func in searcher scraper publisher publishing-catchup; do
  echo "=== Logs for $func ==="
  gcloud functions logs read $func \
    --region=$GCP_REGION \
    --gen2 \
    --limit=10
  echo ""
done
```

### Check Cloud Scheduler status

```bash
# List all scheduler jobs
gcloud scheduler jobs list --location=$GCP_REGION

# View details of a specific job
gcloud scheduler jobs describe search-scheduler \
  --location=$GCP_REGION

# View recent executions
gcloud scheduler jobs describe search-scheduler \
  --location=$GCP_REGION \
  --format="table(status.lastAttemptTime, status.code)"
```

### Check Cloud Tasks queues

```bash
# List all queues
gcloud tasks queues list --location=$GCP_REGION

# View queue details and stats
gcloud tasks queues describe search-queue \
  --location=$GCP_REGION

# List pending tasks in a queue
gcloud tasks list --queue=search-queue \
  --location=$GCP_REGION
```

### Query Firestore data

```bash
# Count activities in the database
gcloud firestore databases documents list \
  --collection-ids=activities \
  --format="value(name)" | wc -l

# View a specific activity
gcloud firestore databases documents describe \
  projects/${GCP_PROJECT}/databases/(default)/documents/activities/ACTIVITY_ID
```

## Troubleshooting

### 401 Unauthorized errors

**For manual invocations:**
- Verify you have the `Cloud Run Invoker` role
- Regenerate your identity token (they expire after 1 hour)
- Check that the function is deployed and accessible

**For Cloud Scheduler invocations:**
If you see errors like "The request was not authenticated" in function logs:

1. Verify the scheduler service account has permissions:
   ```bash
   gcloud run services get-iam-policy searcher \
     --region=$GCP_REGION \
     --platform=managed \
     --filter="bindings.role:roles/run.invoker"
   ```

2. Check that the service account exists:
   ```bash
   gcloud iam service-accounts describe \
     scheduler-invoker@${GCP_PROJECT}.iam.gserviceaccount.com
   ```

3. Verify scheduler job is using OIDC authentication:
   ```bash
   gcloud scheduler jobs describe search-scheduler \
     --location=$GCP_REGION \
     --format="yaml(httpTarget.oidcToken)"
   ```

### 429 Rate Limit errors

Functions are configured to handle 429 responses gracefully and will back off. Check the Cloud Logs for "Backing off" messages.

### No activities being published

1. Check Cloud Logs for errors:
   ```bash
   gcloud functions logs read publisher --region=$GCP_REGION --gen2 --limit=50
   ```

2. Verify the Discord bot token secret is set correctly:
   ```bash
   gcloud secrets describe discord-bot-token
   gcloud secrets versions access latest --secret=discord-bot-token
   ```

3. Manually trigger the publishing catchup function:
   ```bash
   gcloud scheduler jobs run publishing-catchup-scheduler --location=$GCP_REGION
   ```

4. Verify the Discord channel ID environment variable is set.

### Functions not running on schedule

1. Verify Cloud Scheduler jobs exist and are enabled:
   ```bash
   gcloud scheduler jobs list --location=$GCP_REGION
   ```

2. Check that the scheduler service account has the `Cloud Run Invoker` role.

3. Review scheduler job execution history:
   ```bash
   gcloud scheduler jobs describe search-scheduler \
     --location=$GCP_REGION \
     --format="yaml(status)"
   ```

## Queue Management

The system includes queue management functions to handle scenarios with bad or undesirable data.

### Processing Control

Processing can be paused and resumed using Firestore-based configuration:

```bash
# Pause processing (stops searcher and scraper from processing new tasks)
gcloud functions call pause-processing \
  --region=$GCP_REGION \
  --gen2

# Resume processing
gcloud functions call resume-processing \
  --region=$GCP_REGION \
  --gen2

# Drain queues (purge all pending tasks)
gcloud functions call drain-queues \
  --region=$GCP_REGION \
  --gen2
```

### Recommended Workflow for Data Issues

When bad or undesirable data enters the system:

1. **Pause processing** to prevent new tasks from being processed:
   ```bash
   gcloud functions call pause-processing --region=$GCP_REGION --gen2
   ```

2. **Drain queues** to clear all pending tasks:
   ```bash
   gcloud functions call drain-queues --region=$GCP_REGION --gen2
   ```

3. **Fix data issues** in Firestore manually or via scripts

4. **Resume processing** to restart the pipeline:
   ```bash
   gcloud functions call resume-processing --region=$GCP_REGION --gen2
   ```

### Manual Flag Control

You can also manually control the processing flag in Firestore:

```bash
# View current processing state
gcloud firestore databases documents describe \
  projects/${GCP_PROJECT}/databases/(default)/documents/system/config

# Update processing flag (using Firestore console or gcloud)
# Collection: system
# Document: config
# Field: processing_enabled (boolean)
```

When processing is paused, searcher and scraper functions will return:
```json
{
  "status": "skipped",
  "reason": "Processing is currently disabled"
}
```
