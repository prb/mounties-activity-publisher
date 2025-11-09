#!/bin/bash

# Deployment script for Mountaineers Activities Discord Publisher
# This script deploys Cloud Functions, creates Cloud Tasks queues, and sets up Cloud Scheduler
#
# IMPORTANT: This project uses Cloud Functions 2nd gen (built on Cloud Run)
# - All functions must be deployed with --gen2 flag
# - IAM permissions use 'gcloud run services' commands, not 'gcloud functions'
# - OIDC authentication is required for Cloud Scheduler

set -e  # Exit on error

# Configuration - set these before running
PROJECT_ID="${GCP_PROJECT:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
DISCORD_BOT_TOKEN_SECRET="${DISCORD_BOT_TOKEN_SECRET:-discord-bot-token}"
DISCORD_CHANNEL_ID="${DISCORD_CHANNEL_ID:-your-channel-id}"
DEPLOY_ENV="${DEPLOY_ENV:-prod}"
SCHEDULER_SERVICE_ACCOUNT="scheduler-invoker@${PROJECT_ID}.iam.gserviceaccount.com"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Mountaineers Activities Discord Publisher Deployment ===${NC}"
echo ""
echo -e "${YELLOW}Environment: ${DEPLOY_ENV}${NC}"
echo -e "${YELLOW}Project: ${PROJECT_ID}${NC}"
echo -e "${YELLOW}Region: ${REGION}${NC}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if project ID is set
if [ "$PROJECT_ID" = "your-project-id" ]; then
    echo -e "${RED}Error: GCP_PROJECT environment variable not set${NC}"
    echo "Set it with: export GCP_PROJECT=your-project-id"
    exit 1
fi

# Set the project
echo -e "${YELLOW}Setting GCP project to: $PROJECT_ID${NC}"
gcloud config set project "$PROJECT_ID"

# Get current Git SHA for version tracking
if git rev-parse HEAD &> /dev/null; then
    GIT_SHA=$(git rev-parse --short HEAD)
    echo -e "${YELLOW}Deploying version: $GIT_SHA${NC}"
else
    GIT_SHA="unknown"
    echo -e "${YELLOW}Warning: Not a git repository, version will be 'unknown'${NC}"
fi

echo ""
echo -e "${GREEN}Step 0: Enabling required APIs${NC}"
echo ""

# Enable all required APIs
echo -e "${YELLOW}Enabling Cloud Functions API...${NC}"
gcloud services enable cloudfunctions.googleapis.com --quiet

echo -e "${YELLOW}Enabling Cloud Build API...${NC}"
gcloud services enable cloudbuild.googleapis.com --quiet

echo -e "${YELLOW}Enabling Cloud Tasks API...${NC}"
gcloud services enable cloudtasks.googleapis.com --quiet

echo -e "${YELLOW}Enabling Firestore API...${NC}"
gcloud services enable firestore.googleapis.com --quiet

echo -e "${YELLOW}Enabling Secret Manager API...${NC}"
gcloud services enable secretmanager.googleapis.com --quiet

echo -e "${YELLOW}Enabling Cloud Run API...${NC}"
gcloud services enable run.googleapis.com --quiet

echo -e "${YELLOW}Enabling Artifact Registry API...${NC}"
gcloud services enable artifactregistry.googleapis.com --quiet

echo -e "${YELLOW}Enabling Cloud Scheduler API...${NC}"
gcloud services enable cloudscheduler.googleapis.com --quiet

echo -e "${GREEN}✓ All APIs enabled${NC}"

echo ""
echo -e "${GREEN}Step 1: Creating Firestore database${NC}"
echo ""

# Check if Firestore database exists, create if it doesn't
echo -e "${YELLOW}Checking if Firestore database exists...${NC}"
if gcloud firestore databases describe --database="(default)" 2>&1 | grep -q "NOT_FOUND"; then
    echo -e "${YELLOW}Creating Firestore database in $REGION...${NC}"
    gcloud firestore databases create --location="$REGION" --quiet
    echo -e "${GREEN}✓ Firestore database created${NC}"
else
    echo -e "${YELLOW}Firestore database already exists${NC}"
fi

echo ""
echo -e "${GREEN}Step 2: Creating service account for Cloud Scheduler${NC}"
echo ""

