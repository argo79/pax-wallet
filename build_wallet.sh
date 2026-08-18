#!/bin/bash
# build_wallet.sh - Build wallet CLI (multi-lingua) e Desktop GUI
# CLI: wallet_it_cli.py -> paxwallet-it, wallet_en_cli.py -> paxwallet-en
# Desktop: wallet_desktop.py -> paxwallet-gui

set -e

# ============================================================
# 0. RILEVA PIATTAFORMA
# ============================================================

detect_platform() {
    echo ""
    echo "🔍 Rilevamento piattaforma..."
    
    if [[ -d "/data/data/com.termux" ]] || [[ -f "/system/build.prop" ]]; then
        PLATFORM="android"
        echo "   ✅ Piattaforma: Android (Termux)"
        return
    fi
    
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
# 1. SELEZIONE TIPO BUILD
# ============================================================

select_build_type() {
    echo ""
    echo "=========================================="
    echo "📦 Seleziona il tipo di build:"
    echo "  1) CLI Italiano (paxwallet-it)"
    echo "  2) CLI Inglese (paxwallet-en)"
    echo "  3) CLI Entrambi (it + en)"
    echo "  4) Desktop GUI (paxwallet-gui)"
    echo "  5) Tutto (CLI it + en + Desktop GUI)"
    echo "=========================================="
    read -p "Scelta (1-5): " BUILD_CHOICE

    case $BUILD_CHOICE in
        1)
            BUILD_TYPE="cli-it"
            echo "✅ Build CLI Italiano selezionata"
            SCRIPT_FILES=("wallet_it_cli.py")
            APP_NAMES=("paxwallet-it")
            ;;
        2)
            BUILD_TYPE="cli-en"
            echo "✅ Build CLI Inglese selezionata"
            SCRIPT_FILES=("wallet_en_cli.py")
            APP_NAMES=("paxwallet-en")
            ;;
        3)
            BUILD_TYPE="cli-both"
            echo "✅ Build CLI Italiano + Inglese selezionata"
            SCRIPT_FILES=("wallet_it_cli.py" "wallet_en_cli.py")
            APP_NAMES=("paxwallet-it" "paxwallet-en")
            ;;
        4)
            BUILD_TYPE="desktop"
            echo "✅ Build Desktop GUI selezionata"
            SCRIPT_FILES=("wallet_desktop.py")
            APP_NAMES=("paxwallet-gui")
            ;;
        5)
            BUILD_TYPE="all"
            echo "✅ Build TUTTO selezionata (CLI it + en + Desktop GUI)"
            SCRIPT_FILES=("wallet_it_cli.py" "wallet_en_cli.py" "wallet_desktop.py")
            APP_NAMES=("paxwallet-it" "paxwallet-en" "paxwallet-gui")
            ;;
        *)
            echo "❌ Scelta non valida. Uscita."
            exit 1
            ;;
    esac
    
    # Crea array associativo script -> app_name
    declare -gA SCRIPT_TO_APP
    for i in "${!SCRIPT_FILES[@]}"; do
        SCRIPT_TO_APP["${SCRIPT_FILES[$i]}"]="${APP_NAMES[$i]}"
    done
}

# ============================================================
# 2. VERIFICA FILE DI BUILD
# ============================================================

