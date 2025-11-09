# Deployment Environments Guide

This guide explains how to set up multiple deployment environments (development, staging, production).

## Recommended Approach: Separate GCP Projects

The cleanest way to separate environments is to use **different GCP projects** for each environment.

### Benefits
- Complete isolation between environments
- No risk of cross-environment interference
- Separate billing and quotas
- Simple resource naming (no prefixes needed)
- Independent IAM policies

### Setup

#### 1. Create separate projects

```bash
# Create development project
gcloud projects create myproject-dev --name="My Project (Dev)"

# Create production project
gcloud projects create myproject-prod --name="My Project (Prod)"
```

#### 2. Create environment-specific configuration files

Create shell scripts for each environment:

**dev-env.sh:**
```bash
#!/bin/bash
export GCP_PROJECT=myproject-dev
export GCP_REGION=us-central1
export DISCORD_CHANNEL_ID=123456789012345678  # Dev Discord channel
export DISCORD_BOT_TOKEN_SECRET=discord-bot-token
export DEPLOY_ENV=dev
```

**prod-env.sh:**
```bash
#!/bin/bash
export GCP_PROJECT=myproject-prod
export GCP_REGION=us-central1
export DISCORD_CHANNEL_ID=987654321098765432  # Prod Discord channel
export DISCORD_BOT_TOKEN_SECRET=discord-bot-token
export DEPLOY_ENV=prod
```

Make them executable:
```bash
chmod +x dev-env.sh prod-env.sh
```

#### 3. Deploy to each environment

```bash
# Deploy to development
source dev-env.sh
./deploy.sh

# Deploy to production
source prod-env.sh
./deploy.sh
```

### Testing Workflow

1. **Develop locally** - Test code changes with unit tests
2. **Deploy to dev** - Deploy to development environment
3. **Manual testing** - Test in dev Discord channel
4. **Deploy to prod** - After validation, deploy to production

### Firestore Data Separation

Each project has its own Firestore database, ensuring complete data isolation:
- Dev environment scrapes and publishes to dev Discord channel
- Prod environment scrapes and publishes to prod Discord channel
- No risk of test data in production

### Cost Considerations

- **Free tier applies per project** - Both projects can use free tier
- **Recommended**: Keep dev environment scheduler paused when not actively testing
- Pause dev schedulers:
  ```bash
  source dev-env.sh
  gcloud scheduler jobs pause search-scheduler --location=$GCP_REGION
  gcloud scheduler jobs pause publishing-catchup-scheduler --location=$GCP_REGION
  ```

## Alternative Approach: Same Project with Prefixes

If you want to use a single project, you can use resource name prefixes (e.g., `dev-searcher`, `prod-searcher`).

### Limitations
- More complex deployment script needed
- Shared billing and quotas
- Risk of configuration mistakes affecting wrong environment
- Same Firestore database (need collection prefixes or separate database)

### Implementation

This would require modifying `deploy.sh` to add `DEPLOY_ENV` prefix to all resources:
- Functions: `${DEPLOY_ENV}-searcher`
- Queues: `${DEPLOY_ENV}-search-queue`
- Schedulers: `${DEPLOY_ENV}-search-scheduler`
- Service accounts: `${DEPLOY_ENV}-scheduler-invoker`
- Secrets: `${DEPLOY_ENV}-discord-bot-token`

**Not recommended** for production use due to complexity and risk.

## Quick Reference

### Current environment

```bash
echo "Project: $GCP_PROJECT"
echo "Region: $GCP_REGION"
echo "Environment: $DEPLOY_ENV"
```

### Switch between environments

```bash
# Switch to dev
source dev-env.sh

# Switch to prod
source prod-env.sh
```

### List deployed resources by project

```bash
# Functions
gcloud functions list --gen2 --region=$GCP_REGION

# Schedulers
gcloud scheduler jobs list --location=$GCP_REGION

# Queues
gcloud tasks queues list --location=$GCP_REGION
```

### Discord Setup

Create separate Discord channels for each environment:
1. In your Discord server, create channels: `#activities-dev` and `#activities-prod`
2. Right-click each channel → Copy Channel ID
3. Use different channel IDs in each environment's config file

Optionally, create a separate Discord bot for dev to make the separation even clearer.
