#!/bin/bash

# ============================================================
# SCRIPT DI COMPILAZIONE PER WALLET-CORE
# Piattaforme: Linux, Windows, Android (Termux)
# ============================================================

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    WALLET-CORE BUILDER v1.0${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ============================================================
# 0. RILEVA PIATTAFORMA
# ============================================================
detect_platform() {
    # Rileva Termux PRIMA di tutto
    if [[ -d "/data/data/com.termux" ]]; then
        PLATFORM="termux"
        echo -e "${GREEN}✅ Piattaforma: Termux/Android${NC}"
        return
    fi
    
    case "$(uname -s)" in
        Linux*)
            PLATFORM="linux"
            echo -e "${GREEN}✅ Piattaforma rilevata: Linux${NC}"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            PLATFORM="windows"
            echo -e "${GREEN}✅ Piattaforma rilevata: Windows${NC}"
            ;;
        *)
            PLATFORM="linux"
            echo -e "${YELLOW}⚠️ Piattaforma non riconosciuta, assumo Linux${NC}"
            ;;
    esac
}

detect_platform

# ============================================================
# 1. SELEZIONA MODALITÀ (DEBUG / RELEASE)
# ============================================================
echo ""
echo -e "${YELLOW}Seleziona la modalità di compilazione:${NC}"
echo "  1) Debug  (veloce, con simboli di debug, 25MB)"
echo "  2) Release (ottimizzato, senza debug, 3-5MB)"
echo ""
read -p "Scelta (1 o 2): " MODE_CHOICE

case $MODE_CHOICE in
    1)
        BUILD_MODE="debug"
        CARGO_FLAG=""
        echo -e "${GREEN}✓ Modalità DEBUG selezionata${NC}"
        ;;
    2)
        BUILD_MODE="release"
        CARGO_FLAG="--release"
        echo -e "${GREEN}✓ Modalità RELEASE selezionata${NC}"
        ;;
    *)
        echo -e "${RED}✗ Scelta non valida. Uscita.${NC}"
        exit 1
        ;;
esac
echo ""

# ============================================================
# 2. SELEZIONA PIATTAFORMA DA COMPILARE
# ============================================================
echo -e "${YELLOW}Seleziona la piattaforma da compilare:${NC}"
echo "  1) Linux (x86_64)"
echo "  2) Windows (x86_64)"
echo "  3) Android ARM64 (Termux)"
echo "  4) Tutte e tre"
echo ""
read -p "Scelta (1-4): " PLATFORM_CHOICE

# ============================================================
# 3. PULISCI PRIMA DI COMPILARE?
# ============================================================
read -p "Pulire la cache prima di compilare? (s/N): " CLEAN_CHOICE
if [[ "$CLEAN_CHOICE" == "s" ]] || [[ "$CLEAN_CHOICE" == "S" ]]; then
    echo -e "${YELLOW}🧹 Pulizia cache...${NC}"
    cargo clean
    echo -e "${GREEN}✓ Cache pulita${NC}"
    echo ""
fi

# ============================================================
# 4. CREA CARTELLA PER I FILE DI OUTPUT
# ============================================================
mkdir -p lib

# ============================================================
# 5. FUNZIONI DI COMPILAZIONE
# ============================================================

compile_linux() {
    echo -e "${BLUE}🐧 Compilazione per Linux (x86_64)...${NC}"
    
    # Per Linux x86_64
    cargo build $CARGO_FLAG --target x86_64-unknown-linux-gnu 2>/dev/null || {
        echo -e "${YELLOW}⚠️ Target x86_64-unknown-linux-gnu fallito, provo nativo...${NC}"
        cargo build $CARGO_FLAG
    }
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Linux compilato con successo!${NC}"
        
        # Cerca il file
        if [ -f "target/x86_64-unknown-linux-gnu/$BUILD_MODE/libwallet_core.so" ]; then
            cp "target/x86_64-unknown-linux-gnu/$BUILD_MODE/libwallet_core.so" "lib/libwallet_core_linux.so"
            echo -e "   📂 lib/libwallet_core_linux.so"
        elif [ -f "target/$BUILD_MODE/libwallet_core.so" ]; then
            cp "target/$BUILD_MODE/libwallet_core.so" "lib/libwallet_core_linux.so"
            echo -e "   📂 lib/libwallet_core_linux.so"
        fi
        
        # Copia anche come wallet_core.so per compatibilità
        if [ -f "lib/libwallet_core_linux.so" ]; then
            cp "lib/libwallet_core_linux.so" "wallet_core.so"
            echo -e "   📂 wallet_core.so (link a libwallet_core_linux.so)"
        fi
    else
        echo -e "${RED}❌ Errore nella compilazione per Linux${NC}"
        exit 1
    fi
    echo ""
}