check_files() {
    echo ""
    echo "🔍 Verifica file necessari..."
    
    # Verifica script CLI
    if [[ "$BUILD_TYPE" == "cli-it" ]] || [[ "$BUILD_TYPE" == "cli-both" ]] || [[ "$BUILD_TYPE" == "all" ]]; then
        if [[ ! -f "wallet_it_cli.py" ]]; then
            echo "   ❌ wallet_it_cli.py non trovato!"
            exit 1
        fi
        echo "   ✅ wallet_it_cli.py trovato"
    fi
    
    if [[ "$BUILD_TYPE" == "cli-en" ]] || [[ "$BUILD_TYPE" == "cli-both" ]] || [[ "$BUILD_TYPE" == "all" ]]; then
        if [[ ! -f "wallet_en_cli.py" ]]; then
            echo "   ❌ wallet_en_cli.py non trovato!"
            exit 1
        fi
        echo "   ✅ wallet_en_cli.py trovato"
    fi
    
    # Verifica script Desktop
    if [[ "$BUILD_TYPE" == "desktop" ]] || [[ "$BUILD_TYPE" == "all" ]]; then
        if [[ ! -f "wallet_desktop.py" ]]; then
            echo "   ❌ wallet_desktop.py non trovato!"
            exit 1
        fi
        echo "   ✅ wallet_desktop.py trovato"
        
        if [[ ! -d "ui" ]]; then
            echo "   ❌ ui/ non trovata! Necessaria per desktop"
            exit 1
        fi
        echo "   ✅ ui/ trovata"
        
        if [[ ! -f "ui/main_window.py" ]]; then
            echo "   ❌ ui/main_window.py non trovato!"
            exit 1
        fi
        echo "   ✅ ui/main_window.py trovato"
        
        if [[ ! -f "ui/reticulum_view.py" ]]; then
            echo "   ❌ ui/reticulum_view.py non trovato!"
            exit 1
        fi
        echo "   ✅ ui/reticulum_view.py trovato"
        
        if [[ ! -f "ui/address_book_view.py" ]]; then
            echo "   ❌ ui/address_book_view.py non trovato!"
            exit 1
        fi
        echo "   ✅ ui/address_book_view.py trovato"
        
        if [[ ! -d "ui/resources" ]]; then
            echo "   ⚠️ ui/resources/ non trovata (skin potrebbe non funzionare)"
        else
            echo "   ✅ ui/resources/ trovata"
        fi
    fi
    
    # Verifica wallet_core
    if [[ "$PLATFORM" == "android" ]]; then
        if [[ -f "wallet_core.so" ]]; then
            echo "   ✅ wallet_core.so trovato"
        else
            echo "   ❌ wallet_core.so non trovato!"
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
    
    if [[ -f "address_book.py" ]]; then
        echo "   ✅ address_book.py trovato"
    else
        echo "   ⚠️ address_book.py non trovato!"
    fi
    
    if [[ -f "wallet_backend.py" ]]; then
        echo "   ✅ wallet_backend.py trovato"
    else
        echo "   ⚠️ wallet_backend.py non trovato!"
    fi
    
    if [[ -f "test_api.py" ]]; then
        echo "   ⚠️ test_api.py trovato! Rinomino in test_api.bak"
        mv test_api.py test_api.bak
    fi
}

# ============================================================
# 3. INSTALLA DIPENDENZE
# ============================================================

install_deps() {
    echo ""
    echo "📦 Verifica dipendenze Python..."
    
    if [[ "$PLATFORM" == "android" ]]; then
        echo "   📱 Android/Termux: usando versioni compatibili..."
        pip install coincurve==19.0.0
        pip install bip32 mnemonic xrpl-py stellar-sdk ecdsa base58 pyinstaller
        pip install colorama
        pip install RNS --no-deps
        pip install PySocks
        pip install 'requests[socks]'
        pip install 'httpx[socks]'
    else
        pip install bip32 mnemonic xrpl-py stellar-sdk cryptography ecdsa base58 pyinstaller
        pip install colorama
        pip install RNS
        pip install PySocks
        pip install 'requests[socks]'
        pip install 'httpx[socks]'
    fi
    
    # Dipendenze per desktop GUI
    if [[ "$BUILD_TYPE" == "desktop" ]] || [[ "$BUILD_TYPE" == "all" ]]; then
        echo "   🖥️ Installazione dipendenze GUI..."
        if [[ "$PLATFORM" == "android" ]]; then
            echo "   ⚠️ Android: PySide6 potrebbe non funzionare correttamente"
        fi
        pip install PySide6
    fi
    
    echo "✅ Dipendenze installate"
}

# ============================================================
# 4. PULIZIA SOLO DEL TARGET
# ============================================================

