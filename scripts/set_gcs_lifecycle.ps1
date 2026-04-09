# Auto-delete old prediction files from GCS after 30 days

$lifecycleJson = @"
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 30,
          "matchesPrefix": ["predictions/"]
        }
      }
    ]
  }
}
"@

$lifecycleJson | Out-File -FilePath "$env:TEMP\lifecycle.json" -Encoding utf8

gcloud storage buckets update gs://ultimate-engine-2026-vault `
  --lifecycle-file="$env:TEMP\lifecycle.json"

Write-Host "✅ GCS lifecycle policy set: predictions/ files auto-delete after 30 days" -ForegroundColor Green
