#!/usr/bin/env python3
"""
paxwallet.py - CLI Frontend per PAX Wallet
Usa WalletBackend per TUTTA la logica
Solo UI e menu - ~600 righe
"""

import sys
import json
import getpass
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# ============================================================
# IMPORTA IL BACKEND E LE UTILITY CONDIVISE
# ============================================================

from wallet_backend import WalletBackend, create_backend, Colors, format_time_ago, parse_tx_date


# ============================================================
# VERSIONE
# ============================================================
VERSION = "0.9.3b"
__version__ = VERSION


# ============================================================
# FUNZIONI DI STAMPA CON COLORI (USANO Colors DAL BACKEND)
# ============================================================

def print_green(msg): print(f"{Colors.GREEN}{msg}{Colors.RESET}")
def print_yellow(msg): print(f"{Colors.YELLOW}{msg}{Colors.RESET}")
def print_blue(msg): print(f"{Colors.BLUE}{msg}{Colors.RESET}")
def print_red(msg): print(f"{Colors.RED}{msg}{Colors.RESET}")
def print_cyan(msg): print(f"{Colors.CYAN}{msg}{Colors.RESET}")
def print_bold(msg): print(f"{Colors.BOLD}{msg}{Colors.RESET}")


# ============================================================
# UTILITY (solo specifiche del frontend)
# ============================================================

def format_address(address: str, length: int = 25) -> str:
    if not address:
        return "N/A"
    if len(address) <= length:
        return address
    return address[:length] + "..."


# ============================================================
# CLASSE CLI
# ============================================================