clean_target() {
    local APP_NAME="$1"
    echo "   🧹 Pulizia target ${APP_NAME}..."
    
    # Rimuovi SOLO il file specifico
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
}

# ============================================================
# 5. BUILD SINGOLO SCRIPT
# ============================================================

build_single() {
    local SCRIPT_FILE="$1"
    local APP_NAME="${SCRIPT_TO_APP[$SCRIPT_FILE]}"
    local SCRIPT_NAME=$(basename "$SCRIPT_FILE" .py)
    
    echo ""
    echo "📦 Build ${SCRIPT_NAME} -> ${APP_NAME}..."
    
    # Pulisci SOLO il target di questa build
    clean_target "$APP_NAME"
    
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
    
    mkdir -p dist
    
    # Determina se è desktop o cli
    if [[ "$SCRIPT_NAME" == "wallet_desktop" ]]; then
        BUILD_UI_FLAG="--onefile --windowed"
        EXTRA_FLAGS="--add-data ui:ui --add-data ui/resources:ui/resources"
        echo "   🖥️ Build Desktop GUI (--onefile)"
    else
        BUILD_UI_FLAG="--onefile --console"
        EXTRA_FLAGS=""
        echo "   💻 Build CLI (--onefile)"
    fi
    
    pyinstaller $BUILD_UI_FLAG \
        --name "${APP_NAME}" \
        --collect-all RNS \
        --add-data "wallet_core.so:." \
        --add-data "$DEFINITIONS_PATH:xrpl/core/binarycodec/definitions/" \
        --add-data "reticulum:reticulum" \
        --add-data "commands:commands" \
        --add-data "utils:utils" \
        --add-data "address_book.py:." \
        --add-data "wallet_backend.py:." \
        $EXTRA_FLAGS \
        --hidden-import bip32 \
        --hidden-import mnemonic \
        --hidden-import xrpl \
        --hidden-import stellar_sdk \
        --hidden-import cryptography \
        --hidden-import ecdsa \
        --hidden-import base58 \
        --hidden-import coincurve \
        --hidden-import wallet_manager \
        --hidden-import core_wrapper \
        --hidden-import colorama \
        --hidden-import RNS.Interfaces \
        --hidden-import RNS.Interfaces.Interface \
        --hidden-import PySocks \
        --hidden-import socks \
        --hidden-import httpx \
        --hidden-import socksio \
        --hidden-import address_book \
        "$SCRIPT_FILE"
    
    # Verifica se il file esiste
    if [[ -f "dist/${APP_NAME}" ]] || [[ -f "dist/${APP_NAME}.exe" ]]; then
        echo "   ✅ Build completato: dist/${APP_NAME}"
        # Crea link simbolico solo per CLI (non per GUI)
        if [[ "$SCRIPT_NAME" != "wallet_desktop" ]]; then
            ln -sf "${APP_NAME}" dist/wallet 2>/dev/null || true
        fi
    else
        # Controlla se è una directory (caso --onefile fallito)
        if [[ -d "dist/${APP_NAME}" ]]; then
            echo "   ⚠️ PyInstaller ha creato una directory, cerco l'eseguibile dentro..."
            if [[ -f "dist/${APP_NAME}/${APP_NAME}" ]]; then
                mv "dist/${APP_NAME}/${APP_NAME}" "dist/${APP_NAME}"
                rm -rf "dist/${APP_NAME}"
                echo "   ✅ Build completato: dist/${APP_NAME}"
            else
                echo "   ❌ Errore: dist/${APP_NAME} non creato"
                exit 1
            fi
        else
            echo "   ❌ Errore: dist/${APP_NAME} non creato"
            exit 1
        fi
    fi
}

# ============================================================
# 6. BUILD WINDOWS
# ============================================================

