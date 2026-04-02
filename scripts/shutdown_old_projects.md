# Shut Down Old GCP Projects

Project shutdown must be done via GCP Console (cannot be automated via CLI for safety).

## Steps to Shut Down Projects

### 1. Shut down `project-6172aadc-bdc0-43ee-8ac`

1. Go to: https://console.cloud.google.com/home/dashboard?project=project-6172aadc-bdc0-43ee-8ac
2. Click **Settings** in left menu
3. Click **Shut down**
4. Type the project ID to confirm: `project-6172aadc-bdc0-43ee-8ac`
5. Click **Shut down**

### 2. Shut down `hkjc-training`

1. Go to: https://console.cloud.google.com/home/dashboard?project=hkjc-training
2. Click **Settings** in left menu
3. Click **Shut down**
4. Type the project ID to confirm: `hkjc-training`
5. Click **Shut down**

## What's Already Cleaned Up

- ✅ Old endpoint undeployed and deleted
- ✅ Old GCS bucket `hkjc-vault-6172aadc` deleted
- ✅ All resources migrated to `hkjc-v2`

## After Shutdown

Projects will be scheduled for deletion in 30 days. They can be restored during this period if needed.

**Estimated savings:** ~$15/month (no more Vertex AI endpoint idle costs)
