#!/bin/bash
# build_wallet.sh - Build wallet_cli.py con supporto multi-lingua e rilevamento piattaforma

set -e

# ============================================================
# 0. RILEVA PIATTAFORMA
# ============================================================

detect_platform() {
    echo ""
    echo "🔍 Rilevamento piattaforma..."
    
    # Rileva se siamo su Termux/Android
    if [[ -d "/data/data/com.termux" ]] || [[ -f "/system/build.prop" ]]; then
        PLATFORM="android"
        echo "   ✅ Piattaforma: Android (Termux)"
        return
    fi
    
    # Rileva sistema operativo
    case "$(uname -s)" in
        Linux*)
            PLATFORM="linux"
            echo "   ✅ Piattaforma: Linux"
            ;;
        Darwin*)
            PLATFORM="macos"
            echo "   ✅ Piattaforma: macOS"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            PLATFORM="windows"
            echo "   ✅ Piattaforma: Windows"
            ;;
        *)
            PLATFORM="linux"
            echo "   ⚠️ Piattaforma non riconosciuta, assumo Linux"
            ;;
    esac
}

# ============================================================
# 1. SELEZIONE LINGUA
# ============================================================

select_language() {
    echo ""
    echo "=========================================="
    echo "🌍 Seleziona la lingua per la build:"
    echo "  1) Italiano (wallet_it_cli.py)"
    echo "  2) Inglese (wallet_en_cli.py)"
    echo "=========================================="
    read -p "Scelta (1-2): " LANG_CHOICE

    case $LANG_CHOICE in
        1)
            SCRIPT_FILE="wallet_it_cli.py"
            LANG_TAG="it"
            echo "✅ Build italiana selezionata"
            ;;
        2)
            SCRIPT_FILE="wallet_en_cli.py"
            LANG_TAG="en"
            echo "✅ Build inglese selezionata"
            ;;
        *)
            echo "❌ Scelta non valida. Uscita."
            exit 1
            ;;
    esac
}

# ============================================================
# 2. LEGGI VERSIONE
# ============================================================

read_version() {
    if [[ -f "$SCRIPT_FILE" ]]; then
        CURRENT_VERSION=$(grep -E 'VERSION\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+[a-z]*"' "$SCRIPT_FILE" | head -1 | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+[a-z]*)".*/\1/')
        
        if [[ -z "$CURRENT_VERSION" ]]; then
            CURRENT_VERSION=$(grep -E '__version__\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+[a-z]*"' "$SCRIPT_FILE" | head -1 | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+[a-z]*)".*/\1/')
        fi
        
        if [[ -z "$CURRENT_VERSION" ]]; then
            CURRENT_VERSION="0.9.1b"
        fi
    else
        echo "❌ File $SCRIPT_FILE non trovato!"
        exit 1
    fi
}

# ============================================================
# 3. NOME OUTPUT CON LINGUA
# ============================================================

APP_NAME="paxwallet-${LANG_TAG}"

echo "=========================================="
echo "📦 Build ${APP_NAME} v${CURRENT_VERSION}"
echo "   Piattaforma: ${PLATFORM}"
echo "=========================================="

# ============================================================
# 4. PULIZIA SOLO DEL TARGET (NON TUTTO!)
# ============================================================

clean_target() {
    echo ""
    echo "🧹 Pulizia del file target ${APP_NAME}..."
    
    # Rimuovi SOLO il file specifico, non tutto dist/
    rm -f "dist/${APP_NAME}" 2>/dev/null || true
    rm -f "dist/${APP_NAME}.exe" 2>/dev/null || true
    rm -f "dist_windows/${APP_NAME}.exe" 2>/dev/null || true
    
    # Rimuovi solo il link wallet se punta a questo file
    if [[ -L "dist/wallet" ]] && [[ "$(readlink dist/wallet)" == "${APP_NAME}" ]]; then
        rm -f dist/wallet
    fi
    
    # Pulisci solo i file temporanei di questa build
    rm -rf "build/${APP_NAME}" 2>/dev/null || true
    rm -f "${APP_NAME}.spec" 2>/dev/null || true
    
    echo "✅ Pulizia target completata"
}

