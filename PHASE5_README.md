# Phase 5: Cloud Tasks Configuration & Deployment

This phase covers deploying the application to Google Cloud Platform with Cloud Functions and Cloud Tasks.

## Overview

Phase 5 makes the application production-ready by:
- Configuring Cloud Tasks queues with retry policies and rate limits
- Creating Cloud Functions entry points
- Setting up deployment configuration
- Providing automated deployment scripts

## Files Created

```
mounties-activities-discord-publisher/
├── main.py              # Cloud Functions entry points
├── requirements.txt     # Production dependencies
├── queues.yaml          # Cloud Tasks queue configuration
├── deploy.sh            # Automated deployment script
└── .gcloudignore        # Files to exclude from deployment
```

## Prerequisites

### 1. Google Cloud Platform Setup

```bash
# Install gcloud CLI
# macOS
brew install google-cloud-sdk

# Or download from: https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Set your project
export GCP_PROJECT=your-project-id
gcloud config set project $GCP_PROJECT
```

### 2. Enable Required APIs

```bash
# Enable Cloud Functions, Cloud Tasks, Firestore, and Cloud Scheduler
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudtasks.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### 3. Set Up Firebase/Firestore

```bash
# Create Firestore database (if not already created)
gcloud firestore databases create --location=us-central

# Or use Firebase Console: https://console.firebase.google.com/
```

### 4. Store Discord Bot Token in Secret Manager

```bash
# Create secret for Discord bot token
# Replace "your_discord_bot_token_here" with your actual Discord bot token
echo -n "your_discord_bot_token_here" | gcloud secrets create discord-bot-token --data-file=-

# Verify secret was created
gcloud secrets describe discord-bot-token

# Grant the Cloud Functions service account access to the secret
# Note: The deployment script now does this automatically, but you can also do it manually:
PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding discord-bot-token \
    --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

**Important Notes:**
- Use `echo -n` (the `-n` prevents adding a trailing newline)
- Replace `your_discord_bot_token_here` with your actual bot token from Discord Developer Portal
- The deployment script automatically grants secret access, so you typically don't need to run the last command manually

### 5. Set Environment Variables

```bash
# Required
export GCP_PROJECT=your-project-id
export GCP_REGION=us-central1
export DISCORD_CHANNEL_ID=your_discord_channel_id

# Optional (defaults to "discord-bot-token")
export DISCORD_BOT_TOKEN_SECRET=discord-bot-token
```

## Cloud Tasks Queue Configuration

The `queues.yaml` file defines three queues with different rate limits and retry policies:

### Search Queue
- **Rate**: 10 requests/minute (~1 every 6 seconds)
- **Concurrency**: 1 (sequential processing)
- **Retries**: Up to 3 attempts
- **Backoff**: 10s to 300s
- **Purpose**: Fetch and process search results

### Scrape Queue
- **Rate**: 30 requests/minute (~1 every 2 seconds)
- **Concurrency**: 5 (parallel processing)
- **Retries**: Up to 5 attempts
- **Backoff**: 5s to 120s
- **Purpose**: Fetch and parse activity detail pages

### Publish Queue
- **Rate**: 5 requests/minute (~1 every 12 seconds)
- **Concurrency**: 1 (sequential to respect Discord rate limits)
- **Retries**: Up to 3 attempts
- **Backoff**: 2s to 60s
- **Purpose**: Publish activities to Discord

These conservative rate limits ensure:
- We're a good citizen when scraping the Mountaineers website
- We don't hit Discord API rate limits
- We stay well within Google Cloud free tier

## Deployment

### Automated Deployment

The easiest way to deploy is using the provided script:

```bash
# Make sure environment variables are set
export GCP_PROJECT=your-project-id
export DISCORD_CHANNEL_ID=your_channel_id

# Run deployment script
./deploy.sh
```

The script will:
1. Deploy all three Cloud Functions (searcher, scraper, publisher)
2. Grant secret access to the Cloud Functions service account
3. Create Cloud Tasks queues
4. Configure function URLs for task enqueueing
5. Set environment variables and secrets

### Manual Deployment

If you prefer to deploy manually:

#### 1. Deploy Searcher Function

```bash
gcloud functions deploy searcher \
    --gen2 \
    --runtime=python313 \
    --region=us-central1 \
    --source=. \
    --entry-point=searcher \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT=$GCP_PROJECT,GCP_LOCATION=us-central1" \
    --timeout=540s \
    --memory=512MB
```

#### 2. Deploy Scraper Function

```bash
gcloud functions deploy scraper \
    --gen2 \
    --runtime=python313 \
    --region=us-central1 \
    --source=. \
    --entry-point=scraper \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT=$GCP_PROJECT,GCP_LOCATION=us-central1" \
    --timeout=540s \
    --memory=512MB
```

#### 3. Deploy Publisher Function

```bash
gcloud functions deploy publisher \
    --gen2 \
    --runtime=python313 \
    --region=us-central1 \
    --source=. \
    --entry-point=publisher \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT=$GCP_PROJECT,GCP_LOCATION=us-central1,DISCORD_CHANNEL_ID=$DISCORD_CHANNEL_ID" \
    --set-secrets="DISCORD_BOT_TOKEN=discord-bot-token:latest" \
    --timeout=540s \
    --memory=256MB
```

#### 4. Create Cloud Tasks Queues

```bash
gcloud tasks queues create search-queue --location=us-central1
gcloud tasks queues create scrape-queue --location=us-central1
gcloud tasks queues create publish-queue --location=us-central1
```

