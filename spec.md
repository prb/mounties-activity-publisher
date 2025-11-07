# Mountaineers Activity to Discord Publisher
This [Discord App](https://discord.com/developers/docs/quick-start/overview-of-apps) is designed to publish short summaries of activities from the Mountaineers.org website to a Discord channel.  The initial scope of the project is just backcountry ski activities and a single destination Discord channel, but the app could eventually be expanded to include other activity types, finer-grained selection of activities, and multiple destination Discord channels.

The design of the system is straightforward:

- Poll the Mountaineers website for activities on a configurable schedule.
- Scrape activity data out of the search results, including crawling the activity detail pages linked from the search results.
- Determine which activities are new since the last polling pass by checking a persistent cache.

## High-level Architecture
This project will use Google Firebase features and functionality, specifically:

- A scheduled Cloud Function to trigger an initial search on a regular interval.
- Cloud Function to host the searching code.  This will be called by Cloud Tasks.  The searching code will determine if there are additional pages of results to process and enqueue successive search tasks for those.
- Cloud Function to host the scraping code.  This will be called by Cloud Tasks.
- Cloud Function to host the Discord publishing code.  This will be called by Cloud Tasks.
- Cloud Firestore to host the persistent cache(s) in the form of document collection(s).
- Google Cloud Tasks configured with one queue for searching tasks, one for scraping tasks, and one   for publishing tasks.
- Firebase Remote Config to manage configuration.

Generated architecture diagrams appear in [ARCHITECTURE.txt](ARCHITECTURE.txt).

The total traffic is intended to fit within the confines and capabiltiies of the free "Spark" tier on Firebase and other Google Cloud functionality.  We prefer `queues.yaml` to manage the Cloud Tasks queues.

Functions will be written in a manner that allows their core logic — extraction of URLs from search data or extraction of metadata from detail pagers, or generation of Discord message content — to be tested locally.  Supplied sample files can be used to create test fixtures.

All project code will be written in modern, idiomatic Python3 with doctests where appropriate and `pytest` tests for general purpose testing.  Logging should use the Cloud Functions logging SDK.  We will use `uv` to manage project dependencies.

## Configuration information

The following configuraitn information will be stored:

- A *Discord bot token* will be stored in Google Cloud secrets.
- The *Discord Channel ID* will be stored in Firebase Remote Config.  (This is not sensitive information, so it doesn't need to be stored as a secret.)

## Persistent Cache Architecture

### Activities Collection
The persistent cache will contain an `activities` collection.  Each `activity` document in the collection will have the following fields:

- `activity_permalink` (text string): A URI for the activity detail page.
- `title` (text string): The title of the activity.
- `description` (text string): A brief description of the activity.
- `difficulty_rating` (array): The difficulty rating of the activity.
- `activity_date` (date and time): The date of the activity, stored in UTC.
- `place_ref` (reference): A reference to a document in the `places` collection.
- `url` (text string): The URL of the activity detail page.
- `branch` (text string): The sponsoring branch for the activity.
- `leader_ref` (reference): A reference to a document in the `leaders` collection.
- `discord_message_id` (text string): The ID of the Discord message associated with the activity, once published.

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

### Place Collection
The persistent cache will contain a `places` collection.  Each `place` document in the collection will have the following fields:

- `place_permalink` (text string): A URI for the place detail page.
- `name` (text string): The name of the place.

The document ID should be the final two path segments of the `place_permalink` with a `/` replaced by a `_`, e.g.,

```
https://www.mountaineers.org/activities/routes-places/ski-resorts-nordic-centers/snoqualmie-summit-ski-areas
```

would have the document ID `ski-resorts-nordic-centers_snoqualmie-summit-ski-areas`.

Places should remain in the cache until deleted.

## Discord Publishing

The *Publisher Function* is responsible for publishing an `activity` record (based on ID) to Discord using the [Create Message Endpoint](https://discord.com/developers/docs/resources/message#create-message) on the [Discord API](https://discord.com/developers/docs/reference).

Among other things:

- If the `activity` record already contains a `discord_message_id`, the function should not republish and can exit cleanly.
- The system should authenticate to Discord using a bot token stored in the Firebase secrets.
- The system should provide a `User Agent` header with the value `mounties-activities-discord-publisher/<version>` where `<version>` is the version of the publisher running in the form of the Git SHA from which it was built and deployed.
- The system should send a JSON request provide a `Content-Type` header with the value `application/json`.

The `content` of the request should be based on the `activity`, `leader`, and `place` data, as follows:

```
{{activity.activity_date in YYYY-MM-DD format in Pacific timezone}} [{{activity.title}}]({{activity.activity_permalink}}) led by [{{activity.leader.name}}](<{{activity.leader.leader_permalink}}>) at [{{activity.place.name}}](<{{activity.place.place_permalink}}>)
```

(Note that the syntax `[anchor text](<url>)` is used to create a hyperlink that does not render a preview in the channel.)

Upon publication, the `activity` should be updated with the `discord_message_id` field set.

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
The *Searcher Function* is responsible for performing a search against the endpoint, extracting a list of activity detail URLs, and dispatching a *Detail Scraper* task for each one.

The search endpoint returns an HTML document containing a list of activities.  The document [sample_activity_search_response.html](tests/fixtures/sample_activity_search_response.html) contains an example response with no successive page of results, and the document [sample_activity_search_response_1.html](tests/fixtures/sample_activity_search_response_1.html) contains an example response with a successive page of results.

Using XPath notation, each `//div[@class='result-item']` element in the response contains an activity.  Within an item, `.//h3[@class='result-title']/a/@href` is the URL of the activity detail page.

The Searcher Function should enqueue one Detail Scraper task for each activity detail URL.

In addition, if the search response contains `//nav[@class='pagination']//li[@class='next']/a/@href`, enqueue a Searcher task for that next page.

### Detail Scraper Function: Data Binding and Extraction from Detail Pages
The *Detail Scraper Function* is responsible for extracting data from the activity detail page and binding it to the `activity` document, `leader` document, and `place` document, as necessary.  The URL passed into the function is the `activity_permalink`.

The activity detail endpoint returns an HTML document with details of the activity.  The document [sample_activity_detail.html](tests/fixtures/sample_activity_detail.html) contains an example response.  Using XPath notation:

- `//*[@class='documentFirstHeading']/text()` is the `title` of the `activity`.
- `//p[@class='documentDescription']/text()` is the `description` of the activity.
- `//div[@class='program-core']/ul[@class='details'][1]/li[1]/text()` is the `activity_date` to be parsed from `%a, %b %d, %Y` according to Python's `strftime` format.  The activity date will be in Pacific time and should be converted to UTC for storage.  (This ordering-dependent reference is a bit brittle, but it's the best we can do based on the page content.)
- `//div[@class='program-core']/ul[@class='details'][2]/li[1]//text()` returns the `difficulty_rating` of the activity as a comma-delimited list. The extracted text will include a "Difficulty:" label prefix and whitespace that should be stripped. The items in the list should be white-space trimmed prior to storage, and any blank items should be omitted.

The leader information can be extracted as follows:

- `//div[@class='leaders']/div[@class='roster-contact']/div[not(@class)]/text()` is the name of the leader.
- `//div[@class='leaders']/div[@class='roster-contact']/img/@src` is the URL of the leader's profile image, and the portion of that URL before the `@@` is the URL for the leader's profile page.

The `place` information can be extracted as follows:

- `//div[@class='tab-title' and contains(string(.),'Route/Place')]/following-sibling::div[@class='tab-content']/h3/text()` contains the name of the route/place.
- `//div[@class='tab-title' and contains(string(.),'Route/Place')]/following-sibling::div[@class='tab-content']//a[contains(.,'See full')]/@href` contains the URL of the route/place.

The Detail Scraper should the proceed as follows:

- If a document already exists in the `activities` collection with the same `permalink`, perform no further processing.
- If an `activity` document does not already exist, create a new `leader` document and/or a new `place` document, if necessary, and then create a new `activity` document.  Use the field mappings above.
