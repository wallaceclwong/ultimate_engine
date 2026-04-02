# Run this script as WallaceCLWong@gmail.com to optimize Cloud Logging costs
# Reduces log retention from 30 days to 7 days for Cloud Run logs

$PROJECT_ID = "hkjc-v2"

Write-Host "Setting up optimized log retention for $PROJECT_ID..." -ForegroundColor Cyan

# Set account (run this manually first: gcloud auth login)
gcloud config set project $PROJECT_ID

# Update default log bucket retention to 7 days
Write-Host "`nSetting _Default log bucket retention to 7 days..." -ForegroundColor Yellow
gcloud logging buckets update _Default `
  --location=global `
  --retention-days=7

# Create exclusion filters for noisy logs that don't need retention
Write-Host "`nCreating log exclusions for non-critical logs..." -ForegroundColor Yellow

# Exclude health check logs (these are noisy and not useful)
gcloud logging exclusions create exclude-health-checks `
  --log-filter='resource.type="cloud_run_revision" AND httpRequest.requestUrl=~"/ping" AND httpRequest.status=200' `
  --description="Exclude successful health check pings" `
  2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "Health check exclusion already exists" -ForegroundColor Gray }

# Exclude successful GET requests to static assets
gcloud logging exclusions create exclude-static-assets `
  --log-filter='resource.type="cloud_run_revision" AND httpRequest.requestMethod="GET" AND httpRequest.status=200 AND (httpRequest.requestUrl=~"\.js$" OR httpRequest.requestUrl=~"\.css$" OR httpRequest.requestUrl=~"\.png$" OR httpRequest.requestUrl=~"\.jpg$")' `
  --description="Exclude successful static asset requests" `
  2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "Static asset exclusion already exists" -ForegroundColor Gray }

Write-Host "`n✅ Logging optimization complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Changes made:" -ForegroundColor Cyan
Write-Host "  - Log retention: 30 days → 7 days"
Write-Host "  - Excluded: Health check logs"
Write-Host "  - Excluded: Static asset GET requests"
Write-Host ""
Write-Host "Expected savings: ~`$10-15/month" -ForegroundColor Green
Write-Host ""
Write-Host "To verify, visit: https://console.cloud.google.com/logs/storage?project=$PROJECT_ID" -ForegroundColor Cyan