#### 5. Get Function URLs

```bash
SEARCHER_URL=$(gcloud functions describe searcher --region=us-central1 --gen2 --format="value(serviceConfig.uri)")
SCRAPER_URL=$(gcloud functions describe scraper --region=us-central1 --gen2 --format="value(serviceConfig.uri)")
PUBLISHER_URL=$(gcloud functions describe publisher --region=us-central1 --gen2 --format="value(serviceConfig.uri)")

echo "Searcher: $SEARCHER_URL"
echo "Scraper: $SCRAPER_URL"
echo "Publisher: $PUBLISHER_URL"
```

#### 6. Update Functions with URLs

```bash
# Update searcher with URLs it needs
gcloud functions deploy searcher \
    --gen2 \
    --update-env-vars="SCRAPE_FUNCTION_URL=$SCRAPER_URL,SEARCH_FUNCTION_URL=$SEARCHER_URL"

# Update scraper with publisher URL
gcloud functions deploy scraper \
    --gen2 \
    --update-env-vars="PUBLISH_FUNCTION_URL=$PUBLISHER_URL"
```

## Testing Deployment

### 1. Test Searcher Function

```bash
# Get the searcher URL
SEARCHER_URL=$(gcloud functions describe searcher --region=us-central1 --gen2 --format="value(serviceConfig.uri)")

# Trigger manually
curl -X POST "$SEARCHER_URL" \
    -H "Content-Type: application/json" \
    -d '{"start_index": 0, "activity_type": "Backcountry Skiing"}'
```

Expected response:
```json
{
  "status": "success",
  "activities_found": 14,
  "has_next_page": false
}
```

### 2. Check Cloud Tasks Queues

```bash
# List tasks in scrape queue
gcloud tasks queues describe scrape-queue --location=us-central1

# View task statistics
gcloud tasks queues list --location=us-central1
```

### 3. Check Firestore

```bash
# List activities in Firestore (requires firestore CLI or console)
# Or use Firebase Console: https://console.firebase.google.com/
```

### 4. Check Discord Channel

Activities should appear in your Discord channel!

## Monitoring and Logs

### View Function Logs

```bash
# Searcher logs
gcloud functions logs read searcher --region=us-central1 --limit=50

# Scraper logs
gcloud functions logs read scraper --region=us-central1 --limit=50

# Publisher logs
gcloud functions logs read publisher --region=us-central1 --limit=50
```

### View Logs in Cloud Console

Navigate to: https://console.cloud.google.com/logs

Filter by:
- `resource.type="cloud_function"`
- `resource.labels.function_name="searcher"` (or "scraper" or "publisher")

### Monitor Cloud Tasks

```bash
# View queue stats
gcloud tasks queues describe search-queue --location=us-central1
gcloud tasks queues describe scrape-queue --location=us-central1
gcloud tasks queues describe publish-queue --location=us-central1

# List tasks
gcloud tasks list --queue=scrape-queue --location=us-central1
```

## Cost Estimation

With the free tier, you should be able to run this application at **zero cost**:

### Free Tier Limits (per month)
- **Cloud Functions**: 2M invocations, 400K GB-seconds, 200K GHz-seconds
- **Cloud Tasks**: 1M operations
- **Firestore**: 1 GB storage, 50K reads, 20K writes, 20K deletes
- **Cloud Scheduler**: 3 jobs

### Expected Usage (polling every 60 minutes)
- **Searcher**: ~720 invocations/month (1 per hour)
- **Scraper**: ~10,000 invocations/month (assuming ~14 activities per poll)
- **Publisher**: ~10,000 invocations/month
- **Cloud Tasks**: ~20,000 operations/month
- **Firestore**: Minimal reads/writes

**Total cost: $0** (well within free tier)

## Troubleshooting

### Function Deployment Fails

```bash
# Check deployment status
gcloud functions describe searcher --region=us-central1 --gen2

# View build logs
gcloud functions logs read searcher --region=us-central1
```

### Tasks Not Being Created

Check that function URLs are set correctly:
```bash
gcloud functions describe searcher --region=us-central1 --gen2 --format="value(serviceConfig.environmentVariables)"
```

### Discord Messages Not Appearing

1. Check Discord bot token is correct in Secret Manager
2. Verify channel ID is correct
3. Check publisher function logs for errors
4. Verify bot has permissions in Discord channel

### Firestore Permission Errors

Ensure Cloud Functions service account has Firestore permissions:
```bash
# Get service account email
SERVICE_ACCOUNT=$(gcloud projects describe $GCP_PROJECT --format="value(projectNumber)")@cloudbuild.gserviceaccount.com

# Grant Firestore permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/datastore.user"
```

## Updating Deployment

To update the code after making changes:

```bash
# Option 1: Run deploy script again
./deploy.sh

# Option 2: Deploy specific function
gcloud functions deploy searcher \
    --gen2 \
    --runtime=python313 \
    --region=us-central1 \
    --source=.
```

## Security Notes

- **Bot Token**: Stored in Secret Manager (encrypted)
- **Function URLs**: Currently allow unauthenticated access
  - Consider adding authentication for production
  - Use Cloud Tasks with service accounts for better security
- **Firestore**: Use security rules to restrict access
- **Environment Variables**: Channel ID is not sensitive, safe to store as env var

## Next Steps

Phase 6 will add:
- **Cloud Scheduler**: Automated periodic polling
- **Firebase Remote Config**: Dynamic configuration
- **Activity TTL Cleanup**: Remove old activities from Firestore
- **Full automation**: End-to-end hands-off operation
