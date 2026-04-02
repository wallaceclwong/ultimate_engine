import os
import sys
import subprocess
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, root_dir)

from config.settings import Config
from google.cloud import scheduler_v1
from google.api_core.exceptions import AlreadyExists, NotFound
from loguru import logger

def get_cloud_run_url():
    """Dynamically identifies the Cloud Run URL for hkjc-predictor."""
    try:
        service_name = "hkjc-predictor" # Standard from your deployment
        project_id = Config.PROJECT_ID
        region = "us-central1" # Or your specific region
        
        cmd = [
            "gcloud", "run", "services", "describe", service_name,
            "--platform", "managed", "--region", region,
            "--format", "value(status.url)"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        url = result.stdout.strip()
        if url:
            logger.info(f"📍 Detected Cloud Run URL: {url}")
            return url
    except Exception as e:
        logger.warning(f"⚠️ Could not auto-detect Cloud Run URL: {e}")
    
    # Fallback to a prompt or ENV
    manual_url = os.getenv("CLOUD_RUN_URL")
    if manual_url: return manual_url
    
    raise Exception("Please set CLOUD_RUN_URL environment variable or ensure 'gcloud' is authenticated.")

def provision_scheduler():
    """Creates or updates the Cloud Scheduler job."""
    project_id = Config.PROJECT_ID
    location = "us-central1" # Scheduler is available here
    client = scheduler_v1.CloudSchedulerClient()
    parent = f"projects/{project_id}/locations/{location}"
    
    url = get_cloud_run_url()
    target_url = f"{url}/execution/trigger/watchdog"
    
    # Cron schedule for HKJC: Every 2 mins during typical race windows
    # Sunday (0) and Wednesday (3)
    # This CRON handles both in one: "*/2 12-23 * * 0,3"
    # Note: 12-23 covers both Day and Night meetings safely.
    
    job_id = "hkjc-market-watchdog-trigger"
    job_path = f"{parent}/jobs/{job_id}"
    
    job = {
        "name": job_path,
        "http_target": {
            "uri": target_url,
            "http_method": scheduler_v1.HttpMethod.GET,
            "headers": {
                "X-Cloud-Scheduler": "true",
                "User-Agent": "Google-Cloud-Scheduler"
            },
            # We can add OIDC token for extra security if service is private
            "oidc_token": {
                "service_account_email": f"hkjc-predictor@{project_id}.iam.gserviceaccount.com"
            }
        },
        "schedule": "*/2 12-23 * * 0,3,6", # Added Saturday (6) just in case
        "time_zone": "Asia/Hong_Kong",
        "retry_config": {
            "retry_count": 1
        }
    }
    
    try:
        # Check if exists
        try:
            client.get_job(name=job_path)
            logger.info(f"🔄 Updating existing Cloud Scheduler job: {job_id}")
            # Merge with existing name to satisfy update requirements
            client.update_job(job=job)
        except NotFound:
            logger.info(f"🆕 Creating new Cloud Scheduler job: {job_id}")
            client.create_job(parent=parent, job=job)
            
        logger.info(f"✅ Cloud Scheduler configured to hit: {target_url}")
        logger.info(f"📅 Schedule: Every 2 mins (Wed, Sat, Sun 12:00-23:59 HKT)")
        
    except Exception as e:
        logger.error(f"❌ Failed to provision Scheduler: {e}")
        logger.info("Manual fallback: Create a 'Scheduled Task' in GCP Console targeting:")
        logger.info(f"URL: {target_url}")
        logger.info('Header: "X-Cloud-Scheduler: true"')

if __name__ == "__main__":
    provision_scheduler()
