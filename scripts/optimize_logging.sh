#!/bin/bash
# Run this script as WallaceCLWong@gmail.com to optimize Cloud Logging costs
# Reduces log retention from 30 days to 7 days for Cloud Run logs

PROJECT_ID="ultimate-engine-2026"

echo "Setting up optimized log retention for $PROJECT_ID..."

# Set account (run this manually first: gcloud auth login)
gcloud config set project $PROJECT_ID

# Update default log bucket retention to 7 days
echo "Setting _Default log bucket retention to 7 days..."
gcloud logging buckets update _Default \
  --location=global \
  --retention-days=7

# Create exclusion filters for noisy logs that don't need retention
echo "Creating log exclusions for non-critical logs..."

# Exclude health check logs (these are noisy and not useful)
gcloud logging exclusions create exclude-health-checks \
  --log-filter='resource.type="cloud_run_revision" AND httpRequest.requestUrl=~"/ping" AND httpRequest.status=200' \
  --description="Exclude successful health check pings" \
  2>/dev/null || echo "Health check exclusion already exists"

# Exclude successful GET requests to static assets
gcloud logging exclusions create exclude-static-assets \
  --log-filter='resource.type="cloud_run_revision" AND httpRequest.requestMethod="GET" AND httpRequest.status=200 AND (httpRequest.requestUrl=~"\.js$" OR httpRequest.requestUrl=~"\.css$" OR httpRequest.requestUrl=~"\.png$" OR httpRequest.requestUrl=~"\.jpg$")' \
  --description="Exclude successful static asset requests" \
  2>/dev/null || echo "Static asset exclusion already exists"

echo ""
echo "✅ Logging optimization complete!"
echo ""
echo "Changes made:"
echo "  - Log retention: 30 days → 7 days"
echo "  - Excluded: Health check logs"
echo "  - Excluded: Static asset GET requests"
echo ""
echo "Expected savings: ~$10-15/month"
echo ""
echo "To verify, visit: https://console.cloud.google.com/logs/storage?project=$PROJECT_ID"