class PaxWalletCLI:
    """Frontend CLI per PAX Wallet - USA IL BACKEND"""
    
    def __init__(self):
        self.backend: Optional[WalletBackend] = None
        self._password: Optional[str] = None
        self._running = True

    # ============================================================
    # UNLOCK
    # ============================================================
    
    def _unlock(self) -> bool:
        """Chiede la password e inizializza il backend"""
        print("\n" + "=" * 60)
        print("  🔐 PAX WALLET - UNLOCK")
        print("=" * 60)
        print("")
        
        temp_backend = create_backend()
        has_encrypted = temp_backend._has_encrypted_files()
        
        if has_encrypted:
            print("   Inserisci la password per sbloccare il wallet.")
            print("")
            max_attempts = 3
            attempts = 0
            
            while attempts < max_attempts:
                password = getpass.getpass("🔐 Password: ")
                if not password:
                    print_red("❌ La password non può essere vuota")
                    attempts += 1
                    continue
                
                # 🔥 PROVA A INIZIALIZZARE CON QUESTA PASSWORD
                self.backend = create_backend(password)
                result = self.backend.init()
                
                # Verifica se il wallet è stato caricato correttamente
                active = self.backend.get_active_wallet()
                if active.get("name") and active.get("loaded"):
                    self._password = password
                    print_green("✅ Password verificata")
                    return True
                
                # Se arriva qui, la password è sbagliata
                attempts += 1
                remaining = max_attempts - attempts
                print_red(f"❌ Password errata. Tentativi rimasti: {remaining}")
                
                if remaining == 0:
                    print_red("❌ Troppi tentativi falliti.")
                    return False
        else:
            print("   🔑 Nessun wallet cifrato trovato.")
            print("   Crea una nuova password per proteggere i tuoi wallet.")
            print("")
            while True:
                password = getpass.getpass("🔐 Nuova password: ")
                if not password:
                    print_red("❌ La password non può essere vuota")
                    continue
                confirm = getpass.getpass("   Conferma password: ")
                if confirm == password:
                    break
                print_red("❌ Le password non corrispondono")
            
            self._password = password
            self.backend = create_backend(password)
            self.backend.init()
            print_green("✅ Password creata")
            return True
        
        return False
    
    # ============================================================
    # MAIN LOOP
    # ============================================================
    
    def run(self):
        """Avvia il loop principale"""
        if not self._unlock():
            print_red("❌ Impossibile avviare PAX Wallet")
            return
        
        print_bold("\n" + "=" * 60)
        print_bold("    💰 PAX WALLET")
        print_bold("=" * 60)
        print("")
        print_green("🔐 Wallet cifrato con AES-256-GCM")
        print_green(f"📡 Reticulum: {'Attivo' if self.backend.reticulum else 'Non disponibile'}")
        
        while self._running:
            try:
                self._show_main_menu()
                choice = input("\nScelta: ").strip()
                self._handle_main_choice(choice)
            except KeyboardInterrupt:
                print("\n")
                print_yellow("⚠️ Interrotto")
                break
            except Exception as e:
                print_red(f"❌ Errore: {e}")
        
        self._cleanup()
        print_green("👋 Arrivederci!")
    
    def _cleanup(self):
        """Pulisce alla chiusura"""
        if self.backend and self.backend.reticulum:
            try:
                if self.backend.metrics:
                    self.backend.metrics.stop_query_loop()
            except:
                pass
            try:
                status = self.backend.reticulum.get_status()
                if status.get('is_gateway', False):
                    self.backend.reticulum.stop_gateway()
            except:
                pass
    
    # ============================================================
    # MENU
    # ============================================================
    
    def _show_main_menu(self):
        """Mostra il menu principale"""
        active = self.backend.get_active_wallet() if self.backend else {}
        status = self.backend.get_status() if self.backend else {}
        
        print("\n" + "-" * 40)
        print("  1) Wallet")
        print("  2) Mostra saldo")
        print("  3) Mostra indirizzo")
        print("  4) Deriva indirizzi")
        print("  5) Invia pagamento")
        print("  6) Info wallet")
        print("  7) Storico")
        print("  8) Fund testnet (XLM)")
        print("  9) Esporta")
        print(" 10) Trustline")
        print(" 11) Invia token")
        print(" 12) Reticulum")
        print(" 13) Cambia password")
        print("  0) Esci")
        
        if active.get("name"):
            print_yellow(f"  📂 Wallet: {active['name']} ({active['network'].upper()} - {active['crypto']})")
        else:
            print_red("  📂 Nessun wallet caricato")
        
        if status.get('gateway_active'):
            print_yellow("  📡 Gateway attivo")
        print("-" * 40)
    
    def _handle_main_choice(self, choice: str):
        """Gestisce le scelte del menu principale"""
        if choice == '0':
            self._running = False
        elif choice == '1':
            self._menu_wallet()
        elif choice == '2':
            self._cmd_balance()
        elif choice == '3':
            self._cmd_address()
        elif choice == '4':
            self._cmd_derive()
        elif choice == '5':
            self._cmd_send()
        elif choice == '6':
            self._cmd_info()
        elif choice == '7':
            self._cmd_history()
        elif choice == '8':
            self._cmd_fund_testnet()
        elif choice == '9':
            self._cmd_export()
        elif choice == '10':
            self._menu_trustline()
        elif choice == '11':
            self._cmd_send_token()
        elif choice == '12':
            self._menu_reticulum()
        elif choice == '13':
            self._cmd_change_password()
        else:
            print_red("❌ Scelta non valida")
    
    # ============================================================
    # SOTTOMENU WALLET
    # ============================================================
    
    def _menu_wallet(self):
        """Sottomenu gestione wallet"""
        while True:
            active = self.backend.get_active_wallet()
            wallets = self.backend.list_wallets()
            
            print("\n" + "=" * 50)
            print("  📂 WALLET")
            print("=" * 50)
            print(f"  Wallet attivo: {active.get('name') or 'NESSUNO'}")
            print("\n  📋 Lista wallet:")
            if wallets:
                for i, w in enumerate(wallets, 1):
                    marker = "▶" if w.get("is_active") else " "
                    address = w.get("address", "unknown")
                    # 🔥 NON TRONCARE! Mostra l'indirizzo COMPLETO
                    print(f"    {i}. {marker} {w['name']:<15} ({w['crypto']} - {w['network']}) {address}")
            else:
                print("    ❌ Nessun wallet salvato")
            
            print("\n" + "-" * 50)
            print("  1) Crea wallet")
            print("  2) Importa wallet")
            print("  3) Rimuovi wallet")
            print("  4) Cambia wallet")
            print("  0) Torna al menu principale")
            print("-" * 50)
            
            sub = input("\nScelta: ").strip()
            
            if sub == '0':
                break
            elif sub == '1':
                self._cmd_create()
            elif sub == '2':
                self._cmd_import()
            elif sub == '3':
                self._cmd_remove()
            elif sub == '4':
                self._cmd_switch()
            else:
                print_red("❌ Scelta non valida")
    
    # ============================================================
    # COMANDI WALLET
    # ============================================================
    
    def _cmd_create(self):
        """Crea un nuovo wallet con supporto per strength e passphrase"""
        name = input("Nome (default): ").strip() or "default"
        crypto = input("Crypto (XRP/XLM): ").strip().upper() or "XRP"
        network = input("Rete (testnet/mainnet): ").strip().lower() or "testnet"
        
        print("\n   🔐 Scegli il numero di parole:")
        print("      1) 12 parole (standard)")
        print("      2) 24 parole (massima sicurezza)")
        choice = input("   Scelta (1 o 2, default 2): ").strip()
        strength = 128 if choice == "1" else 256
        
        print("\n   🔐 Passphrase (opzionale, Invio per saltare):")
        print("      Se la dimentichi, il wallet è irrecuperabile.")
        passphrase = getpass.getpass("   Passphrase: ").strip()
        if passphrase:
            confirm = getpass.getpass("   Conferma passphrase: ").strip()
            if confirm != passphrase:
                print_red("❌ Le passphrase non corrispondono!")
                return
            print_cyan(f"   🔐 Passphrase impostata")
        else:
            print_yellow("   ⚠️ Nessuna passphrase")
        
        # 🔥 PASSA strength E passphrase AL BACKEND
        result = self.backend.create_wallet(name, crypto, network, strength=strength, passphrase=passphrase)
        
        if result.get("success"):
            print_green(f"\n✅ Wallet creato su {network.upper()}!")
            print(f"   Address: {result.get('address', 'N/A')}")
            print(f"   Mnemonic: {result.get('mnemonic', 'N/A')}")
            print(f"   Word Count: {result.get('word_count', 0)}")
            if passphrase:
                print(f"   Passphrase: {'*' * len(passphrase)}")
                print_yellow("\n   ⚠️ ATTENZIONE: La passphrase NON è memorizzata nel wallet!")
                print_yellow("   Conservala in un luogo sicuro, SEPARATO dal seed.")
                print_yellow("   Senza la passphrase NON puoi recuperare il wallet.")
            print(f"   Seed: {result.get('seed', 'N/A')}")
        else:
            print_red(f"❌ Errore: {result.get('error', 'Unknown error')}")
    
    def _cmd_import(self):
        """Importa un wallet con supporto per passphrase"""
        seed = input("Inserisci seed/mnemonic/numeri: ").strip()
        if not seed:
            return
        
        # 🔥 RILEVA SE È UNA MNEMONICA
        words = seed.strip().split()
        is_mnemonic = len(words) in [12, 24] and all(w.isalpha() for w in words)
        
        passphrase = ""
        if is_mnemonic:
            print("\n   🔐 Passphrase (opzionale, Invio per saltare):")
            print("      Inserisci la passphrase se il wallet è stato creato con una.")
            passphrase = getpass.getpass("   Passphrase: ").strip()
            if passphrase:
                print_cyan(f"   🔐 Passphrase usata")
            else:
                print_yellow("   ⚠️ Nessuna passphrase")
        
        name = input("Nome (imported): ").strip() or "imported"
        crypto = input("Crypto (auto/XRP/XLM): ").strip().upper() or "auto"
        network = input("Rete (testnet/mainnet): ").strip().lower() or "testnet"
        
        # 🔥 PASSA LA PASSPHRASE AL BACKEND
        result = self.backend.import_wallet(seed, name, crypto, network, passphrase=passphrase)
        if result.get("success"):
            print_green(f"\n✅ Wallet importato!")
            print(f"   Address: {result.get('address', 'N/A')}")
            print(f"   Type: {result.get('seed_type', 'N/A')}")
            if passphrase:
                print(f"   Passphrase: {'*' * len(passphrase)}")
        else:
            print_red(f"❌ Errore: {result.get('error', 'Unknown error')}")
    
    def _cmd_remove(self):
        """Rimuove un wallet"""
        wallets = self.backend.list_wallets()
        if not wallets:
            print_red("❌ Nessun wallet salvato")
            return
        
        print("\n🗑️  RIMUOVI WALLET")
        for i, w in enumerate(wallets, 1):
            marker = "▶" if w.get("is_active") else " "
            print(f"  {i}. {marker} {w['name']} ({w['crypto']} - {w['network']})")
        
        choice = input("\nNumero wallet da rimuovere (o Invio): ").strip()
        if not choice or not choice.isdigit():
            return
        
        idx = int(choice) - 1
        if 0 <= idx < len(wallets):
            name = wallets[idx]["name"]
            if wallets[idx].get("is_active"):
                print_red("❌ Non puoi rimuovere il wallet attivo")
                return
            confirm = input(f"   Rimuovere '{name}'? (s/N): ").strip().lower()
            if confirm == 's':
                result = self.backend.remove_wallet(name)
                if result.get("success"):
                    print_green(f"✅ {result.get('message', '')}")
                else:
                    print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_switch(self):
        """Cambia wallet attivo"""
        wallets = self.backend.list_wallets()
        if not wallets:
            print_red("❌ Nessun wallet salvato")
            return
        
        print("\n🔄 CAMBIA WALLET")
        for i, w in enumerate(wallets, 1):
            marker = "▶" if w.get("is_active") else " "
            address = w.get("address", "unknown")
            # 🔥 INDIRIZZO COMPLETO
            print(f"  {i}. {marker} {w['name']} ({w['crypto']} - {w['network']}) {address}")
        
        choice = input("\nNumero wallet (o Invio): ").strip()
        if not choice or not choice.isdigit():
            return
        
        idx = int(choice) - 1
        if 0 <= idx < len(wallets):
            name = wallets[idx]["name"]
            result = self.backend.switch_wallet(name)
            if result.get("success"):
                print_green(f"✅ Wallet cambiato a: {name}")
                print_yellow(f"   Rete: {result.get('network', 'testnet').upper()} | Crypto: {result.get('crypto', 'XRP')}")
            else:
                print_red(f"❌ {result.get('message', 'Errore')}")
    
    # ============================================================
    # COMANDI PRINCIPALI
    # ============================================================
    
    def _cmd_balance(self):
        """Mostra saldo"""
        result = self.backend.get_balance()
        if result.get("success"):
            print_green(f"💰 Saldo: {result.get('balance', 0):.6f} {result.get('crypto', 'XRP')}")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_address(self):
        """Mostra indirizzo"""
        result = self.backend.get_address()
        if result.get("success"):
            print_green(f"📤 Address: {result.get('address', 'N/A')}")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_derive(self):
        """Deriva indirizzi - FORMATTATO IN TABELLA"""
        keyword = input("Keyword (default): ").strip() or "default"
        count = int(input("Numero (5): ").strip() or "5")
        
        result = self.backend.derive_addresses(keyword, count)
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Errore')}")
            return
        
        addresses = result.get("addresses", [])
        
        if not addresses:
            print_yellow("❌ Nessun indirizzo derivato.")
            return
        
        print_bold(f"\n📤 INDIRIZZI DERIVATI ({keyword}: 0-{len(addresses)-1})")
        print("=" * 120)
        
        # Intestazione tabella
        print(f"{'#':<6} {'Indirizzo':<40} {'Private Key':<35} {'Public Key'}")
        print("-" * 120)
        
        for addr in addresses:
            idx = addr.get("index", 0)
            address = addr.get("address", "N/A")
            priv = addr.get("private_key", "")
            pub = addr.get("public_key", "")
            
            # Tronca le chiavi se troppo lunghe
            priv_display = priv[:30] + "..." if len(priv) > 33 else priv
            pub_display = pub[:30] + "..." if len(pub) > 33 else pub
            
            print(f"{idx:<6} {address:<40} {priv_display:<35} {pub_display}")
        
        print("-" * 120)
        print(f"Totale: {len(addresses)} indirizzi derivati")
        print("=" * 120)
    
    def _cmd_send(self):
        """Invia pagamento"""
        to_addr = input("Indirizzo destinatario: ").strip()
        if not to_addr:
            return
        try:
            amount = float(input("Ammontare: ").strip())
        except ValueError:
            print_red("❌ Ammontare non valido")
            return
        memo = input("Memo (opzionale): ").strip()
        
        result = self.backend.send_payment(to_addr, amount, memo)
        
        # 🔥 SE È VIA RETICULUM, MOSTRA IN BLU
        if result.get("via_reticulum", False):
            print_blue(f"📡 Richiesta transazione via Reticulum")
        
        if result.get("success"):
            print_green(f"✅ Pagamento inviato!")
            print(f"   Hash: {result.get('tx_hash', 'N/A')}")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_info(self):
        """Info wallet"""
        result = self.backend.get_wallet_info()
        if result.get("success"):
            print_bold("\n📊 INFO COMPLETA WALLET")
            print("=" * 60)
            print(f"   Crypto: {result.get('crypto', 'N/A')}")
            print(f"   Network: {result.get('network', 'N/A').upper()}")
            print(f"   Address: {result.get('address', 'N/A')}")
            print(f"   Seed Type: {result.get('seed_type', 'N/A')}")
            if result.get('balance') is not None:
                print(f"   Balance: {result.get('balance', 0):.6f} {result.get('crypto', 'XRP')}")
            if result.get('mnemonic'):
                print(f"\n   Mnemonic: {result.get('mnemonic')}")
                print(f"   Word Count: {len(result.get('mnemonic', '').split())}")
            if result.get('secret_numbers'):
                print(f"\n   Secret Numbers: {result.get('secret_numbers')}")
            if result.get('xrp_seed'):
                print(f"\n   XRP Seed: {result.get('xrp_seed')}")
            if result.get('stellar_seed'):
                print(f"\n   Stellar Seed: {result.get('stellar_seed')}")
            if result.get('private_key'):
                print(f"\n   Private Key: {result.get('private_key')}")
            if result.get('derived_wallets'):
                print(f"\n   Derived Wallets: {len(result.get('derived_wallets', []))}")
                for w in result.get('derived_wallets', [])[:5]:
                    print(f"      - {w.get('address', 'N/A')} ({w.get('keyword', 'default')}:{w.get('index', 0)})")
            print("=" * 60)
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_history(self):
        """Storico transazioni - FORMATTA E STAMPA"""
        limit = int(input("Numero transazioni (10): ").strip() or "10")
        result = self.backend.get_history(limit)
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Errore')}")
            return
        
        transactions = result.get("transactions", [])
        address = result.get("address", "")
        
        if not transactions:
            print_yellow("❌ Nessuna transazione trovata.")
            return
        
        # 🔥 FORMATTA E STAMPA (usa parse_tx_date importato)
        self._print_transactions(transactions, address)
        
        # Mostra explorer
        network = result.get("network", "mainnet")
        if network == "mainnet":
            explorer = f"https://xrpscan.com/account/{address}"
        elif network == "testnet":
            explorer = f"https://testnet.xrpl.org/accounts/{address}"
        else:
            explorer = f"https://devnet.xrpl.org/accounts/{address}"
        print(f"\n🔗 Visualizza tutto: {explorer}")
    
    def _print_transactions(self, transactions: List, address: str) -> None:
        """Stampa transazioni in formato tabella - UI SOLO"""
        import base64
        from datetime import datetime
        
        print("\n┌────┬─────────────────────┬────────────┬──────────────────┬────────────┬──────────────────────────────────────────────────┬────────────────────┐")
        print(f"│ #  │ Data/Ora            │ Tipo       │ Importo          │ Fee        │ Da/A                                              │ Memo               │")
        print("├────┼─────────────────────┼────────────┼──────────────────┼────────────┼──────────────────────────────────────────────────┼────────────────────┤")
        
        for idx, tx_data in enumerate(transactions, 1):
            tx = tx_data.get("tx_json", {})
            if not tx:
                continue
            
            tx_type = tx.get("TransactionType", "Unknown")
            date_str = parse_tx_date(tx, tx_data)  # <-- USA FUNZIONE GLOBALE
            
            fee_drops = tx.get("Fee", "0")
            try:
                fee_xrp = int(fee_drops) / 1_000_000
                fee_str = f"{fee_xrp:.6f}".rstrip('0').rstrip('.')
                if '.' in fee_str:
                    fee_str = fee_str[:10]
                if fee_str == "":
                    fee_str = "0"
            except:
                fee_str = fee_drops
            
            if tx_type == "Payment":
                amount = tx.get("Amount", tx.get("DeliverMax", "0"))
                
                if isinstance(amount, dict):
                    token_value = amount.get('value', '0')
                    token_currency = amount.get('currency', '???')
                    
                    # Decodifica currency se necessario
                    if len(token_currency) > 3:
                        try:
                            bytes_data = bytes.fromhex(token_currency)
                            while bytes_data and bytes_data[-1] == 0:
                                bytes_data = bytes_data[:-1]
                            decoded = bytes_data.decode('utf-8', errors='ignore').strip()
                            if decoded and all(32 <= ord(c) <= 126 for c in decoded):
                                token_currency = decoded
                        except:
                            pass
                    
                    try:
                        val_float = float(token_value)
                        amount_str = f"{val_float:.6f}".rstrip('0').rstrip('.')
                        if not amount_str:
                            amount_str = "0"
                        amount_str += f" {token_currency}"
                    except:
                        amount_str = f"{token_value[:8]} {token_currency}"
                else:
                    try:
                        amount_xrp = int(amount) / 1_000_000
                        amount_str = f"{amount_xrp:.6f}".rstrip('0').rstrip('.')
                        if not amount_str:
                            amount_str = "0"
                        amount_str += " XRP"
                    except:
                        amount_str = f"{amount} drops"
                
                sender = tx.get("Account", "unknown")
                destination = tx.get("Destination", "unknown")
                
                if destination == address:
                    direction = "RICEVUTO"
                    da_a = f"Da: {sender}"
                elif sender == address:
                    direction = "INVIATO"
                    da_a = f"A: {destination}"
                else:
                    direction = "ALTRO"
                    da_a = f"{sender} → {destination}"
                
                memo_display = ""
                memos = tx.get("Memos", [])
                if memos:
                    try:
                        memo_dict = memos[0].get("Memo", {})
                        memo_data = memo_dict.get("MemoData", "")
                        if memo_data:
                            memo_text = ""
                            try:
                                memo_bytes = bytes.fromhex(memo_data)
                                memo_text = memo_bytes.decode('utf-8', errors='ignore')
                            except:
                                try:
                                    while len(memo_data) % 4 != 0:
                                        memo_data += '='
                                    memo_bytes = base64.b64decode(memo_data)
                                    memo_text = memo_bytes.decode('utf-8', errors='ignore')
                                except:
                                    memo_text = memo_data[:20]
                            
                            if memo_text:
                                memo_clean = ''.join(c for c in memo_text if c.isprintable() or c == ' ')
                                if memo_clean.strip():
                                    memo_display = memo_clean[:256]
                    except:
                        pass
                
                if len(da_a) > 48:
                    da_a_display = da_a[:45] + "..."
                else:
                    da_a_display = da_a
                
                if len(memo_display) > 18:
                    memo_display = memo_display[:15] + "..."
                
                print(f"│ {idx:<2} │ {date_str[:19]:<19} │ {direction:<10} │ {amount_str:<16} │ {fee_str:<10} │ {da_a_display:<48} │ {memo_display:<18} │")
            else:
                print(f"│ {idx:<2} │ {date_str[:19]:<19} │ {tx_type:<10} │ {'':<16} │ {fee_str:<10} │ {'':<48} │ {'':<18} │")
        
        print("└────┴─────────────────────┴────────────┴──────────────────┴────────────┴──────────────────────────────────────────────────┴────────────────────┘")
        print(f"Totale: {len(transactions)} transazioni mostrate")

    def _cmd_fund_testnet(self):
        """Fund testnet"""
        result = self.backend.fund_testnet()
        if result.get("success"):
            print_green(f"✅ {result.get('message', '')}")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_export(self):
        """Esporta wallet"""
        include_private = input("Includi chiave privata? (s/N): ").strip().lower() == 's'
        result = self.backend.export_wallet(include_private)
        if result.get("success"):
            print(json.dumps(result.get("data", {}), indent=2, default=str))
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_change_password(self):
        """Cambia password"""
        old = getpass.getpass("Password attuale: ")
        if old != self._password:
            print_red("❌ Password errata")
            return
        new = getpass.getpass("Nuova password: ")
        confirm = getpass.getpass("Conferma password: ")
        if new != confirm:
            print_red("❌ Le password non corrispondono")
            return
        result = self.backend.change_password(old, new)
        if result.get("success"):
            self._password = new
            print_green("✅ Password cambiata con successo!")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    # ============================================================
    # TRUSTLINE
    # ============================================================
    
    def _menu_trustline(self):
        """Sottomenu trustline"""
        while True:
            print("\n🔗 GESTIONE TRUSTLINE")
            print("  1) Mostra trustline")
            print("  2) Crea trustline")
            print("  3) Rimuovi trustline")
            print("  4) Info trustline")
            print("  0) Torna al menu principale")
            
            sub = input("\nScelta: ").strip()
            
            if sub == '0':
                break
            elif sub == '1':
                self._cmd_trustlines()
            elif sub == '2':
                self._cmd_trustline_create()
            elif sub == '3':
                self._cmd_trustline_remove()
            elif sub == '4':
                self._cmd_trustline_info()
            else:
                print_red("❌ Scelta non valida")
    
    def _cmd_trustlines(self):
        """Mostra trustline - FORMATTATO COME LE ALTRE TABELLE"""
        result = self.backend.get_trustlines()
        if result.get("success"):
            trustlines = result.get("trustlines", [])
            if not trustlines:
                print_yellow("❌ Nessuna trustline trovata")
                return
            
            # 🔥 DETERMINA IL NETWORK
            network = "MAINNET" if self.backend.wallet._xrp_manager.network == "mainnet" else "TESTNET"
            crypto = self.backend.wallet._xrp_manager.crypto_type
            
            print_bold(f"\n🔗 TRUSTLINES ({crypto}) su {network}")
            print("=" * 100)
            print(f"{'#':<4} {'Asset':<12} {'Issuer':<36} {'Balance':<16} {'Limit':<14} {'Status'}")
            print("-" * 100)
            
            for i, tl in enumerate(trustlines, 1):
                asset = tl.get('currency', tl.get('asset_code', '???'))
                issuer = tl.get('issuer', tl.get('asset_issuer', 'N/A'))
                balance = tl.get('balance', 0)
                limit = tl.get('limit', 0)
                is_active = tl.get('is_active', False)
                
                # 🔥 FORMATTA NUMERI
                try:
                    bal_str = f"{float(balance):.6f}".rstrip('0').rstrip('.')
                    if not bal_str:
                        bal_str = "0"
                except:
                    bal_str = str(balance)
                
                try:
                    lim_str = f"{float(limit):.6f}".rstrip('0').rstrip('.')
                    if not lim_str:
                        lim_str = "0"
                except:
                    lim_str = str(limit)
                
                # 🔥 STATUS
                if is_active:
                    status = "✅ Active"
                elif balance > 0:
                    status = "⚠️ Has balance"
                else:
                    status = "⏳ Pending"
                
                # 🔥 TRONCA ISSUER SE TROPPO LUNGO
                issuer_display = issuer if len(issuer) <= 34 else issuer[:32] + "..."
                
                print(f"{i:<4} {asset:<12} {issuer_display:<36} {bal_str:<16} {lim_str:<14} {status}")
            
            print("=" * 100)
            print(f"Total: {len(trustlines)} trustlines")
            print("=" * 100)
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_trustline_create(self):
        """Crea trustline"""
        asset = input("Asset (es. RLUSD): ").strip()
        issuer = input("Issuer address: ").strip()
        try:
            limit = float(input("Limite (0 per rimuovere): ").strip() or "0")
        except ValueError:
            limit = 0
        result = self.backend.create_trustline(asset, issuer, limit)
        if result.get("success"):
            print_green(f"✅ Trustline creata per {asset}!")
            print(f"   Hash: {result.get('hash', 'N/A')}")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_trustline_remove(self):
        """Rimuovi trustline"""
        asset = input("Asset: ").strip()
        issuer = input("Issuer address: ").strip()
        result = self.backend.remove_trustline(asset, issuer)
        if result.get("success"):
            print_green(f"✅ Trustline rimossa per {asset}!")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_trustline_info(self):
        """Info trustline"""
        asset = input("Asset: ").strip()
        issuer = input("Issuer (opzionale): ").strip() or None
        result = self.backend.get_trustline_info(asset, issuer)
        if result.get("success"):
            print_bold(f"\n📊 INFO TRUSTLINE {asset}")
            print("=" * 60)
            print(f"   Asset: {result.get('asset', 'N/A')}")
            print(f"   Issuer: {result.get('issuer', 'N/A')}")
            print(f"   Balance: {result.get('balance', 0):.6f}")
            print(f"   Limit: {result.get('limit', 0):.6f}")
            print(f"   Status: {'✅ Attiva' if result.get('is_active') else '⏳ In attesa'}")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    # ============================================================
    # TOKEN
    # ============================================================
    
    def _cmd_send_token(self):
        """Invia token"""
        to_addr = input("Indirizzo destinatario: ").strip()
        if not to_addr:
            return
        token = input("Nome token (es. Arg0): ").strip()
        if not token:
            return
        try:
            amount = float(input("Ammontare: ").strip())
        except ValueError:
            print_red("❌ Ammontare non valido")
            return
        issuer = input("Issuer (opzionale): ").strip() or None
        
        # 🔥 CHIEDI DESTINATION TAG
        dest_tag_input = input("Destination Tag (opzionale, numero): ").strip()
        dest_tag = int(dest_tag_input) if dest_tag_input else None
        
        result = self.backend.send_token(to_addr, token, amount, issuer, dest_tag)
        if result.get("success"):
            print_green(f"✅ {amount} {token} inviati!")
            print(f"   Hash: {result.get('tx_hash', 'N/A')}")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    # ============================================================
    # RETICULUM
    # ============================================================
    
    def _menu_reticulum(self):
        while True:
            status = self.backend.get_status()
            internet_status = "🌐 ON" if self.backend.use_internet else "📡 OFF (Reticulum)"
            
            print("\n" + "=" * 50)
            print("  📡 RETICULUM")
            print("=" * 50)
            print(f"  Gateway: {'✅ Attivo' if status.get('gateway_active') else '❌ Fermo'}")
            print(f"  Peer conosciuti: {status.get('wallet_count', 0)}")
            print(f"  Modalità internet: {internet_status}")
            
            print("\n" + "-" * 50)
            print("  1) Stato gateway")
            print("  2) Avvia gateway")
            print("  3) Ferma gateway")
            print("  4) Scopri gateway")
            print("  5) Scopri wallet")
            print("  6) Peer metriche")
            print("  7) Miglior gateway")
            print("  8) Richiedi info gateway")
            print("  9) Testa tutti i gateway")
            print(" 10) 🌐 Toggle internet (usa Reticulum)")
            print(" 11) 🗑️ Rimuovi gateway manualmente")
            print("  0) Torna al menu principale")
            
            sub = input("\nScelta: ").strip()
            
            if sub == '0':
                break
            elif sub == '1':
                self._cmd_gateway_status()
            elif sub == '2':
                self._cmd_gateway_start()
            elif sub == '3':
                self._cmd_gateway_stop()
            elif sub == '4':
                self._cmd_discover_gateways()
            elif sub == '5':
                self._cmd_discover_wallets()
            elif sub == '6':
                self._cmd_peer_metrics()
            elif sub == '7':
                self._cmd_best_gateway()
            elif sub == '8':
                self._cmd_request_info()
            elif sub == '9':
                self._cmd_test_gateways()
            elif sub == '10':
                self._cmd_toggle_internet()
            elif sub == '11':
                self._cmd_remove_gateway()
            else:
                print_red("❌ Scelta non valida")
    
    def _cmd_gateway_status(self):
        """Stato gateway"""
        result = self.backend.get_gateway_status()
        if result.get("success"):
            status = result.get("status", {})
            print_bold("\n📊 STATO GATEWAY")
            print("=" * 60)
            print(f"   Running: {status.get('running', False)}")
            print(f"   Gateway: {status.get('is_gateway', False)}")
            print(f"   PID: {status.get('pid', 'N/A')}")
            if status.get('started_at'):
                print(f"   Started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(status['started_at']))}")
            print(f"   Gateway Address: {status.get('gateway_address', 'N/A')}")
            print(f"   Wallet Address: {status.get('wallet_address', 'N/A')}")
            print(f"   Gateway Count: {status.get('gateway_count', 0)}")
            print(f"   Wallet Count: {status.get('wallet_count', 0)}")
            print("=" * 60)
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_gateway_start(self):
        """Avvia gateway"""
        result = self.backend.start_gateway()
        if result.get("success"):
            print_green("✅ Gateway avviato")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_gateway_stop(self):
        """Ferma gateway"""
        result = self.backend.stop_gateway()
        if result.get("success"):
            print_green("✅ Gateway fermato")
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_discover_gateways(self):
        """Scopri gateway - FORMATTATO COME PRIMA"""
        result = self.backend.discover_gateways()
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Errore')}")
            return
        
        gateways = result.get("gateways", [])
        
        print_bold(f"\n🔍 GATEWAY TROVATI ({len(gateways)})")
        print("=" * 100)
        print(f"{'Nome':<20} {'Hash':<36} {'First Seen':<20} {'Last Seen':<20} {'Hops':<6}")
        print("-" * 100)
        
        for gw in gateways:
            name = gw.get('name', 'Sconosciuto')[:18]
            gw_id = gw.get('gateway_id', '?')
            first_seen = gw.get('first_seen')
            last_seen = gw.get('last_seen')
            
            first_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(first_seen)) if first_seen else 'Mai'
            last_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen)) if last_seen else 'Mai'
            hops = gw.get('hops', '?')
            
            print(f"{name:<20} {gw_id:<36} {first_str:<20} {last_str:<20} {hops:<6}")
        
        print("=" * 100)
        print(f"Totale: {len(gateways)} gateway in cache")
        print("=" * 100)

    def _cmd_discover_wallets(self):
        """Scopri wallet - FORMATTATO COME PRIMA"""
        result = self.backend.discover_wallets()
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Errore')}")
            return
        
        wallets = result.get("wallets", [])
        
        print_bold(f"\n🔍 WALLET TROVATI ({len(wallets)})")
        print("=" * 100)
        print(f"{'Nome':<20} {'Hash':<36} {'First Seen':<20} {'Last Seen':<20} {'Hops':<6}")
        print("-" * 100)
        
        for w in wallets:
            name = w.get('name', 'Sconosciuto')[:18]
            w_id = w.get('wallet_id', '?')
            first_seen = w.get('first_seen')
            last_seen = w.get('last_seen')
            
            first_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(first_seen)) if first_seen else 'Mai'
            last_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen)) if last_seen else 'Mai'
            hops = w.get('hops', '?')
            
            print(f"{name:<20} {w_id:<36} {first_str:<20} {last_str:<20} {hops:<6}")
        
        print("=" * 100)
        print(f"Totale: {len(wallets)} wallet in cache")
        print("=" * 100)
    
    def _cmd_peer_metrics(self):
        """Peer metriche - USA SCORE DAL BACKEND"""
        result = self.backend.get_peer_metrics()
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Errore')}")
            return
        
        peers = result.get("peers", [])
        if not peers:
            print_yellow("⚠️ Nessun peer conosciuto")
            return
        
        print_bold(f"\n🔍 PEER ORDINATI PER PERFORMANCE ({len(peers)})")
        print("=" * 260)
        print(f"{'#':<3} {'Nome':<22} {'Score':<6} {'Rel':<6} {'Rep':<4} {'Hops':<5} {'RTT':<8} {'XRP':<14} {'Stellar':<14} {'Internet':<9} {'Ultimo visto':<15} {'ID':<36} {'Assets'}")
        print("-" * 260)
        
        for idx, p in enumerate(peers, 1):
            # 🔥 SCORE GIÀ CALCOLATO DAL BACKEND
            sc = round(p.get('_score', 0))
            name = str(p.get('name', 'UNKNOWN'))[:16]            
            rel = round(p.get('reliability', 0), 2)
            rep = p.get('reputation', 50)
            hops = str(p.get('hops', '?'))
            rtt = f"{p.get('latency_ms', '?')}ms"
            
            # XRP
            if p.get('xrp_reachable'):
                xrp_lat = p.get('xrp_latency_ms')
                xrp_str = f"✅{xrp_lat}ms" if xrp_lat else "✅ OK"
            else:
                xrp_str = "❌"
            
            # Stellar
            if p.get('stellar_reachable'):
                stellar_lat = p.get('stellar_latency_ms')
                stellar_str = f"✅{stellar_lat}ms" if stellar_lat else "✅ OK"
            else:
                stellar_str = "❌"
            
            internet = "🌐" if p.get('has_internet') else "📡"
            last_seen = format_time_ago(p.get('last_seen'))  # <-- USA FUNZIONE GLOBALE
            gw_id = p.get('gateway_id', 'N/A')[:36]
            
            assets = p.get('assets', [])
            if isinstance(assets, list):
                assets_str = ', '.join(assets[:3])
                if len(assets) > 3:
                    assets_str += f" +{len(assets)-3}"
            else:
                assets_str = str(assets)[:20]
            
            # Colori
            sc_color = Colors.GREEN if sc > 70 else Colors.YELLOW if sc > 40 else Colors.RED
            rel_color = Colors.GREEN if rel > 0.9 else Colors.YELLOW if rel > 0.7 else Colors.RED
            
            print(f"{idx:<3} {name:<20} {sc_color}{sc:5.0f}{Colors.RESET} {rel_color}{rel:5.2f}{Colors.RESET} {rep:<4} {hops:<5} {rtt:<8} {xrp_str:<14} {stellar_str:<14} {internet:<9} {last_seen:<15} {gw_id:<36} {assets_str}")
        
        print("=" * 260)
        
        # Statistiche
        stats = result.get("stats", {})
        if stats:
            print(f"\n📊 Statistiche:")
            print(f"   Totale peer: {stats.get('total_peers', 0)}")
            print(f"   Online: {stats.get('online_peers', 0)}")
            print(f"   Offline: {stats.get('offline_peers', 0)}")
            print(f"   Reputazione media: {round(stats.get('avg_reputation', 0), 1)}")
            if stats.get('avg_latency_ms'):
                print(f"   Latenza media Reticulum: {round(stats.get('avg_latency_ms'), 0)}ms")
            if stats.get('avg_score'):
                print(f"   Score medio: {round(stats.get('avg_score'))}")
        
        # Miglior peer
        if peers:
            b = peers[0]
            best_score = b.get('_score', 0)
            print(f"\n🏆 MIGLIOR PEER: {b.get('name', 'UNKNOWN')}")
            print(f"   Score: {best_score:.0f} | Rel: {b.get('reliability', 0):.2f} | Rep: {b.get('reputation', 50)}")
            print(f"   Gateway ID: {b.get('gateway_id', 'N/A')}")
            print(f"   RTT Reticulum: {b.get('latency_ms', '?')}ms | Hops: {b.get('hops', '?')}")
            print(f"   XRP: {'✅' if b.get('xrp_reachable') else '❌'} ({b.get('xrp_latency_ms', '?')}ms)")
            print(f"   Stellar: {'✅' if b.get('stellar_reachable') else '❌'} ({b.get('stellar_latency_ms', '?')}ms)")
            print(f"   Internet: {'✅' if b.get('has_internet') else '❌'}")
            if b.get('assets'):
                print(f"   Assets: {', '.join(b.get('assets', []))}")
    
    def _cmd_best_gateway(self):
        """Miglior gateway - MOSTRA TUTTE LE INFO"""
        asset = input("Asset (es. RLUSD): ").strip()
        if not asset:
            print_red("❌ Specifica un asset")
            return
        result = self.backend.get_best_gateway(asset)
        if result.get("success"):
            gw = result.get("gateway", {})
            if not gw:
                print_yellow(f"⚠️ Nessun gateway trovato per {asset}")
                return
            
            print_bold(f"\n🏆 MIGLIOR GATEWAY PER {asset.upper()}")
            print("=" * 70)
            print(f"   Nome:           {gw.get('name', 'UNKNOWN')}")
            print(f"   Gateway ID:     {gw.get('gateway_id', 'N/A')}")
            print(f"   Hops:           {gw.get('hops', '?')}")
            print(f"   RTT Reticulum:  {gw.get('latency_ms', '?')}ms")
            print(f"   Reputazione:    {gw.get('reputation', 50)}")
            print(f"   Affidabilità:   {gw.get('reliability', 0):.2f}")
            print(f"   Internet:       {'✅' if gw.get('has_internet') else '❌'}")
            print(f"   Status:         {'✅ ONLINE' if gw.get('is_online') else '❌ OFFLINE'}")
            print("-" * 70)
            
            # XRP
            if gw.get('xrp_reachable'):
                print(f"   XRP:            ✅ Raggiungibile ({gw.get('xrp_latency_ms', '?')}ms)")
            else:
                print(f"   XRP:            ❌ Non raggiungibile")
            
            # Stellar
            if gw.get('stellar_reachable'):
                print(f"   Stellar:        ✅ Raggiungibile ({gw.get('stellar_latency_ms', '?')}ms)")
            else:
                print(f"   Stellar:        ❌ Non raggiungibile")
            
            # Assets
            assets = gw.get('assets', [])
            if isinstance(assets, list) and assets:
                print(f"   Assets:         {', '.join(assets)}")
            
            # Networks
            networks = gw.get('networks', [])
            if isinstance(networks, list) and networks:
                print(f"   Networks:       {', '.join(networks)}")
            
            # Fee
            fee = gw.get('fee', 'N/A')
            fee_asset = gw.get('fee_asset', '')
            if fee != 'N/A':
                print(f"   Fee:            {fee} {fee_asset}")
            
            # RSSI/SNR (se disponibili)
            if gw.get('rssi') is not None:
                print(f"   RSSI:           {gw.get('rssi')}dBm")
            if gw.get('snr') is not None:
                print(f"   SNR:            {gw.get('snr')}dB")
            
            print("=" * 70)
        else:
            print_red(f"❌ {result.get('message', 'Errore')}")
    
    def _cmd_request_info(self):
        """Richiedi info a un gateway specifico - USA discover_gateways()"""
        if not self.backend.metrics:
            print_red("❌ Metriche non disponibili")
            return
        
        # 🔥 USA discover_gateways() DEL BACKEND
        result = self.backend.discover_gateways(active_only=False)
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Errore')}")
            return
        
        gateways = result.get("gateways", [])
        
        # 🔥 FILTRA IL PROPRIO GATEWAY
        my_id = self.backend.reticulum.gateway_address if hasattr(self.backend.reticulum, 'gateway_address') else None
        if my_id:
            gateways = [g for g in gateways if g.get('gateway_id') != my_id]
        
        if not gateways:
            print_yellow("⚠️ Solo il proprio gateway trovato, nessun peer disponibile")
            return
        
        # 🔥 MOSTRA LISTA CON INDIRIZZO COMPLETO
        print_blue("🔍 Gateway disponibili:")
        print(f"   Trovati {len(gateways)} gateway (escluso se stesso)")
        for i, gw in enumerate(gateways, 1):
            name = gw.get('name', 'UNKNOWN')
            gw_id = gw.get('gateway_id', '?')
            hops = gw.get('hops', '?')
            rssi = gw.get('rssi')
            rssi_str = f" RSSI:{rssi:.1f}dBm" if rssi is not None else ""
            print(f"   {i}) {name} ({gw_id}) Hops:{hops}{rssi_str}")
        
        try:
            choice = input("\nScegli gateway (numero): ").strip()
            if not choice:
                return
            
            idx = int(choice) - 1
            if 0 <= idx < len(gateways):
                gateway_id = gateways[idx].get('gateway_id')
                if gateway_id:
                    print_blue(f"📡 Richiedo info a {gateway_id}")
                    result = self.backend.request_gateway_info(gateway_id)
                    
                    if result.get("success"):
                        peer = result.get("peer")
                        if peer:
                            self.backend._show_single_peer(peer)
                        else:
                            print_green("✅ Richiesta inviata e risposta ricevuta!")
                    else:
                        print_red(f"❌ {result.get('message', 'Errore')}")
                else:
                    print_red("❌ Gateway ID non valido")
            else:
                print_red("❌ Scelta non valida")
        except ValueError:
            print_red("❌ Inserisci un numero valido")
    
    def _cmd_test_gateways(self):
        """Testa tutti i gateway attivi"""
        print("\n📡 Test di tutti i gateway attivi in corso...")
        print("   Questo aggiornerà i dati dei peer nel database.")
        print("   Per vedere la classifica, usa '6) Peer metriche'.\n")
        
        result = self.backend.test_all_gateways()
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Errore')}")
            return
        
        results = result.get("results", [])
        
        if not results:
            print_yellow("⚠️ Nessun gateway attivo trovato")
            return
        
        print_bold(f"\n📊 TEST COMPLETATO")
        print("=" * 60)
        print(f"   Gateway testati: {result.get('count', 0)}")
        print(f"   Risposte ricevute: {result.get('successful', 0)}")
        print("=" * 60)
        
        # Tabella semplice
        print("\n📋 RISULTATI:")
        print("-" * 80)
        print(f"{'#':<3} {'Nome':<20} {'Stato':<12} {'Hops':<6}")
        print("-" * 80)
        
        for idx, r in enumerate(results, 1):
            print(f"{idx:<3} {r.get('name', 'UNKNOWN'):<20} {r.get('status', '?'):<12} {r.get('hops', '?'):<6}")
        
        print("-" * 80)
        print_green("\n✅ Dati aggiornati! Usa '6) Peer metriche' per vedere la classifica completa.")

    def _cmd_remove_gateway(self):
        """Rimuovi un gateway manualmente da announce_cache e gateway_peers"""
        print("\n🗑️ RIMUOVI GATEWAY MANUALMENTE")
        print("=" * 60)
        print("   Questa operazione rimuove il gateway da:")
        print("   - announce_cache.db (annunci)")
        print("   - gateway_peers.db (metriche)")
        print("")
        
        # Prima mostra la lista dei gateway disponibili
        result = self.backend.discover_gateways(active_only=False)
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Errore')}")
            return
        
        gateways = result.get("gateways", [])
        if not gateways:
            print_yellow("⚠️ Nessun gateway trovato")
            return
        
        print("📋 GATEWAY DISPONIBILI:")
        print("-" * 80)
        print(f"{'#':<4} {'Nome':<20} {'ID':<38} {'Last Seen'}")
        print("-" * 80)
        
        for i, gw in enumerate(gateways, 1):
            name = gw.get('name', 'UNKNOWN')[:18]
            gw_id = gw.get('gateway_id', '?')
            last_seen = gw.get('last_seen')
            if last_seen:
                last_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen))
            else:
                last_str = 'Mai'
            print(f"{i:<4} {name:<20} {gw_id:<38} {last_str}")
        
        print("-" * 80)
        print("")
        
        choice = input("Numero gateway da rimuovere (o Invio per annullare): ").strip()
        if not choice:
            print_yellow("❌ Operazione annullata")
            return
        
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(gateways):
                print_red("❌ Numero non valido")
                return
            
            gw = gateways[idx]
            gw_id = gw.get('gateway_id')
            name = gw.get('name', 'UNKNOWN')
            
            # Chiedi conferma
            print(f"\n⚠️ Stai per rimuovere: {name} ({gw_id[:16]}...)")
            confirm = input("   Confermi? (s/N): ").strip().lower()
            if confirm != 's':
                print_yellow("❌ Operazione annullata")
                return
            
            # Esegui la rimozione
            result = self.backend.remove_gateway(gw_id)
            if result.get("success"):
                print_green(f"✅ {result.get('message', 'Rimosso con successo')}")
                if result.get("removed_from_announce"):
                    print("   ✅ Rimosso da announce_cache.db")
                if result.get("removed_from_peers"):
                    print("   ✅ Rimosso da gateway_peers.db")
            else:
                print_red(f"❌ {result.get('message', 'Errore')}")
                
        except ValueError:
            print_red("❌ Inserisci un numero valido")

    def _cmd_toggle_internet(self):
        """Toggle uso internet / reticulum"""
        current = self.backend.use_internet
        self.backend.set_use_internet(not current)
        if current:
            print_green("🌐 Modalità Internet disattivata")
            print_yellow("   Le operazioni useranno Reticulum (se disponibile)")
        else:
            print_green("🌐 Modalità Internet attivata")
            print_yellow("   Le operazioni useranno connessione diretta")

# ============================================================
# MAIN
# ============================================================

def main():
    """Entry point"""
    cli = PaxWalletCLI()
    cli.run()


if __name__ == "__main__":
    main()