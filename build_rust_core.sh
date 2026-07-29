#!/bin/bash

# ============================================================
# SCRIPT DI COMPILAZIONE PER WALLET-CORE
# Piattaforme: Linux, Windows, Android
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
# 1. SELEZIONA MODALITÀ (DEBUG / RELEASE)
# ============================================================
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
# 2. SELEZIONA PIATTAFORMA
# ============================================================
echo -e "${YELLOW}Seleziona la piattaforma da compilare:${NC}"
echo "  1) Linux (con Python)"
echo "  2) Windows (con Python)"
echo "  3) Android (senza Python)"
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
# 4. FUNZIONE DI COMPILAZIONE
# ============================================================
compile_linux() {
    echo -e "${BLUE}🐧 Compilazione per Linux...${NC}"
    cargo build $CARGO_FLAG
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Linux compilato con successo!${NC}"
        echo -e "   File: target/$BUILD_MODE/libwallet_core.so"
        echo -e "   Copiato come: wallet_core.so"
        cp "target/$BUILD_MODE/libwallet_core.so" "wallet_core.so"
    else
        echo -e "${RED}❌ Errore nella compilazione per Linux${NC}"
        exit 1
    fi
    echo ""
}

compile_windows() {
    echo -e "${BLUE}🪟 Compilazione per Windows...${NC}"
    cargo build --target x86_64-pc-windows-gnu $CARGO_FLAG
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Windows compilato con successo!${NC}"
        echo -e "   File: target/x86_64-pc-windows-gnu/$BUILD_MODE/wallet_core.dll"
        echo -e "   Copiato come: wallet_core.dll"
        cp "target/x86_64-pc-windows-gnu/$BUILD_MODE/wallet_core.dll" "wallet_core.dll"
    else
        echo -e "${RED}❌ Errore nella compilazione per Windows${NC}"
        exit 1
    fi
    echo ""
}

compile_android() {
    echo -e "${BLUE}🤖 Compilazione per Android (ARM64)...${NC}"
    cargo build --target aarch64-linux-android $CARGO_FLAG --no-default-features
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Android compilato con successo!${NC}"
        echo -e "   File: target/aarch64-linux-android/$BUILD_MODE/libwallet_core.so"
        echo -e "   Copiato come: libwallet_core_android.so"
        cp "target/aarch64-linux-android/$BUILD_MODE/libwallet_core.so" "libwallet_core_android.so"
    else
        echo -e "${RED}❌ Errore nella compilazione per Android${NC}"
        exit 1
    fi
    echo ""
}

# ============================================================
# 5. ESEGUI LA COMPILAZIONE
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
# 6. RIEPILOGO FINALE
# ============================================================
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ COMPILAZIONE COMPLETATA!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${YELLOW}📂 File generati nella root:${NC}"

case $PLATFORM_CHOICE in
    1|4)
        echo "   🐧 Linux: wallet_core.so"
        ;;
esac

case $PLATFORM_CHOICE in
    2|4)
        echo "   🪟 Windows: wallet_core.dll"
        ;;
esac

case $PLATFORM_CHOICE in
    3|4)
        echo "   🤖 Android: libwallet_core_android.so"
        ;;
esac

echo ""
echo -e "${GREEN}🚀 Fatto!${NC}"