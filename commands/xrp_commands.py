#!/usr/bin/env python3
"""
commands/xrp_commands.py - Comandi per XRP (XRPL)
"""

import logging
import json
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Import condizionale per xrpl-py
try:
    from xrpl.account import get_balance
    from xrpl.models.transactions import Payment, Memo, TrustSet  # <-- CORRETTO: TrustSet
    from xrpl.transaction import autofill, sign, submit_and_wait, autofill_and_sign
    from xrpl.clients import JsonRpcClient
    from xrpl.models.amounts import IssuedCurrencyAmount
    from xrpl.wallet import Wallet as XRPWallet
    from xrpl.constants import CryptoAlgorithm
    from xrpl.models.requests import AccountTx, AccountInfo
    from xrpl.models.response import ResponseStatus
    XRP_AVAILABLE = True
except ImportError as e:
    XRP_AVAILABLE = False
    logger.warning(f"⚠️ xrpl-py non installato. I comandi XRP non saranno disponibili: {e}")

    # Classi placeholder per evitare errori di import
    class XRPWallet: pass
    class CryptoAlgorithm: pass
    class Payment: pass
    class Memo: pass
    class TrustSet: pass  # <-- CORRETTO
    class IssuedCurrencyAmount: pass
    class JsonRpcClient: pass
    class AccountTx: pass
    class AccountInfo: pass
    class ResponseStatus: pass


def _check_xrp_available() -> bool:
    if not XRP_AVAILABLE:
        print("❌ xrpl-py non installato!")
        print("   Installa con: pip install xrpl-py")
        return False
    return True


def _get_manager(cli_instance):
    """Ottiene il manager dal CLI (supporta sia vecchio che nuovo)"""
    if hasattr(cli_instance, 'wallet') and cli_instance.wallet:
        return cli_instance.wallet._xrp_manager
    if hasattr(cli_instance, 'manager'):
        return cli_instance.manager
    if hasattr(cli_instance, 'backend') and hasattr(cli_instance.backend, 'wallet'):
        return cli_instance.backend.wallet._xrp_manager
    return None


def _get_client(network: str = "testnet") -> Optional[JsonRpcClient]:
    """Restituisce il client XRP per il network specificato."""
    if not _check_xrp_available():
        return None
    urls = {
        "mainnet": "https://s1.ripple.com:51234/",
        "testnet": "https://s.altnet.rippletest.net:51234/",
        "devnet": "https://s.devnet.rippletest.net:51234/"
    }
    return JsonRpcClient(urls.get(network, urls["testnet"]))


def _get_wallet_from_manager(manager):
    """Ottiene il wallet XRP dal manager (supporta diversi seed_type)."""
    if not _check_xrp_available():
        return None
    
    seed_type = manager.seed_type
    
    if seed_type in ["bip39", "private_key"]:
        private_key_hex = manager.base_private.hex() if manager.base_private else None
        if not private_key_hex:
            raise ValueError("Nessuna private key disponibile")
        public_key_hex, address = manager._private_key_to_keypair(private_key_hex)
        return XRPWallet(
            public_key=public_key_hex,
            private_key=private_key_hex,
            algorithm=CryptoAlgorithm.SECP256K1
        )
    else:
        return manager.get_wallet()


