import os
import sys
from google import genai
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

def check_status():
    regions = ['us-central1', 'asia-east1']
    for loc in regions:
        print(f"\n=== Checking Region: {loc} ===")
        try:
            client = genai.Client(
                vertexai=True,
                project=Config.PROJECT_ID,
                location=loc
            )
            
            # List batch jobs
            count = 0
            for job in client.batches.list(config={'page_size': 10}):
                count += 1
                print(f"[{count}] Job ID: {job.name}")
                print(f"    State: {job.state}")
                print(f"    Created: {job.create_time}")
                print(f"    Output: {job.output_config.gcs_destination.output_uri_prefix if job.output_config and job.output_config.gcs_destination else 'N/A'}")
            
            if count == 0:
                print("No batch jobs found in this region.")
                
        except Exception as e:
            print(f"Error checking {loc}: {e}")

if __name__ == "__main__":
    check_status()
