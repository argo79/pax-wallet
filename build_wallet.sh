#!/bin/bash
# build_wallet.sh - Build SOLO wallet_cli.py con --collect-all RNS

set -e

# ============================================================
# 0. LEGGI VERSIONE (solo per info, non per il nome)
# ============================================================

if [[ -f "wallet_cli.py" ]]; then
    CURRENT_VERSION=$(grep -E 'VERSION\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+[a-z]*"' wallet_cli.py | head -1 | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+[a-z]*)".*/\1/')
    
    if [[ -z "$CURRENT_VERSION" ]]; then
        CURRENT_VERSION=$(grep -E '__version__\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+[a-z]*"' wallet_cli.py | head -1 | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+[a-z]*)".*/\1/')
    fi
    
    if [[ -z "$CURRENT_VERSION" ]]; then
        CURRENT_VERSION="0.9.1b"
    fi
else
    CURRENT_VERSION="0.9.1b"
fi

# ============================================================
# NOME FINALE: paxwallet (senza estensione per Linux)
# ============================================================
APP_NAME="paxwallet"

echo "=========================================="
echo "📦 Build ${APP_NAME} v${CURRENT_VERSION}"
echo "=========================================="

# ============================================================
# 1. PULIZIA COMPLETA
# ============================================================

clean_all() {
    echo ""
    echo "🧹 Pulizia completa..."
    
    rm -rf build dist build_windows dist_windows portable
    rm -rf *.spec
    rm -rf __pycache__
    rm -f wallet wallet.exe "${APP_NAME}"*
    
    echo "✅ Pulizia completata"
}

# ============================================================
# 2. VERIFICA FILE DI BUILD
# ============================================================

check_files() {
    echo ""
    echo "🔍 Verifica file necessari..."
    
    if [[ ! -f "wallet_cli.py" ]]; then
        echo "   ❌ wallet_cli.py non trovato!"
        exit 1
    fi
    echo "   ✅ wallet_cli.py trovato"
    
    if [[ -f "wallet_core.so" ]]; then
        echo "   ✅ wallet_core.so trovato"
    else
        echo "   ❌ wallet_core.so non trovato!"
        exit 1
    fi
    
    if [[ -f "wallet_core.dll" ]]; then
        echo "   ✅ wallet_core.dll trovato"
    else
        echo "   ⚠️ wallet_core.dll non trovato (skip Windows build)"
    fi
    
    if [[ -f "test_api.py" ]]; then
        echo ""
        echo "   ⚠️ ATTENZIONE: test_api.py trovato! Rinomino..."
        mv test_api.py test_api.bak
        echo "   ✅ test_api.py rinominato in test_api.bak"
    fi
}

# ============================================================
# 3. INSTALLA DIPENDENZE
# ============================================================

install_deps() {
    echo ""
    echo "📦 Verifica dipendenze Python..."
    pip install bip32 mnemonic xrpl-py stellar-sdk cryptography ecdsa base58 pyinstaller
    pip install colorama
    pip install RNS
    echo "✅ Dipendenze installate"
}

# ============================================================
# 4. BUILD LINUX (paxwallet)
# ============================================================

build_linux() {
    echo ""
    echo "🐧 Build eseguibile per Linux (${APP_NAME})..."
    
    XRPL_PATH=$(python -c "import xrpl, os; print(os.path.dirname(xrpl.__file__))" 2>/dev/null || echo "")
    if [[ -z "$XRPL_PATH" ]]; then
        echo "   ⚠️ xrpl non trovato, installa: pip install xrpl-py"
        return 1
    fi
    echo "   📂 XRPL path: $XRPL_PATH"
    
    DEFINITIONS_PATH="${XRPL_PATH}/core/binarycodec/definitions/definitions.json"
    if [[ ! -f "$DEFINITIONS_PATH" ]]; then
        echo "   ❌ definitions.json non trovato in: $DEFINITIONS_PATH"
        exit 1
    fi
    
    pyinstaller --onefile \
        --name "${APP_NAME}" \
        --collect-all RNS \
        --add-data "wallet_core.so:." \
        --add-data "$DEFINITIONS_PATH:xrpl/core/binarycodec/definitions/" \
        --add-data "reticulum:reticulum" \
        --add-data "commands:commands" \
        --add-data "utils:utils" \
        --add-data "node_modules:node_modules" \
        --add-data "package.json:." \
        --hidden-import bip32 \
        --hidden-import mnemonic \
        --hidden-import xrpl \
        --hidden-import stellar_sdk \
        --hidden-import cryptography \
        --hidden-import ecdsa \
        --hidden-import base58 \
        --hidden-import wallet_manager \
        --hidden-import core_wrapper \
        --hidden-import colorama \
        --hidden-import RNS.Interfaces \
        --hidden-import RNS.Interfaces.Interface \
        wallet_cli.py
    
    if [[ -f "dist/${APP_NAME}" ]]; then
        echo "   ✅ Linux build completato: dist/${APP_NAME}"
    else
        echo "   ❌ Errore: dist/${APP_NAME} non creato"
        exit 1
    fi
}

