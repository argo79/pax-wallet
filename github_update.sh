#!/bin/bash
# github_update.sh - Aggiorna repository GitHub e release per PAX Wallet
# Questo file viene automaticamente ignorato da git

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║     🕊️  PAX WALLET - GITHUB UPDATE & RELEASE                  ║"
echo "║     Peace Through Free Money                                   ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BRANCH="master"

# ============================================================
# 📖 LEGGI VERSIONE DA wallet_cli.py
# ============================================================

if [ -f "wallet_cli.py" ]; then
    CURRENT_VERSION=$(grep -E 'VERSION\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+[a-z]*"' wallet_cli.py | head -1 | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+[a-z]*)".*/\1/')
    
    if [ -z "$CURRENT_VERSION" ]; then
        CURRENT_VERSION=$(grep -E '__version__\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+[a-z]*"' wallet_cli.py | head -1 | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+[a-z]*)".*/\1/')
    fi
    
    if [ -z "$CURRENT_VERSION" ]; then
        CURRENT_VERSION=$(grep -E 'VERSION="[0-9]+\.[0-9]+\.[0-9]+[a-z]*"' build_wallet.sh | head -1 | sed -E 's/.*VERSION="([0-9]+\.[0-9]+\.[0-9]+[a-z]*)".*/\1/')
    fi
    
    if [ -z "$CURRENT_VERSION" ]; then
        CURRENT_VERSION="0.9.0b"
    fi
else
    CURRENT_VERSION="0.9.0b"
fi

echo -e "${BLUE}📌 PAX Wallet Versione: v${CURRENT_VERSION}${NC}"

# Calcola prossima versione
IFS='.' read -r major minor patch <<< "$CURRENT_VERSION"
patch="${patch%[a-z]*}"
NEXT_PATCH=$((patch + 1))
NEXT_VERSION="v$major.$minor.$NEXT_PATCH"

# ============================================================
# 🛡️ AUTO-ESCLUSIONE DA GIT
# ============================================================

if [ ! -f ".gitignore" ]; then
    echo "github_update.sh" > .gitignore
    echo -e "${GREEN}✅ .gitignore creato${NC}"
else
    if ! grep -q "github_update.sh" .gitignore; then
        echo "github_update.sh" >> .gitignore
        echo -e "${GREEN}✅ github_update.sh aggiunto a .gitignore${NC}"
    fi
fi

# ============================================================
# 📊 STATO
# ============================================================

echo ""
echo -e "${BLUE}📊 Stato attuale:${NC}"
git status --short

