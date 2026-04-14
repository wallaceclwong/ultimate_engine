import os
import sys
from pathlib import Path
from google.cloud import pubsub_v1

# Add project root to path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from config.settings import Config

def trigger_pulse():
    project_id = Config.PROJECT_ID
    topic_id = "ultimate-engine-trigger-topic"
    
    # Use explicit credentials from config
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(root_dir / "config" / "ultimate-engine-sa-key.json")
    
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)
    
    print(f"Sending TEST_PULSE to {topic_path}...")
    
    data = b"TEST_PULSE"
    future = publisher.publish(topic_path, data)
    
    try:
        message_id = future.result()
        print(f"Success! Message ID: {message_id}")
        print("Now check tmp/cloud_orchestrator.log for receipt confirmation.")
    except Exception as e:
        print(f"Failed to publish: {e}")

if __name__ == "__main__":
    trigger_pulse()
