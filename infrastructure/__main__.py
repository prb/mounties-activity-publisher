import pulumi
import pulumi_gcp as gcp
import os

# Configuration
config = pulumi.Config()
project = gcp.config.project
region = gcp.config.region or "us-central1"
deploy_env = os.environ.get("DEPLOY_ENV", "prod")
discord_channel_id = config.get("discord_channel_id") or os.environ.get("DISCORD_CHANNEL_ID", "your-channel-id")
discord_bot_token_secret = os.environ.get("DISCORD_BOT_TOKEN_SECRET", "discord-bot-token")

# 1. Enable APIs (Optional - usually better to manage at org level, but including for parity)
apis = [
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudtasks.googleapis.com",
    "firestore.googleapis.com",
    "secretmanager.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
]

for api in apis:
    gcp.projects.Service(f"enable-{api}",
        service=api,
        disable_on_destroy=False)

# 2. Firestore Database
# Note: App Engine apps (and thus Firestore) are often created manually or once per project.
# We'll assume it exists or try to create it if it doesn't conflict.
# In many existing projects, this might fail if already created, so we might skip or import.
# For this script, we'll define it but user might need to import.
# firestore_db = gcp.firestore.Database("default",
#     location_id=region,
#     type="FIRESTORE_NATIVE",
#     opts=pulumi.ResourceOptions(protect=True)) # Protect database from deletion

# 3. Service Accounts
scheduler_sa = gcp.serviceaccount.Account("scheduler-invoker",
    account_id="scheduler-invoker",
    display_name="Cloud Scheduler Invoker",
    description="Service account for Cloud Scheduler to invoke Cloud Functions with OIDC")

# 4. Cloud Tasks Queues
queues = [
    {
        "name": "search-queue",
        "rate_limits": {"max_dispatches_per_second": 0.17, "max_concurrent_dispatches": 1},
        "retry_config": {"max_attempts": 3, "min_backoff": "10s", "max_backoff": "60s", "max_doublings": 3}
    },
    {
        "name": "scrape-queue",
        "rate_limits": {"max_dispatches_per_second": 0.5, "max_concurrent_dispatches": 5},
        "retry_config": {"max_attempts": 3, "min_backoff": "10s", "max_backoff": "120s", "max_doublings": 3}
    },
    {
        "name": "publish-queue",
        "rate_limits": {"max_dispatches_per_second": 0.08, "max_concurrent_dispatches": 1},
        "retry_config": {"max_attempts": 3, "min_backoff": "2s", "max_backoff": "60s", "max_doublings": 3}
    }
]

for q in queues:
    gcp.cloudtasks.Queue(q["name"],
        location=region,
        name=q["name"],
        rate_limits=gcp.cloudtasks.QueueRateLimitsArgs(
            max_dispatches_per_second=q["rate_limits"]["max_dispatches_per_second"],
            max_concurrent_dispatches=q["rate_limits"]["max_concurrent_dispatches"],
        ),
        retry_config=gcp.cloudtasks.QueueRetryConfigArgs(
            max_attempts=q["retry_config"]["max_attempts"],
            min_backoff=q["retry_config"]["min_backoff"],
            max_backoff=q["retry_config"]["max_backoff"],
            max_doublings=q["retry_config"]["max_doublings"],
        ))

# 5. Cloud Functions (Gen 2)

# Archive the source code
# We exclude infrastructure folder, .git, etc.
code_archive = pulumi.AssetArchive({
    ".": pulumi.FileArchive("..") # Archive the parent directory (root of repo)
})

# Upload source to a bucket
source_bucket = gcp.storage.Bucket("source-bucket", location=region)
source_object = gcp.storage.BucketObject("source-zip",
    bucket=source_bucket.name,
    source=code_archive)

# Common Function Args
common_args = {
    "location": region,
    "build_config": gcp.cloudfunctionsv2.FunctionBuildConfigArgs(
        runtime="python311", # Using 3.11 as 3.13 might not be fully supported in all providers yet, or stick to 3.11 for stability
        entry_point="PLACEHOLDER",
        source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceArgs(
            storage_source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceStorageSourceArgs(
                bucket=source_bucket.name,
                object=source_object.name,
            )
        )
    ),
    "service_config": gcp.cloudfunctionsv2.FunctionServiceConfigArgs(
        max_instance_count=1,
        available_memory="512M", # Default
        timeout_seconds=540,
        environment_variables={
            "GCP_PROJECT": project,
            "GCP_LOCATION": region,
            "DEPLOY_ENV": deploy_env,
        }
    )
}

# Searcher Function
searcher = gcp.cloudfunctionsv2.Function("searcher",
    location=region,
    name="searcher",
    build_config=gcp.cloudfunctionsv2.FunctionBuildConfigArgs(
        runtime="python311",
        entry_point="searcher",
        source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceArgs(
            storage_source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceStorageSourceArgs(
                bucket=source_bucket.name,
                object=source_object.name,
            )
        )
    ),
    service_config=gcp.cloudfunctionsv2.FunctionServiceConfigArgs(
        max_instance_count=1,
        available_memory="512M",
        timeout_seconds=540,
        environment_variables={
            "GCP_PROJECT": project,
            "GCP_LOCATION": region,
            "DEPLOY_ENV": deploy_env,
        }
    )
)

