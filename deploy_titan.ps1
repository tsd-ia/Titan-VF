# TITAN DEPLOYMENT SYSTEM v1.0
# Automates pushing Core (Python) and Dashboard (Vercel) to their respective remotes.

$RootPath = "c:\proyectosvscode\scalping"
$DashboardPath = "c:\proyectosvscode\scalping\titan-dashboard"

Write-Host "🚀 STARTING GLOBAL DEPLOYMENT..." -ForegroundColor Cyan

# 1. CORE (PYTHON)
Write-Host "`n[1/2] Syncing Titan Core..." -ForegroundColor Yellow
Set-Location $RootPath
git add TitanBrain_VPIN.py
git commit -m "Auto-Sync Titan Core: v18.9.83 (Quantum Trailing & 8-Bullet Protocol)"
# Try pushing to the available remote
$CoreRemote = git remote get-url origin
Write-Host "Target: $CoreRemote" -ForegroundColor Gray
git push origin main --force

# 2. DASHBOARD (NEXT.JS / VERCEL)
Write-Host "`n[2/2] Syncing Titan Dashboard..." -ForegroundColor Yellow
Set-Location $DashboardPath
git add .
git commit -m "Auto-Sync Dashboard: Premium UI & 500% Goal Tracking"
$DashRemote = git remote get-url origin
Write-Host "Target: $DashRemote" -ForegroundColor Gray
git push origin main

Write-Host "`n✅ DEPLOYMENT COMPLETE!" -ForegroundColor Green