# ============================================================
# 5. VERIFICA FILE DI BUILD
# ============================================================

check_files() {
    echo ""
    echo "🔍 Verifica file necessari..."
    
    if [[ ! -f "$SCRIPT_FILE" ]]; then
        echo "   ❌ $SCRIPT_FILE non trovato!"
        exit 1
    fi
    echo "   ✅ $SCRIPT_FILE trovato"
    
    # Verifica wallet_core in base alla piattaforma
    if [[ "$PLATFORM" == "android" ]]; then
        if [[ -f "wallet_core.so" ]]; then
            echo "   ✅ wallet_core.so trovato"
        else
            echo "   ❌ wallet_core.so non trovato!"
            echo "   Esegui: ./build_rust_core.sh (o compila per Android)"
            exit 1
        fi
    elif [[ "$PLATFORM" == "linux" ]] || [[ "$PLATFORM" == "macos" ]]; then
        if [[ -f "wallet_core.so" ]]; then
            echo "   ✅ wallet_core.so trovato"
        else
            echo "   ❌ wallet_core.so non trovato!"
            exit 1
        fi
    elif [[ "$PLATFORM" == "windows" ]]; then
        if [[ -f "wallet_core.dll" ]]; then
            echo "   ✅ wallet_core.dll trovato"
        else
            echo "   ❌ wallet_core.dll non trovato!"
            exit 1
        fi
    fi
    
    if [[ -f "test_api.py" ]]; then
        echo ""
        echo "   ⚠️ ATTENZIONE: test_api.py trovato! Rinomino..."
        mv test_api.py test_api.bak
        echo "   ✅ test_api.py rinominato in test_api.bak"
    fi
}

# ============================================================
# 6. INSTALLA DIPENDENZE (ADATTATO PER PIATTAFORMA)
# ============================================================

install_deps() {
    echo ""
    echo "📦 Verifica dipendenze Python..."
    
    if [[ "$PLATFORM" == "android" ]]; then
        echo "   📱 Android/Termux: usando versioni compatibili..."
        pip install bip32 mnemonic xrpl-py stellar-sdk ecdsa base58 pyinstaller
        pip install colorama
        pip install RNS --no-deps
    else
        pip install bip32 mnemonic xrpl-py stellar-sdk cryptography ecdsa base58 pyinstaller
        pip install colorama
        pip install RNS
    fi
    
    echo "✅ Dipendenze installate"
}

# ============================================================
# 7. BUILD LINUX/ANDROID - SOLO TARGET
# ============================================================

build_linux_android() {
    echo ""
    echo "🐧 Build eseguibile per Linux/Android (${APP_NAME})..."
    
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
    
    # Assicura che dist esista
    mkdir -p dist
    
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
        "$SCRIPT_FILE"
    
    if [[ -f "dist/${APP_NAME}" ]]; then
        echo "   ✅ Build Linux/Android completato: dist/${APP_NAME}"
        # Crea link simbolico wallet -> versione corrente
        ln -sf "${APP_NAME}" dist/wallet 2>/dev/null || true
    else
        echo "   ❌ Errore: dist/${APP_NAME} non creato"
        exit 1
    fi
}

# ============================================================
# 8. BUILD WINDOWS - SOLO TARGET
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
        rm -rf build_windows
        
        mkdir -p dist_windows
        
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
            "$SCRIPT_FILE"
        
        cp dist/"${APP_NAME}.exe" dist_windows/ 2>/dev/null || true
        cp wallet_core.dll dist_windows/ 2>/dev/null || true
        
        echo "   ✅ Windows build completato: dist_windows/${APP_NAME}.exe"
    else
        echo "   ⚠️ wine non trovato, skip Windows build"
    fi
}

