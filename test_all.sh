#!/bin/bash
# ============================================================
# test_all.sh - Script completo di test per wallet XRP/XLM
# Testa: creazione wallet, trustline, emissione token, rimozione
# ============================================================

set -e

# ============================================================
# COLORI
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

print_green() { echo -e "${GREEN}$1${RESET}"; }
print_red() { echo -e "${RED}$1${RESET}"; }
print_yellow() { echo -e "${YELLOW}$1${RESET}"; }
print_blue() { echo -e "${BLUE}$1${RESET}"; }
print_cyan() { echo -e "${CYAN}$1${RESET}"; }
print_bold() { echo -e "${BOLD}$1${RESET}"; }

# ============================================================
# FUNZIONI DI TEST
# ============================================================

test_start() {
    echo ""
    print_bold "============================================================"
    print_bold "  $1"
    print_bold "============================================================"
}

test_pass() {
    print_green "✅ PASS: $1"
}

test_fail() {
    print_red "❌ FAIL: $1"
    exit 1
}

test_info() {
    print_yellow "ℹ️  $1"
}

test_cmd() {
    print_cyan "▶ $1"
}

# ============================================================
# 1. VERIFICA PREREQUISITI
# ============================================================

test_start "VERIFICA PREREQUISITI"

# Verifica Python
if ! command -v python3 &> /dev/null; then
    test_fail "Python3 non trovato"
fi
test_pass "Python3 trovato"

# Verifica wallet_core.so
if [ ! -f "wallet_core.so" ]; then
    test_fail "wallet_core.so non trovato"
fi
test_pass "wallet_core.so trovato"

# Verifica wallet_cli.py
if [ ! -f "wallet_cli.py" ]; then
    test_fail "wallet_cli.py non trovato"
fi
test_pass "wallet_cli.py trovato"

# ============================================================
# 2. BACKUP DATABASE
# ============================================================

test_start "BACKUP DATABASE"

# Crea cartella backup
mkdir -p backup_tests

# Backup dei database esistenti
for db in wallet_cli.db wallet_core.db test.db test_wallet.db; do
    if [ -f "$db" ]; then
        cp "$db" "backup_tests/${db}.bak"
        test_pass "Backup di $db"
    fi
done

test_info "Backup salvati in backup_tests/"

# ============================================================
# 3. TEST: CREAZIONE EMETTITORE (mew)
# ============================================================

test_start "CREAZIONE EMETTITORE (mew)"

test_cmd "python3 wallet_cli.py create --name mew --crypto XRP --network mainnet"

# Crea wallet mew con seed predefinito
python3 -c "
from wallet_manager import create_manager
from xrpl.wallet import Wallet

# Usa il seed esistente per mew (private key)
seed = '2d2bb3b3ae2012af879dfde7a8190d465f50beb56a207ca37e8871c91a8150b4'
manager = create_manager('wallets/mew.json', 'XRP', 'mainnet')
manager.import_wallet(seed, input_type='private_key')
manager.save()
print('✅ Emettitore mew creato')
" || test_fail "Creazione emettitore fallita"

test_pass "Emettitore mew creato"

