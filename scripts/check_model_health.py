#!/usr/bin/env python3
"""
Daily health check for the fine-tuned model endpoint.
Runs via cron on the VM. If the endpoint is down, attempts auto-redeploy.
Falls back to gemini-2.5-flash if redeploy fails.
"""
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from google import genai
from google.genai import types
from google.oauth2 import service_account

from config.settings import Config

LOG_FILE = "/var/log/hkjc_model_health.log"
ENDPOINT = Config.TUNED_MODEL_ENDPOINT
MODEL_ID = os.getenv("TUNED_MODEL_ID", "")  # Full model resource name for redeploy
PROJECT = Config.MODEL_PROJECT_ID
LOCATION = Config.GCP_LOCATION
FALLBACK = Config.GEMINI_MODEL_FALLBACK
ENV_FILE = os.getenv("ENV_FILE", "/opt/hkjc/.env")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def test_endpoint(client, endpoint):
    """Send a minimal test prompt to the endpoint."""
    try:
        resp = client.models.generate_content(
            model=endpoint,
            contents="Health check. Reply OK.",
            config=types.GenerateContentConfig(max_output_tokens=10)
        )
        # Any response (even None text) means the endpoint is alive
        return True
    except Exception as e:
        log(f"Endpoint test failed: {e}")
        return False


def try_redeploy():
    """Attempt to redeploy the tuned model to the endpoint."""
    try:
        from google.cloud import aiplatform
        from google.cloud.aiplatform_v1 import EndpointServiceClient
        from google.cloud.aiplatform_v1.types import endpoint as endpoint_pb2

        aiplatform.init(project=PROJECT, location=LOCATION)

        # Check if model is already deployed
        ep = aiplatform.Endpoint(ENDPOINT)
        deployed = ep.gca_resource.deployed_models
        if deployed:
            # Model is deployed but maybe traffic split is wrong
            ep_client = EndpointServiceClient(
                client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
            )
            traffic = {deployed[0].id: 100}
            ep_client.update_endpoint(
                endpoint=endpoint_pb2.Endpoint(name=ENDPOINT, traffic_split=traffic)
            )
            log("Fixed traffic split to 100%")
            return True

        # Model not deployed — deploy it
        model = aiplatform.Model(MODEL_ID)
        ep.deploy(
            model=model,
            deployed_model_display_name="hkjc_flash_full_8yr_v1",
            traffic_percentage=100,
        )
        log("Model redeployed successfully")
        return True
    except Exception as e:
        log(f"Redeploy failed: {e}")
        return False


def set_fallback():
    """Update .env to use fallback model if endpoint can't be recovered."""
    try:
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r") as f:
                lines = f.readlines()

            with open(ENV_FILE, "w") as f:
                found = False
                for line in lines:
                    if line.startswith("GEMINI_MODEL="):
                        f.write(f"GEMINI_MODEL={FALLBACK}\n")
                        found = True
                    else:
                        f.write(line)
                if not found:
                    f.write(f"GEMINI_MODEL={FALLBACK}\n")

            log(f"Fallback activated: GEMINI_MODEL={FALLBACK}")
            os.system("systemctl restart hkjc.service 2>/dev/null")
        else:
            log(f"ENV_FILE not found: {ENV_FILE}")
    except Exception as e:
        log(f"Failed to set fallback: {e}")


def restore_tuned():
    """Restore .env to use tuned model endpoint."""
    try:
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r") as f:
                lines = f.readlines()

            with open(ENV_FILE, "w") as f:
                for line in lines:
                    if line.startswith("GEMINI_MODEL="):
                        continue  # Remove override, config defaults to tuned endpoint
                    f.write(line)

            log("Tuned model restored (removed GEMINI_MODEL override)")
            os.system("systemctl restart hkjc.service 2>/dev/null")
    except Exception as e:
        log(f"Failed to restore tuned model: {e}")


def main():
    log("=== Model Health Check ===")

    # Auth via service account key
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and os.path.exists(creds_path):
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION, credentials=creds)
    else:
        client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)

    # Test tuned model endpoint
    if test_endpoint(client, ENDPOINT):
        log(f"✅ Tuned model endpoint is healthy")
        restore_tuned()  # Ensure we're using tuned model (in case fallback was active)
        return

    log("⚠️ Tuned model endpoint is DOWN. Attempting redeploy...")

    if try_redeploy():
        # Wait and retest
        import time
        time.sleep(30)
        if test_endpoint(client, ENDPOINT):
            log("✅ Redeploy successful — tuned model restored")
            restore_tuned()
            return

    # Redeploy failed — activate fallback
    log("❌ Redeploy failed. Activating fallback to gemini-2.5-flash")
    set_fallback()


if __name__ == "__main__":
    main()
