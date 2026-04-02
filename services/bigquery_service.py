import os
import sys
from google.cloud import bigquery
from typing import Dict, Any, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

class BigQueryService:
    def __init__(self):
        self.client = bigquery.Client(project=Config.PROJECT_ID)
        self.dataset_id = f"{Config.PROJECT_ID}.hkjc_dw"
        self.tables = {
            "race_results": "race_results",
            "ai_predictions": "ai_predictions"
        }

    def create_dataset(self):
        dataset = bigquery.Dataset(self.dataset_id)
        dataset.location = Config.GCP_LOCATION
        try:
            self.client.create_dataset(dataset, timeout=30, exists_ok=True)
            print(f"[INFO] BigQuery Dataset created: {self.dataset_id}")
        except Exception as e:
            print(f"[ERROR] BigQuery Dataset creation failed: {e}")

    def get_results_schema(self) -> List[bigquery.SchemaField]:
        return [
            bigquery.SchemaField("race_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("venue", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("race_no", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("distance", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("going", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("course", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("horse_results", "RECORD", mode="REPEATED", fields=[
                bigquery.SchemaField("pos", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("horse_no", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("horse_name", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("jockey", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("trainer", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("win_odds", "FLOAT", mode="NULLABLE"),
                bigquery.SchemaField("draw", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("weight", "FLOAT", mode="NULLABLE"),
            ]),
            bigquery.SchemaField("sectional_times", "STRING", mode="REPEATED"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]

    def get_prediction_schema(self) -> List[bigquery.SchemaField]:
        return [
            bigquery.SchemaField("race_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("confidence_score", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("recommended_bet", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("roi", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("is_best_bet", "BOOLEAN", mode="NULLABLE"),
            bigquery.SchemaField("target_horse", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]

    def create_table(self, table_name: str, schema: List[bigquery.SchemaField]):
        table_id = f"{self.dataset_id}.{table_name}"
        table = bigquery.Table(table_id, schema=schema)
        try:
            self.client.create_table(table, exists_ok=True)
            print(f"[INFO] BigQuery Table created: {table_id}")
        except Exception as e:
            print(f"[ERROR] BigQuery Table creation failed: {e}")

    def upsert_prediction(self, prediction_data: Dict[str, Any]):
        table_id = f"{self.dataset_id}.ai_predictions"
        try:
            errors = self.client.insert_rows_json(table_id, [prediction_data])
            if errors:
                print(f"[ERROR] BigQuery insertion errors: {errors}")
        except Exception as e:
            print(f"[ERROR] BigQuery upsert failed: {e}")

    def update_prediction_roi(self, race_id: str, roi: float, target_horse: str = None):
        """Updates the ROI for an existing prediction record."""
        table_id = f"{self.dataset_id}.ai_predictions"
        # Since BQ DML is asynchronous and requires careful matching, we use a simple update
        query = f"""
            UPDATE `{table_id}`
            SET roi = {roi}, target_horse = '{target_horse if target_horse else ""}'
            WHERE race_id = '{race_id}'
        """
        try:
            query_job = self.client.query(query)
            query_job.result() # Wait for completion
            # print(f"[INFO] BigQuery ROI updated for {race_id}: {roi}%")
        except Exception as e:
            print(f"[ERROR] BigQuery ROI update failed for {race_id}: {e}")

if __name__ == "__main__":
    bq = BigQueryService()
    bq.create_dataset()
    bq.create_table("race_results", bq.get_results_schema())
    bq.create_table("ai_predictions", bq.get_prediction_schema())