build_windows() {
    echo ""
    echo "🪟 Build Windows..."
    
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
    
    if ! command -v wine &> /dev/null; then
        echo "   ⚠️ wine non trovato, skip Windows build"
        return 1
    fi
    
    mkdir -p dist_windows
    
    for SCRIPT in "${SCRIPT_FILES[@]}"; do
        local APP_NAME="${SCRIPT_TO_APP[$SCRIPT]}"
        local SCRIPT_NAME=$(basename "$SCRIPT" .py)
        
        echo "   🪟 Build ${SCRIPT_NAME} -> ${APP_NAME}.exe..."
        
        # Pulisci il target Windows
        rm -f "dist_windows/${APP_NAME}.exe" 2>/dev/null || true
        
        if [[ "$SCRIPT_NAME" == "wallet_desktop" ]]; then
            WIN_UI_FLAG="--onefile --windowed"
            WIN_EXTRA="--add-data ui;ui --add-data ui/resources;ui/resources"
        else
            WIN_UI_FLAG="--onefile --console"
            WIN_EXTRA=""
        fi
        
        WINEPREFIX="${HOME}/.wine" wine python -m PyInstaller $WIN_UI_FLAG \
            --name "${APP_NAME}.exe" \
            --collect-all RNS \
            --add-data "wallet_core.dll;." \
            --add-data "${DEFINITIONS_PATH};xrpl/core/binarycodec/definitions/" \
            --add-data "reticulum;reticulum" \
            --add-data "commands;commands" \
            --add-data "utils;utils" \
            --add-data "address_book.py;." \
            --add-data "wallet_backend.py;." \
            $WIN_EXTRA \
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
            --hidden-import address_book \
            "$SCRIPT"
        
        # Copia il file se esiste
        if [[ -f "dist/${APP_NAME}.exe" ]]; then
            cp "dist/${APP_NAME}.exe" "dist_windows/" 2>/dev/null || true
            echo "   ✅ ${APP_NAME}.exe creato"
        fi
    done
    
    cp wallet_core.dll dist_windows/ 2>/dev/null || true
    echo "   ✅ Windows build completato: dist_windows/"
}

# ============================================================
# 7. CREA SCRIPT PER WINDOWS NATIVO
# ============================================================