# ============================================================
# 5. BUILD WINDOWS (paxwallet.exe)
# ============================================================

build_windows() {
    echo ""
    echo "🪟 Build eseguibile per Windows..."
    
    if [[ ! -f "wallet_core.dll" ]]; then
        echo "   ⚠️ wallet_core.dll non trovato! Skip Windows build"
        return 1
    fi
    
    XRPL_PATH=$(python -c "import xrpl, os; print(os.path.dirname(xrpl.__file__))" 2>/dev/null || echo "")
    if [[ -z "$XRPL_PATH" ]]; then
        echo "   ⚠️ xrpl non trovato"
        return 1
    fi
    
    DEFINITIONS_PATH="${XRPL_PATH}/core/binarycodec/definitions/definitions.json"
    if [[ ! -f "$DEFINITIONS_PATH" ]]; then
        echo "   ❌ definitions.json non trovato"
        exit 1
    fi
    
    if command -v wine &> /dev/null; then
        echo "   🍷 Usando wine per buildare..."
        rm -rf build_windows dist_windows
        
        WINEPREFIX="${HOME}/.wine" wine python -m PyInstaller --onefile --console \
            --name "${APP_NAME}.exe" \
            --collect-all RNS \
            --add-data "wallet_core.dll;." \
            --add-data "${DEFINITIONS_PATH};xrpl/core/binarycodec/definitions/" \
            --add-data "reticulum;reticulum" \
            --add-data "commands;commands" \
            --add-data "utils;utils" \
            --hidden-import bip32 \
            --hidden-import mnemonic \
            --hidden-import xrpl \
            --hidden-import stellar_sdk \
            --hidden-import cryptography \
            --hidden-import ecdsa \
            --hidden-import base58 \
            --hidden-import wallet_manager \
            --hidden-import core_wrapper \
            --hidden-import colorama \
            --hidden-import RNS.Interfaces \
            --hidden-import RNS.Interfaces.Interface \
            wallet_cli.py
        
        mkdir -p dist_windows
        cp dist/"${APP_NAME}.exe" dist_windows/ 2>/dev/null || true
        cp wallet_core.dll dist_windows/ 2>/dev/null || true
        
        echo "   ✅ Windows build completato: dist_windows/${APP_NAME}.exe"
    else
        echo "   ⚠️ wine non trovato, skip Windows build"
    fi
}

# ============================================================
# 6. CREA SCRIPT PER WINDOWS NATIVO
# ============================================================