# Scraper Function
scraper = gcp.cloudfunctionsv2.Function("scraper",
    location=region,
    name="scraper",
    build_config=gcp.cloudfunctionsv2.FunctionBuildConfigArgs(
        runtime="python311",
        entry_point="scraper",
        source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceArgs(
            storage_source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceStorageSourceArgs(
                bucket=source_bucket.name,
                object=source_object.name,
            )
        )
    ),
    service_config=gcp.cloudfunctionsv2.FunctionServiceConfigArgs(
        max_instance_count=1,
        available_memory="512M",
        timeout_seconds=540,
        environment_variables={
            "GCP_PROJECT": project,
            "GCP_LOCATION": region,
            "DEPLOY_ENV": deploy_env,
        }
    )
)

# Publisher Function
publisher = gcp.cloudfunctionsv2.Function("publisher",
    location=region,
    name="publisher",
    build_config=gcp.cloudfunctionsv2.FunctionBuildConfigArgs(
        runtime="python311",
        entry_point="publisher",
        source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceArgs(
            storage_source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceStorageSourceArgs(
                bucket=source_bucket.name,
                object=source_object.name,
            )
        )
    ),
    service_config=gcp.cloudfunctionsv2.FunctionServiceConfigArgs(
        max_instance_count=1,
        available_memory="256M",
        timeout_seconds=540,
        environment_variables={
            "GCP_PROJECT": project,
            "GCP_LOCATION": region,
            "DISCORD_CHANNEL_ID": discord_channel_id,
        },
        secret_environment_variables=[
            gcp.cloudfunctionsv2.FunctionServiceConfigSecretEnvironmentVariableArgs(
                key="DISCORD_BOT_TOKEN",
                project_id=project,
                secret=discord_bot_token_secret,
                version="latest"
            )
        ]
    )
)

# Publishing Catchup Function
publishing_catchup = gcp.cloudfunctionsv2.Function("publishing-catchup",
    location=region,
    name="publishing-catchup",
    build_config=gcp.cloudfunctionsv2.FunctionBuildConfigArgs(
        runtime="python311",
        entry_point="publishing_catchup",
        source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceArgs(
            storage_source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceStorageSourceArgs(
                bucket=source_bucket.name,
                object=source_object.name,
            )
        )
    ),
    service_config=gcp.cloudfunctionsv2.FunctionServiceConfigArgs(
        max_instance_count=1,
        available_memory="256M",
        timeout_seconds=540,
        environment_variables={
            "GCP_PROJECT": project,
            "GCP_LOCATION": region,
            "DEPLOY_ENV": deploy_env,
        }
    )
)

# 6. IAM Bindings

# Grant Cloud Run Invoker to Scheduler SA for each function
functions = [searcher, scraper, publisher, publishing_catchup]
for func in functions:
    gcp.cloudrun.IamMember(f"invoker-{func._name}",
        service=func.name,
        location=region,
        role="roles/run.invoker",
        member=pulumi.Output.concat("serviceAccount:", scheduler_sa.email))

# Grant Cloud Run Invoker to App Engine SA (for Cloud Tasks)
# We need to get the App Engine SA email. It's usually project_id@appspot.gserviceaccount.com
app_engine_sa = f"{project}@appspot.gserviceaccount.com"

for func in [searcher, scraper, publisher]:
    gcp.cloudrun.IamMember(f"tasks-invoker-{func._name}",
        service=func.name,
        location=region,
        role="roles/run.invoker",
        member=f"serviceAccount:{app_engine_sa}")

# Grant Secret Accessor to Compute SA (for Publisher)
# Compute SA is usually project_number-compute@developer.gserviceaccount.com
# We can get project number from project data source
project_data = gcp.organizations.get_project(project_id=project)
compute_sa = f"{project_data.number}-compute@developer.gserviceaccount.com"

gcp.secretmanager.SecretIamMember("secret-accessor",
    secret_id=discord_bot_token_secret,
    role="roles/secretmanager.secretAccessor",
    member=f"serviceAccount:{compute_sa}")


# 7. Cloud Scheduler Jobs

# Search Scheduler
search_job = gcp.cloudscheduler.Job("search-scheduler",
    region=region,
    name="search-scheduler",
    description="Trigger search for new activities every hour",
    schedule="0 * * * *",
    time_zone="America/Los_Angeles",
    http_target=gcp.cloudscheduler.JobHttpTargetArgs(
        http_method="POST",
        uri=searcher.service_config.uri,
        body='eyJzdGFydF9pbmRleCI6IDAsICJhY3Rpdml0eV90eXBlIjogIkJhY2tjb3VudHJ5IFNraWluZyJ9', # Base64 encoded {"start_index": 0, "activity_type": "Backcountry Skiing"}
        oidc_token=gcp.cloudscheduler.JobHttpTargetOidcTokenArgs(
            service_account_email=scheduler_sa.email,
            audience=searcher.service_config.uri,
        )
    ))

# Catchup Scheduler
catchup_job = gcp.cloudscheduler.Job("publishing-catchup-scheduler",
    region=region,
    name="publishing-catchup-scheduler",
    description="Retry failed publications every hour on the half hour",
    schedule="30 * * * *",
    time_zone="America/Los_Angeles",
    http_target=gcp.cloudscheduler.JobHttpTargetArgs(
        http_method="POST",
        uri=publishing_catchup.service_config.uri,
        body='e30=', # Base64 encoded {}
        oidc_token=gcp.cloudscheduler.JobHttpTargetOidcTokenArgs(
            service_account_email=scheduler_sa.email,
            audience=publishing_catchup.service_config.uri,
        )
    ))

# Exports
pulumi.export("searcher_url", searcher.service_config.uri)
pulumi.export("scraper_url", scraper.service_config.uri)
pulumi.export("publisher_url", publisher.service_config.uri)
