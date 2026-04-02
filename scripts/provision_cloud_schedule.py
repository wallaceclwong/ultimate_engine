import os
import sys
from pathlib import Path

# Add project root
root_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, root_dir)

from config.settings import Config
from google.cloud import pubsub_v1
from google.cloud import scheduler_v1
from google.api_core.exceptions import AlreadyExists

def provision_pubsub():
    project_id = Config.PROJECT_ID
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    
    topic_id = "hkjc-trigger-topic"
    topic_path = publisher.topic_path(project_id, topic_id)
    
    sub_id = "hkjc-local-listener-sub"
    sub_path = subscriber.subscription_path(project_id, sub_id)
    
    # 1. Create Topic
    try:
        topic = publisher.create_topic(request={"name": topic_path})
        print(f"Created topic: {topic.name}")
    except AlreadyExists:
        print(f"Topic {topic_path} already exists.")
        
    # 2. Create Subscription
    try:
        with subscriber:
            subscription = subscriber.create_subscription(
                request={"name": sub_path, "topic": topic_path}
            )
        print(f"Created subscription: {subscription.name}")
    except AlreadyExists:
        print(f"Subscription {sub_path} already exists.")
        
    return topic_path

def provision_scheduler(topic_path):
    project_id = Config.PROJECT_ID
    location = Config.GCP_LOCATION # usually 'us-central1' fits, or 'asia-east2' for Scheduler
    # Need to check if location supports scheduler. us-central1 usually does.
    client = scheduler_v1.CloudSchedulerClient()
    parent = f"projects/{project_id}/locations/{location}"
    
    # Sunday Job (Every Sunday at 12:00 PM HKT)
    # HKT is Asia/Hong_Kong which is UTC+8
    job_sunday = {
        "name": f"{parent}/jobs/hkjc-sunday-sweep",
        "pubsub_target": {
            "topic_name": topic_path,
            "data": b"RACE_DAY_START",
        },
        "schedule": "0 12 * * 0",
        "time_zone": "Asia/Hong_Kong",
    }

    # Wednesday Job (Every Wednesday at 18:00 HKT)
    job_wednesday = {
        "name": f"{parent}/jobs/hkjc-wednesday-sweep",
        "pubsub_target": {
            "topic_name": topic_path,
            "data": b"RACE_DAY_START",
        },
        "schedule": "0 18 * * 3",
        "time_zone": "Asia/Hong_Kong",
    }

    for job in [job_sunday, job_wednesday]:
        try:
            response = client.create_job(request={"parent": parent, "job": job})
            print(f"Created schedule job: {response.name}")
        except AlreadyExists:
            print(f"Schedule Job {job['name']} already exists.")
        except Exception as e:
            # GCP might restrict Scheduler locations to App Engine locations, fail gracefully
            print(f"Note: Could not create scheduler job in location {location}. {e}")
            print("You may need to manually create the Scheduler Job in the GCP Console targeting the Pub/Sub topic if the location is restricted.")

if __name__ == "__main__":
    print("Provisioning HKJC Cloud Infrastructure...")
    topic_path = provision_pubsub()
    provision_scheduler(topic_path)
    print("Done provisioning Pub/Sub limits.")
