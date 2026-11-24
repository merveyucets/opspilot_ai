# OpsPilot AI - tek komutla baslatma (once kurulum.ps1 calistirilmis olmali)
# Kullanim:  powershell -ExecutionPolicy Bypass -File .\baslat.ps1
# Yapar: siparis tarihlerini BUGUNE gore yeniler, MCP sunucusunu (:8001) ve API + paneli (:8000) ayri pencerelerde
# baslatir (zaten calisiyorsa dokunmaz), dil modelini bellege yukler ve paneli tarayicida acar.
# Durdurmak icin acilan iki PowerShell penceresini kapatin.

Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Once kurulum.ps1 calistirin." -ForegroundColor Red; exit 1 }

function PortAcik([int]$port) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect("127.0.0.1", $port); return $true } catch { return $false } finally { $c.Close() }
}
function Bekle([int]$port, [string]$ad) {
    for ($i = 0; $i -lt 60; $i++) { if (PortAcik $port) { Write-Host "$ad hazir (127.0.0.1:$port)" -ForegroundColor Green; return } ; Start-Sleep -Milliseconds 500 }
    Write-Host "UYARI: $ad 30 sn icinde acilmadi; acilan pencerede hata mesajina bakin." -ForegroundColor Yellow
}

try { Invoke-RestMethod "http://localhost:11434/api/version" -TimeoutSec 5 | Out-Null }
catch { Write-Host "HATA: Ollama calismiyor. Ollama uygulamasini baslatin ve tekrar deneyin." -ForegroundColor Red; exit 1 }

# Siparis tarihleri "bugunden X gun once" olarak tutulur: demo hangi gun yapiliyorsa o gune gore yenilenir.
& $py -m app.veritabani --seed

if (PortAcik 8001) { Write-Host "MCP sunucusu zaten calisiyor (127.0.0.1:8001)" }
else {
    Start-Process powershell -WorkingDirectory $PSScriptRoot -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='OpsPilot MCP :8001'; & '$py' -m app.mcp_sunucusu"
    Bekle 8001 "MCP sunucusu"
}
if (PortAcik 8000) { Write-Host "API + panel zaten calisiyor (127.0.0.1:8000)" }
else {
    Start-Process powershell -WorkingDirectory $PSScriptRoot -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='OpsPilot API :8000'; & '$py' -m uvicorn app.api:app --host 127.0.0.1 --port 8000"
    Bekle 8000 "API + panel"
}

# Modeli arka planda bellege yukle (ilk analiz yavas olmasin). num_ctx config.py ile ayni olmali; farkliysa Ollama yeniden yukler.
Start-Job -ScriptBlock {
    $govde = @{ model = "qwen3:8b"; prompt = ""; keep_alive = "60m"; options = @{ num_ctx = 6144 } } | ConvertTo-Json
    try { Invoke-RestMethod "http://localhost:11434/api/generate" -Method Post -Body $govde -ContentType "application/json" -TimeoutSec 600 | Out-Null } catch {}
} | Out-Null
Write-Host "Model bellege yukleniyor (ust cubuktaki 'Model hazir' yesil olunca analizler hizlanir)."

Start-Process "http://127.0.0.1:8000"
Write-Host "`nPanel: http://127.0.0.1:8000   (onceki panel: /eski)" -ForegroundColor Green