compile_windows() {
    echo -e "${BLUE}🪟 Compilazione per Windows (x86_64)...${NC}"
    
    cargo build --target x86_64-pc-windows-gnu $CARGO_FLAG 2>/dev/null || {
        echo -e "${YELLOW}⚠️ MinGW non trovato, skip Windows build${NC}"
        return 1
    }
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Windows compilato con successo!${NC}"
        if [ -f "target/x86_64-pc-windows-gnu/$BUILD_MODE/wallet_core.dll" ]; then
            cp "target/x86_64-pc-windows-gnu/$BUILD_MODE/wallet_core.dll" "lib/libwallet_core_windows.dll"
            echo -e "   📂 lib/libwallet_core_windows.dll"
        fi
    else
        echo -e "${RED}❌ Errore nella compilazione per Windows${NC}"
        exit 1
    fi
    echo ""
}

compile_android() {
    echo -e "${BLUE}🤖 Compilazione per Android ARM64 (Termux)...${NC}"
    
    if [[ "$PLATFORM" == "termux" ]]; then
        # Su Termux, compila nativamente
        echo -e "   📱 Compilazione nativa su Termux..."
        cargo build $CARGO_FLAG
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Android compilato con successo!${NC}"
            if [ -f "target/$BUILD_MODE/libwallet_core.so" ]; then
                cp "target/$BUILD_MODE/libwallet_core.so" "lib/libwallet_core_android.so"
                echo -e "   📂 lib/libwallet_core_android.so"
                # Copia anche come wallet_core.so per compatibilità
                cp "lib/libwallet_core_android.so" "wallet_core.so"
                echo -e "   📂 wallet_core.so (link a libwallet_core_android.so)"
            fi
        else
            echo -e "${RED}❌ Errore nella compilazione per Android${NC}"
            exit 1
        fi
    else
        # Cross-compilazione per Android (da Linux/Windows)
        echo -e "   🔄 Cross-compilazione per Android..."
        export CC_aarch64_linux_android="clang"
        export CXX_aarch64_linux_android="clang++"
        export AR_aarch64_linux_android="llvm-ar"
        
        cargo build --target aarch64-linux-android $CARGO_FLAG --no-default-features 2>/dev/null || {
            echo -e "${YELLOW}⚠️ Cross-compilazione fallita, skip Android build${NC}"
            return 1
        }
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Android compilato con successo!${NC}"
            if [ -f "target/aarch64-linux-android/$BUILD_MODE/libwallet_core.so" ]; then
                cp "target/aarch64-linux-android/$BUILD_MODE/libwallet_core.so" "lib/libwallet_core_android.so"
                echo -e "   📂 lib/libwallet_core_android.so"
            fi
        fi
    fi
    echo ""
}

# ============================================================
# 6. ESEGUI LA COMPILAZIONE
# ============================================================

case $PLATFORM_CHOICE in
    1)
        compile_linux
        ;;
    2)
        compile_windows
        ;;
    3)
        compile_android
        ;;
    4)
        compile_linux
        compile_windows
        compile_android
        ;;
    *)
        echo -e "${RED}✗ Scelta non valida. Uscita.${NC}"
        exit 1
        ;;
esac

# ============================================================
# 7. RIEPILOGO FINALE
# ============================================================

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ COMPILAZIONE COMPLETATA!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${YELLOW}📂 File generati in lib/:${NC}"
ls -la lib/ 2>/dev/null || echo "   (nessun file)"

echo ""
echo -e "${YELLOW}📂 File nella root:${NC}"
ls -la wallet_core.so 2>/dev/null || echo "   wallet_core.so non presente"

echo ""
echo -e "${GREEN}🚀 Fatto!${NC}"