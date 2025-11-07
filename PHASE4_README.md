# Phase 4: Discord Publisher Function

This phase implements the Discord publishing functionality to send activity announcements to a Discord channel.

## Overview

The Publisher function retrieves activities from Firestore and publishes them to Discord using the Discord API.

**Data Flow:**
```
Cloud Task (from Scraper)
    ↓
[Publisher Function]
    ↓
    ├─→ get activity from Firestore
    ├─→ check if already published
    ├─→ format message
    ├─→ send to Discord API
    └─→ update discord_message_id in Firestore
```

## Project Structure

```
src/
├── discord_client.py       # Discord API client
└── functions/
    └── publisher.py        # Publisher Cloud Function

tests/
└── test_publisher.py       # Tests for Discord client and publisher (11 tests)
```

## Components

### 1. Discord Client (`src/discord_client.py`)

Handles Discord API communication and message formatting.

**Key Functions:**

```python
from src.discord_client import (
    format_activity_message,
    send_discord_message,
    publish_activity_to_discord,
)

# Format an activity message
message = format_activity_message(activity)
# "2026-02-10 [Backcountry Ski...](url) led by [Randy Oakley](<url>) at [Snoqualmie...](<url>)"

# Send a message to Discord
message_id = send_discord_message(
    content="Hello, Discord!",
    channel_id="123456789",
    bot_token="your_bot_token"
)

# Publish an activity (combines formatting and sending)
message_id = publish_activity_to_discord(activity)
```

**Message Format:**

According to spec, messages are formatted as:
```
{date} [{title}]({activity_url}) led by [{leader}](<{leader_url}>) at [{place}](<{place_url}>)
```

Example:
```
2026-02-10 [Backcountry Ski/Snowboard - Snoqualmie Summit West](https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10) led by [Randy Oakley](<https://www.mountaineers.org/members/randy-oakley>) at [Snoqualmie Summit Ski Areas](<https://www.mountaineers.org/activities/routes-places/ski-resorts-nordic-centers/snoqualmie-summit-ski-areas>)
```

**Key Features:**
- Date in Pacific timezone (YYYY-MM-DD format)
- Uses `[text](<url>)` syntax to prevent Discord from showing link previews
- Proper User-Agent header: `mounties-activities-discord-publisher/{version}`
- Bot token authentication
- Returns Discord message ID for tracking

### 2. Publisher Function (`src/functions/publisher.py`)

Cloud Function entry point for publishing activities.

**Input (JSON):**
```json
{
  "activity_id": "backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10"
}
```

**Output (JSON - Success):**
```json
{
  "status": "success",
  "message_id": "1234567890123456789"
}
```

**Output (JSON - Skipped):**
```json
{
  "status": "skipped",
  "message_id": "1234567890123456789",
  "reason": "Activity already published to Discord"
}
```

**Output (JSON - Error):**
```json
{
  "status": "error",
  "error": "Activity not found: some-activity-id"
}
```

**Process:**
1. Retrieves activity from Firestore by ID (with leader and place)
2. Checks if activity already has `discord_message_id` (idempotent)
3. Formats message according to spec
4. Sends message to Discord via API
5. Updates activity document with `discord_message_id`

**Error Handling:**
- Skips activities already published (idempotent)
- Returns error if activity not found
- Returns error if Discord API fails
- Logs all operations for debugging

## Configuration

### Environment Variables

Required for production:

```bash
# Discord Configuration
export DISCORD_BOT_TOKEN=your_discord_bot_token_here
export DISCORD_CHANNEL_ID=your_channel_id_here

# Application Version (set to Git SHA in CI/CD)
export APP_VERSION=abc123def
```

### Getting Discord Credentials

1. **Create Discord App:**
   - Go to https://discord.com/developers/applications
   - Click "New Application"
   - Give it a name (e.g., "Mountaineers Activities")

2. **Create Bot:**
   - Go to "Bot" section
   - Click "Add Bot"
   - Copy the bot token (this is `DISCORD_BOT_TOKEN`)

3. **Enable Bot Permissions:**
   - Under "Bot" → "Privileged Gateway Intents", enable:
     - Message Content Intent (if needed)
   - Under "Bot" → "Bot Permissions", select:
     - Send Messages
     - Embed Links

