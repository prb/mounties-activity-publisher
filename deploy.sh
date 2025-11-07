#!/bin/bash

# Deployment script for Mountaineers Activities Discord Publisher
# This script deploys Cloud Functions and creates Cloud Tasks queues

set -e  # Exit on error

# Configuration - set these before running
PROJECT_ID="${GCP_PROJECT:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
DISCORD_BOT_TOKEN_SECRET="${DISCORD_BOT_TOKEN_SECRET:-discord-bot-token}"
DISCORD_CHANNEL_ID="${DISCORD_CHANNEL_ID:-your-channel-id}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Mountaineers Activities Discord Publisher Deployment ===${NC}"
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
echo -e "${GREEN}Step 2: Deploying Cloud Functions${NC}"
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
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT=$PROJECT_ID,GCP_LOCATION=$REGION,APP_VERSION=$GIT_SHA" \
    --timeout=540s \
    --memory=512MB

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
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT=$PROJECT_ID,GCP_LOCATION=$REGION,APP_VERSION=$GIT_SHA" \
    --timeout=540s \
    --memory=512MB

echo -e "${GREEN}✓ Scraper function deployed${NC}"

# Grant secret access to the service account before deploying Publisher
echo ""
echo -e "${YELLOW}Granting secret access to service account...${NC}"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
SERVICE_ACCOUNT="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

# Grant Secret Manager Secret Accessor role
gcloud secrets add-iam-policy-binding "$DISCORD_BOT_TOKEN_SECRET" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
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
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT=$PROJECT_ID,GCP_LOCATION=$REGION,APP_VERSION=$GIT_SHA,DISCORD_CHANNEL_ID=$DISCORD_CHANNEL_ID" \
    --set-secrets="DISCORD_BOT_TOKEN=$DISCORD_BOT_TOKEN_SECRET:latest" \
    --timeout=540s \
    --memory=256MB

echo -e "${GREEN}✓ Publisher function deployed${NC}"

echo ""
echo -e "${GREEN}Step 3: Getting function URLs${NC}"
echo ""

# Get function URLs and save for Cloud Tasks configuration
SEARCHER_URL=$(gcloud functions describe searcher --region="$REGION" --gen2 --format="value(serviceConfig.uri)")
SCRAPER_URL=$(gcloud functions describe scraper --region="$REGION" --gen2 --format="value(serviceConfig.uri)")
PUBLISHER_URL=$(gcloud functions describe publisher --region="$REGION" --gen2 --format="value(serviceConfig.uri)")

echo "Searcher URL: $SEARCHER_URL"
echo "Scraper URL: $SCRAPER_URL"
echo "Publisher URL: $PUBLISHER_URL"

echo ""
echo -e "${GREEN}Step 4: Creating Cloud Tasks queues${NC}"
echo ""

# Create queues if they don't exist
for queue in search-queue scrape-queue publish-queue; do
    echo -e "${YELLOW}Checking if queue $queue exists...${NC}"
    if gcloud tasks queues describe "$queue" --location="$REGION" 2>&1 | grep -q "NOT_FOUND\|PERMISSION_DENIED"; then
        echo -e "${YELLOW}Creating queue: $queue${NC}"
        gcloud tasks queues create "$queue" --location="$REGION"
    else
        echo -e "${YELLOW}Queue $queue already exists${NC}"
    fi
done

echo -e "${GREEN}✓ Queues created${NC}"

echo ""
echo -e "${GREEN}Step 5: Updating function URLs in environment${NC}"
echo ""

# Update functions with the URLs they need to enqueue tasks
echo -e "${YELLOW}Updating Searcher function with URLs...${NC}"
gcloud functions deploy searcher \
    --gen2 \
    --runtime=python313 \
    --region="$REGION" \
    --source=. \
    --entry-point=searcher \
    --trigger-http \
    --allow-unauthenticated \
    --update-env-vars="SCRAPE_FUNCTION_URL=$SCRAPER_URL,SEARCH_FUNCTION_URL=$SEARCHER_URL" \
    --timeout=540s \
    --memory=512MB

echo -e "${YELLOW}Updating Scraper function with URLs...${NC}"
gcloud functions deploy scraper \
    --gen2 \
    --runtime=python313 \
    --region="$REGION" \
    --source=. \
    --entry-point=scraper \
    --trigger-http \
    --allow-unauthenticated \
    --update-env-vars="PUBLISH_FUNCTION_URL=$PUBLISHER_URL" \
    --timeout=540s \
    --memory=512MB

echo -e "${GREEN}✓ Function URLs updated${NC}"

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Set up Cloud Scheduler to trigger the searcher function periodically"
echo "2. Configure Firebase Remote Config for polling frequency and TTL"
echo "3. Test the deployment by manually triggering the searcher function"
echo ""
echo "To trigger manually:"
echo "  curl -X POST $SEARCHER_URL -H 'Content-Type: application/json' -d '{\"start_index\": 0}'"
echo ""
