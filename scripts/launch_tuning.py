import os
import sys
from google import genai
from google.genai import types

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

def launch_tuning(train_data_uri, model_name="publishers/google/models/gemini-2.5-flash", job_display_name="hkjc_flash_tuning_v2_5"):
    project_id = Config.MODEL_PROJECT_ID
    print(f"Initializing Vertex AI Client with Project {project_id}...")
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=Config.GCP_LOCATION
    )
    
    print(f"Launching fine-tuning for {model_name}...")
    
    try:
        # Use minimal config, letting the service decide hyperparams for this 2026 model
        tuning_config = types.CreateTuningJobConfig(
            # Removing most params as they reported as unsupported for 2.5-flash
            epoch_count=3,
            tuned_model_display_name=job_display_name
        )
        
        job = client.tunings.tune(
            base_model=model_name,
            training_dataset=types.TuningDataset(
                gcs_uri=train_data_uri
            ),
            config=tuning_config
        )
        
        print(f"Tuning job launched successfully!")
        print(f"Job Name: {job.name}")
        print(f"State: {job.state}")
        
    except Exception as e:
        print(f"Failed to launch tuning job: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default=f"gs://{Config.GCS_BUCKET_NAME}/tuning/tuning_subset_1000.jsonl")
    parser.add_argument("--model", type=str, default="publishers/google/models/gemini-2.5-flash")
    parser.add_argument("--name", type=str, default="hkjc_flash_tuning_v2_5")
    args = parser.parse_args()
    
    launch_tuning(args.data, args.model, args.name)
