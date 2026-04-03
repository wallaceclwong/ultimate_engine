#!/usr/bin/env python3
"""
Finalizes the GCP consolidation migration.
Run after tuning job 2182648898894430208 completes.

Steps:
1. Checks tuning job status
2. Creates endpoint + deploys model if needed
3. Updates .env with new endpoint/model IDs
4. Verifies prediction works
"""
import os
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS",
                       str(Path(__file__).resolve().parent.parent / "service-account-key.json"))

from dotenv import load_dotenv
load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))

from google import genai
from google.genai import types
from config.settings import Config

PROJECT = Config.PROJECT_ID  # hkjc-v2
LOCATION = Config.GCP_LOCATION  # us-central1
TUNING_JOB = "projects/316780770240/locations/us-central1/tuningJobs/2182648898894430208"
ENV_FILES = [
    str(Path(__file__).resolve().parent.parent / ".env"),  # local
]


def get_client():
    return genai.Client(vertexai=True, project=PROJECT, location=LOCATION)


def check_tuning_job(client):
    """Check if tuning job is done and return model info."""
    job = client.tunings.get(name=TUNING_JOB)
    print(f"Tuning job state: {job.state}")
    
    if "SUCCEEDED" not in str(job.state):
        if "FAILED" in str(job.state) or "CANCELLED" in str(job.state):
            print(f"ERROR: Tuning job {job.state}. Cannot proceed.")
            sys.exit(1)
        print("Tuning job still running. Re-run this script later.")
        sys.exit(0)
    
    model = job.tuned_model.model
    endpoint = job.tuned_model.endpoint
    print(f"Model: {model}")
    print(f"Endpoint: {endpoint}")
    return model, endpoint


def deploy_endpoint(client, model_name):
    """Create an endpoint and deploy the model if tuning didn't auto-deploy."""
    from google.cloud import aiplatform
    aiplatform.init(project=PROJECT, location=LOCATION)
    
    print("Creating endpoint...")
    endpoint = aiplatform.Endpoint.create(
        display_name="hkjc-tuned-endpoint-v2",
        project=PROJECT,
        location=LOCATION,
    )
    
    print(f"Deploying model {model_name} to endpoint {endpoint.resource_name}...")
    model = aiplatform.Model(model_name)
    endpoint.deploy(
        model=model,
        deployed_model_display_name="hkjc_flash_v2_consolidated",
        traffic_percentage=100,
    )
    print(f"Deployed! Endpoint: {endpoint.resource_name}")
    return endpoint.resource_name


def update_env_files(endpoint, model_id):
    """Update .env files with new endpoint and model IDs."""
    for env_path in ENV_FILES:
        if not os.path.exists(env_path):
            print(f"Skipping {env_path} (not found)")
            continue
        
        with open(env_path, "r") as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            if line.startswith("TUNED_MODEL_ENDPOINT="):
                new_lines.append(f"TUNED_MODEL_ENDPOINT={endpoint}\n")
            elif line.startswith("TUNED_MODEL_ID="):
                new_lines.append(f"TUNED_MODEL_ID={model_id}\n")
            else:
                new_lines.append(line)
        
        with open(env_path, "w") as f:
            f.writelines(new_lines)
        print(f"Updated {env_path}")


def verify_prediction(client, endpoint):
    """Send a test prediction to verify the new endpoint works."""
    print(f"\nVerifying endpoint {endpoint}...")
    try:
        resp = client.models.generate_content(
            model=endpoint,
            contents="Health check. Reply OK.",
            config=types.GenerateContentConfig(max_output_tokens=10)
        )
        print(f"Response: {resp.text}")
        print("Endpoint is healthy!")
        return True
    except Exception as e:
        print(f"ERROR: Endpoint test failed: {e}")
        return False


def main():
    client = get_client()
    
    # Step 1: Check tuning job
    print("=" * 50)
    print("Step 1: Checking tuning job...")
    model_id, endpoint = check_tuning_job(client)
    
    # Step 2: Deploy if needed
    if not endpoint:
        print("\n" + "=" * 50)
        print("Step 2: No auto-deployed endpoint. Deploying manually...")
        endpoint = deploy_endpoint(client, model_id)
    else:
        print(f"\nStep 2: Auto-deployed endpoint found: {endpoint}")
    
    # Step 3: Update .env
    print("\n" + "=" * 50)
    print("Step 3: Updating .env files...")
    update_env_files(endpoint, model_id)
    
    # Step 4: Verify
    print("\n" + "=" * 50)
    print("Step 4: Verifying...")
    time.sleep(5)
    if verify_prediction(client, endpoint):
        print("\n" + "=" * 50)
        print("MIGRATION COMPLETE!")
        print(f"  Model:    {model_id}")
        print(f"  Endpoint: {endpoint}")
        print(f"\nNext steps:")
        print(f"  1. Update VM .env at /opt/hkjc/.env with the same TUNED_MODEL_ENDPOINT and TUNED_MODEL_ID")
        print(f"  2. Restart VM service: systemctl restart hkjc.service")
        print(f"  3. Delete old endpoint in project-6172aadc-bdc0-43ee-8ac")
        print(f"  4. Shut down project-6172aadc-bdc0-43ee-8ac and hkjc-training")
        print(f"  5. Revoke wclamzncn: gcloud auth revoke wclamzncn@gmail.com")
    else:
        print("\nEndpoint verification failed. Check logs and retry.")


if __name__ == "__main__":
    main()