create_windows_script() {
    echo ""
    echo "📄 Creazione script per Windows nativo..."
    
    cat > build_windows.ps1 << 'EOF'
# build_windows.ps1 - Build Windows con --collect-all RNS

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "📦 Build PAX Wallet per Windows" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# PULIZIA
Write-Host ""
Write-Host "🧹 Pulizia..." -ForegroundColor Yellow
Remove-Item -Recurse -Force build, dist, *.spec -ErrorAction SilentlyContinue

# VERIFICA
Write-Host ""
Write-Host "🔍 Verifica file..." -ForegroundColor Yellow
if (-not (Test-Path "wallet_cli.py")) {
    Write-Host "   ❌ wallet_cli.py non trovato!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ wallet_cli.py trovato" -ForegroundColor Green

if (-not (Test-Path "wallet_core.dll")) {
    Write-Host "   ❌ wallet_core.dll non trovato!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ wallet_core.dll trovato" -ForegroundColor Green

if (Test-Path "test_api.py") {
    Write-Host "   ⚠️ test_api.py trovato, rinomino..." -ForegroundColor Yellow
    Rename-Item test_api.py test_api.bak
    Write-Host "   ✅ test_api.py rinominato" -ForegroundColor Green
}

# DIPENDENZE
Write-Host ""
Write-Host "📦 Dipendenze..." -ForegroundColor Yellow
pip install bip32 mnemonic xrpl-py stellar-sdk cryptography ecdsa base58 pyinstaller
pip install colorama
pip install RNS

# BUILD
Write-Host ""
Write-Host "🪟 Build paxwallet.exe..." -ForegroundColor Yellow

$XRPL_PATH = python -c "import xrpl, os; print(os.path.dirname(xrpl.__file__))" 2>$null
$DEF_PATH = "$XRPL_PATH/core/binarycodec/definitions/definitions.json"

pyinstaller --onefile --console `
    --name "paxwallet.exe" `
    --collect-all RNS `
    --add-data "wallet_core.dll;." `
    --add-data "$DEF_PATH;xrpl/core/binarycodec/definitions/" `
    --add-data "reticulum;reticulum" `
    --add-data "commands;commands" `
    --add-data "utils;utils" `
    --hidden-import bip32 `
    --hidden-import mnemonic `
    --hidden-import xrpl `
    --hidden-import stellar_sdk `
    --hidden-import cryptography `
    --hidden-import ecdsa `
    --hidden-import base58 `
    --hidden-import wallet_manager `
    --hidden-import core_wrapper `
    --hidden-import colorama `
    --hidden-import RNS.Interfaces `
    --hidden-import RNS.Interfaces.Interface `
    wallet_cli.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Build completato!" -ForegroundColor Green
    Copy-Item wallet_core.dll dist\
    Write-Host "📂 Eseguibile: dist\paxwallet.exe" -ForegroundColor Green
} else {
    Write-Host "❌ Errore nella build!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "💡 Per eseguire:" -ForegroundColor Cyan
Write-Host "   .\dist\paxwallet.exe interactive" -ForegroundColor Yellow
EOF

    echo "   ✅ Script creato: build_windows.ps1"
}

# ============================================================
# 7. VERSIONE PORTABLE
# ============================================================

create_portable() {
    echo ""
    echo "📦 Creazione versione portable..."

    # Linux
    if [[ -f "dist/${APP_NAME}" ]]; then
        mkdir -p portable/linux
        cp "dist/${APP_NAME}" "portable/linux/"
        cp wallet_core.so portable/linux/ 2>/dev/null || true
        echo "   ✅ Linux portable: portable/linux/${APP_NAME}"
    fi

    # Windows
    if [[ -f "dist_windows/${APP_NAME}.exe" ]]; then
        mkdir -p portable/windows
        cp "dist_windows/${APP_NAME}.exe" "portable/windows/"
        cp wallet_core.dll portable/windows/ 2>/dev/null || true
        echo "   ✅ Windows portable: portable/windows/${APP_NAME}.exe"
    fi

    # Config
    cp annuncio_config.json portable/ 2>/dev/null || true
    echo "   ✅ Portable creato in portable/"
}

# ============================================================
# 8. MAIN
# ============================================================

main() {
    clean_all
    check_files
    install_deps
    
    build_linux
    build_windows
    create_windows_script
    
    create_portable
    
    echo ""
    echo "=========================================="
    echo "✅ BUILD COMPLETATA!"
    echo "=========================================="
    echo ""
    echo "📂 Eseguibili:"
    echo "   Linux:    dist/${APP_NAME}"
    echo "   Windows:  dist_windows/${APP_NAME}.exe"
    echo "   Portable: portable/"
    echo ""
    echo "💡 Per eseguire:"
    echo "   ./dist/${APP_NAME} interactive"
    echo "   ./dist/${APP_NAME} --help"
    echo ""
    echo "📄 Per buildare su Windows nativo:"
    echo "   powershell -File build_windows.ps1"
    echo "=========================================="
}

main