create_windows_script() {
    echo ""
    echo "📄 Creazione script per Windows nativo..."
    
    cat > build_windows.ps1 << 'EOF'
# build_windows.ps1 - Build PAX Wallet per Windows

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "📦 Build PAX Wallet per Windows" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# PULIZIA SOLO DEI TARGET
Write-Host ""
Write-Host "🧹 Pulizia target..." -ForegroundColor Yellow

$TARGETS = @("paxwallet-it.exe", "paxwallet-en.exe", "paxwallet-gui.exe")
foreach ($T in $TARGETS) {
    Remove-Item "dist\$T" -ErrorAction SilentlyContinue
    Remove-Item "dist_windows\$T" -ErrorAction SilentlyContinue
}
Remove-Item "build\paxwallet-*" -Recurse -ErrorAction SilentlyContinue
Remove-Item "*.spec" -ErrorAction SilentlyContinue

# VERIFICA
Write-Host ""
Write-Host "🔍 Verifica file..." -ForegroundColor Yellow

$SCRIPTS = @()
$APPS = @()

if (Test-Path "wallet_it_cli.py") { 
    $SCRIPTS += "wallet_it_cli.py"
    $APPS += "paxwallet-it"
    Write-Host "   ✅ wallet_it_cli.py trovato -> paxwallet-it" -ForegroundColor Green
}
if (Test-Path "wallet_en_cli.py") { 
    $SCRIPTS += "wallet_en_cli.py"
    $APPS += "paxwallet-en"
    Write-Host "   ✅ wallet_en_cli.py trovato -> paxwallet-en" -ForegroundColor Green
}
if (Test-Path "wallet_desktop.py") { 
    $SCRIPTS += "wallet_desktop.py"
    $APPS += "paxwallet-gui"
    Write-Host "   ✅ wallet_desktop.py trovato -> paxwallet-gui" -ForegroundColor Green
}

if ($SCRIPTS.Count -eq 0) {
    Write-Host "   ❌ Nessun wallet_*.py trovato!" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "wallet_core.dll")) {
    Write-Host "   ❌ wallet_core.dll non trovato!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ wallet_core.dll trovato" -ForegroundColor Green

# DIPENDENZE
Write-Host ""
Write-Host "📦 Dipendenze..." -ForegroundColor Yellow
pip install bip32 mnemonic xrpl-py stellar-sdk cryptography ecdsa base58 pyinstaller
pip install colorama
pip install RNS
pip install PySocks
pip install 'requests[socks]'
pip install 'httpx[socks]'
pip install PySide6

$XRPL_PATH = python -c "import xrpl, os; print(os.path.dirname(xrpl.__file__))" 2>$null
$DEF_PATH = "$XRPL_PATH/core/binarycodec/definitions/definitions.json"

# BUILD
for ($i=0; $i -lt $SCRIPTS.Count; $i++) {
    $SCRIPT = $SCRIPTS[$i]
    $APP = $APPS[$i]
    $NAME = [System.IO.Path]::GetFileNameWithoutExtension($SCRIPT)
    
    Write-Host ""
    Write-Host "📦 Build $NAME -> $APP ..." -ForegroundColor Yellow
    
    if ($NAME -eq "wallet_desktop") {
        $FLAGS = "--onefile --windowed"
        $EXTRA = "--add-data ui;ui --add-data ui/resources;ui/resources"
        Write-Host "   🖥️ Build Desktop GUI" -ForegroundColor Cyan
    } else {
        $FLAGS = "--onefile --console"
        $EXTRA = ""
        Write-Host "   💻 Build CLI" -ForegroundColor Cyan
    }
    
    pyinstaller $FLAGS `
        --name "$APP.exe" `
        --collect-all RNS `
        --add-data "wallet_core.dll;." `
        --add-data "$DEF_PATH;xrpl/core/binarycodec/definitions/" `
        --add-data "reticulum;reticulum" `
        --add-data "commands;commands" `
        --add-data "utils;utils" `
        --add-data "address_book.py;." `
        --add-data "wallet_backend.py;." `
        $EXTRA `
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
        --hidden-import address_book `
        $SCRIPT
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Build $APP completato!" -ForegroundColor Green
        if (Test-Path "dist\$APP.exe") {
            Copy-Item "dist\$APP.exe" "dist_windows\" -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "   ❌ Errore build $APP!" -ForegroundColor Red
    }
}

Copy-Item wallet_core.dll dist_windows\ -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ BUILD COMPLETATA!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📂 Eseguibili in dist_windows\" -ForegroundColor Yellow
Get-ChildItem dist_windows\paxwallet-*.exe -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "   $($_.Name)" -ForegroundColor Green
}
EOF

    echo "   ✅ Script creato: build_windows.ps1"
}

# ============================================================
# 8. PORTABLE
# ============================================================

create_portable() {
    echo ""
    echo "📦 Creazione versione portable..."
    
    mkdir -p portable/linux portable/windows
    
    for SCRIPT in "${SCRIPT_FILES[@]}"; do
        local APP_NAME="${SCRIPT_TO_APP[$SCRIPT]}"
        local SCRIPT_NAME=$(basename "$SCRIPT" .py)
        
        if [[ -f "dist/${APP_NAME}" ]]; then
            mkdir -p "portable/linux/${APP_NAME}"
            cp "dist/${APP_NAME}" "portable/linux/${APP_NAME}/"
            cp wallet_core.so "portable/linux/${APP_NAME}/" 2>/dev/null || true
            echo "   ✅ Linux portable: portable/linux/${APP_NAME}/${APP_NAME}"
        fi
        
        if [[ -f "dist_windows/${APP_NAME}.exe" ]]; then
            mkdir -p "portable/windows/${APP_NAME}"
            cp "dist_windows/${APP_NAME}.exe" "portable/windows/${APP_NAME}/"
            cp wallet_core.dll "portable/windows/${APP_NAME}/" 2>/dev/null || true
            echo "   ✅ Windows portable: portable/windows/${APP_NAME}/${APP_NAME}.exe"
        fi
    done
    
    cp address_book.py portable/ 2>/dev/null || true
    cp annuncio_config.json portable/ 2>/dev/null || true
    echo "   ✅ Portable creato in portable/"
}

