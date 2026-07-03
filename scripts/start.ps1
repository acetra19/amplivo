# Production start on VPS – run via SSH
# For first deploy use: .\scripts\deploy-vps.sh (on Linux VPS)

Write-Host "Production runs on VPS. From Windows, deploy via SSH:"
Write-Host ""
Write-Host "  ssh user@your-vps-ip"
Write-Host "  cd /opt/agentur && ./scripts/deploy-vps.sh"
Write-Host ""
Write-Host "Import leads from this PC:"
Write-Host "  python scripts/import-leads.py leads.csv --webhook https://n8n.amplivo.net/webhook/new-lead"
