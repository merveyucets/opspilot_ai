# OpsPilot AI - tek komutla kurulum (Windows PowerShell 5.1+)
# Kullanim:  powershell -ExecutionPolicy Bypass -File .\kurulum.ps1
# Yapar: .venv (Python 3.12) + paketler (test edilmis surumler), Ollama modelleri, SQLite verisi, politika indeksi, birim testleri.
# Tekrar calistirmak guvenlidir: kurulu olanlar atlanir.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
function Adim($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Kontrol($m) { if ($LASTEXITCODE -ne 0) { Write-Host "HATA: $m" -ForegroundColor Red; exit 1 } }

Adim "1/5 Python sanal ortami (.venv, Python 3.12)"
if (-not (Test-Path $py)) {
    py -3.12 -m venv .venv
    Kontrol "Python 3.12 bulunamadi. https://www.python.org/downloads/ adresinden 3.12 kurun ve tekrar deneyin."
} else { Write-Host ".venv mevcut" }

Adim "2/5 Python paketleri (requirements.lock.txt: test edilen surumler)"
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r requirements.lock.txt --quiet
Kontrol "Paket kurulumu basarisiz. Internet baglantisini kontrol edin."

Adim "3/5 Ollama ve modeller (qwen3:8b ~5,2 GB, bge-m3 ~1,2 GB)"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "HATA: Ollama kurulu degil. https://ollama.com/download adresinden kurun, sonra bu betigi tekrar calistirin." -ForegroundColor Red; exit 1
}
try { Invoke-RestMethod "http://localhost:11434/api/version" -TimeoutSec 5 | Out-Null }
catch { Write-Host "HATA: Ollama calismiyor. Ollama uygulamasini baslatin (veya 'ollama serve') ve tekrar deneyin." -ForegroundColor Red; exit 1 }
$yuklu = @((Invoke-RestMethod "http://localhost:11434/api/tags").models | ForEach-Object { $_.name })
foreach ($m in @("qwen3:8b", "bge-m3")) {
    if ($yuklu -contains $m -or $yuklu -contains "$($m):latest") { Write-Host "$m mevcut" }
    else { ollama pull $m; Kontrol "$m indirilemedi" }
}

Adim "4/5 Veritabani (kurgusal siparisler, tarihler BUGUNE gore) ve politika indeksi"
& $py -m app.veritabani --seed
Kontrol "Veritabani olusturulamadi"
& $py -m app.rag.indexer
Kontrol "Politika indeksi olusturulamadi (Ollama ve bge-m3 calisiyor mu?)"

Adim "5/5 Birim testleri (model gerektirmez)"
& $py -m unittest
Kontrol "Birim testleri basarisiz"

Write-Host "`nKurulum tamam. Baslatmak icin:  powershell -ExecutionPolicy Bypass -File .\baslat.ps1" -ForegroundColor Green