def send_xrp(cli_instance, args):
    """
    Invia XRP (XRPL) con supporto memo.
    Uso: send_xrp <destinatario> <importo> [memo]
    """
    if not _check_xrp_available():
        return
    
    manager = _get_manager(cli_instance)
    if not manager or not manager.is_loaded():
        print("❌ Nessun wallet caricato!")
        return

    if not args or len(args) < 2:
        print("❌ Specifica destinatario e importo.")
        print("Esempio: send_xrp r... 10 'memo opzionale'")
        return

    destination = args[0]

    try:
        amount = float(args[1])
        if amount <= 0:
            print("❌ L'importo deve essere maggiore di 0")
            return
    except ValueError:
        print("❌ Importo non valido.")
        return

    memo_text = ""
    if len(args) > 2:
        memo_text = " ".join(args[2:])

    try:
        wallet = _get_wallet_from_manager(manager)
        if not wallet:
            print("❌ Impossibile ottenere il wallet")
            return

        client = _get_client(manager.network)
        if not client:
            return

        source_address = wallet.classic_address

        # Verifica saldo
        balance_drops = get_balance(source_address, client)
        balance_xrp = int(balance_drops) / 1_000_000 if isinstance(balance_drops, str) else balance_drops / 1_000_000

        if balance_xrp < amount:
            print(f"❌ Saldo insufficiente: {balance_xrp:.6f} XRP")
            return

        # Prepara transazione
        amount_drops = str(int(amount * 1_000_000))
        payment_params = {
            "account": source_address,
            "amount": amount_drops,
            "destination": destination
        }
        if memo_text:
            memo_hex = memo_text.encode('utf-8').hex()
            if len(memo_hex) % 2 != 0:
                memo_hex = '0' + memo_hex
            payment_params["memos"] = [Memo(memo_data=memo_hex)]

        payment = Payment(**payment_params)
        tx = autofill(payment, client)
        signed_tx = sign(tx, wallet)
        response = submit_and_wait(signed_tx, client)

        tx_hash = response.result.get("hash", "unknown")
        result_code = response.result.get('meta', {}).get('TransactionResult')

        if result_code == "tesSUCCESS":
            print(f"\n✅ TRANSAZIONE INVIATA!")
            print("=" * 60)
            print(f"Hash:   {tx_hash}")
            print(f"Da:     {source_address}")
            print(f"A:      {destination}")
            print(f"Importo: {amount:.6f} XRP")
            if memo_text:
                print(f"📝 Memo: {memo_text}")
            print("=" * 60)

            if manager.network == "mainnet":
                explorer = f"https://xrpscan.com/tx/{tx_hash}"
            else:
                explorer = f"https://testnet.xrpl.org/transactions/{tx_hash}"
            print(f"🔗 {explorer}")
        else:
            print(f"❌ Transazione fallita: {result_code}")

    except Exception as e:
        print(f"❌ Errore: {e}")
        logger.error(f"Errore invio XRP: {e}", exc_info=True)


def history_xrp(cli_instance, args):
    """
    Storico transazioni per XRP (XRPL).
    Uso: history_xrp [--limit N] [--json]
    """
    if not _check_xrp_available():
        return

    manager = _get_manager(cli_instance)
    if not manager or not manager.is_loaded():
        print("❌ Nessun wallet caricato!")
        return

    limit = 10
    json_output = False

    clean_args = []
    i = 0
    while i < len(args):
        if args[i] == "--limit" or args[i] == "-l":
            if i + 1 < len(args) and args[i + 1].isdigit():
                limit = int(args[i + 1])
                if limit > 200:
                    print("⚠️  Limite massimo 200 transazioni")
                    limit = 200
                i += 2
                continue
            else:
                i += 1
                continue
        elif args[i] == "--json":
            json_output = True
            i += 1
            continue
        clean_args.append(args[i])
        i += 1

    try:
        address = manager.get_address()
        client = _get_client(manager.network)
        if not client:
            return

        wallet_name = "nessun wallet"
        if hasattr(cli_instance, '_get_active_wallet_name'):
            wallet_name = cli_instance._get_active_wallet_name() or "nessun wallet"

        print(f"\n📜 STORICO TRANSAZIONI XRP")
        print("=" * 80)
        print(f"Wallet:    {wallet_name}")
        print(f"Indirizzo: {address}")
        print(f"Rete:      {manager.network.upper()}")
        print(f"Limite:    {limit} transazioni")
        print("=" * 80)

        request = AccountTx(
            account=address,
            ledger_index_min=-1,
            ledger_index_max=-1,
            limit=limit,
            forward=False
        )
        response = client.request(request)

        if response.status != ResponseStatus.SUCCESS:
            print(f"❌ Errore: {response.status}")
            return

        transactions = response.result.get("transactions", [])

        if not transactions:
            print("❌ Nessuna transazione trovata.")
            return

        if json_output:
            print(json.dumps(transactions, indent=2, default=str))
            return

        print("\n┌────┬─────────────────────┬────────────┬──────────────────┬────────────┬──────────────────────────────────────────────────┬────────────────────┐")
        print("│ #  │ Data/Ora            │ Tipo       │ Importo          │ Fee        │ Da/A                                              │ Memo               │")
        print("├────┼─────────────────────┼────────────┼──────────────────┼────────────┼──────────────────────────────────────────────────┼────────────────────┤")

        for idx, tx_data in enumerate(transactions[:limit], 1):
            tx = tx_data.get("tx_json", {})
            if not tx:
                continue

            tx_type = tx.get("TransactionType", "Unknown")

            # Data
            date_str = ""
            if "date" in tx:
                try:
                    ledger_time = tx.get("date", 0)
                    if ledger_time:
                        date_obj = datetime.fromtimestamp(ledger_time + 946684800)
                        date_str = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass

            # Fee
            fee_drops = tx.get("Fee", "0")
            try:
                fee_xrp = int(fee_drops) / 1_000_000
                fee_str = f"{fee_xrp:.6f}".rstrip('0').rstrip('.')
                if not fee_str or fee_str == "":
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

                # Memo
                memo_display = ""
                memos = tx.get("Memos", [])
                if memos:
                    try:
                        memo_dict = memos[0].get("Memo", {})
                        memo_data = memo_dict.get("MemoData", "")
                        if memo_data:
                            try:
                                memo_bytes = bytes.fromhex(memo_data)
                                memo_text = memo_bytes.decode('utf-8', errors='ignore')[:30]
                            except:
                                try:
                                    import base64
                                    while len(memo_data) % 4 != 0:
                                        memo_data += '='
                                    memo_bytes = base64.b64decode(memo_data)
                                    memo_text = memo_bytes.decode('utf-8', errors='ignore')[:30]
                                except:
                                    memo_text = memo_data[:30]

                            if memo_text:
                                memo_clean = ''.join(c for c in memo_text if c.isprintable() or c == ' ')
                                if memo_clean.strip():
                                    memo_display = memo_clean[:30]
                    except:
                        pass

                da_a_display = da_a[:48] + "..." if len(da_a) > 48 else da_a
                memo_display = memo_display[:18] + "..." if len(memo_display) > 18 else memo_display

                print(f"│ {idx:<2} │ {date_str[:19]:<19} │ {direction:<10} │ {amount_str:<16} │ {fee_str:<10} │ {da_a_display:<48} │ {memo_display:<18} │")
            else:
                print(f"│ {idx:<2} │ {date_str[:19]:<19} │ {tx_type:<10} │ {'':<16} │ {fee_str:<10} │ {'':<48} │ {'':<18} │")

        print("└────┴─────────────────────┴────────────┴──────────────────┴────────────┴──────────────────────────────────────────────────┴────────────────────┘")
        print(f"Totale: {len(transactions)} transazioni mostrate")

        if manager.network == "mainnet":
            explorer = f"https://xrpscan.com/account/{address}"
        else:
            explorer = f"https://testnet.xrpl.org/accounts/{address}"
        print(f"\n🔗 Visualizza tutto: {explorer}")

    except Exception as e:
        print(f"❌ Errore: {e}")
        logger.error(f"Errore storico XRP: {e}", exc_info=True)