# ============================================================
# 9. CREA SCRIPT PER WINDOWS NATIVO
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
if (-not (Test-Path "wallet_en_cli.py") -and -not (Test-Path "wallet_it_cli.py")) {
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

# Determina il file da buildare
$SCRIPT_FILE = "wallet_en_cli.py"
if (Test-Path "wallet_it_cli.py") {
    Write-Host "   📂 wallet_it_cli.py trovato, build italiano" -ForegroundColor Yellow
    $SCRIPT_FILE = "wallet_it_cli.py"
} else {
    Write-Host "   📂 wallet_en_cli.py trovato, build inglese" -ForegroundColor Yellow
    $SCRIPT_FILE = "wallet_en_cli.py"
}

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
    $SCRIPT_FILE

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
# 10. VERSIONE PORTABLE - SOLO TARGET
# ============================================================

create_portable() {
    echo ""
    echo "📦 Creazione versione portable per ${APP_NAME}..."

    # Linux/Android
    if [[ -f "dist/${APP_NAME}" ]]; then
        mkdir -p "portable/linux-${LANG_TAG}"
        cp "dist/${APP_NAME}" "portable/linux-${LANG_TAG}/"
        cp wallet_core.so "portable/linux-${LANG_TAG}/" 2>/dev/null || true
        echo "   ✅ Linux portable: portable/linux-${LANG_TAG}/${APP_NAME}"
    fi

    # Windows
    if [[ -f "dist_windows/${APP_NAME}.exe" ]]; then
        mkdir -p "portable/windows-${LANG_TAG}"
        cp "dist_windows/${APP_NAME}.exe" "portable/windows-${LANG_TAG}/"
        cp wallet_core.dll "portable/windows-${LANG_TAG}/" 2>/dev/null || true
        echo "   ✅ Windows portable: portable/windows-${LANG_TAG}/${APP_NAME}.exe"
    fi

    # Config
    cp annuncio_config.json portable/ 2>/dev/null || true
    echo "   ✅ Portable creato in portable/"
}

# ============================================================
# 11. MAIN
# ============================================================

main() {
    detect_platform
    select_language
    read_version
    
    echo ""
    echo "=========================================="
    echo "📦 Build ${APP_NAME} v${CURRENT_VERSION}"
    echo "   Piattaforma: ${PLATFORM}"
    echo "=========================================="
    
    clean_target
    check_files
    install_deps
    
    # Build per piattaforma
    if [[ "$PLATFORM" == "android" ]] || [[ "$PLATFORM" == "linux" ]] || [[ "$PLATFORM" == "macos" ]]; then
        build_linux_android
    elif [[ "$PLATFORM" == "windows" ]]; then
        build_windows
    else
        echo "❌ Piattaforma non supportata: ${PLATFORM}"
        exit 1
    fi
    
    # Build Windows aggiuntivo (se su Linux e wine disponibile)
    if [[ "$PLATFORM" != "windows" ]] && [[ -f "wallet_core.dll" ]] && command -v wine &> /dev/null; then
        build_windows
    fi
    
    create_windows_script
    create_portable
    
    echo ""
    echo "=========================================="
    echo "✅ BUILD COMPLETATA!"
    echo "=========================================="
    echo ""
    echo "📂 Eseguibili:"
    if [[ "$PLATFORM" == "android" ]] || [[ "$PLATFORM" == "linux" ]] || [[ "$PLATFORM" == "macos" ]]; then
        echo "   Linux/Android:    dist/${APP_NAME}  (link: dist/wallet)"
    fi
    if [[ -f "dist_windows/${APP_NAME}.exe" ]]; then
        echo "   Windows:          dist_windows/${APP_NAME}.exe"
    fi
    echo "   Portable:          portable/linux-${LANG_TAG}/  o portable/windows-${LANG_TAG}/"
    echo ""
    echo "💡 Per eseguire:"
    if [[ "$PLATFORM" == "android" ]] || [[ "$PLATFORM" == "linux" ]] || [[ "$PLATFORM" == "macos" ]]; then
        echo "   ./dist/${APP_NAME} interactive"
    fi
    if [[ -f "dist_windows/${APP_NAME}.exe" ]]; then
        echo "   ./dist_windows/${APP_NAME}.exe interactive"
    fi
    echo "   ./dist/${APP_NAME} --help"
    echo ""
    echo "📄 Per buildare su Windows nativo:"
    echo "   powershell -File build_windows.ps1"
    echo "=========================================="
}

main