# Create service account for Cloud Scheduler
echo -e "${YELLOW}Creating service account: scheduler-invoker${NC}"
if gcloud iam service-accounts describe "$SCHEDULER_SERVICE_ACCOUNT" 2>&1 | grep -q "NOT_FOUND\|does not exist"; then
    gcloud iam service-accounts create scheduler-invoker \
        --display-name="Cloud Scheduler Invoker" \
        --description="Service account for Cloud Scheduler to invoke Cloud Functions with OIDC" \
        --quiet
    echo -e "${GREEN}✓ Service account created${NC}"
else
    echo -e "${YELLOW}Service account already exists${NC}"
fi

echo ""
echo -e "${GREEN}Step 3: Deploying Cloud Functions${NC}"
echo ""
echo -e "${YELLOW}Note: You may see informational messages about '100% traffic' - these are expected.${NC}"
echo ""

# Deploy Searcher Function
echo -e "${YELLOW}Deploying Searcher function...${NC}"
gcloud functions deploy searcher \
    --gen2 \
    --runtime=python313 \
    --region="$REGION" \
    --source=. \
    --entry-point=searcher \
    --trigger-http \
    --no-allow-unauthenticated \
    --set-env-vars="GCP_PROJECT=$PROJECT_ID,GCP_LOCATION=$REGION,APP_VERSION=$GIT_SHA,DEPLOY_ENV=$DEPLOY_ENV" \
    --timeout=540s \
    --memory=512MB \
    --quiet

echo -e "${GREEN}✓ Searcher function deployed${NC}"

# Deploy Scraper Function
echo -e "${YELLOW}Deploying Scraper function...${NC}"
gcloud functions deploy scraper \
    --gen2 \
    --runtime=python313 \
    --region="$REGION" \
    --source=. \
    --entry-point=scraper \
    --trigger-http \
    --no-allow-unauthenticated \
    --set-env-vars="GCP_PROJECT=$PROJECT_ID,GCP_LOCATION=$REGION,APP_VERSION=$GIT_SHA,DEPLOY_ENV=$DEPLOY_ENV" \
    --timeout=540s \
    --memory=512MB \
    --quiet

echo -e "${GREEN}✓ Scraper function deployed${NC}"

# Grant secret access and Cloud Run Invoker role to service accounts
echo ""
echo -e "${YELLOW}Configuring service account permissions...${NC}"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

# Cloud Tasks uses App Engine default service account by default
APPENGINE_SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"

# Compute service account (for Cloud Functions runtime)
COMPUTE_SERVICE_ACCOUNT="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