def info_xrp(cli_instance, args):
    """
    Info wallet per XRP (XRPL).
    Uso: info_xrp [--show-private]
    """
    if not _check_xrp_available():
        return

    manager = _get_manager(cli_instance)
    if not manager or not manager.is_loaded():
        print("❌ Nessun wallet caricato!")
        return

    show_private = "--show-private" in args

    try:
        address = manager.get_address()
        wallet = _get_wallet_from_manager(manager)
        
        wallet_name = "nessun wallet"
        if hasattr(cli_instance, '_get_active_wallet_name'):
            wallet_name = cli_instance._get_active_wallet_name() or "nessun wallet"

        print("\n📋 INFO WALLET XRP")
        print("=" * 60)
        print(f"Wallet:    {wallet_name}")
        print(f"Rete:      {manager.network.upper()}")
        print(f"Crypto:    XRP")
        print(f"Seed Type: {manager.seed_type}")
        print(f"🏠 Indirizzo: {address}")

        # Saldo
        try:
            client = _get_client(manager.network)
            if client:
                balance_drops = get_balance(address, client)
                balance = int(balance_drops) / 1_000_000 if isinstance(balance_drops, str) else balance_drops / 1_000_000
                print(f"💰 Saldo:   {balance:.6f} XRP")
        except Exception as e:
            print(f"💰 Saldo:   ❌ {e}")

        # Chiave pubblica (sempre visibile)
        if wallet:
            print(f"📤 Public Key: {wallet.public_key}")

        # Chiave privata (solo se richiesto)
        if show_private and wallet:
            print(f"🔐 Private Key: {wallet.private_key}")

        # Seed info
        info = manager.get_seed_info()
        if info.get('seed_type') == 'bip39':
            print(f"Parole: {info.get('word_count')}")
            if show_private:
                print(f"Frase: {info.get('seed_phrase')}")
                if info.get('passphrase'):
                    print(f"🔐 Passphrase: {info.get('passphrase')}")
        elif info.get('seed_type') == 'xrp_seed':
            if show_private:
                print(f"Seed XRP: {info.get('seed_xrp')}")
        elif info.get('seed_type') == 'numbers':
            if show_private:
                print(f"Secret Numbers: {info.get('formatted')}")

        # Wallet derivati
        derived = manager.list_derived()
        if derived:
            print(f"\n📂 Wallet derivati: {len(derived)}")
            for w in derived[:5]:
                print(f"   - {w.get('address', 'N/A')} ({w.get('keyword', 'default')}:{w.get('index', 0)})")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"❌ Errore: {e}")
        logger.error(f"Errore info XRP: {e}", exc_info=True)


