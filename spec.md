# Mountaineers Activity to Discord Publisher
This [Discord App](https://discord.com/developers/docs/quick-start/overview-of-apps) is designed to publish short summaries of activities from the Mountaineers.org website to a Discord channel.  The initial scope of the project is just backcountry ski activities and a single destination Discord channel, but the app could eventually be expanded to include other activity types, finer-grained selection of activities, and multiple destination Discord channels.

The design of the system is straightforward:

- Poll the Mountaineers website for activities on a configurable schedule.
- Scrape activity data out of the search results.
- For each search result that hasn't already been processed, crawl the activity detail pages linked from the search results.
- Store any new activities in a persistent cache and publish a message to Discord.

## High-level Architecture
This project will use Google Firebase features and functionality, specifically:

- A scheduled Cloud Function to trigger an initial search on a regular interval.
- A scheduled Cloud Function to trigger publishing catch-up code on a regular interval.
- Cloud Function to host the searching code.  This will be called by Cloud Tasks.  The searching code will determine if there are additional pages of results to process and enqueue successive search tasks for those.
- Cloud Function to host the scraping code.  This will be called by Cloud Tasks.
- Cloud Function to host the Discord publishing code.  This will be called by Cloud Tasks.
- Cloud Firestore to host the persistent cache(s) in the form of document collection(s).
- Google Cloud Tasks configured with one queue for searching tasks, one for scraping tasks, and one for publishing tasks.
- Firebase Remote Config to manage configuration.
- Google Cloud Secrets to manage secrets.

Up to date architecture diagrams should be generated using PlantUML (see [architecture.puml](architecture.puml)) and stored in [ARCHITECTURE.txt](ARCHITECTURE.txt).

The total traffic is intended to fit within the confines and capabiltiies of the free "Spark" tier on Firebase and other Google Cloud functionality.  We prefer `queues.yaml` to manage the Cloud Tasks queues.

### Cloud Functions Generation

**IMPORTANT:** This project uses **Google Cloud Functions (2nd gen)**, not 1st gen.

Key implications:
- 2nd gen functions are built on Cloud Run and Eventarc
- Runtime: Python 3.13 (or latest available Python 3.x)
- Deployment uses `--gen2` flag
- IAM permissions must be granted via `gcloud run services` commands, not `gcloud functions` commands
- Functions are deployed with `--no-allow-unauthenticated` for IAM authentication
- OIDC token authentication is used for Cloud Scheduler invocations
- Supports longer timeouts (up to 60 minutes vs 9 minutes for gen1)
- Better scalability and integration with Cloud Run ecosystem
- **Predictable URLs**: Gen2 functions have URLs in the format `https://{region}-{project-id}.cloudfunctions.net/{function-name}`, which can be constructed without querying

Reference: [Cloud Functions 2nd gen documentation](https://cloud.google.com/functions/docs/2nd-gen/overview)

#### Function URL Construction

Cloud Tasks needs to know the URLs of target functions for task enqueueing. Rather than querying deployed functions and redeploying with URLs as environment variables, the code constructs URLs using the predictable Gen2 naming pattern:

```python
# Format: https://{region}-{project-id}.cloudfunctions.net/{function-name}
url = f"https://{LOCATION}-{PROJECT_ID}.cloudfunctions.net/scraper"
```

This eliminates the need for double deployment and reduces deployment time.

### Development and Testing

Functions will be written in a manner that allows their core logic — extraction of URLs from search data or extraction of metadata from detail pagers, or generation of Discord message content — to be tested locally.  Supplied sample files can be used to create test fixtures.

There is a `bookkeeping` collection in the persistent cache where functions should record the status of their execution.

All project code will be written in modern, idiomatic Python3 with doctests where appropriate and `pytest` tests for general purpose testing.  Logging should use the Cloud Functions logging SDK.  We will use `uv` to manage project dependencies.

@todo add logging levels and expectations.
@todo true-up the architecture and free-tier Firebase expectations, e.g., Secrets and Cloud Tasks aren't available as part of the Firebase free tier but do have their own free usage thresholds.

### Security

All Cloud Functions should be deployed with **IAM authentication required** (no unauthenticated access).

#### Cloud Scheduler Authentication

The search and publishing catchup functions will be invoked via Cloud Scheduler using **OIDC (OpenID Connect) token authentication**. Cloud Scheduler will be configured with a dedicated service account (`scheduler-invoker@{project}.iam.gserviceaccount.com`) that has the `Cloud Run Invoker` role. While these functions will have HTTP endpoints, they will reject unauthenticated requests.

#### Cloud Tasks Authentication

The scraper and publisher functions (invoked via Cloud Tasks) **must also use OIDC token authentication**. Cloud Tasks will use the App Engine default service account (`{project-id}@appspot.gserviceaccount.com`) to generate OIDC tokens for invoking Gen2 Cloud Functions.

**Critical requirement**: All Cloud Tasks must include OIDC token configuration:
```python
'oidc_token': {
    'service_account_email': '{project-id}@appspot.gserviceaccount.com',
    'audience': 'https://{region}-{project}.cloudfunctions.net/{function-name}',
}
```

The App Engine default service account must have the `Cloud Run Invoker` role for all functions invoked by Cloud Tasks (searcher, scraper, publisher).

### Deployment Environments

The system supports multiple deployment environments (e.g., development, production) to allow safe testing before production deployment.

Environment separation is achieved through:
- **Separate GCP projects** (recommended) OR **resource name prefixes** within the same project
- **Environment-specific configuration**: Different Discord channels, secrets, and Firestore databases per environment
- **Environment variable**: `DEPLOY_ENV` (defaults to `prod`, can be set to `dev`, `staging`, etc.)

Example deployment workflow:
```bash
# Deploy to development
export DEPLOY_ENV=dev
export GCP_PROJECT=myproject-dev
export DISCORD_CHANNEL_ID=dev-channel-id
./deploy.sh

# Deploy to production
export DEPLOY_ENV=prod
export GCP_PROJECT=myproject-prod
export DISCORD_CHANNEL_ID=prod-channel-id
./deploy.sh
```

When using resource name prefixes (same project), resources should be named: `{env}-searcher`, `{env}-search-queue`, etc.

### Configuration Information

The following configuration information will be stored:

- A *Discord Bot Token* will be stored in Google Cloud Secrets.  The Discord Publisher function should trim any additional whitespace on the bot token secret.
  - Secret name format: `discord-bot-token` (or `{env}-discord-bot-token` for multi-env in same project)
- The *Discord Channel ID* will be passed as an environment variable to the publisher function.
  - Different channels should be used for different environments (dev vs prod)

### Scheduling, Retries, Backoff, and Catchup

The default schedule for search execution should be every hour on the hour.  The default schedule for publishing cleanup should be every hour on the half hour.

All functions should respond gracefull to `429` response codes and log an informative message.  Rate limits, concurrency, and backoff should be as follows:

- Search queue: 10rpm, concurrency one, three retries, 10s initial backoff, doubling up to 60s
- Scrape queue: 30rpm, concurrency five, three retries, 10s initial backoff, doubling up to 120s
- Publish queue: 5rpm, concurrency one, three retries, 2s initial backoff, doubling up to 60s

The publish queue configuration is intended to align with Discord API usage expectations.
@todo add link to Discord API usage expectations.

## Persistent Cache Architecture

@todo Document field semantics around `null`/`None` and not inserting those fields.  (Implementation already supports this.)

### Activities Collection
The persistent cache will contain an `activities` collection.  Each `activity` document in the collection will have the following fields:

- `activity_permalink` (text string): A URI for the activity detail page.
- `activity_type` (text string): The type of the activity, e.g., `Backcountry Skiing`.
- `title` (text string): The title of the activity.
- `description` (text string): A brief description of the activity.
- `difficulty_rating` (array): The difficulty rating of the activity.
- `activity_date` (date and time): The date of the activity, stored in UTC.
- `place_ref` (reference): A reference to a document in the `places` collection.
- `url` (text string): The URL of the activity detail page.
- `branch` (text string): The sponsoring branch for the activity.
- `leader_ref` (reference): A reference to a document in the `leaders` collection.
- `discord_message_id` (text string): The ID of the Discord message associated with the activity, once published.

@todo Add `activity_type` to the data model and consider a backfill one-time operation.

The document ID should be final path segment of the `activity_permalink`, e.g.,

```
https://www.mountaineers.org/activities/activities/death-gully-72
```

would have a document ID of `death-gully-72`.  Activities should remain in the cache until a configurable number of days after the `activity_date`.

### Leaders Collection
The persistent cache will contain a `leaders` collection.  Each `leader` document in the collection will have the following fields:

- `leader_permalink` (text string): A URI for the leader detail page.
- `name` (text string): The name of the leader.

The document ID should be the final path segment of the `leader_permalink`, e.g.,

```
https://www.mountaineers.org/members/bob-dobelina
```

would have a document ID of `bob-dobelina`.

Leaders should remain in the cache until deleted.

### Places Collection
The persistent cache will contain a `places` collection.  Each `place` document in the collection will have the following fields:

- `place_permalink` (text string): A URI for the place detail page.
- `name` (text string): The name of the place.

The document ID should be the final two path segments of the `place_permalink` with a `/` replaced by a `_`, e.g.,

```
https://www.mountaineers.org/activities/routes-places/ski-resorts-nordic-centers/snoqualmie-summit-ski-areas
```

would have the document ID `ski-resorts-nordic-centers_snoqualmie-summit-ski-areas`.

Places should remain in the cache until deleted.

### Bookkeeping Collection
The `bookkeeping` collection contains a single document with the following fields:

- `last_search_success` (date and time): completion date and time for the last successful search function completion.
- `search_status` (text string): status of the last search function execution.
- `last_scrape_success` (date and time): completion date and time of the last successful scrape function execution.
- `scrape_status` (text string): status of the last search function execution.
- `last_publish_success` (date and time): completion date and time of the last successful publish function execution but only if the publish was actually performed; this field should not be updated when the publication is skipped due to an existing `discord_message_id`.
- `publish_status` (text string): status of the last publish function execution.

The status message should be one of:

- `Green` if the function completed successfully.
- `Yellow: Backing off.` if the function is in backoff due to a `429`
- `Red: {message}` if the function failed, and `{message}` is a descriptive message.

## Discord Publishing

### Publisher Function: Publish Messages for Activties

The *Publisher Function* is responsible for publishing an `activity` record (based on ID) to Discord using the [Create Message Endpoint](https://discord.com/developers/docs/resources/message#create-message) on the [Discord API](https://discord.com/developers/docs/reference).

Among other things:

- If the `activity` record already contains a `discord_message_id`, the function should not republish and can exit cleanly.
- The system should authenticate to Discord using a bot token stored in the Firebase secrets.
- The system should provide a `User Agent` header with the value `mounties-activities-discord-publisher/<version>` where `<version>` is the version of the publisher running in the form of the Git SHA (`git rev-parse --short HEAD`)from which it was built and deployed.
- The system should send a JSON request provide a `Content-Type` header with the value `application/json`.

The `content` of the request should be based on the `activity`, `leader`, and `place` data, as follows:

@todo Update the code for the prettier output.
```
📆 {{activity.activity_date in YYYY-MM-DD format in Pacific timezone}} {{emoji for activity.activity_type}} [{{activity.title}}]({{activity.activity_permalink}})
Leader: [{{activity.leader.name}}](<{{activity.leader.leader_permalink}}>) at [{{activity.place.name}}](<{{activity.place.place_permalink}}>)
Difficulty Ratings: {{comma-concatenated activity.difficulty_rating with optional emojis}}
```

(Note that the syntax `[anchor text](<url>)` is used to create a hyperlink that does not render a preview in the channel.)

The emoji for the `Backcountry Skiing` activity type should be "⛷️".

The optional emojis for difficulty ratings are:

- "🟥" for a difficulty that starts with `M3`
- "◆" for a difficulty that starts with `M2`
- "🟦" for a difficulty that starts with `M1-M2`
- "🟢" for a difficulty that starts with `M1`
- "🧊" for a difficulty that contains "Glacier"

The optional emoji or emojis plus a space should be placed before the difficulty rating, e.g., "◆🧊 M2G Advanced Glacier Ski" or "🟢 M1 Intermediate Ski".

Upon successful publication, the `activity` should be updated with the `discord_message_id` field set.

### Cleanup Function: Re-Attempt Publication

This cloud function should query the `activities` collection for documents without the `discord_message_id` set and enqueue a publishing operation for each of them.

## Mountaineers Website Search API, Polling, and Scraping

### Search API
The activities search endpoint from the Mountaineers website presents a single `GET` endpoint as follows:

```
https://www.mountaineers.org/activities/activities/@@faceted_query?b_start:int=[start_index]&c4%5B%5D=[type]
```

The `[start_index]` parameter is a zero-based record number to start the page of results at; pages are of length up to 20, with a page of fewer than 20 records indicating the end of the results.  The `[type]` parameter is one of the following activity types:

- `Backcountry Skiing`

Parameters should be encoded according to `application/x-www-form-urlencoded`.

### Searcher Function: Activity Detail URLs from Search Results
The *Searcher Function* is responsible for performing a search against the endpoint, extracting a list of activity detail URLs, and dispatching a *Detail Scraper* task for each new one.

The search endpoint returns an HTML document containing a list of activities.  The document [sample_activity_search_response.html](tests/fixtures/sample_activity_search_response.html) contains an example response with no successive page of results, and the document [sample_activity_search_response_1.html](tests/fixtures/sample_activity_search_response_1.html) contains an example response with a successive page of results.

Using XPath notation, each `//div[@class='result-item']` element in the response contains an activity.  Within an item, `.//h3[@class='result-title']/a/@href` is the URL of the activity detail page.

(*Pro Tip:* For validation of XPath expressions at the commandline, `xmllint --xpath` is super useful.)

The Searcher Function should check the `activities` collection for a corresponding activity and enqueue one Detail Scraper task for each new activity detail URL.

In addition, if the search response contains `//nav[@class='pagination']//li[@class='next']/a/@href`, enqueue a Searcher task for that next page.

### Detail Scraper Function: Data Binding and Extraction from Detail Pages
The *Detail Scraper Function* is responsible for extracting data from the activity detail page and binding it to the `activity` document, `leader` document, and `place` document, as necessary.  The URL passed into the function is the `activity_permalink`.

The activity detail endpoint returns an HTML document with details of the activity.  The document [sample_activity_detail.html](tests/fixtures/sample_activity_detail.html) contains an example response.  Using XPath notation:

- `//*[@class='documentFirstHeading']/text()` is the `title` of the `activity`.
- `//li[label[contains(text(),'Activity Type')]]/text()` is the `activity_type` of the `activity`; it should be white-space trimmed prior to use.
- `//p[@class='documentDescription']/text()` is the `description` of the `activity`.
- `//div[@class='program-core']/ul[@class='details'][1]/li[1]/text()` is the `activity_date` to be parsed from `%a, %b %d, %Y` according to Python's `strftime` format.  The activity date will be in Pacific time and should be converted to UTC for storage.  (This ordering-dependent reference is a bit brittle, but it's the best we can do based on the page content.)
- `//div[@class='program-core']/ul[@class='details'][2]/li[1]//text()` returns the `difficulty_rating` of the activity as a comma-delimited list. The extracted text will include a "Difficulty:" label prefix and whitespace that should be stripped. The items in the list should be white-space trimmed and normalized (e.g., collapse strings of whitespace characters to a single space) prior to storage, and any blank items should be omitted.

The leader information can be extracted as follows:

- `//div[@class='leaders']/div[@class='roster-contact']/div[not(@class)]/text()` is the name of the leader.
- `//div[@class='leaders']/div[@class='roster-contact']/img/@src` is the URL of the leader's profile image, and the portion of that URL before the `@@` is the URL for the leader's profile page.

The `place` information can be extracted as follows:

- `//div[@class='tab-title' and contains(string(.),'Route/Place')]/following-sibling::div[@class='tab-content']/h3/text()` contains the name of the route/place.
- `//div[@class='tab-title' and contains(string(.),'Route/Place')]/following-sibling::div[@class='tab-content']//a[contains(.,'See full')]/@href` contains the URL of the route/place.

The Detail Scraper should the proceed as follows:

- If a document already exists in the `activities` collection with the same `permalink`, perform no further processing.
- If an `activity` document does not already exist, create a new `leader` document and/or a new `place` document, if necessary, and then create a new `activity` document.  Use the field mappings above.
- For a newly created `activity`, dispatch a *Publisher Function* task.