# Verifica indirizzo
mew_address=$(python3 -c "
from wallet_manager import create_manager
manager = create_manager('wallets/mew.json', 'XRP', 'mainnet')
manager.load()
print(manager.get_address())
" 2>/dev/null)

if [ -z "$mew_address" ]; then
    test_fail "Indirizzo mew non trovato"
fi
test_pass "Indirizzo mew: $mew_address"

# ============================================================
# 4. TEST: CREAZIONE RICEVENTE (imported)
# ============================================================

test_start "CREAZIONE RICEVENTE (imported)"

test_cmd "python3 wallet_cli.py create --name imported --crypto XRP --network mainnet"

# Usa il seed esistente per imported (numeri Xaman)
python3 -c "
from wallet_manager import create_manager
manager = create_manager('wallets/imported.json', 'XRP', 'mainnet')
numbers = ['301814', '193740', '115707', '234581', '635220', '476547', '389141', '480766']
manager.import_wallet(numbers, input_type='numbers')
manager.save()
print('✅ Ricevente imported creato')
" || test_fail "Creazione ricevente fallita"

test_pass "Ricevente imported creato"

# Verifica indirizzo
imported_address=$(python3 -c "
from wallet_manager import create_manager
manager = create_manager('wallets/imported.json', 'XRP', 'mainnet')
manager.load()
print(manager.get_address())
" 2>/dev/null)

if [ -z "$imported_address" ]; then
    test_fail "Indirizzo imported non trovato"
fi
test_pass "Indirizzo imported: $imported_address"

# ============================================================
# 5. TEST: CREAZIONE TRUSTLINE
# ============================================================

test_start "CREAZIONE TRUSTLINE (imported → mew)"

test_cmd "python3 wallet_cli.py switch imported"
python3 wallet_cli.py switch imported > /dev/null 2>&1

test_cmd "python3 wallet_cli.py trustline-set Arg0 $mew_address 1000000000"

# Crea trustline su imported verso mew
python3 -c "
from wallet_manager import create_manager
manager = create_manager('wallets/imported.json', 'XRP', 'mainnet')
manager.load()
result = manager.set_trustline('Arg0', '$mew_address', 1000000000)
if result.get('success'):
    print('✅ Trustline creata: ' + result.get('hash', 'unknown'))
else:
    print('❌ Errore: ' + result.get('error', 'unknown'))
    exit(1)
" || test_fail "Creazione trustline fallita"

test_pass "Trustline creata su imported verso mew"

# ============================================================
# 6. TEST: VERIFICA TRUSTLINE
# ============================================================

test_start "VERIFICA TRUSTLINE"

# Controlla su imported
python3 -c "
from wallet_manager import create_manager
manager = create_manager('wallets/imported.json', 'XRP', 'mainnet')
manager.load()
trustlines = manager.get_trustlines(force_refresh=True)
found = False
for tl in trustlines:
    if tl.get('currency') == 'Arg0' and tl.get('issuer') == '$mew_address':
        found = True
        print(f'✅ Trustline Arg0 trovata: balance={tl.get(\"balance\", 0)}, limit={tl.get(\"limit\", 0)}')
        break
if not found:
    print('❌ Trustline Arg0 non trovata')
    exit(1)
" || test_fail "Trustline non trovata su imported"

test_pass "Trustline Arg0 attiva su imported"

# ============================================================
# 7. TEST: EMISSIONE TOKEN
# ============================================================

test_start "EMISSIONE TOKEN (mew → imported)"

test_cmd "python3 wallet_cli.py switch mew"
python3 wallet_cli.py switch mew > /dev/null 2>&1

# Invia 10 Arg0 da mew a imported
python3 -c "
from wallet_manager import create_manager
from xrpl.models.transactions import Payment
from xrpl.transaction import autofill, sign, submit_and_wait
from xrpl.clients import JsonRpcClient
from xrpl.models.amounts import IssuedCurrencyAmount

# Carica emettitore
manager = create_manager('wallets/mew.json', 'XRP', 'mainnet')
manager.load()

to_address = '$imported_address'
token = 'Arg0'
issuer = '$mew_address'
amount = 10

print(f'📤 Invio {amount} {token} a {to_address}')

client = JsonRpcClient('https://s1.ripple.com:51234/')
wallet = manager.get_wallet('default', 0)

currency_hex = token.encode('utf-8').hex().upper()
currency = currency_hex.ljust(40, '0')

amount_obj = IssuedCurrencyAmount(
    currency=currency,
    issuer=issuer,
    value=str(amount)
)

payment = Payment(
    account=wallet.classic_address,
    destination=to_address,
    amount=amount_obj
)

tx = autofill(payment, client)
signed_tx = sign(tx, wallet)
response = submit_and_wait(signed_tx, client)

print(f'✅ Transazione inviata!')
print(f'   Hash: {response.result.get(\"hash\", \"unknown\")}')
" || test_fail "Emissione token fallita"

test_pass "10 Arg0 emessi da mew a imported"

# ============================================================
# 8. TEST: VERIFICA SALDO
# ============================================================

test_start "VERIFICA SALDO"

# Controlla saldo su imported
python3 -c "
from wallet_manager import create_manager
manager = create_manager('wallets/imported.json', 'XRP', 'mainnet')
manager.load()
trustlines = manager.get_trustlines(force_refresh=True)
for tl in trustlines:
    if tl.get('currency') == 'Arg0' and tl.get('issuer') == '$mew_address':
        balance = tl.get('balance', 0)
        print(f'💰 Saldo Arg0 su imported: {balance}')
        if balance >= 10:
            print('✅ Saldo corretto!')
        else:
            print('❌ Saldo non corretto (atteso >= 10)')
            exit(1)
        break
" || test_fail "Verifica saldo fallita"

test_pass "Saldo Arg0 su imported: 10"

# ============================================================
# 9. TEST: RIMOZIONE TRUSTLINE
# ============================================================

test_start "RIMOZIONE TRUSTLINE (imported → mew)"

test_cmd "python3 wallet_cli.py switch imported"
python3 wallet_cli.py switch imported > /dev/null 2>&1

# Rimuovi trustline
python3 -c "
from wallet_manager import create_manager
manager = create_manager('wallets/imported.json', 'XRP', 'mainnet')
manager.load()
result = manager.remove_trustline('Arg0', '$mew_address')
if result.get('success'):
    print('✅ Trustline rimossa: ' + result.get('hash', 'unknown'))
else:
    print('❌ Errore: ' + result.get('error', 'unknown'))
    exit(1)
" || test_fail "Rimozione trustline fallita"

test_pass "Trustline rimossa"

# ============================================================
# 10. TEST: PULIZIA DATABASE
# ============================================================

test_start "PULIZIA DATABASE"

# Rimuovi identità duplicate
sqlite3 wallet_cli.db << 'EOF' 2>/dev/null
DELETE FROM identities WHERE name = 'imported' AND id NOT IN (
    SELECT id FROM identities WHERE name = 'imported' ORDER BY created_at DESC LIMIT 1
);
DELETE FROM identities WHERE name NOT IN ('mew', 'imported', 'alb', 'alb_xlm');
DELETE FROM trustlines WHERE identity_id NOT IN (SELECT id FROM identities);
VACUUM;
EOF

test_pass "Database pulito"

# ============================================================
# 11. RIEPILOGO FINALE
# ============================================================

test_start "RIEPILOGO FINALE"

echo ""
print_green "✅ TUTTI I TEST SUPERATI!"
echo ""
print_bold "📊 RIEPILOGO:"
echo "   Emettitore (mew): $mew_address"
echo "   Ricevente (imported): $imported_address"
echo "   Token: Arg0"
echo "   Emessi: 10 Arg0"
echo ""
print_bold "📁 FILE GENERATI:"
echo "   wallets/mew.json"
echo "   wallets/imported.json"
echo "   wallet_cli.db (pulito)"
echo "   backup_tests/ (backup originali)"
echo ""
print_bold "📋 COMANDI PER VERIFICARE:"
echo "   python3 wallet_cli.py switch mew"
echo "   python3 wallet_cli.py trustlines --refresh"
echo "   python3 wallet_cli.py switch imported"
echo "   python3 wallet_cli.py trustlines --refresh"
echo ""
print_green "🚀 FATTO!"

# ============================================================
# 12. RIAVVIA IL WALLET ATTIVO
# ============================================================

python3 wallet_cli.py switch imported > /dev/null 2>&1
print_yellow "ℹ️  Wallet attivo: imported"

exit 0