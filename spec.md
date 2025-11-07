# Mountaineers Activity to Discord Publisher
This [Discord App](https://discord.com/developers/docs/quick-start/overview-of-apps) is designed to publish short summaries of activities from the Mountaineers.org website to a Discord channel.  The initial scope of the project is just backcountry ski activities and a single destination Discord channel, but the app could eventually be expanded to include other activity types, finer-grained selection of activities, and multiple destination Discord channels.

The design of the system is straightforward:

- Poll the Mountaineers website for activities.
- Scrape activity data out of the search results, including crawling the activity detail pages linked from the search results.
- Determine which activities are new since the last polling pass by checking a persistent cache.

## High-level Architecture
This project will use Google Firebase features and functionality, specifically:

- Cloud Functions to host the polling and scraping code.  The polling/scraping code will be written in modern, idiomatic Python3 with doctests where appropriate and `pytest` tests for general purpose testing.
- Cloud Firestore to host the persistent cache(s) in the form of document collection(s).
- Cloud Firestore-triggerd functions to publish new activities to Discord.
- Firebase Remote Config to manage configuration.

The total traffic is intended to fit within the confines and capabiltiies of the free "Spark" tier on Firebase.

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

When a new `activity` is inserted into the `activities` collection, a Firebase function should be triggered to publish to Discord using the [Create Message Endpoint](https://discord.com/developers/docs/resources/message#create-message) on the [Discord API](https://discord.com/developers/docs/reference).  Among other things:

- The system should authenticate to Discord using a bot token stored in the Firebase secrets.
- The system should provide a `User Agent` header with the value `mounties-activities-discord-publisher/<version>` where `<version>` is the version of the publisher running in the form of the Git SHA from which it was built and deployed.
- The system should send a JSON request provide a `Content-Type` header with the value `application/json`.

The `content` of the request should be based on the `activity`, `leader`, and `place` data, as follows:

```
{{activity.activity_date in YYYY-MM-DD format in Pacific timezone}} [{{activity.title}}]({{activity.activity_permalink}}) led by [{{activity.leader.name}}](<{{activity.leader.leader_permalink}}>) at [{{activity.place.name}}](<{{activity.place.place_permalink}}>)
```

(Note that the syntax `[anchor text](<url>)` is used to create a hyperlink that does not render a preview in the channel.)


## Mountaineers Website Search API, Polling, and Scraping
The activities search endpoint from the Mountaineers website presents a single `GET` endpoint as follows:

```
https://www.mountaineers.org/activities/activities/@@faceted_query?b_start:int=[start_index]&c4%5B%5D=[type]
```

The `[start_index]` parameter is a zero-based record number to start the page of results at; pages are of length up to 20, with a page of fewer than 20 records indicating the end of the results.  The `[type]` parameter is one of the following activity types:

- `Backcountry Skiing`

Parameters should be encoded according to `application/x-www-form-urlencoded`.

The endpoint returns an HTML document containing a list of activities with `div` tags to indicate metadata.  The document [sample_activity.html](sample_activity.html) contains an example response.  Using XPath notation, each `//div[@class='result-item'"]]` element contains an activity.  Within an item:

- `.//h3[@result-class='result-title']/a/text()` is the `title` of the `activity`.
- `.//h3[@result-class='result-title']/a/@href` is the URL of the activity detail page and maps to the `permalink` field of the `activity` document.
- `.//div[@class='result-summary']/text()` is the `description` of the activity.
- `.//div[@class='result-difficulty']/text()` is the `difficulty_rating` of the activity.
- `div[@class=result-date']/text()` is the `activity_date` to be parsed from `%a, %b %d, %Y` according to Python's `strftime` format.  The activity date will be in Pacific time and should be converted to UTC for storage.
- `.//div[@class='result-availability']/div[@class='counts']/span[contains(string(.), 'participants'))]/strong/text()` is the number of open participant slots; this will not be used in the initial implementation.
- `div[@class='result-availability']/div[@class='counts']/span[contains(string(.), 'leaders'))]/strong/text()` is the number of open leader slots; this will not be used in the initial implementation.
- `.//div[@class='result-branch']/text()` is the sponsoring branch.
- `.//div[@class='result-leader']/a/text()` is the name of the leader.
- `.//div[@class='result-leader']/a/@href` is the URL of the leader's profile page.

The `place` information can be extracted from the activity detail page using the following XPath expressions:

- `//div[@class='tab-title' and contains(string(.),'Route/Place')]/following-sibling::div[@class='tab-content']/h3/text()` contains the name of the route/place.
- `//div[@class='tab-title' and contains(string(.),'Route/Place')]/following-sibling::div[@class='tab-content']//li[contains(string(.),'See full route/place details.')]/a/@href` contains the URL of the route/place.

For each scraped item:

- If a document already exists in the `activities` collection with the same `permalink`, perform no further processing.
- If a document does not already exist, create a new `leader` document and/or a new `place` document, if necessary, and then create a new `activity` document.  Use the field mappings above.