def fund_testnet_xrp(cli_instance):
    """
    Faucet per XRP Testnet.
    NOTA: XRP non ha un faucet API automatico come Stellar.
    Usa https://xrpl.org/resources/dev-tools/xrp-faucet.html
    """
    if not _check_xrp_available():
        return

    manager = _get_manager(cli_instance)
    if not manager or not manager.is_loaded():
        print("❌ Nessun wallet caricato!")
        return

    if manager.network != "testnet":
        print("❌ Il faucet XRP funziona SOLO su TESTNET!")
        return

    try:
        address = manager.get_address()
        if not address:
            print("❌ Nessun wallet caricato. Crea un wallet prima.")
            return

        print(f"\n💰 FAUCET XRP - RICHIESTA XRP DI TEST")
        print("=" * 60)
        print(f"📤 Richiesta per: {address}")
        print()
        print("⚠️  XRP non ha un faucet API automatico.")
        print("   Usa il faucet manuale:")
        print(f"   🔗 https://xrpl.org/resources/dev-tools/xrp-faucet.html?account={address}")
        print()
        print("   Oppure per testnet:")
        print(f"   🔗 https://testnet.xrpl.org/accounts/{address}")

        # Prova a usare il faucet se disponibile
        try:
            import requests
            response = requests.get(
                f"https://faucet.xrpl.org/accounts/{address}",
                timeout=30
            )
            if response.status_code == 200:
                print("\n✅ XRP DI TEST RICEVUTI!")
                client = _get_client(manager.network)
                if client:
                    balance_drops = get_balance(address, client)
                    balance = int(balance_drops) / 1_000_000 if isinstance(balance_drops, str) else balance_drops / 1_000_000
                    print(f"💰 Nuovo saldo: {balance:.6f} XRP")
            else:
                print(f"\n⚠️  Non è stato possibile usare il faucet automatico.")
                print("   Usa il link manuale sopra.")
        except:
            pass

    except Exception as e:
        print(f"❌ Errore: {e}")
        logger.error(f"Errore faucet XRP: {e}", exc_info=True)


def trustline_xrp(cli_instance, args):
    """
    Gestione trustline per XRP.
    Uso: trustline_xrp [list|create|remove] [asset] [issuer] [limit]
    """
    if not _check_xrp_available():
        return

    manager = _get_manager(cli_instance)
    if not manager or not manager.is_loaded():
        print("❌ Nessun wallet caricato!")
        return

    if not args or args[0] == "list":
        # Lista trustline
        try:
            address = manager.get_address()
            print("\n🔗 TRUSTLINE XRP")
            print("=" * 60)
            print("⚠️  Per vedere le trustline, usa un explorer:")
            if manager.network == "mainnet":
                print(f"   🔗 https://xrpscan.com/account/{address}/trustlines")
            else:
                print(f"   🔗 https://testnet.xrpl.org/accounts/{address}/trustlines")
            print("=" * 60)

        except Exception as e:
            print(f"❌ Errore: {e}")

    elif args[0] == "create":
        if len(args) < 4:
            print("❌ Uso: trustline_xrp create <asset> <issuer> <limit>")
            return

        asset = args[1]
        issuer = args[2]
        try:
            limit = float(args[3])
        except ValueError:
            print("❌ Limite non valido")
            return

        try:
            wallet = _get_wallet_from_manager(manager)
            if not wallet:
                return

            client = _get_client(manager.network)
            if not client:
                return

            if len(asset) == 3:
                currency = asset
            else:
                currency_hex = asset.encode('utf-8').hex().upper()
                currency = currency_hex.ljust(40, '0')

            # CORRETTO: TrustSet invece di SetTrustLine
            trustline = TrustSet(
                account=wallet.classic_address,
                limit_amount=IssuedCurrencyAmount(
                    currency=currency,
                    issuer=issuer,
                    value=str(limit) if limit > 0 else "0"
                ),
                flags=0  # 0 = nessun flag speciale
            )

            tx = autofill(trustline, client)
            signed_tx = sign(tx, wallet)
            response = submit_and_wait(signed_tx, client)

            tx_hash = response.result.get("hash", "unknown")
            result_code = response.result.get('meta', {}).get('TransactionResult')

            if result_code == "tesSUCCESS":
                print(f"\n✅ Trustline creata per {asset}!")
                print(f"Hash: {tx_hash}")
                if manager.network == "mainnet":
                    print(f"🔗 https://xrpscan.com/tx/{tx_hash}")
                else:
                    print(f"🔗 https://testnet.xrpl.org/transactions/{tx_hash}")
            else:
                print(f"❌ Transazione fallita: {result_code}")

        except Exception as e:
            print(f"❌ Errore: {e}")

    elif args[0] == "remove":
        if len(args) < 3:
            print("❌ Uso: trustline_xrp remove <asset> <issuer>")
            return

        asset = args[1]
        issuer = args[2]

        try:
            wallet = _get_wallet_from_manager(manager)
            if not wallet:
                return

            client = _get_client(manager.network)
            if not client:
                return

            if len(asset) == 3:
                currency = asset
            else:
                currency_hex = asset.encode('utf-8').hex().upper()
                currency = currency_hex.ljust(40, '0')

            # CORRETTO: TrustSet con flag tfClearTrustLine (0x00020000)
            trustline = TrustSet(
                account=wallet.classic_address,
                limit_amount=IssuedCurrencyAmount(
                    currency=currency,
                    issuer=issuer,
                    value="0"
                ),
                flags=0x00020000  # tfClearTrustLine
            )

            tx = autofill(trustline, client)
            signed_tx = sign(tx, wallet)
            response = submit_and_wait(signed_tx, client)

            tx_hash = response.result.get("hash", "unknown")
            result_code = response.result.get('meta', {}).get('TransactionResult')

            if result_code == "tesSUCCESS":
                print(f"\n✅ Trustline rimossa per {asset}!")
                print(f"Hash: {tx_hash}")
            else:
                print(f"❌ Transazione fallita: {result_code}")

        except Exception as e:
            print(f"❌ Errore: {e}")

    else:
        print("❌ Comando non riconosciuto.")
        print("Uso: trustline_xrp [list|create|remove] [asset] [issuer] [limit]")


