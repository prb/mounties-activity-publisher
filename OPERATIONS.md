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

The Pulumi program (`infrastructure/`) uses a **project-local virtualenv**
(`infrastructure/venv`, gitignored) declared via `runtime.options.virtualenv` in
`Pulumi.yaml`. Provider versions are pinned in `infrastructure/requirements.txt`
(pulumi-gcp 9.x). Create/refresh the venv once with:
```bash
cd infrastructure && pulumi install   # or: uv venv venv && uv pip install -r requirements.txt
```

### Authentication and stack
- **Backend:** Pulumi state lives in a GCS bucket and is read via **Application
  Default Credentials**. If a Pulumi command fails with
  `oauth2: "invalid_grant"` / `Bad Request` when reading the state bucket, your
  ADC token has expired — refresh it with `gcloud auth application-default login`
  (this is separate from `gcloud auth login`).
- **Passphrase:** the `prod` stack encrypts config/secrets with a passphrase.
  `pulumi preview`/`up` require `PULUMI_CONFIG_PASSPHRASE` (or
  `PULUMI_CONFIG_PASSPHRASE_FILE`) to be set in the environment.
- **Target:** the deployed stack is `prod` (project `backcountry-ski-activity-feed`,
  region `us-central1`). Note this differs from a typical personal default
  `gcloud config` project, so pass `--project=backcountry-ski-activity-feed`
  explicitly to `gcloud` commands.

### Required Secrets
Before deploying, ensure the following files exist in the project root:
- `DISCORD_CHANNEL_ID.secret`: Contains the Discord Channel ID.
- `DISCORD_BOT_TOKEN.secret`: Contains the Discord Bot Token.

### Deploying Changes
1. Navigate to the infrastructure directory:
   ```bash
   cd infrastructure
   ```
2. Set the stack passphrase (see above):
   ```bash
   export PULUMI_CONFIG_PASSPHRASE='...'
   ```
3. Preview changes and review the plan — a provider-version bump can show many
   `~ update [+deletionPolicy]` lines, which are cosmetic (a provider default
   recorded into state), not real infrastructure changes:
   ```bash
   pulumi preview --stack prod
   ```
4. Deploy:
   ```bash
   pulumi up --stack prod
   ```

## Manual Function Invocation

All Cloud Functions are deployed with IAM authentication required. To invoke them manually, you need to include an identity token in your requests.

### Deployed Functions

- `searcher` - Single-pass: build activities from the approved listing and enqueue publish tasks (triggered by Cloud Scheduler). See issue #31.
- `scraper` - **Dormant** (issue #31): detail pages are Cloudflare-protected, so nothing enqueues scrape tasks. Retained for fallback / manual reprocessing.
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

### Seasonal Pause (off-season)

Backcountry-ski activities are seasonal, so the pipeline is normally **held
paused during the off-season** and resumed for ski season. A full pause is two
steps — the processing flag *and* the hourly scheduler:

```bash
# Pause: flag off + stop the hourly searcher trigger
gcloud functions call pause-processing --gen2 --region=us-central1 --project=backcountry-ski-activity-feed
gcloud scheduler jobs pause search-scheduler --location=us-central1 --project=backcountry-ski-activity-feed

# Resume for ski season
gcloud functions call resume-processing --gen2 --region=us-central1 --project=backcountry-ski-activity-feed
gcloud scheduler jobs resume search-scheduler --location=us-central1 --project=backcountry-ski-activity-feed
```

Notes:
- The `processing_enabled` flag is the real gate: even if `search-scheduler`
  fires, a paused searcher/scraper returns `skipped`. Pausing the scheduler just
  avoids pointless hourly invocations.
- The **publisher is not gated** by the flag (so catchup can always deliver).
  With processing paused no new activities are created, so nothing is published;
  to fully quiesce you may also `gcloud scheduler jobs pause publishing-catchup-scheduler`.
- Verify: `gcloud scheduler jobs describe search-scheduler --location=us-central1 --project=backcountry-ski-activity-feed --format='value(state)'`
  should report `PAUSED`, and a direct `searcher` invocation should return
  `{"status":"skipped"}`.

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