# ============================================================
# 9. MAIN
# ============================================================

main() {
    detect_platform
    select_build_type
    check_files
    install_deps
    
    echo ""
    echo "=========================================="
    echo "📦 Build PAX Wallet su ${PLATFORM}"
    echo "=========================================="
    
    # NON cancellare dist/ - solo i target specifici verranno puliti
    mkdir -p dist
    
    # Build per piattaforma
    if [[ "$PLATFORM" == "android" ]] || [[ "$PLATFORM" == "linux" ]] || [[ "$PLATFORM" == "macos" ]]; then
        for SCRIPT in "${SCRIPT_FILES[@]}"; do
            build_single "$SCRIPT"
        done
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
    
    for SCRIPT in "${SCRIPT_FILES[@]}"; do
        local APP_NAME="${SCRIPT_TO_APP[$SCRIPT]}"
        local SCRIPT_NAME=$(basename "$SCRIPT" .py)
        
        if [[ "$PLATFORM" == "android" ]] || [[ "$PLATFORM" == "linux" ]] || [[ "$PLATFORM" == "macos" ]]; then
            if [[ -f "dist/${APP_NAME}" ]]; then
                if [[ "$SCRIPT_NAME" == "wallet_desktop" ]]; then
                    echo "   Desktop GUI:    dist/${APP_NAME}"
                else
                    echo "   CLI:            dist/${APP_NAME}"
                fi
            fi
        fi
        
        if [[ -f "dist_windows/${APP_NAME}.exe" ]]; then
            if [[ "$SCRIPT_NAME" == "wallet_desktop" ]]; then
                echo "   Desktop GUI:    dist_windows/${APP_NAME}.exe"
            else
                echo "   CLI:            dist_windows/${APP_NAME}.exe"
            fi
        fi
    done
    
    if [[ -f "dist/paxwallet-it" ]] || [[ -f "dist/paxwallet-en" ]]; then
        echo "   Link CLI:       dist/wallet (link simbolico)"
    fi
    
    echo "   Portable:       portable/linux/ o portable/windows/"
    echo ""
    echo "💡 Per eseguire:"
    
    if [[ "$PLATFORM" == "android" ]] || [[ "$PLATFORM" == "linux" ]] || [[ "$PLATFORM" == "macos" ]]; then
        for SCRIPT in "${SCRIPT_FILES[@]}"; do
            local APP_NAME="${SCRIPT_TO_APP[$SCRIPT]}"
            local SCRIPT_NAME=$(basename "$SCRIPT" .py)
            if [[ -f "dist/${APP_NAME}" ]]; then
                if [[ "$SCRIPT_NAME" == "wallet_desktop" ]]; then
                    echo "   ./dist/${APP_NAME}"
                else
                    echo "   ./dist/${APP_NAME} interactive"
                fi
            fi
        done
    fi
    
    if [[ -f "dist_windows/paxwallet-it.exe" ]]; then
        echo "   ./dist_windows/paxwallet-it.exe interactive"
    fi
    if [[ -f "dist_windows/paxwallet-en.exe" ]]; then
        echo "   ./dist_windows/paxwallet-en.exe interactive"
    fi
    if [[ -f "dist_windows/paxwallet-gui.exe" ]]; then
        echo "   ./dist_windows/paxwallet-gui.exe"
    fi
    
    if [[ -f "dist/paxwallet-it" ]] || [[ -f "dist/paxwallet-en" ]]; then
        echo "   ./dist/wallet interactive  (link alla CLI)"
    fi
    
    echo ""
    echo "📄 Per buildare su Windows nativo:"
    echo "   powershell -File build_windows.ps1"
    echo "=========================================="
}

main