def send_token_xrp(cli_instance, args):
    """
    Invia token (issued currency) su XRP.
    Uso: send_token_xrp <destinatario> <token> <importo> <issuer> [destination_tag]
    """
    if not _check_xrp_available():
        return

    manager = _get_manager(cli_instance)
    if not manager or not manager.is_loaded():
        print("❌ Nessun wallet caricato!")
        return

    if len(args) < 4:
        print("❌ Uso: send_token_xrp <destinatario> <token> <importo> <issuer> [destination_tag]")
        return

    destination = args[0]
    token = args[1]
    try:
        amount = float(args[2])
    except ValueError:
        print("❌ Importo non valido")
        return
    issuer = args[3]
    destination_tag = None
    if len(args) > 4:
        try:
            destination_tag = int(args[4])
        except ValueError:
            pass

    try:
        wallet = _get_wallet_from_manager(manager)
        if not wallet:
            return

        client = _get_client(manager.network)
        if not client:
            return

        if len(token) == 3:
            currency = token
        else:
            currency_hex = token.encode('utf-8').hex().upper()
            currency = currency_hex.ljust(40, '0')

        amount_obj = IssuedCurrencyAmount(currency=currency, issuer=issuer, value=str(amount))

        payment_params = {
            "account": wallet.classic_address,
            "destination": destination,
            "amount": amount_obj
        }
        if destination_tag is not None:
            payment_params["destination_tag"] = destination_tag

        payment = Payment(**payment_params)
        signed_tx = autofill_and_sign(payment, client, wallet)
        response = submit_and_wait(signed_tx, client)

        tx_hash = response.result.get("hash", "unknown")
        result_code = response.result.get('meta', {}).get('TransactionResult')

        if result_code == "tesSUCCESS":
            print(f"\n✅ {amount} {token} inviati!")
            print(f"Hash: {tx_hash}")
            if destination_tag is not None:
                print(f"Destination Tag: {destination_tag}")
            if manager.network == "mainnet":
                print(f"🔗 https://xrpscan.com/tx/{tx_hash}")
            else:
                print(f"🔗 https://testnet.xrpl.org/transactions/{tx_hash}")
        else:
            print(f"❌ Transazione fallita: {result_code}")

    except Exception as e:
        print(f"❌ Errore: {e}")
        logger.error(f"Errore invio token XRP: {e}", exc_info=True)


__all__ = [
    'send_xrp',
    'history_xrp',
    'info_xrp',
    'fund_testnet_xrp',
    'trustline_xrp',
    'send_token_xrp'
]