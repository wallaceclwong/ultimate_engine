# Deploy Firebase Hosting with cache headers
# Run this manually when convenient

Write-Host "Deploying Firebase Hosting..." -ForegroundColor Cyan

# Ensure logged in as WallaceCLWong
gcloud config set account wallaceclwong@gmail.com

# Deploy
npx firebase-tools deploy --only hosting

Write-Host "`n✅ Firebase hosting deployed with optimized cache headers!" -ForegroundColor Green