CHANGES=$(git status --porcelain | wc -l)
if [ $CHANGES -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Nessun cambiamento${NC}"
else
    echo -e "${GREEN}📝 $CHANGES file modificati${NC}"
fi

# ============================================================
# 🔄 SINCORNIZZA
# ============================================================

echo ""
echo -e "${BLUE}🔄 Sincronizzazione...${NC}"
git pull origin $BRANCH --rebase 2>/dev/null || git pull origin $BRANCH

# ============================================================
# 📦 COMMIT
# ============================================================

echo ""
read -p "📝 Messaggio commit (Invio per default): " COMMIT_MSG
if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="PAX Wallet - Aggiornamento v$CURRENT_VERSION"
fi

git add .
git commit -m "$COMMIT_MSG"

# ============================================================
# 📤 PUSH
# ============================================================

echo ""
echo -e "${BLUE}📤 Push...${NC}"
git push origin $BRANCH

# ============================================================
# 🏷️ RELEASE
# ============================================================

echo ""
echo -e "${YELLOW}📦 Creare nuova release?${NC}"
echo -e "   ${GREEN}1) Nuova release${NC}"
echo -e "   ${YELLOW}2) Sovrascrivi esistente${NC}"
echo -e "   ${RED}3) Salta${NC}"
read -p "Scelta (1-3): " RELEASE_CHOICE

if [ "$RELEASE_CHOICE" == "1" ] || [ "$RELEASE_CHOICE" == "2" ]; then
    
    echo ""
    echo -e "${BLUE}📌 Versione attuale: v${CURRENT_VERSION}${NC}"
    
    if [ "$RELEASE_CHOICE" == "1" ]; then
        DEFAULT_VERSION="$NEXT_VERSION"
        echo -e "${GREEN}   Prossima versione: $DEFAULT_VERSION${NC}"
    else
        DEFAULT_VERSION="v$CURRENT_VERSION"
        echo -e "${YELLOW}   (sovrascrivi v$CURRENT_VERSION)${NC}"
    fi
    
    echo ""
    read -p "📌 Versione [default: $DEFAULT_VERSION]: " RELEASE_VERSION
    if [ -z "$RELEASE_VERSION" ]; then
        RELEASE_VERSION="$DEFAULT_VERSION"
    fi
    
    DEFAULT_TITLE="PAX Wallet $RELEASE_VERSION - Peace Through Free Money"
    read -p "📝 Titolo release [default: $DEFAULT_TITLE]: " RELEASE_TITLE
    if [ -z "$RELEASE_TITLE" ]; then
        RELEASE_TITLE="$DEFAULT_TITLE"
    fi
    
    if [ "$RELEASE_CHOICE" == "1" ]; then
        DEFAULT_NOTES="## 🕊️ PAX Wallet - $RELEASE_VERSION

### ✨ Novità
- 

### 🐛 Bug Fix
- 

### 🔧 Miglioramenti
- 

### 📦 Dipendenze
- 

---
**PAX Wallet - Peace Through Free Money**
**HOPE Ecosystem - Human Open Payment Ecosystem**"
    else
        DEFAULT_NOTES="## 🔄 Sovrascrittura PAX Wallet $RELEASE_VERSION

### ✨ Novità
- 

### 🐛 Bug Fix
- 

### 🔧 Miglioramenti
- 

---
**PAX Wallet - Peace Through Free Money**"
    fi
    
    echo ""
    echo -e "${BLUE}📝 Note release (modifica se necessario):${NC}"
    echo -e "${YELLOW}   (premi Invio per usare il template)${NC}"
    echo ""
    read -p "📝 Note release [default: template automatico]: " RELEASE_NOTES
    if [ -z "$RELEASE_NOTES" ]; then
        RELEASE_NOTES="$DEFAULT_NOTES"
    fi
    
    # Se sovrascrivi, elimina la vecchia
    if [ "$RELEASE_CHOICE" == "2" ]; then
        echo ""
        echo -e "${RED}🗑️  Eliminazione release esistente...${NC}"
        gh release delete "$RELEASE_VERSION" --yes 2>/dev/null
        git tag -d "$RELEASE_VERSION" 2>/dev/null
        git push origin ":refs/tags/$RELEASE_VERSION" 2>/dev/null
        echo -e "${GREEN}✅ Release eliminata${NC}"
    fi
    
    # Crea tag e release
    echo ""
    echo -e "${BLUE}🏷️  Creazione tag...${NC}"
    git tag -a "$RELEASE_VERSION" -m "$RELEASE_TITLE"
    git push origin "$RELEASE_VERSION"
    echo -e "${GREEN}✅ Tag creato${NC}"
    
    echo ""
    echo -e "${BLUE}📦 Creazione release...${NC}"
    gh release create "$RELEASE_VERSION" \
        --title "$RELEASE_TITLE" \
        --notes "$RELEASE_NOTES"
    
    # ============================================================
    # 📂 CARICA ASSET DA dist/
    # ============================================================
    
    if [ -d "dist" ] && [ "$(ls -A dist 2>/dev/null)" ]; then
        echo ""
        echo -e "${BLUE}📂 Asset disponibili in dist/:${NC}"
        ls -la dist/
        
        echo ""
        echo -e "${YELLOW}📤 Caricare asset?${NC}"
        echo -e "   ${GREEN}1) Carica tutti${NC}"
        echo -e "   ${GREEN}2) Carica solo Linux${NC}"
        echo -e "   ${GREEN}3) Carica solo Windows${NC}"
        echo -e "   ${GREEN}4) Seleziona manualmente${NC}"
        echo -e "   ${RED}5) Salta${NC}"
        read -p "Scelta (1-5): " UPLOAD_CHOICE
        
        case $UPLOAD_CHOICE in
            1)
                echo -e "${BLUE}📤 Caricamento tutti gli asset...${NC}"
                cd dist
                for file in *; do
                    if [ -f "$file" ]; then
                        echo -e "   ${GREEN}⬆️  $file${NC}"
                        gh release upload "$RELEASE_VERSION" "$file" --clobber
                    fi
                done
                cd ..
                echo -e "${GREEN}✅ Tutti gli asset caricati!${NC}"
                ;;
            2)
                LINUX_FILE=$(ls dist/wallet* 2>/dev/null | grep -v ".exe" | head -n 1)
                if [ -n "$LINUX_FILE" ]; then
                    echo -e "${BLUE}📤 Caricamento $LINUX_FILE...${NC}"
                    gh release upload "$RELEASE_VERSION" "$LINUX_FILE" --clobber
                    echo -e "${GREEN}✅ $LINUX_FILE caricato!${NC}"
                else
                    echo -e "${RED}❌ Nessun file Linux trovato!${NC}"
                fi
                ;;
            3)
                WIN_FILE=$(ls dist/*.exe 2>/dev/null | head -n 1)
                if [ -n "$WIN_FILE" ]; then
                    echo -e "${BLUE}📤 Caricamento $WIN_FILE...${NC}"
                    gh release upload "$RELEASE_VERSION" "$WIN_FILE" --clobber
                    echo -e "${GREEN}✅ $WIN_FILE caricato!${NC}"
                else
                    echo -e "${RED}❌ Nessun file Windows trovato!${NC}"
                fi
                ;;
            4)
                echo ""
                echo -e "${BLUE}📂 Seleziona file da caricare:${NC}"
                cd dist
                select file in *; do
                    if [ -n "$file" ]; then
                        echo -e "   ${GREEN}⬆️  $file${NC}"
                        gh release upload "$RELEASE_VERSION" "$file" --clobber
                        echo -e "${GREEN}✅ $file caricato!${NC}"
                        break
                    fi
                done
                cd ..
                ;;
            *)
                echo -e "${YELLOW}⏭️  Upload saltato${NC}"
                ;;
        esac
    else
        echo ""
        echo -e "${YELLOW}⚠️  Nessun asset trovato in dist/${NC}"
        echo -e "   Per caricare asset, esegui prima ./build_wallet.sh"
    fi
    
    echo ""
    echo -e "${GREEN}✅ Release creata!${NC}"
    REPO_URL=$(git remote get-url origin | sed 's/.*://' | sed 's/\.git$//')
    echo -e "${GREEN}🔗 https://github.com/$REPO_URL/releases/tag/$RELEASE_VERSION${NC}"
fi

# ============================================================
# 🎯 FINE
# ============================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  ✅ COMPLETATO!                                                 ║"
echo "║  🕊️  PAX Wallet - Peace Through Free Money                     ║"
echo "║  🌍  HOPE Ecosystem - Human Open Payment Ecosystem             ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
REPO_URL=$(git remote get-url origin | sed 's/.*://' | sed 's/\.git$//')
echo -e "${GREEN}📁 Repository: https://github.com/$REPO_URL${NC}"
echo -e "${GREEN}🌿 Branch: $BRANCH${NC}"
echo -e "${GREEN}📦 Release: https://github.com/$REPO_URL/releases${NC}"
echo -e "${GREEN}📌 Versione: v$CURRENT_VERSION${NC}"
echo ""