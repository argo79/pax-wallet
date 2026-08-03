#!/usr/bin/env python3
"""
paxwallet.py - CLI Frontend for PAX Wallet
Uses WalletBackend for ALL logic
UI and menu only - ~600 lines
"""

import sys
import json
import getpass
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# ============================================================
# IMPORT BACKEND AND SHARED UTILITIES
# ============================================================

from wallet_backend import WalletBackend, create_backend, Colors, format_time_ago, parse_tx_date


# ============================================================
# VERSION
# ============================================================
VERSION = "0.10.1b"
__version__ = VERSION


# ============================================================
# COLOR PRINT FUNCTIONS (USE Colors FROM BACKEND)
# ============================================================

def print_green(msg): print(f"{Colors.GREEN}{msg}{Colors.RESET}")
def print_yellow(msg): print(f"{Colors.YELLOW}{msg}{Colors.RESET}")
def print_blue(msg): print(f"{Colors.BLUE}{msg}{Colors.RESET}")
def print_red(msg): print(f"{Colors.RED}{msg}{Colors.RESET}")
def print_cyan(msg): print(f"{Colors.CYAN}{msg}{Colors.RESET}")
def print_bold(msg): print(f"{Colors.BOLD}{msg}{Colors.RESET}")


# ============================================================
# UTILITIES (frontend-specific only)
# ============================================================

def format_address(address: str, length: int = 25) -> str:
    if not address:
        return "N/A"
    if len(address) <= length:
        return address
    return address[:length] + "..."


# ============================================================
# CLI CLASS
# ============================================================

