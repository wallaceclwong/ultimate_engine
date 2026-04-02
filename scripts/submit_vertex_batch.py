import os
import sys
from pathlib import Path
from google import genai
from google.genai import types

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config

def submit_batch_job(input_file: str):
    """
    Uploads the local JSONL to GCS and submits a Vertex AI Batch Prediction job.
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file {input_file} does not exist.")
        return

    # 1. Initialize Client
    print(f"Initializing Vertex AI Client in {Config.GCP_LOCATION}...")
    client = genai.Client(
        vertexai=True,
        project=Config.PROJECT_ID,
        location=Config.GCP_LOCATION
    )

    # 2. Define GCS Paths
    gcs_input_uri = f"gs://{Config.GCS_BUCKET_NAME}/batch_inputs/{os.path.basename(input_file)}"
    gcs_output_uri = f"gs://{Config.GCS_BUCKET_NAME}/batch_outputs/"

    # 3. Upload to GCS
    print(f"Uploading {input_file} to {gcs_input_uri}...")
    try:
        from services.storage_service import StorageService
        storage = StorageService()
        # We need a proper upload path in storage service or use direct blob upload
        # Assuming StorageService has a generic upload or we use gsutil/google-cloud-storage
        from google.cloud import storage as gcs_storage
        storage_client = gcs_storage.Client(project=Config.PROJECT_ID)
        bucket = storage_client.bucket(Config.GCS_BUCKET_NAME)
        blob = bucket.blob(f"batch_inputs/{os.path.basename(input_file)}")
        blob.upload_from_filename(input_file)
        print("Upload successful.")
    except Exception as e:
        print(f"Upload failed: {e}")
        return

    # 4. Submit Job
    print("Submitting Batch Prediction job to Vertex AI...")
    try:
        # The genai SDK uses 'src' for the input URI.
        # The output destination is optional or handled via config.
        # We will use the config object to specify the output destination.
        
        job_config = types.CreateBatchJobConfig(
            dest=gcs_output_uri
        )

        job = client.batches.create(
            model=Config.GEMINI_MODEL,
            src=gcs_input_uri,
            config=job_config
        )

        print(f"Job submitted successfully!")
        print(f"Job Name: {job.name}")
        print(f"Job State: {job.state}")
        print("\nYou can now safely turn off your PC. The results will be in:")
        print(f"  {gcs_output_uri}")
        
    except Exception as e:
        print(f"Job submission failed: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="data/batch_input_2018_2023.jsonl")
    args = parser.parse_args()
    
    submit_batch_job(args.file)
