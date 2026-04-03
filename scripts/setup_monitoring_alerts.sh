#!/bin/bash
# setup_monitoring_alerts.sh
# Automates the creation of GCP Monitoring Alerts for hkjc-predictor Cloud Run service.

# 1. Configuration
SERVICE_NAME="hkjc-predictor"
PROJECT_ID=$(gcloud config get-value project)
echo "--------------------------------------------------------"
echo "🛠️ Provisioning Monitoring Alerts for $SERVICE_NAME"
echo "Project: $PROJECT_ID"
echo "--------------------------------------------------------"

# 2. Create Notification Channel (Email)
echo "📧 We need a destination for alerts."
read -p "Enter your alert email address: " ALERT_EMAIL

# Create the channel and capture the ID
CHANNEL_JSON=$(gcloud alpha monitoring channels create \
  --display-name="HKJC Admin Alerts" \
  --type=email \
  --labels=email_address=$ALERT_EMAIL \
  --format=json)

CHANNEL_ID=$(echo $CHANNEL_JSON | grep -oP '(?<="name": ")[^"]+')
echo "✅ Notification Channel Created: $CHANNEL_ID"

# 3. Create Alert Policy for "High Error Rate"
echo "🚨 Creating Alert Policy for 5xx Errors..."
gcloud alpha monitoring policies create \
  --display-name="HKJC Web API Failure Alert" \
  --notification-channels=$CHANNEL_ID \
  --condition-filter="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\"" \
  --condition-display-name="High 5xx error count on $SERVICE_NAME" \
  --threshold-value=1 \
  --duration=60s \
  --comparison=COMPARISON_GT \
  --combiner=OR

# 4. Create Alert Policy for "Scraper Failures" (Log-based)
echo "🚨 Creating Log-based Alert for Scraper Timeouts..."
gcloud alpha monitoring policies create \
  --display-name="HKJC Scraper Timeout Alert" \
  --notification-channels=$CHANNEL_ID \
  --condition-filter="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND textPayload=~\"Watchdog failed to fetch odds\"" \
  --condition-display-name="Scraper Timeout Detected" \
  --threshold-value=3 \
  --duration=300s \
  --comparison=COMPARISON_GT \
  --combiner=OR

echo "--------------------------------------------------------"
echo "🎉 PROPER ALERTING IS ACTIVE!"
echo "If $SERVICE_NAME returns errors or the scraper times out,"
echo "you will receive an email at $ALERT_EMAIL."
echo "--------------------------------------------------------"
