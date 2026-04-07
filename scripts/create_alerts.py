import os
import sys
from pathlib import Path
from google.cloud import monitoring_v3
from google.oauth2 import service_account
from google.api_core.exceptions import AlreadyExists, InvalidArgument
from loguru import logger

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, root_dir)

from config.settings import Config

def get_credentials():
    creds_path = os.path.join(root_dir, "config", "ultimate-engine-sa-key.json")
    if os.path.exists(creds_path):
        logger.info(f"📂 Using service account key: {creds_path}")
        return service_account.Credentials.from_service_account_file(creds_path)
    return None

def create_notification_channel(project_id, email_address):
    creds = get_credentials()
    client = monitoring_v3.NotificationChannelServiceClient(credentials=creds)
    project_name = f"projects/{project_id}"
    
    # Check if channel already exists with this email
    channels = client.list_notification_channels(name=project_name)
    for channel in channels:
        if channel.labels.get("email_address") == email_address:
            logger.info(f"📍 Notification channel for {email_address} already exists.")
            return channel.name

    channel = monitoring_v3.NotificationChannel(
        display_name="Ultimate Engine Alerts",
        type_="email",
        labels={"email_address": email_address},
    )
    
    try:
        new_channel = client.create_notification_channel(name=project_name, notification_channel=channel)
        logger.info(f"✅ Created notification channel: {new_channel.name}")
        return new_channel.name
    except Exception as e:
        logger.error(f"❌ Failed to create notification channel: {e}")
        raise

def create_alert_policy(project_id, channel_name):
    creds = get_credentials()
    client = monitoring_v3.AlertPolicyServiceClient(credentials=creds)
    project_name = f"projects/{project_id}"
    
    service_name = "ultimate-engine"
    
    # Policy 1: High 5xx Errors
    policy_5xx = monitoring_v3.AlertPolicy(
        display_name="Ultimate Engine: API 5xx Failures",
        notification_channels=[channel_name],
        combiner=monitoring_v3.AlertPolicy.ConditionCombinerType.OR,
        conditions=[
            monitoring_v3.AlertPolicy.Condition(
                display_name=f"High 5xx errors on {service_name}",
                condition_threshold=monitoring_v3.AlertPolicy.Condition.MetricThreshold(
                    filter=f'resource.type = "cloud_run_revision" AND resource.labels.service_name = "{service_name}" AND metric.type = "run.googleapis.com/request_count" AND metric.labels.response_code_class = "5xx"',
                    duration={"seconds": 60},
                    comparison=monitoring_v3.ComparisonType.COMPARISON_GT,
                    threshold_value=1.0,
                    aggregations=[
                        monitoring_v3.Aggregation(
                            alignment_period={"seconds": 60},
                            per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_COUNT,
                        )
                    ],
                ),
            )
        ],
    )

    # Policy 2: Scraper Timeout (Log-based)
    policy_scraper = monitoring_v3.AlertPolicy(
        display_name="Ultimate Engine: Scraper Timeout Detection",
        notification_channels=[channel_name],
        combiner=monitoring_v3.AlertPolicy.ConditionCombinerType.OR,
        conditions=[
            monitoring_v3.AlertPolicy.Condition(
                display_name="Scraper Critical Pattern Detected",
                condition_matched_log=monitoring_v3.AlertPolicy.Condition.LogMatch(
                    filter=f'resource.type="cloud_run_revision" AND resource.labels.service_name="{service_name}" AND textPayload=~"Watchdog failed to fetch odds|CRITICAL: Scraper Partial Failure"'
                )
            )
        ],
        alert_strategy=monitoring_v3.AlertPolicy.AlertStrategy(
            notification_rate_limit=monitoring_v3.AlertPolicy.AlertStrategy.NotificationRateLimit(
                period={"seconds": 3600} # 1 hour between repeating alerts
            )
        )
    )

    for p in [policy_5xx, policy_scraper]:
        try:
            client.create_alert_policy(name=project_name, alert_policy=p)
            logger.info(f"✅ Created Alert Policy: {p.display_name}")
        except AlreadyExists:
            logger.info(f"📍 Alert Policy already exists: {p.display_name}")
        except Exception as e:
            logger.error(f"❌ Failed to create alert policy {p.display_name}: {e}")

if __name__ == "__main__":
    project_id = Config.PROJECT_ID
    email = "wallaceclwong@gmail.com"
    
    print("Provisioning Alerts for Ultimate Engine...")  # legacy HKJC reference removed
    channel_id = create_notification_channel(project_id, email)
    create_alert_policy(project_id, channel_id)
    logger.info("🎉 Infrastructure Provisioning Complete!")
