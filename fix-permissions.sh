#!/bin/bash

# Quick fix for Cloud Scheduler authentication issues
# Run this if you're seeing "request was not authenticated" errors

set -e

PROJECT_ID="${GCP_PROJECT:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
SCHEDULER_SERVICE_ACCOUNT="scheduler-invoker@${PROJECT_ID}.iam.gserviceaccount.com"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Fixing Cloud Scheduler Authentication ===${NC}"
echo ""

# Check if project ID is set
if [ "$PROJECT_ID" = "your-project-id" ]; then
    echo -e "${RED}Error: GCP_PROJECT environment variable not set${NC}"
    echo "Set it with: export GCP_PROJECT=your-project-id"
    exit 1
fi

gcloud config set project "$PROJECT_ID"

echo -e "${YELLOW}Granting Cloud Run Invoker role to scheduler service account...${NC}"
echo ""

# Grant invoker role for each function using Cloud Run commands (not Cloud Functions)
for function in searcher publishing-catchup; do
    echo -e "${YELLOW}  - Granting role for $function${NC}"
    gcloud run services add-iam-policy-binding "$function" \
        --region="$REGION" \
        --member="serviceAccount:$SCHEDULER_SERVICE_ACCOUNT" \
        --role="roles/run.invoker" \
        --platform=managed \
        --quiet
done

echo ""
echo -e "${GREEN}✓ Permissions granted${NC}"
echo ""

# Also grant permissions for Cloud Tasks to invoke functions
# Cloud Tasks uses App Engine default service account for OIDC tokens
APPENGINE_SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"

echo -e "${YELLOW}Granting Cloud Run Invoker role to App Engine service account (for Cloud Tasks)...${NC}"
echo ""

for function in searcher scraper publisher; do
    echo -e "${YELLOW}  - Granting role for $function${NC}"
    gcloud run services add-iam-policy-binding "$function" \
        --region="$REGION" \
        --member="serviceAccount:$APPENGINE_SERVICE_ACCOUNT" \
        --role="roles/run.invoker" \
        --platform=managed \
        --quiet
done

echo ""
echo -e "${GREEN}✓ Cloud Tasks permissions granted${NC}"
echo ""

# Verify the permissions
echo -e "${YELLOW}Verifying permissions...${NC}"
echo ""

for function in searcher publishing-catchup; do
    echo -e "${YELLOW}IAM policy for $function:${NC}"
    gcloud run services get-iam-policy "$function" \
        --region="$REGION" \
        --platform=managed \
        --format="table(bindings.role, bindings.members)" \
        --filter="bindings.role:roles/run.invoker"
    echo ""
done

echo -e "${GREEN}=== Permissions Fixed ===${NC}"
echo ""
echo "Now try triggering the scheduler job:"
echo "  gcloud scheduler jobs run search-scheduler --location=$REGION"
echo ""
echo "Or wait for the next scheduled run and check the logs:"
echo "  gcloud functions logs read searcher --region=$REGION --gen2 --limit=20"
echo ""
