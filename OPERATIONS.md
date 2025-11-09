# Operations Guide

This guide covers operational tasks for the Mountaineers Activities Discord Publisher.

> **Note:** This project uses Cloud Functions 2nd gen, which are built on Cloud Run. Function invocation requires proper IAM permissions and OIDC tokens.

## Manual Function Invocation

All Cloud Functions are deployed with IAM authentication required. To invoke them manually, you need to include an identity token in your requests.

### Deployed Functions

- `searcher` - Search for new activities (triggered by Cloud Scheduler)
- `scraper` - Scrape activity details (triggered by Cloud Tasks)
- `publisher` - Publish to Discord (triggered by Cloud Tasks)
- `publishing-catchup` - Retry failed publications (triggered by Cloud Scheduler)

### Prerequisites

- Ensure your user account has the `Cloud Run Invoker` role for the function:
  ```bash
  gcloud run services add-iam-policy-binding searcher \
    --region=$GCP_REGION \
    --member="user:your-email@example.com" \
    --role="roles/run.invoker" \
    --platform=managed
  ```
- Have the `gcloud` CLI installed and authenticated

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

### Method 3: Impersonate the scheduler service account

```bash
# Get a token for the specific service account that Cloud Scheduler uses
TOKEN=$(gcloud auth print-identity-token \
  --impersonate-service-account=scheduler-invoker@${GCP_PROJECT}.iam.gserviceaccount.com)

# Get function URL
SEARCHER_URL=$(gcloud functions describe searcher \
  --region=$GCP_REGION \
  --gen2 \
  --format="value(serviceConfig.uri)")

# Invoke with scheduler service account token
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"start_index": 0, "activity_type": "Backcountry Skiing"}' \
  $SEARCHER_URL
```

This is useful for testing exactly how Cloud Scheduler will invoke the function.

## Monitoring and Debugging

### Check function logs

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

# Check both scheduler jobs
for job in search-scheduler publishing-catchup-scheduler; do
  echo "=== Status for $job ==="
  gcloud scheduler jobs describe $job \
    --location=$GCP_REGION \
    --format="yaml(status)"
  echo ""
done
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

# Check all queues
for queue in search-queue scrape-queue publish-queue; do
  echo "=== Queue: $queue ==="
  gcloud tasks queues describe $queue \
    --location=$GCP_REGION \
    --format="yaml(name, rateLimits, retryConfig, state)"
  echo ""
done
```

### Query Firestore data

```bash
# Count activities in the database
gcloud firestore databases documents list \
  --collection-ids=activities \
  --format="value(name)" | wc -l

# View bookkeeping status
gcloud firestore databases documents describe \
  projects/${GCP_PROJECT}/databases/(default)/documents/bookkeeping/status

# View a specific activity
gcloud firestore databases documents describe \
  projects/${GCP_PROJECT}/databases/(default)/documents/activities/ACTIVITY_ID
```

## Common Operations

### Trigger a full search manually

```bash
# Get function URL
SEARCHER_URL=$(gcloud functions describe searcher \
  --region=$GCP_REGION \
  --gen2 \
  --format="value(serviceConfig.uri)")

# Get a token
TOKEN=$(gcloud auth print-identity-token)

# Trigger the search (will process all pages)
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"start_index": 0, "activity_type": "Backcountry Skiing"}' \
  $SEARCHER_URL
```

### Retry failed publications

```bash
# Get function URL
PUBLISHING_CATCHUP_URL=$(gcloud functions describe publishing-catchup \
  --region=$GCP_REGION \
  --gen2 \
  --format="value(serviceConfig.uri)")

# Get a token
TOKEN=$(gcloud auth print-identity-token)

# Trigger the publishing catchup function
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  $PUBLISHING_CATCHUP_URL
```

### Force a scheduler job to run now (Recommended)

```bash
# Don't wait for the schedule - run immediately
gcloud scheduler jobs run search-scheduler \
  --location=$GCP_REGION

gcloud scheduler jobs run publishing-catchup-scheduler \
  --location=$GCP_REGION
```

## Troubleshooting

### 401 Unauthorized errors

**For manual invocations:**
- Verify you have the `Cloud Run Invoker` role
- Regenerate your identity token (they expire after 1 hour)
- Check that the function is deployed and accessible

**For Cloud Scheduler invocations:**
If you see errors like "The request was not authenticated" in function logs:

1. Run the fix script:
   ```bash
   ./fix-permissions.sh
   ```

2. Verify the scheduler service account has permissions:
   ```bash
   gcloud run services get-iam-policy searcher \
     --region=$GCP_REGION \
     --platform=managed \
     --filter="bindings.role:roles/run.invoker"
   ```

3. Check that the service account exists:
   ```bash
   gcloud iam service-accounts describe \
     scheduler-invoker@${GCP_PROJECT}.iam.gserviceaccount.com
   ```

4. Verify scheduler job is using OIDC authentication:
   ```bash
   gcloud scheduler jobs describe search-scheduler \
     --location=$GCP_REGION \
     --format="yaml(httpTarget.oidcToken)"
   ```

### 429 Rate Limit errors

Functions are configured to handle 429 responses gracefully and will back off. Check the bookkeeping collection for status:
- `Yellow: Backing off.` indicates the system is handling rate limits correctly
- These should resolve automatically after the backoff period

### No activities being published

1. Check the bookkeeping collection for error status:
   ```bash
   gcloud firestore databases documents describe \
     projects/${GCP_PROJECT}/databases/(default)/documents/bookkeeping/status
   ```

2. Verify the Discord bot token secret is set correctly:
   ```bash
   gcloud secrets describe discord-bot-token
   gcloud secrets versions access latest --secret=discord-bot-token
   ```

3. Check function logs for errors:
   ```bash
   gcloud functions logs read publisher --region=$GCP_REGION --gen2 --limit=50
   ```

4. Manually trigger the publishing catchup function:
   ```bash
   gcloud scheduler jobs run publishing-catchup-scheduler --location=$GCP_REGION
   ```

5. Verify the Discord channel ID environment variable is set

### Functions not running on schedule

1. Verify Cloud Scheduler jobs exist and are enabled:
   ```bash
   gcloud scheduler jobs list --location=$GCP_REGION
   ```

2. Check that the scheduler service account has the `Cloud Run Invoker` role:
   ```bash
   gcloud run services get-iam-policy searcher \
     --region=$GCP_REGION \
     --platform=managed
   ```

3. Review scheduler job execution history:
   ```bash
   gcloud scheduler jobs describe search-scheduler \
     --location=$GCP_REGION \
     --format="yaml(status)"
   ```

4. Check function logs for errors during scheduled runs:
   ```bash
   gcloud functions logs read searcher --region=$GCP_REGION --gen2 --limit=50
   ```