class PaxWalletCLI:
    """CLI Frontend for PAX Wallet - USES BACKEND"""
    
    def __init__(self):
        self.backend: Optional[WalletBackend] = None
        self._password: Optional[str] = None
        self._running = True

    # ============================================================
    # UNLOCK
    # ============================================================
    
    def _unlock(self) -> bool:
        """Ask for password and initialize backend"""
        print("\n" + "=" * 60)
        print("  🔐 PAX WALLET - UNLOCK")
        print("=" * 60)
        print("")
        
        temp_backend = create_backend()
        has_encrypted = temp_backend._has_encrypted_files()
        
        if has_encrypted:
            print("   Enter the password to unlock the wallet.")
            print("")
            max_attempts = 3
            attempts = 0
            
            while attempts < max_attempts:
                password = getpass.getpass("🔐 Password: ")
                if not password:
                    print_red("❌ Password cannot be empty")
                    attempts += 1
                    continue
                
                # 🔥 TRY TO INITIALIZE WITH THIS PASSWORD
                self.backend = create_backend(password)
                result = self.backend.init()
                
                # Verify if wallet loaded correctly
                active = self.backend.get_active_wallet()
                if active.get("name") and active.get("loaded"):
                    self._password = password
                    print_green("✅ Password verified")
                    return True
                
                # If we get here, password is wrong
                attempts += 1
                remaining = max_attempts - attempts
                print_red(f"❌ Incorrect password. Attempts remaining: {remaining}")
                
                if remaining == 0:
                    print_red("❌ Too many failed attempts.")
                    return False
        else:
            print("   🔑 No encrypted wallet found.")
            print("   Create a new password to protect your wallets.")
            print("")
            while True:
                password = getpass.getpass("🔐 New password: ")
                if not password:
                    print_red("❌ Password cannot be empty")
                    continue
                confirm = getpass.getpass("   Confirm password: ")
                if confirm == password:
                    break
                print_red("❌ Passwords do not match")
            
            self._password = password
            self.backend = create_backend(password)
            self.backend.init()
            print_green("✅ Password created")
            return True
        
        return False
    
    # ============================================================
    # MAIN LOOP
    # ============================================================
    
    def run(self):
        """Start the main loop"""
        if not self._unlock():
            print_red("❌ Cannot start PAX Wallet")
            return
        
        print_bold("\n" + "=" * 60)
        print_bold("    💰 PAX WALLET")
        print_bold("=" * 60)
        print("")
        print_green("🔐 Wallet encrypted with AES-256-GCM")
        print_green(f"📡 Reticulum: {'Active' if self.backend.reticulum else 'Not available'}")
        
        while self._running:
            try:
                self._show_main_menu()
                choice = input("\nChoice: ").strip()
                self._handle_main_choice(choice)
            except KeyboardInterrupt:
                print("\n")
                print_yellow("⚠️ Interrupted")
                break
            except Exception as e:
                print_red(f"❌ Error: {e}")
        
        self._cleanup()
        print_green("👋 Goodbye!")
    
    def _cleanup(self):
        """Clean up on exit"""
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
        """Show main menu"""
        active = self.backend.get_active_wallet() if self.backend else {}
        status = self.backend.get_status() if self.backend else {}
        
        print("\n" + "-" * 40)
        print("  1) Wallet")
        print("  2) Show balance")
        print("  3) Show address")
        print("  4) Derive addresses")
        print("  5) Send payment")
        print("  6) Wallet info")
        print("  7) History")
        print("  8) Fund testnet (XLM)")
        print("  9) Export")
        print(" 10) Trustline")
        print(" 11) Send token")
        print(" 12) Reticulum")
        print(" 13) Change password")
        print("  0) Exit")
        
        if active.get("name"):
            print_yellow(f"  📂 Wallet: {active['name']} ({active['network'].upper()} - {active['crypto']})")
        else:
            print_red("  📂 No wallet loaded")
        
        if status.get('gateway_active'):
            print_yellow("  📡 Gateway active")
        print("-" * 40)
    
    def _handle_main_choice(self, choice: str):
        """Handle main menu choices"""
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
            print_red("❌ Invalid choice")
    
    # ============================================================
    # WALLET SUBMENU
    # ============================================================
    
    def _menu_wallet(self):
        """Wallet management submenu"""
        while True:
            active = self.backend.get_active_wallet()
            wallets = self.backend.list_wallets()
            
            print("\n" + "=" * 50)
            print("  📂 WALLET")
            print("=" * 50)
            print(f"  Active wallet: {active.get('name') or 'NONE'}")
            print("\n  📋 Wallet list:")
            if wallets:
                for i, w in enumerate(wallets, 1):
                    marker = "▶" if w.get("is_active") else " "
                    address = w.get("address", "unknown")
                    # 🔥 DON'T TRUNCATE! Show COMPLETE address
                    print(f"    {i}. {marker} {w['name']:<15} ({w['crypto']} - {w['network']}) {address}")
            else:
                print("    ❌ No saved wallets")
            
            print("\n" + "-" * 50)
            print("  1) Create wallet")
            print("  2) Import wallet")
            print("  3) Remove wallet")
            print("  4) Switch wallet")
            print("  0) Return to main menu")
            print("-" * 50)
            
            sub = input("\nChoice: ").strip()
            
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
                print_red("❌ Invalid choice")
    
    # ============================================================
    # WALLET COMMANDS
    # ============================================================
    
    def _cmd_create(self):
        """Create a new wallet with support for strength and passphrase"""
        name = input("Name (default): ").strip() or "default"
        crypto = input("Crypto (XRP/XLM): ").strip().upper() or "XRP"
        network = input("Network (testnet/mainnet): ").strip().lower() or "testnet"
        
        print("\n   🔐 Choose number of words:")
        print("      1) 12 words (standard)")
        print("      2) 24 words (maximum security)")
        choice = input("   Choice (1 or 2, default 2): ").strip()
        strength = 128 if choice == "1" else 256
        
        print("\n   🔐 Passphrase (optional, Enter to skip):")
        print("      If you forget it, the wallet is unrecoverable.")
        passphrase = getpass.getpass("   Passphrase: ").strip()
        if passphrase:
            confirm = getpass.getpass("   Confirm passphrase: ").strip()
            if confirm != passphrase:
                print_red("❌ Passphrases do not match!")
                return
            print_cyan(f"   🔐 Passphrase set")
        else:
            print_yellow("   ⚠️ No passphrase")
        
        # 🔥 PASS strength AND passphrase TO BACKEND
        result = self.backend.create_wallet(name, crypto, network, strength=strength, passphrase=passphrase)
        
        if result.get("success"):
            print_green(f"\n✅ Wallet created on {network.upper()}!")
            print(f"   Address: {result.get('address', 'N/A')}")
            print(f"   Mnemonic: {result.get('mnemonic', 'N/A')}")
            print(f"   Word Count: {result.get('word_count', 0)}")
            if passphrase:
                print(f"   Passphrase: {'*' * len(passphrase)}")
                print_yellow("\n   ⚠️ WARNING: Passphrase is NOT stored in the wallet!")
                print_yellow("   Keep it in a safe place, SEPARATE from the seed.")
                print_yellow("   Without the passphrase you CANNOT recover the wallet.")
            print(f"   Seed: {result.get('seed', 'N/A')}")
        else:
            print_red(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    def _cmd_import(self):
        """Import a wallet with passphrase support"""
        seed = input("Enter seed/mnemonic/numbers: ").strip()
        if not seed:
            return
        
        # 🔥 DETECT IF IT'S A MNEMONIC
        words = seed.strip().split()
        is_mnemonic = len(words) in [12, 24] and all(w.isalpha() for w in words)
        
        passphrase = ""
        if is_mnemonic:
            print("\n   🔐 Passphrase (optional, Enter to skip):")
            print("      Enter the passphrase if the wallet was created with one.")
            passphrase = getpass.getpass("   Passphrase: ").strip()
            if passphrase:
                print_cyan(f"   🔐 Passphrase used")
            else:
                print_yellow("   ⚠️ No passphrase")
        
        name = input("Name (imported): ").strip() or "imported"
        crypto = input("Crypto (auto/XRP/XLM): ").strip().upper() or "auto"
        network = input("Network (testnet/mainnet): ").strip().lower() or "testnet"
        
        # 🔥 PASS PASSPHRASE TO BACKEND
        result = self.backend.import_wallet(seed, name, crypto, network, passphrase=passphrase)
        if result.get("success"):
            print_green(f"\n✅ Wallet imported!")
            print(f"   Address: {result.get('address', 'N/A')}")
            print(f"   Type: {result.get('seed_type', 'N/A')}")
            if passphrase:
                print(f"   Passphrase: {'*' * len(passphrase)}")
        else:
            print_red(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    def _cmd_remove(self):
        """Remove a wallet"""
        wallets = self.backend.list_wallets()
        if not wallets:
            print_red("❌ No saved wallets")
            return
        
        print("\n🗑️  REMOVE WALLET")
        for i, w in enumerate(wallets, 1):
            marker = "▶" if w.get("is_active") else " "
            print(f"  {i}. {marker} {w['name']} ({w['crypto']} - {w['network']})")
        
        choice = input("\nWallet number to remove (or Enter): ").strip()
        if not choice or not choice.isdigit():
            return
        
        idx = int(choice) - 1
        if 0 <= idx < len(wallets):
            name = wallets[idx]["name"]
            if wallets[idx].get("is_active"):
                print_red("❌ Cannot remove the active wallet")
                return
            confirm = input(f"   Remove '{name}'? (y/N): ").strip().lower()
            if confirm == 'y':
                result = self.backend.remove_wallet(name)
                if result.get("success"):
                    print_green(f"✅ {result.get('message', '')}")
                else:
                    print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_switch(self):
        """Switch active wallet"""
        wallets = self.backend.list_wallets()
        if not wallets:
            print_red("❌ No saved wallets")
            return
        
        print("\n🔄 SWITCH WALLET")
        for i, w in enumerate(wallets, 1):
            marker = "▶" if w.get("is_active") else " "
            address = w.get("address", "unknown")
            # 🔥 COMPLETE ADDRESS
            print(f"  {i}. {marker} {w['name']} ({w['crypto']} - {w['network']}) {address}")
        
        choice = input("\nWallet number (or Enter): ").strip()
        if not choice or not choice.isdigit():
            return
        
        idx = int(choice) - 1
        if 0 <= idx < len(wallets):
            name = wallets[idx]["name"]
            result = self.backend.switch_wallet(name)
            if result.get("success"):
                print_green(f"✅ Wallet switched to: {name}")
                print_yellow(f"   Network: {result.get('network', 'testnet').upper()} | Crypto: {result.get('crypto', 'XRP')}")
            else:
                print_red(f"❌ {result.get('message', 'Error')}")
    
    # ============================================================
    # MAIN COMMANDS
    # ============================================================
    
    def _cmd_balance(self):
        """Show balance"""
        result = self.backend.get_balance()
        if result.get("success"):
            print_green(f"💰 Balance: {result.get('balance', 0):.6f} {result.get('crypto', 'XRP')}")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_address(self):
        """Show address"""
        result = self.backend.get_address()
        if result.get("success"):
            print_green(f"📤 Address: {result.get('address', 'N/A')}")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_derive(self):
        """Derive addresses - FORMATTED AS TABLE"""
        keyword = input("Keyword (default): ").strip() or "default"
        count = int(input("Count (5): ").strip() or "5")
        
        result = self.backend.derive_addresses(keyword, count)
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Error')}")
            return
        
        addresses = result.get("addresses", [])
        
        if not addresses:
            print_yellow("❌ No addresses derived.")
            return
        
        print_bold(f"\n📤 DERIVED ADDRESSES ({keyword}: 0-{len(addresses)-1})")
        print("=" * 120)
        
        # Table header
        print(f"{'#':<6} {'Address':<40} {'Private Key':<35} {'Public Key'}")
        print("-" * 120)
        
        for addr in addresses:
            idx = addr.get("index", 0)
            address = addr.get("address", "N/A")
            priv = addr.get("private_key", "")
            pub = addr.get("public_key", "")
            
            # Truncate keys if too long
            priv_display = priv[:30] + "..." if len(priv) > 33 else priv
            pub_display = pub[:30] + "..." if len(pub) > 33 else pub
            
            print(f"{idx:<6} {address:<40} {priv_display:<35} {pub_display}")
        
        print("-" * 120)
        print(f"Total: {len(addresses)} derived addresses")
        print("=" * 120)
    
    def _cmd_send(self):
        """Send payment"""
        to_addr = input("Recipient address: ").strip()
        if not to_addr:
            return
        try:
            amount = float(input("Amount: ").strip())
        except ValueError:
            print_red("❌ Invalid amount")
            return
        memo = input("Memo (optional): ").strip()
        
        result = self.backend.send_payment(to_addr, amount, memo)
        
        # 🔥 IF VIA RETICULUM, SHOW IN BLUE
        if result.get("via_reticulum", False):
            print_blue(f"📡 Transaction request via Reticulum")
        
        if result.get("success"):
            print_green(f"✅ Payment sent!")
            print(f"   Hash: {result.get('tx_hash', 'N/A')}")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_info(self):
        """Wallet info"""
        result = self.backend.get_wallet_info()
        if result.get("success"):
            print_bold("\n📊 COMPLETE WALLET INFO")
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
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_history(self):
        """Transaction history - FORMAT AND PRINT"""
        limit = int(input("Number of transactions (10): ").strip() or "10")
        result = self.backend.get_history(limit)
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Error')}")
            return
        
        transactions = result.get("transactions", [])
        address = result.get("address", "")
        
        if not transactions:
            print_yellow("❌ No transactions found.")
            return
        
        # 🔥 FORMAT AND PRINT (uses parse_tx_date imported)
        self._print_transactions(transactions, address)
        
        # Show explorer
        network = result.get("network", "mainnet")
        if network == "mainnet":
            explorer = f"https://xrpscan.com/account/{address}"
        elif network == "testnet":
            explorer = f"https://testnet.xrpl.org/accounts/{address}"
        else:
            explorer = f"https://devnet.xrpl.org/accounts/{address}"
        print(f"\n🔗 View all: {explorer}")
    
    def _print_transactions(self, transactions: List, address: str) -> None:
        """Print transactions in table format - UI ONLY"""
        import base64
        from datetime import datetime
        
        print("\n┌────┬─────────────────────┬────────────┬──────────────────┬────────────┬──────────────────────────────────────────────────┬────────────────────┐")
        print(f"│ #  │ Date/Time           │ Type       │ Amount           │ Fee        │ From/To                                           │ Memo               │")
        print("├────┼─────────────────────┼────────────┼──────────────────┼────────────┼──────────────────────────────────────────────────┼────────────────────┤")
        
        for idx, tx_data in enumerate(transactions, 1):
            tx = tx_data.get("tx_json", {})
            if not tx:
                continue
            
            tx_type = tx.get("TransactionType", "Unknown")
            date_str = parse_tx_date(tx, tx_data)  # <-- USE GLOBAL FUNCTION
            
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
                    
                    # Decode currency if needed
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
                    direction = "RECEIVED"
                    da_a = f"From: {sender}"
                elif sender == address:
                    direction = "SENT"
                    da_a = f"To: {destination}"
                else:
                    direction = "OTHER"
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
        print(f"Total: {len(transactions)} transactions shown")

    def _cmd_fund_testnet(self):
        """Fund testnet"""
        result = self.backend.fund_testnet()
        if result.get("success"):
            print_green(f"✅ {result.get('message', '')}")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_export(self):
        """Export wallet"""
        include_private = input("Include private key? (y/N): ").strip().lower() == 'y'
        result = self.backend.export_wallet(include_private)
        if result.get("success"):
            print(json.dumps(result.get("data", {}), indent=2, default=str))
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_change_password(self):
        """Change password"""
        old = getpass.getpass("Current password: ")
        if old != self._password:
            print_red("❌ Incorrect password")
            return
        new = getpass.getpass("New password: ")
        confirm = getpass.getpass("Confirm password: ")
        if new != confirm:
            print_red("❌ Passwords do not match")
            return
        result = self.backend.change_password(old, new)
        if result.get("success"):
            self._password = new
            print_green("✅ Password changed successfully!")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    # ============================================================
    # TRUSTLINE
    # ============================================================
    
    def _menu_trustline(self):
        """Trustline submenu"""
        while True:
            print("\n🔗 TRUSTLINE MANAGEMENT")
            print("  1) Show trustlines")
            print("  2) Create trustline")
            print("  3) Remove trustline")
            print("  4) Trustline info")
            print("  0) Return to main menu")
            
            sub = input("\nChoice: ").strip()
            
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
                print_red("❌ Invalid choice")
    
    def _cmd_trustlines(self):
        """Show trustlines - FORMATTED LIKE OTHER TABLES"""
        result = self.backend.get_trustlines()
        if result.get("success"):
            trustlines = result.get("trustlines", [])
            if not trustlines:
                print_yellow("❌ No trustlines found")
                return
            
            # 🔥 DETERMINE NETWORK
            network = "MAINNET" if self.backend.wallet._xrp_manager.network == "mainnet" else "TESTNET"
            crypto = self.backend.wallet._xrp_manager.crypto_type
            
            print_bold(f"\n🔗 TRUSTLINES ({crypto}) on {network}")
            print("=" * 100)
            print(f"{'#':<4} {'Asset':<12} {'Issuer':<36} {'Balance':<16} {'Limit':<14} {'Status'}")
            print("-" * 100)
            
            for i, tl in enumerate(trustlines, 1):
                asset = tl.get('currency', tl.get('asset_code', '???'))
                issuer = tl.get('issuer', tl.get('asset_issuer', 'N/A'))
                balance = tl.get('balance', 0)
                limit = tl.get('limit', 0)
                is_active = tl.get('is_active', False)
                
                # 🔥 FORMAT NUMBERS
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
                
                # 🔥 TRUNCATE ISSUER IF TOO LONG
                issuer_display = issuer if len(issuer) <= 34 else issuer[:32] + "..."
                
                print(f"{i:<4} {asset:<12} {issuer_display:<36} {bal_str:<16} {lim_str:<14} {status}")
            
            print("=" * 100)
            print(f"Total: {len(trustlines)} trustlines")
            print("=" * 100)
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_trustline_create(self):
        """Create trustline"""
        asset = input("Asset (e.g. RLUSD): ").strip()
        issuer = input("Issuer address: ").strip()
        try:
            limit = float(input("Limit (0 to remove): ").strip() or "0")
        except ValueError:
            limit = 0
        result = self.backend.create_trustline(asset, issuer, limit)
        if result.get("success"):
            print_green(f"✅ Trustline created for {asset}!")
            print(f"   Hash: {result.get('hash', 'N/A')}")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_trustline_remove(self):
        """Remove trustline"""
        asset = input("Asset: ").strip()
        issuer = input("Issuer address: ").strip()
        result = self.backend.remove_trustline(asset, issuer)
        if result.get("success"):
            print_green(f"✅ Trustline removed for {asset}!")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_trustline_info(self):
        """Trustline info"""
        asset = input("Asset: ").strip()
        issuer = input("Issuer (optional): ").strip() or None
        result = self.backend.get_trustline_info(asset, issuer)
        if result.get("success"):
            print_bold(f"\n📊 TRUSTLINE INFO {asset}")
            print("=" * 60)
            print(f"   Asset: {result.get('asset', 'N/A')}")
            print(f"   Issuer: {result.get('issuer', 'N/A')}")
            print(f"   Balance: {result.get('balance', 0):.6f}")
            print(f"   Limit: {result.get('limit', 0):.6f}")
            print(f"   Status: {'✅ Active' if result.get('is_active') else '⏳ Pending'}")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    # ============================================================
    # TOKEN
    # ============================================================
    
    def _cmd_send_token(self):
        """Send token"""
        to_addr = input("Recipient address: ").strip()
        if not to_addr:
            return
        token = input("Token name (e.g. Arg0): ").strip()
        if not token:
            return
        try:
            amount = float(input("Amount: ").strip())
        except ValueError:
            print_red("❌ Invalid amount")
            return
        issuer = input("Issuer (optional): ").strip() or None
        
        # 🔥 ASK FOR DESTINATION TAG
        dest_tag_input = input("Destination Tag (optional, number): ").strip()
        dest_tag = int(dest_tag_input) if dest_tag_input else None
        
        result = self.backend.send_token(to_addr, token, amount, issuer, dest_tag)
        if result.get("success"):
            print_green(f"✅ {amount} {token} sent!")
            print(f"   Hash: {result.get('tx_hash', 'N/A')}")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    # ============================================================
    # RETICULUM
    # ============================================================
    
    def _menu_reticulum(self):
        while True:
            status = self.backend.get_status()
            internet_status = "🌐 ON" if self.backend.use_internet else "📡 OFF (Reticulum)"
            
            # 🔥 TOR STATUS ALWAYS VISIBLE
            tor_status = "🧅 ON" if self.backend.use_tor else "🧅 OFF"
            tor_reachable = "✅" if self.backend._test_tor() else "❌"
            
            # IP only if internet is ON
            if self.backend.use_internet:
                ip_info = self.backend.get_ip_status()
                ip = ip_info.get("ip", "N/A")
                ip_display = f"{ip} ({tor_status})"
            else:
                ip_display = "⛔ N/A (Reticulum)"
            
            print("\n" + "=" * 50)
            print("  📡 RETICULUM")
            print("=" * 50)
            print(f"  Gateway: {'✅ Active' if status.get('gateway_active') else '❌ Stopped'}")
            print(f"  Known peers: {status.get('wallet_count', 0)}")
            print(f"  Internet mode: {internet_status}")
            print(f"  TOR: {tor_status} {tor_reachable}")
            print(f"  Public IP: {ip_display}")

            print("\n" + "-" * 50)
            print("  1) Gateway status")
            print("  2) Start gateway")
            print("  3) Stop gateway")
            print("  4) Discover gateways")
            print("  5) Discover wallets")
            print("  6) Peer metrics")
            print("  7) Best gateway")
            print("  8) Request gateway info")
            print("  9) Test all gateways")
            print(" 10) 🌐 Toggle internet (use Reticulum)")
            print(" 11) 🧅 Toggle TOR (use anonymous network)")
            print(" 12) 🗑️ Remove gateway manually")
            print("  0) Return to main menu")
            print("-" * 50)
            
            sub = input("\nChoice: ").strip()
            
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
                self._cmd_toggle_tor()
            elif sub == '12':
                self._cmd_remove_gateway()
            else:
                print_red("❌ Invalid choice")
    
    def _cmd_gateway_status(self):
        """Gateway status with IP and TOR status"""
        result = self.backend.get_gateway_status()
        if result.get("success"):
            status = result.get("status", {})
            
            # 🔥 REAL-TIME TOR TEST
            tor_reachable = "✅" if self.backend._test_tor() else "❌"
            
            print_bold("\n📊 GATEWAY STATUS")
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
            
            # 🔥 SHOW IP AND TOR STATUS
            public_ip = status.get('public_ip', 'N/A')
            use_tor = status.get('use_tor', False)
            internet_on = status.get('internet_on', True)
            
            tor_status = "🧅 TOR ON" if use_tor else "🌐 Direct"
            internet_status = "🌐 ON" if internet_on else "📡 OFF (Reticulum)"
            
            print(f"   TOR: {tor_status} {tor_reachable}")
            print(f"   Public IP: {public_ip} ({tor_status})")
            print(f"   Internet: {internet_status}")
            print("=" * 60)
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_gateway_start(self):
        """Start gateway"""
        result = self.backend.start_gateway()
        if result.get("success"):
            print_green("✅ Gateway started")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_gateway_stop(self):
        """Stop gateway"""
        result = self.backend.stop_gateway()
        if result.get("success"):
            print_green("✅ Gateway stopped")
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_discover_gateways(self):
        """Discover gateways - FORMATTED AS BEFORE"""
        result = self.backend.discover_gateways()
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Error')}")
            return
        
        gateways = result.get("gateways", [])
        
        print_bold(f"\n🔍 GATEWAYS FOUND ({len(gateways)})")
        print("=" * 100)
        print(f"{'Name':<20} {'Hash':<36} {'First Seen':<20} {'Last Seen':<20} {'Hops':<6}")
        print("-" * 100)
        
        for gw in gateways:
            name = gw.get('name', 'Unknown')[:18]
            gw_id = gw.get('gateway_id', '?')
            first_seen = gw.get('first_seen')
            last_seen = gw.get('last_seen')
            
            first_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(first_seen)) if first_seen else 'Never'
            last_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen)) if last_seen else 'Never'
            hops = gw.get('hops', '?')
            
            print(f"{name:<20} {gw_id:<36} {first_str:<20} {last_str:<20} {hops:<6}")
        
        print("=" * 100)
        print(f"Total: {len(gateways)} gateways in cache")
        print("=" * 100)

    def _cmd_discover_wallets(self):
        """Discover wallets - FORMATTED AS BEFORE"""
        result = self.backend.discover_wallets()
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Error')}")
            return
        
        wallets = result.get("wallets", [])
        
        print_bold(f"\n🔍 WALLETS FOUND ({len(wallets)})")
        print("=" * 100)
        print(f"{'Name':<20} {'Hash':<36} {'First Seen':<20} {'Last Seen':<20} {'Hops':<6}")
        print("-" * 100)
        
        for w in wallets:
            name = w.get('name', 'Unknown')[:18]
            w_id = w.get('wallet_id', '?')
            first_seen = w.get('first_seen')
            last_seen = w.get('last_seen')
            
            first_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(first_seen)) if first_seen else 'Never'
            last_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen)) if last_seen else 'Never'
            hops = w.get('hops', '?')
            
            print(f"{name:<20} {w_id:<36} {first_str:<20} {last_str:<20} {hops:<6}")
        
        print("=" * 100)
        print(f"Total: {len(wallets)} wallets in cache")
        print("=" * 100)
    
    def _cmd_peer_metrics(self):
        """Peer metrics - USE SCORE FROM BACKEND"""
        result = self.backend.get_peer_metrics()
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Error')}")
            return
        
        peers = result.get("peers", [])
        if not peers:
            print_yellow("⚠️ No known peers")
            return
        
        print_bold(f"\n🔍 PEERS ORDERED BY PERFORMANCE ({len(peers)})")
        print("=" * 280)
        # 🔥 ADD TOR COLUMN
        print(f"{'#':<3} {'Name':<22} {'Score':<6} {'Rel':<6} {'Rep':<4} {'Hops':<5} {'RTT':<8} {'XRP':<14} {'Stellar':<14} {'Internet':<9} {'TOR':<6} {'Last Seen':<15} {'ID':<36} {'Assets'}")
        print("-" * 280)
        
        for idx, p in enumerate(peers, 1):
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
            last_seen = format_time_ago(p.get('last_seen'))
            gw_id = p.get('gateway_id', 'N/A')[:36]
            
            # 🔥 TOR STATUS
            tor_enabled = p.get('tor_enabled', False)
            tor_reachable = p.get('tor_reachable', False)
            if tor_enabled and tor_reachable:
                tor_str = "🧅✅"
            elif tor_enabled:
                tor_str = "🧅❌"
            else:
                tor_str = "—"
            
            assets = p.get('assets', [])
            if isinstance(assets, list):
                assets_str = ', '.join(assets[:3])
                if len(assets) > 3:
                    assets_str += f" +{len(assets)-3}"
            else:
                assets_str = str(assets)[:20]
            
            # Colors
            sc_color = Colors.GREEN if sc > 70 else Colors.YELLOW if sc > 40 else Colors.RED
            rel_color = Colors.GREEN if rel > 0.9 else Colors.YELLOW if rel > 0.7 else Colors.RED
            
            print(f"{idx:<3} {name:<20} {sc_color}{sc:5.0f}{Colors.RESET} {rel_color}{rel:5.2f}{Colors.RESET} {rep:<4} {hops:<5} {rtt:<8} {xrp_str:<14} {stellar_str:<14} {internet:<9} {tor_str:<6} {last_seen:<15} {gw_id:<36} {assets_str}")
        
        print("=" * 280)
        
        stats = result.get("stats", {})
        if stats:
            print(f"\n📊 Statistics:")
            print(f"   Total peers: {stats.get('total_peers', 0)}")
            print(f"   Online: {stats.get('online_peers', 0)}")
            print(f"   Offline: {stats.get('offline_peers', 0)}")
            print(f"   Average reputation: {round(stats.get('avg_reputation', 0), 1)}")
            if stats.get('avg_latency_ms'):
                print(f"   Average Reticulum latency: {round(stats.get('avg_latency_ms'), 0)}ms")
            if stats.get('avg_score'):
                print(f"   Average score: {round(stats.get('avg_score'))}")
            # 🔥 ADD TOR STATISTICS
            tor_peers = stats.get('tor_peers', 0)
            if tor_peers > 0:
                print(f"   Gateways with TOR: {tor_peers}")
        
        if peers:
            b = peers[0]
            best_score = b.get('_score', 0)
            print(f"\n🏆 BEST PEER: {b.get('name', 'UNKNOWN')}")
            print(f"   Score: {best_score:.0f} | Rel: {b.get('reliability', 0):.2f} | Rep: {b.get('reputation', 50)}")
            print(f"   Gateway ID: {b.get('gateway_id', 'N/A')}")
            print(f"   RTT Reticulum: {b.get('latency_ms', '?')}ms | Hops: {b.get('hops', '?')}")
            print(f"   XRP: {'✅' if b.get('xrp_reachable') else '❌'} ({b.get('xrp_latency_ms', '?')}ms)")
            print(f"   Stellar: {'✅' if b.get('stellar_reachable') else '❌'} ({b.get('stellar_latency_ms', '?')}ms)")
            print(f"   Internet: {'✅' if b.get('has_internet') else '❌'}")
            # 🔥 ADD TOR TO BEST PEER
            tor_enabled = b.get('tor_enabled', False)
            tor_reachable = b.get('tor_reachable', False)
            if tor_enabled and tor_reachable:
                print(f"   TOR: ✅ Active and reachable")
            elif tor_enabled:
                print(f"   TOR: ⚠️ Active but not reachable")
            else:
                print(f"   TOR: ❌ Not active")
            if b.get('assets'):
                print(f"   Assets: {', '.join(b.get('assets', []))}")
    
    def _cmd_best_gateway(self):
        """Best gateway - SHOW ALL INFO"""
        asset = input("Asset (e.g. RLUSD): ").strip()
        if not asset:
            print_red("❌ Specify an asset")
            return
        result = self.backend.get_best_gateway(asset)
        if result.get("success"):
            gw = result.get("gateway", {})
            if not gw:
                print_yellow(f"⚠️ No gateway found for {asset}")
                return
            
            print_bold(f"\n🏆 BEST GATEWAY FOR {asset.upper()}")
            print("=" * 70)
            print(f"   Name:           {gw.get('name', 'UNKNOWN')}")
            print(f"   Gateway ID:     {gw.get('gateway_id', 'N/A')}")
            print(f"   Hops:           {gw.get('hops', '?')}")
            print(f"   RTT Reticulum:  {gw.get('latency_ms', '?')}ms")
            print(f"   Reputation:     {gw.get('reputation', 50)}")
            print(f"   Reliability:    {gw.get('reliability', 0):.2f}")
            print(f"   Internet:       {'✅' if gw.get('has_internet') else '❌'}")
            print(f"   Status:         {'✅ ONLINE' if gw.get('is_online') else '❌ OFFLINE'}")
            print("-" * 70)
            
            # XRP
            if gw.get('xrp_reachable'):
                print(f"   XRP:            ✅ Reachable ({gw.get('xrp_latency_ms', '?')}ms)")
            else:
                print(f"   XRP:            ❌ Not reachable")
            
            # Stellar
            if gw.get('stellar_reachable'):
                print(f"   Stellar:        ✅ Reachable ({gw.get('stellar_latency_ms', '?')}ms)")
            else:
                print(f"   Stellar:        ❌ Not reachable")
            
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
            
            # RSSI/SNR (if available)
            if gw.get('rssi') is not None:
                print(f"   RSSI:           {gw.get('rssi')}dBm")
            if gw.get('snr') is not None:
                print(f"   SNR:            {gw.get('snr')}dB")
            
            print("=" * 70)
        else:
            print_red(f"❌ {result.get('message', 'Error')}")
    
    def _cmd_request_info(self):
        """Request info from a specific gateway - USE discover_gateways()"""
        if not self.backend.metrics:
            print_red("❌ Metrics not available")
            return
        
        # 🔥 USE discover_gateways() FROM BACKEND
        result = self.backend.discover_gateways(active_only=False)
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Error')}")
            return
        
        gateways = result.get("gateways", [])
        
        # 🔥 FILTER OWN GATEWAY
        my_id = self.backend.reticulum.gateway_address if hasattr(self.backend.reticulum, 'gateway_address') else None
        if my_id:
            gateways = [g for g in gateways if g.get('gateway_id') != my_id]
        
        if not gateways:
            print_yellow("⚠️ Only your own gateway found, no peers available")
            return
        
        # 🔥 SHOW LIST WITH COMPLETE ADDRESS
        print_blue("🔍 Available gateways:")
        print(f"   Found {len(gateways)} gateways (excluding self)")
        for i, gw in enumerate(gateways, 1):
            name = gw.get('name', 'UNKNOWN')
            gw_id = gw.get('gateway_id', '?')
            hops = gw.get('hops', '?')
            rssi = gw.get('rssi')
            rssi_str = f" RSSI:{rssi:.1f}dBm" if rssi is not None else ""
            print(f"   {i}) {name} ({gw_id}) Hops:{hops}{rssi_str}")
        
        try:
            choice = input("\nChoose gateway (number): ").strip()
            if not choice:
                return
            
            idx = int(choice) - 1
            if 0 <= idx < len(gateways):
                gateway_id = gateways[idx].get('gateway_id')
                if gateway_id:
                    print_blue(f"📡 Requesting info from {gateway_id}")
                    result = self.backend.request_gateway_info(gateway_id)
                    
                    if result.get("success"):
                        peer = result.get("peer")
                        if peer:
                            self.backend._show_single_peer(peer)
                        else:
                            print_green("✅ Request sent and response received!")
                    else:
                        print_red(f"❌ {result.get('message', 'Error')}")
                else:
                    print_red("❌ Invalid gateway ID")
            else:
                print_red("❌ Invalid choice")
        except ValueError:
            print_red("❌ Enter a valid number")
    
    def _cmd_test_gateways(self):
        """Test all active gateways"""
        print("\n📡 Testing all active gateways in progress...")
        print("   This will update peer data in the database.")
        print("   To see the ranking, use '6) Peer metrics'.\n")
        
        result = self.backend.test_all_gateways()
        
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Error')}")
            return
        
        results = result.get("results", [])
        
        if not results:
            print_yellow("⚠️ No active gateways found")
            return
        
        print_bold(f"\n📊 TEST COMPLETED")
        print("=" * 80)
        print(f"   Gateways tested: {result.get('count', 0)}")
        print(f"   Responses received: {result.get('successful', 0)}")
        print("=" * 80)
        
        # 🔥 TABLE WITH RETICULUM, INTERNET AND TOR STATUS
        print("\n📋 RESULTS:")
        print("-" * 100)
        print(f"{'#':<3} {'Name':<20} {'Reticulum':<12} {'Internet':<10} {'TOR':<8} {'Hops':<6}")
        print("-" * 100)
        
        for idx, r in enumerate(results, 1):
            reticulum_status = "✅ ONLINE" if r.get('status') == "✅ ONLINE" else "❌ OFFLINE"
            internet_status = "🌐 YES" if r.get('has_internet', False) else "📡 NO"
            tor_status = r.get('tor_status', '—')
            hops = r.get('hops', '?')
            
            print(f"{idx:<3} {r.get('name', 'UNKNOWN'):<20} {reticulum_status:<12} {internet_status:<10} {tor_status:<8} {hops:<6}")
        
        print("-" * 100)
        print("\n📌 Legend:")
        print("   Reticulum: ✅ ONLINE = reachable via Reticulum network")
        print("   Internet:  🌐 YES  = gateway has internet access")
        print("   Internet:  📡 NO   = gateway does NOT have internet access")
        print("   TOR:       🧅✅   = TOR active and reachable")
        print("   TOR:       🧅❌   = TOR active but not reachable")
        print("   TOR:       —      = TOR not active")
        
        print_green("\n✅ Data updated! Use '6) Peer metrics' to see the complete ranking.")

    def _cmd_remove_gateway(self):
        """Remove a gateway manually from announce_cache and gateway_peers"""
        print("\n🗑️ REMOVE GATEWAY MANUALLY")
        print("=" * 60)
        print("   This operation removes the gateway from:")
        print("   - announce_cache.db (announcements)")
        print("   - gateway_peers.db (metrics)")
        print("")
        
        # First show the list of available gateways
        result = self.backend.discover_gateways(active_only=False)
        if not result.get("success"):
            print_red(f"❌ {result.get('message', 'Error')}")
            return
        
        gateways = result.get("gateways", [])
        if not gateways:
            print_yellow("⚠️ No gateways found")
            return
        
        print("📋 AVAILABLE GATEWAYS:")
        print("-" * 80)
        print(f"{'#':<4} {'Name':<20} {'ID':<38} {'Last Seen'}")
        print("-" * 80)
        
        for i, gw in enumerate(gateways, 1):
            name = gw.get('name', 'UNKNOWN')[:18]
            gw_id = gw.get('gateway_id', '?')
            last_seen = gw.get('last_seen')
            if last_seen:
                last_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen))
            else:
                last_str = 'Never'
            print(f"{i:<4} {name:<20} {gw_id:<38} {last_str}")
        
        print("-" * 80)
        print("")
        
        choice = input("Gateway number to remove (or Enter to cancel): ").strip()
        if not choice:
            print_yellow("❌ Operation cancelled")
            return
        
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(gateways):
                print_red("❌ Invalid number")
                return
            
            gw = gateways[idx]
            gw_id = gw.get('gateway_id')
            name = gw.get('name', 'UNKNOWN')
            
            # Ask for confirmation
            print(f"\n⚠️ You are about to remove: {name} ({gw_id[:16]}...)")
            confirm = input("   Confirm? (y/N): ").strip().lower()
            if confirm != 'y':
                print_yellow("❌ Operation cancelled")
                return
            
            # Execute removal
            result = self.backend.remove_gateway(gw_id)
            if result.get("success"):
                print_green(f"✅ {result.get('message', 'Removed successfully')}")
                if result.get("removed_from_announce"):
                    print("   ✅ Removed from announce_cache.db")
                if result.get("removed_from_peers"):
                    print("   ✅ Removed from gateway_peers.db")
            else:
                print_red(f"❌ {result.get('message', 'Error')}")
                
        except ValueError:
            print_red("❌ Enter a valid number")

    def _cmd_toggle_internet(self):
        """Toggle internet / reticulum usage"""
        current = self.backend.use_internet
        self.backend.set_use_internet(not current)
        if current:
            print_green("🌐 Internet mode disabled")
            print_yellow("   Operations will use Reticulum (if available)")
        else:
            print_green("🌐 Internet mode enabled")
            print_yellow("   Operations will use direct connection")

    def _cmd_toggle_tor(self):
        """Toggle TOR (anonymous network)"""
        current = self.backend.use_tor
        
        # If enabling TOR, verify it's reachable
        if not current:
            print_blue("🧅 Checking TOR connection...")
            if not self.backend._test_tor():
                print_yellow("⚠️ TOR is not responding on localhost:9050")
                print_yellow("   Make sure TOR is running.")
                print_yellow("   To start it: tor (in a separate terminal)")
                confirm = input("   Enable anyway? (y/N): ").strip().lower()
                if confirm != 'y':
                    print_yellow("❌ TOR not enabled")
                    return
        
        # Change state
        self.backend.set_use_tor(not current)
        
        if current:
            print_green("🧅 TOR disabled")
            print_yellow("   Ledger connections will use direct internet")
        else:
            print_green("🧅 TOR enabled")
            print_yellow("   Ledger connections will use TOR network (slower)")
            # Final verification
            if self.backend._test_tor():
                print_green("✅ TOR reachable and working")
            else:
                print_yellow("⚠️ TOR not responding. Check the daemon.")

# ============================================================
# MAIN
# ============================================================

def main():
    """Entry point"""
    cli = PaxWalletCLI()
    cli.run()


if __name__ == "__main__":
    main()