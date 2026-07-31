# ============================================================
# SCRIPT DI COMPILAZIONE PER WALLET-CORE SU WINDOWS
# Genera wallet_core.dll per Windows x86_64
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    WALLET-CORE BUILDER v1.0 (Windows)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# 1. VERIFICA PREREQUISITI
# ============================================================

Write-Host "🔍 Verifica prerequisiti..." -ForegroundColor Yellow

# Verifica Rust
$rustc = Get-Command rustc -ErrorAction SilentlyContinue
if (-not $rustc) {
    Write-Host "❌ Rust non trovato!" -ForegroundColor Red
    Write-Host "   Installa da: https://rustup.rs/" -ForegroundColor Yellow
    exit 1
}
Write-Host "   ✅ Rust: $(rustc --version)" -ForegroundColor Green

# Verifica Cargo
$cargo = Get-Command cargo -ErrorAction SilentlyContinue
if (-not $cargo) {
    Write-Host "❌ Cargo non trovato!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Cargo: $(cargo --version)" -ForegroundColor Green

# Verifica target Windows
$targets = rustc --print target-list
if ($targets -notmatch "x86_64-pc-windows-msvc") {
    Write-Host "⚠️ Target x86_64-pc-windows-msvc non disponibile" -ForegroundColor Yellow
    Write-Host "   Aggiungi: rustup target add x86_64-pc-windows-msvc" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================
# 2. SELEZIONA MODALITÀ
# ============================================================

Write-Host "Seleziona la modalità di compilazione:" -ForegroundColor Yellow
Write-Host "  1) Debug  (veloce, con simboli di debug, 25MB)"
Write-Host "  2) Release (ottimizzato, senza debug, 3-5MB)"
Write-Host ""
$MODE_CHOICE = Read-Host "Scelta (1 o 2)"

switch ($MODE_CHOICE) {
    "1" { 
        $BUILD_MODE = "debug"
        $CARGO_FLAG = ""
        Write-Host "✅ Modalità DEBUG selezionata" -ForegroundColor Green
    }
    "2" { 
        $BUILD_MODE = "release"
        $CARGO_FLAG = "--release"
        Write-Host "✅ Modalità RELEASE selezionata" -ForegroundColor Green
    }
    default {
        Write-Host "❌ Scelta non valida. Uscita." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""

# ============================================================
# 3. PULIZIA
# ============================================================

$CLEAN_CHOICE = Read-Host "Pulire la cache prima di compilare? (s/N)"
if ($CLEAN_CHOICE -eq "s" -or $CLEAN_CHOICE -eq "S") {
    Write-Host "🧹 Pulizia cache..." -ForegroundColor Yellow
    cargo clean
    Write-Host "✅ Cache pulita" -ForegroundColor Green
    Write-Host ""
}

# ============================================================
# 4. CREA CARTELLA
# ============================================================

New-Item -ItemType Directory -Force -Path "lib" | Out-Null

# ============================================================
# 5. COMPILAZIONE
# ============================================================

Write-Host "🪟 Compilazione per Windows (x86_64-pc-windows-msvc)..." -ForegroundColor Cyan

# Compila per Windows MSVC
cargo build $CARGO_FLAG --target x86_64-pc-windows-msvc --features python

if ($LASTEXITCODE -ne 0) {
    # Prova con target GNU se MSVC fallisce
    Write-Host "⚠️ Target MSVC fallito, provo GNU..." -ForegroundColor Yellow
    cargo build $CARGO_FLAG --target x86_64-pc-windows-gnu --features python
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Compilazione completata!" -ForegroundColor Green
    
    # Cerca il file DLL
    $dll_paths = @(
        "target\x86_64-pc-windows-msvc\$BUILD_MODE\wallet_core.dll",
        "target\x86_64-pc-windows-gnu\$BUILD_MODE\wallet_core.dll",
        "target\$BUILD_MODE\wallet_core.dll"
    )
    
    $found = $false
    foreach ($path in $dll_paths) {
        if (Test-Path $path) {
            Copy-Item $path "lib\wallet_core.dll" -Force
            Copy-Item $path "wallet_core.dll" -Force
            Write-Host "   📂 lib\wallet_core.dll" -ForegroundColor Green
            Write-Host "   📂 wallet_core.dll" -ForegroundColor Green
            $found = $true
            break
        }
    }
    
    if (-not $found) {
        Write-Host "❌ wallet_core.dll non trovato!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "❌ Errore nella compilazione!" -ForegroundColor Red
    exit 1
}

# ============================================================
# 6. RIEPILOGO
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ COMPILAZIONE COMPLETATA!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📂 File generati:" -ForegroundColor Yellow
Get-ChildItem -Path "lib\*.dll" | ForEach-Object { Write-Host "   📂 $($_.Name) ($([math]::Round($_.Length/1KB, 1)) KB)" }

Write-Host ""
Write-Host "📂 File nella root:" -ForegroundColor Yellow
if (Test-Path "wallet_core.dll") {
    $size = [math]::Round((Get-Item "wallet_core.dll").Length/1KB, 1)
    Write-Host "   ✅ wallet_core.dll ($size KB)" -ForegroundColor Green
} else {
    Write-Host "   ❌ wallet_core.dll non presente" -ForegroundColor Red
}

Write-Host ""
Write-Host "🚀 Fatto!" -ForegroundColor Green