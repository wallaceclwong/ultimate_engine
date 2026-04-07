import os
import sys
import time
from pathlib import Path
from loguru import logger
from concurrent.futures import TimeoutError

# Add project root
root_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, root_dir)

from config.settings import Config
from google.cloud import pubsub_v1
import subprocess

def callback(message: pubsub_v1.subscriber.message.Message) -> None:
    request_data = message.data.decode("utf-8")
    logger.info(f"🌩️ CLOUD TRIGGER RECEIVED: {request_data}")
    
    # Acknowledge the message so Pub/Sub doesn't send it again
    message.ack()
    logger.info("Message acknowledged. Waking up local algorithms...")

    if request_data == "RACE_DAY_START":
        try:
            # We execute the main intelligence cascade.
            # Usually, you'd trigger daily_runner.py or the auto_orchestrator's internal logic
            orchestrator_path = Path(root_dir) / "services" / "auto_orchestrator.py"
            # Running the orchestrator in a one-off mode if possible, or just the daily runner:
            runner_path = Path(root_dir) / "services" / "daily_runner.py"
            
            logger.info(f"Firing {runner_path}...")
            # Fire and forget / background process or wait? We wait to simulate a job
            subprocess.run([sys.executable, str(runner_path)], check=True)
            logger.success("Cloud Trigger Execution Complete.")
            
            # Here, it could cleanly transition into the live_betting_orchestrator.py
            live_path = Path(root_dir) / "services" / "live_betting_orchestrator.py"
            logger.info(f"Transitioning to Live Betting Phase: {live_path}...")
            subprocess.Popen([sys.executable, str(live_path)])
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute local cascade: {e}")
        except Exception as e:
            logger.error(f"Execution wrapper error: {e}")
            
    elif request_data == "TEST_PULSE":
        logger.success("Test pulse received successfully. Cloud-to-Edge connection is PERFECT.")

def listen_for_jobs():
    project_id = Config.PROJECT_ID
    # Subscription name for the Ultimate Engine project (configure in GCP Console or via env)
    subscription_id = os.getenv("PUBSUB_SUBSCRIPTION_ID", "ultimate-engine-trigger-sub")
    
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_id)
    
    flow_control = pubsub_v1.types.FlowControl(max_messages=1)
    
    logger.info(f"🎧 Listening for Cloud Scheduler triggers on {subscription_path}...")
    
    # Run the subscriber
    streaming_pull_future = subscriber.subscribe(
        subscription_path, callback=callback, flow_control=flow_control
    )
    
    # Wrap in a loop to keep the main thread alive. 
    # If the internet drops, pubsub auto-reconnects under the hood!
    with subscriber:
        try:
            # Block the main thread forever while the background thread listens
            while True:
                # We check the future's result with a timeout or just sleep
                # result() with no timeout blocks, but if it returns, we want to restart it
                try:
                    streaming_pull_future.result(timeout=60)
                except TimeoutError:
                    continue 
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
            logger.info("Shutting down Cloud Orchestrator gracefully.")
        except Exception as e:
            logger.error(f"Subscriber threw an error: {e}")
            streaming_pull_future.cancel()

if __name__ == "__main__":
    logger.add("tmp/cloud_orchestrator.log", rotation="5 MB")
    listen_for_jobs()
