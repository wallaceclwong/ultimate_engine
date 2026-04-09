#!/bin/bash
# Auto-delete old prediction files from GCS after 30 days

cat > /tmp/lifecycle.json << 'EOF'
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
EOF

gcloud storage buckets update gs://ultimate-engine-2026-vault \
  --lifecycle-file=/tmp/lifecycle.json

echo "✅ GCS lifecycle policy set: predictions/ files auto-delete after 30 days"
