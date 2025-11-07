# Mountaineers Activities Discord Publisher

Automated system to publish Mountaineers backcountry ski activities to Discord. 

## Overview

This application automatically:
1. Polls the Mountaineers website for backcountry ski activities
2. Extracts activity details (title, date, leader, location, difficulty)
3. Stores activities in Firestore
4. Publishes new activities to a Discord channel

Built with Google Cloud Functions, Cloud Tasks, and Firestore.

## Architecture

```
Cloud Scheduler (every 60 min)
    ↓
Searcher Function → Cloud Tasks → Scraper Function → Cloud Tasks → Publisher Function
    ↓                                   ↓                              ↓
Search Results                      Firestore                      Discord Channel
```

## Quick Start

### Prerequisites

1. **Google Cloud SDK (gcloud)**
   ```bash
   # macOS
   brew install google-cloud-sdk

   # Or download from: https://cloud.google.com/sdk/docs/install

   # Authenticate
   gcloud auth login
   ```

2. **Discord Bot**
   - Create a Discord application at https://discord.com/developers/applications
   - Go to the "Bot" section and create a bot
   - Copy the bot token (you'll need this for Secret Manager)
   - Invite the bot to your server using OAuth2 URL Generator:
     - Go to "OAuth2" → "URL Generator"
     - Select scopes: `bot`
     - Select bot permissions: `Send Messages`, `View Channels`, `Embed Links`
     - Copy the generated URL and open it in your browser
     - Select your server and authorize the bot
   - Get your Discord channel ID:
     - Enable Developer Mode: User Settings → Advanced → Developer Mode
     - Right-click on the channel → "Copy Channel ID"

3. **Google Cloud Project**
   - Create a project at https://console.cloud.google.com/
   - Enable billing (free tier is sufficient)

### Installation

1. **Clone and set up:**
   ```bash
   git clone <repository-url>
   cd mounties-activities-discord-publisher
   ```

2. **Set environment variables:**
   ```bash
   export GCP_PROJECT=your-project-id
   export GCP_REGION=us-central1
   export DISCORD_CHANNEL_ID=your_discord_channel_id
   ```

3. **Enable Google Cloud APIs:**
   ```bash
   gcloud services enable cloudfunctions.googleapis.com
   gcloud services enable cloudtasks.googleapis.com
   gcloud services enable firestore.googleapis.com
   gcloud services enable cloudscheduler.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   ```

4. **Create Firestore database:**
   ```bash
   gcloud firestore databases create --location=us-central
   ```

5. **Store Discord bot token:**
   ```bash
   echo -n "your_discord_bot_token" | gcloud secrets create discord-bot-token --data-file=-
   ```

6. **Deploy:**
   ```bash
   ./deploy.sh
   ```

## Testing

The project includes comprehensive tests:

```bash
# Install development dependencies
uv sync

# Run all tests
uv run pytest tests/ -v

# Run specific test suites
uv run pytest tests/test_search_parser.py -v      # Phase 1: Parsers
uv run pytest tests/test_functions.py -v          # Phase 3: Functions
uv run pytest tests/test_publisher.py -v          # Phase 4: Publisher

# With Firestore emulator (Phase 2)
firebase emulators:start --only firestore &
uv run pytest tests/test_firestore_operations.py -v
```

## Project Structure


```
mounties-activities-discord-publisher/
 src/
     models.py              # Data models (Activity, Leader, Place)
     parsers/               # HTML parsing (search results, activity details)
     db/                    # Firestore operations
     tasks/                 # Cloud Tasks client
     functions/             # Cloud Function handlers
     http_client.py         # HTTP client with User-Agent
     discord_client.py      # Discord API client
 tests/                     # Comprehensive test suite (42 tests)
 main.py                    # Cloud Functions entry points
 requirements.txt           # Production dependencies
 deploy.sh                  # Automated deployment script
 queues.yaml                # Cloud Tasks configuration
```

## Documentation

Detailed documentation for each development phase:

- **[Phase 1](PHASE1_README.md)**: Core extraction logic (parsers)
- **[Phase 2](PHASE2_README.md)**: Firestore data model & operations
- **[Phase 3](PHASE3_README.md)**: Searcher & scraper functions
- **[Phase 4](PHASE4_README.md)**: Discord publisher function
- **[Phase 5](PHASE5_README.md)**: Cloud Tasks configuration & deployment

## Manual Testing

After deployment, trigger the searcher function manually:

```bash
# Get the searcher function URL
SEARCHER_URL=$(gcloud functions describe searcher --region=us-central1 --gen2 --format="value(serviceConfig.uri)")

# Trigger it
curl -X POST "$SEARCHER_URL" \
    -H "Content-Type: application/json" \
    -d '{"start_index": 0, "activity_type": "Backcountry Skiing"}'
```

Check your Discord channel for new activity announcements!

## Monitoring

```bash
# View function logs
gcloud functions logs read searcher --region=us-central1 --limit=50
gcloud functions logs read scraper --region=us-central1 --limit=50
gcloud functions logs read publisher --region=us-central1 --limit=50

# View Cloud Tasks queues
gcloud tasks queues list --location=us-central1

# View Firestore data
# Use Firebase Console: https://console.firebase.google.com/
```

## Cost

Expected cost: **$0/month** (within Google Cloud free tier)

- Cloud Functions: ~20,000 invocations/month (free tier: 2M/month)
- Cloud Tasks: ~20,000 operations/month (free tier: 1M/month)
- Firestore: Minimal reads/writes (free tier: 50K reads, 20K writes/month)
- Cloud Scheduler: 1 job (free tier: 3 jobs)

## Configuration

Key configuration options (set via environment variables):

- `GCP_PROJECT`: Your Google Cloud project ID
- `GCP_REGION`: Deployment region (default: us-central1)
- `DISCORD_CHANNEL_ID`: Discord channel for announcements
- `DISCORD_BOT_TOKEN_SECRET`: Secret Manager secret name (default: discord-bot-token)
- `APP_VERSION`: Application version (auto-set to Git SHA)

## Troubleshooting

### Deployment fails with permission errors
```bash
# Grant necessary IAM roles
PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT --format="value(projectNumber)")

gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/cloudbuild.builds.builder"
```

### Discord messages not appearing
1. Check Discord bot token in Secret Manager
2. Verify channel ID is correct
3. Check publisher function logs: `gcloud functions logs read publisher --region=us-central1`
4. Verify bot has "Send Messages" permission in Discord channel

### Activities not being scraped
1. Check searcher function logs
2. Verify Cloud Tasks queues are processing: `gcloud tasks queues describe scrape-queue --location=us-central1`
3. Check for Firestore permission errors

See [PHASE5_README.md](PHASE5_README.md#troubleshooting) for detailed troubleshooting.

## Development

Local development setup:

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Format code
uv run black src/ tests/

# Type checking
uv run mypy src/
```

## License

See [LICENSE](LICENSE) file.

## Contributing

This project was developed iteratively through 5 phases. Each phase built upon the previous:

1. **Phase 1**: HTML parsing and data extraction
2. **Phase 2**: Firestore integration
3. **Phase 3**: HTTP fetching and Cloud Functions
4. **Phase 4**: Discord integration
5. **Phase 5**: Deployment automation

For details on each phase, see the individual phase documentation