4. **Invite Bot to Server:**
   - Go to "OAuth2" → "URL Generator"
   - Select scopes: `bot`
   - Select bot permissions: "Send Messages", "Embed Links"
   - Copy generated URL and open in browser
   - Select your server and authorize

5. **Get Channel ID:**
   - In Discord, enable Developer Mode (Settings → Advanced → Developer Mode)
   - Right-click on the channel you want to post to
   - Click "Copy ID" (this is `DISCORD_CHANNEL_ID`)

### Storing Secrets in Google Cloud

For production deployment:

```bash
# Store Discord bot token in Google Cloud Secret Manager
echo -n "your_discord_bot_token" | gcloud secrets create discord-bot-token --data-file=-

# Store channel ID in Firebase Remote Config
# (Channel ID is not sensitive, so Remote Config is fine)
```

## Testing

All tests use mocking to avoid real Discord API calls.

```bash
# Run Publisher tests only
uv run pytest tests/test_publisher.py -v

# Run all tests (Phases 1, 3, 4)
uv run pytest tests/test_search_parser.py tests/test_detail_parser.py tests/test_functions.py tests/test_publisher.py -v
```

**Test Coverage:**
- Message formatting: 2 tests
- Discord API calls: 3 tests
- Publisher function: 6 tests
- Total: 11 tests

## Usage Examples

### Publishing an Activity

```python
from src.db import initialize_firebase, get_activity
from src.functions.publisher import publisher_handler

# Initialize Firestore
initialize_firebase(use_emulator=True)

# Publish an activity
result = publisher_handler({
    'activity_id': 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
})

if result['status'] == 'success':
    print(f"Published to Discord! Message ID: {result['message_id']}")
elif result['status'] == 'skipped':
    print(f"Already published: {result['reason']}")
else:
    print(f"Error: {result['error']}")
```

### Manual Testing with Discord

For testing with a real Discord channel:

```python
import os
from src.discord_client import send_discord_message

# Set credentials
os.environ['DISCORD_BOT_TOKEN'] = 'your_bot_token_here'
os.environ['DISCORD_CHANNEL_ID'] = 'your_channel_id_here'

# Send a test message
message_id = send_discord_message("Test message from Python!")
print(f"Message sent! ID: {message_id}")
```

## Integration with Cloud Functions

Deployment example:

```python
# functions.py (for deployment)
import functions_framework
from src.db import initialize_firebase
from src.functions import publisher_handler

# Initialize Firebase once at module load
initialize_firebase()

@functions_framework.http
def publisher(request):
    """Publisher Cloud Function entry point."""
    request_json = request.get_json(silent=True)
    result = publisher_handler(request_json or {})
    return result
```

## Discord API Details

**Endpoint Used:**
- POST `https://discord.com/api/v10/channels/{channel_id}/messages`

**Headers:**
```
Authorization: Bot {bot_token}
Content-Type: application/json
User-Agent: mounties-activities-discord-publisher/{version}
```

**Payload:**
```json
{
  "content": "message content here"
}
```

**Response:**
```json
{
  "id": "1234567890123456789",
  "channel_id": "123456789",
  "content": "message content here",
  ...
}
```

## Error Handling

The publisher handles several error scenarios:

1. **Missing activity_id**: Returns error status
2. **Activity not found**: Returns error status
3. **Already published**: Returns skipped status (idempotent)
4. **Discord API error**: Returns error status with details
5. **Network timeout**: Caught by requests library (30s timeout)

All errors are logged for debugging.

## Performance Notes

- Message sending has 30-second timeout
- Idempotent design allows safe retries
- Discord message ID is stored to prevent duplicates
- No rate limiting implemented (relies on Cloud Tasks queue rate limits)

## Next Steps

Phase 5 will implement:
- Cloud Tasks queue configuration (`queues.yaml`)
- Deployment configuration
- Cloud Function deployment
- End-to-end testing

Phase 6 will add:
- Cloud Scheduler for periodic polling
- Firebase Remote Config
- Activity TTL cleanup function
- Full automation