# Grant Secret Manager access to compute service account (for publisher function)
gcloud secrets add-iam-policy-binding "$DISCORD_BOT_TOKEN_SECRET" \
    --member="serviceAccount:$COMPUTE_SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet 2>/dev/null || echo -e "${YELLOW}Secret permission already granted (or secret doesn't exist yet)${NC}"

echo -e "${GREEN}✓ Secret access configured${NC}"
echo ""

# Deploy Publisher Function
echo -e "${YELLOW}Deploying Publisher function...${NC}"
gcloud functions deploy publisher \
    --gen2 \
    --runtime=python313 \
    --region="$REGION" \
    --source=. \
    --entry-point=publisher \
    --trigger-http \
    --no-allow-unauthenticated \
    --set-env-vars="GCP_PROJECT=$PROJECT_ID,GCP_LOCATION=$REGION,APP_VERSION=$GIT_SHA,DISCORD_CHANNEL_ID=$DISCORD_CHANNEL_ID" \
    --set-secrets="DISCORD_BOT_TOKEN=$DISCORD_BOT_TOKEN_SECRET:latest" \
    --timeout=540s \
    --memory=256MB \
    --quiet

echo -e "${GREEN}✓ Publisher function deployed${NC}"

# Deploy Publishing Catchup Function
echo -e "${YELLOW}Deploying Publishing Catchup function...${NC}"
gcloud functions deploy publishing-catchup \
    --gen2 \
    --runtime=python313 \
    --region="$REGION" \
    --source=. \
    --entry-point=publishing_catchup \
    --trigger-http \
    --no-allow-unauthenticated \
    --set-env-vars="GCP_PROJECT=$PROJECT_ID,GCP_LOCATION=$REGION,APP_VERSION=$GIT_SHA,DEPLOY_ENV=$DEPLOY_ENV" \
    --timeout=540s \
    --memory=256MB \
    --quiet

echo -e "${GREEN}✓ Publishing Catchup function deployed${NC}"

echo ""
echo -e "${GREEN}Step 4: Constructing function URLs${NC}"
echo ""

# Gen2 Cloud Functions have predictable URLs
# Format: https://{region}-{project-id}.cloudfunctions.net/{function-name}
SEARCHER_URL="https://${REGION}-${PROJECT_ID}.cloudfunctions.net/searcher"
SCRAPER_URL="https://${REGION}-${PROJECT_ID}.cloudfunctions.net/scraper"
PUBLISHER_URL="https://${REGION}-${PROJECT_ID}.cloudfunctions.net/publisher"
PUBLISHING_CATCHUP_URL="https://${REGION}-${PROJECT_ID}.cloudfunctions.net/publishing-catchup"

echo "Searcher URL: $SEARCHER_URL"
echo "Scraper URL: $SCRAPER_URL"
echo "Publisher URL: $PUBLISHER_URL"
echo "Publishing Catchup URL: $PUBLISHING_CATCHUP_URL"

echo ""
echo -e "${GREEN}Step 5: Granting Cloud Run Invoker role to service account${NC}"
echo ""

# Grant invoker role to scheduler service account for each function
# For Gen2 functions, we need to use 'gcloud run services' commands
for function in searcher scraper publisher publishing-catchup; do
    echo -e "${YELLOW}Granting invoker role for $function...${NC}"
    gcloud run services add-iam-policy-binding "$function" \
        --region="$REGION" \
        --member="serviceAccount:$SCHEDULER_SERVICE_ACCOUNT" \
        --role="roles/run.invoker" \
        --platform=managed \
        --quiet 2>/dev/null || echo -e "${YELLOW}Permission already granted${NC}"
done

echo -e "${GREEN}✓ Cloud Run Invoker role granted${NC}"

# Grant Cloud Run Invoker role to service accounts that invoke functions
echo ""
echo -e "${YELLOW}Granting invoker role to App Engine service account (for Cloud Tasks)...${NC}"

# Cloud Tasks uses App Engine default service account for OIDC tokens
for function in searcher scraper publisher; do
    echo -e "${YELLOW}  - Granting role for $function${NC}"
    gcloud run services add-iam-policy-binding "$function" \
        --region="$REGION" \
        --member="serviceAccount:$APPENGINE_SERVICE_ACCOUNT" \
        --role="roles/run.invoker" \
        --platform=managed \
        --quiet 2>/dev/null || echo -e "${YELLOW}    Permission already granted${NC}"
done

echo -e "${GREEN}✓ Cloud Tasks invoker permissions granted${NC}"

echo ""
echo -e "${GREEN}Step 6: Creating Cloud Tasks queues${NC}"
echo ""

# Create queues if they don't exist
for queue in search-queue scrape-queue publish-queue; do
    echo -e "${YELLOW}Checking if queue $queue exists...${NC}"
    if gcloud tasks queues describe "$queue" --location="$REGION" 2>&1 | grep -q "NOT_FOUND\|PERMISSION_DENIED"; then
        echo -e "${YELLOW}Creating queue: $queue${NC}"
        gcloud tasks queues create "$queue" --location="$REGION" --quiet
    else
        echo -e "${YELLOW}Queue $queue already exists${NC}"
    fi
done

echo -e "${GREEN}✓ Queues created${NC}"

echo ""
echo -e "${GREEN}Step 7: Updating queue configurations${NC}"
echo ""

# Update search queue
echo -e "${YELLOW}Updating search-queue configuration...${NC}"
gcloud tasks queues update search-queue \
    --location="$REGION" \
    --max-dispatches-per-second=0.17 \
    --max-concurrent-dispatches=1 \
    --max-attempts=3 \
    --min-backoff=10s \
    --max-backoff=60s \
    --max-doublings=3 \
    --quiet

# Update scrape queue
echo -e "${YELLOW}Updating scrape-queue configuration...${NC}"
gcloud tasks queues update scrape-queue \
    --location="$REGION" \
    --max-dispatches-per-second=0.5 \
    --max-concurrent-dispatches=5 \
    --max-attempts=3 \
    --min-backoff=10s \
    --max-backoff=120s \
    --max-doublings=3 \
    --quiet

# Update publish queue
echo -e "${YELLOW}Updating publish-queue configuration...${NC}"
gcloud tasks queues update publish-queue \
    --location="$REGION" \
    --max-dispatches-per-second=0.08 \
    --max-concurrent-dispatches=1 \
    --max-attempts=3 \
    --min-backoff=2s \
    --max-backoff=60s \
    --max-doublings=3 \
    --quiet

echo -e "${GREEN}✓ Queue configurations updated${NC}"

echo ""
echo -e "${GREEN}Step 8: Creating Cloud Scheduler jobs${NC}"
echo ""

# Create search scheduler job (every hour on the hour)
echo -e "${YELLOW}Creating/updating search scheduler job...${NC}"
if gcloud scheduler jobs describe search-scheduler --location="$REGION" 2>&1 | grep -q "NOT_FOUND\|does not exist"; then
    gcloud scheduler jobs create http search-scheduler \
        --location="$REGION" \
        --schedule="0 * * * *" \
        --uri="$SEARCHER_URL" \
        --http-method=POST \
        --message-body='{"start_index": 0, "activity_type": "Backcountry Skiing"}' \
        --oidc-service-account-email="$SCHEDULER_SERVICE_ACCOUNT" \
        --oidc-token-audience="$SEARCHER_URL" \
        --time-zone="America/Los_Angeles" \
        --description="Trigger search for new activities every hour" \
        --quiet
    echo -e "${GREEN}✓ Search scheduler job created${NC}"
else
    gcloud scheduler jobs update http search-scheduler \
        --location="$REGION" \
        --schedule="0 * * * *" \
        --uri="$SEARCHER_URL" \
        --http-method=POST \
        --message-body='{"start_index": 0, "activity_type": "Backcountry Skiing"}' \
        --oidc-service-account-email="$SCHEDULER_SERVICE_ACCOUNT" \
        --oidc-token-audience="$SEARCHER_URL" \
        --time-zone="America/Los_Angeles" \
        --description="Trigger search for new activities every hour" \
        --quiet
    echo -e "${GREEN}✓ Search scheduler job updated${NC}"
fi

# Create publishing catchup scheduler job (every hour on the half hour)
echo -e "${YELLOW}Creating/updating publishing catchup scheduler job...${NC}"
if gcloud scheduler jobs describe publishing-catchup-scheduler --location="$REGION" 2>&1 | grep -q "NOT_FOUND\|does not exist"; then
    gcloud scheduler jobs create http publishing-catchup-scheduler \
        --location="$REGION" \
        --schedule="30 * * * *" \
        --uri="$PUBLISHING_CATCHUP_URL" \
        --http-method=POST \
        --message-body='{}' \
        --oidc-service-account-email="$SCHEDULER_SERVICE_ACCOUNT" \
        --oidc-token-audience="$PUBLISHING_CATCHUP_URL" \
        --time-zone="America/Los_Angeles" \
        --description="Retry failed publications every hour on the half hour" \
        --quiet
    echo -e "${GREEN}✓ Publishing catchup scheduler job created${NC}"
else
    gcloud scheduler jobs update http publishing-catchup-scheduler \
        --location="$REGION" \
        --schedule="30 * * * *" \
        --uri="$PUBLISHING_CATCHUP_URL" \
        --http-method=POST \
        --message-body='{}' \
        --oidc-service-account-email="$SCHEDULER_SERVICE_ACCOUNT" \
        --oidc-token-audience="$PUBLISHING_CATCHUP_URL" \
        --time-zone="America/Los_Angeles" \
        --description="Retry failed publications every hour on the half hour" \
        --quiet
    echo -e "${GREEN}✓ Publishing catchup scheduler job updated${NC}"
fi

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Summary:"
echo "- All Cloud Functions deployed with IAM authentication required"
echo "- Function URLs constructed using predictable Gen2 naming pattern"
echo "- Cloud Scheduler configured with OIDC token authentication"
echo "- Cloud Tasks queues created and configured"
echo "- Service account: $SCHEDULER_SERVICE_ACCOUNT"
echo ""
echo "Next steps:"
echo "1. Verify the Discord bot token secret is set correctly:"
echo "   gcloud secrets describe $DISCORD_BOT_TOKEN_SECRET"
echo "2. Test the deployment by manually triggering the search scheduler:"
echo "   gcloud scheduler jobs run search-scheduler --location=$REGION"
echo "3. Monitor function logs:"
echo "   gcloud functions logs read searcher --region=$REGION --gen2 --limit=50"
echo ""
echo "To manually invoke functions (for testing):"
echo "  TOKEN=\$(gcloud auth print-identity-token)"
echo "  curl -H \"Authorization: Bearer \$TOKEN\" -H \"Content-Type: application/json\" \\"
echo "    -d '{\"start_index\": 0}' $SEARCHER_URL"
echo ""
