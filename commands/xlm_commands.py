#!/usr/bin/env python3
"""
commands/xlm_commands.py - Comandi per XLM (Stellar)
"""

import logging
import requests
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Import condizionale per stellar_sdk
try:
    from stellar_sdk import Keypair, TransactionBuilder, Network, Asset
    from stellar_sdk.memo import IdMemo, TextMemo
    from stellar_sdk.exceptions import NotFoundError, BadRequestError
    STELLAR_SDK_AVAILABLE = True
except ImportError:
    STELLAR_SDK_AVAILABLE = False
    logger.warning("⚠️ stellar-sdk non installato. I comandi XLM non saranno disponibili.")

    class Keypair: pass
    class TransactionBuilder: pass
    class Network: pass
    class Asset: pass
    class IdMemo: pass
    class TextMemo: pass


def _check_stellar_available() -> bool:
    if not STELLAR_SDK_AVAILABLE:
        print("❌ stellar-sdk non installato!")
        print("   Installa con: pip install stellar-sdk")
        return False
    return True


def _get_manager(cli_instance):
    """Ottiene il manager dal CLI (supporta sia vecchio che nuovo)"""
    if hasattr(cli_instance, 'wallet') and cli_instance.wallet:
        return cli_instance.wallet._xrp_manager
    if hasattr(cli_instance, 'manager'):
        return cli_instance.manager
    return None


def history_xlm(cli_instance, args):
    """Storico transazioni per XLM (Stellar)"""
    if not _check_stellar_available():
        return
    
    manager = _get_manager(cli_instance)
    if not manager or not manager.is_loaded():
        print("❌ Nessun wallet caricato!")
        return

    limit = 50
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
        
        wallet_name = "nessun wallet"
        if hasattr(cli_instance, '_get_active_wallet_name'):
            wallet_name = cli_instance._get_active_wallet_name() or "nessun wallet"
        elif hasattr(cli_instance, 'active_wallet_name_file'):
            try:
                if cli_instance.active_wallet_name_file.exists():
                    wallet_name = cli_instance.active_wallet_name_file.read_text().strip() or "nessun wallet"
            except:
                pass

        print(f"\n📜 STORICO TRANSAZIONI XLM")
        print("=" * 80)
        print(f"Wallet:    {wallet_name}")
        print(f"Indirizzo: {address}")
        print(f"Limite:    {limit} transazioni")
        print("=" * 80)

        if manager.network == "mainnet":
            horizon_url = "https://horizon.stellar.org"
        else:
            horizon_url = "https://horizon-testnet.stellar.org"

        url = f"{horizon_url}/accounts/{address}/transactions?limit={limit}&order=desc"
        logger.info(f"Richiesta Horizon: {url}")
        
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Errore Horizon: {response.status_code}")
            print(f"   {response.text[:200]}")
            return
            
        data = response.json()
        transactions = data.get('_embedded', {}).get('records', [])
        
        if not transactions:
            print("❌ Nessuna transazione trovata.")
            return

        if json_output:
            print(json.dumps(transactions, indent=2, default=str))
            return

        print("\n┌────┬─────────────────────┬────────────┬──────────────────┬────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────┬──────────────────────┐")
        print(f"│ #  │ Data/Ora            │ Tipo       │ Importo          │ Fee            │ Da/A                                                                                                │ Memo                 │")
        print("├────┼─────────────────────┼────────────┼──────────────────┼────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────┤")

        for idx, tx in enumerate(transactions[:limit], 1):
            created_at = tx.get('created_at', '')
            date_str = created_at.replace('T', ' ').replace('Z', '')[:19] if created_at else ''
            
            tx_type = tx.get('type', 'unknown')
            
            amount_str = ""
            from_to = ""
            direction = ""
            
            operations_url = f"{horizon_url}/transactions/{tx.get('hash')}/operations"
            try:
                ops_response = requests.get(operations_url, timeout=5)
                if ops_response.status_code == 200:
                    ops_data = ops_response.json()
                    ops = ops_data.get('_embedded', {}).get('records', [])
                    
                    for op in ops[:1]:
                        op_type = op.get('type', '')
                        
                        if op_type == 'payment':
                            amount = float(op.get('amount', 0))
                            asset_type = op.get('asset_type', 'native')
                            asset_code = "XLM" if asset_type == 'native' else op.get('asset_code', '?')
                            from_acct = op.get('from', '')
                            to_acct = op.get('to', '')
                            
                            if to_acct == address:
                                from_to = f"Da: {from_acct}"
                                direction = "RICEVUTO"
                            elif from_acct == address:
                                from_to = f"A: {to_acct}"
                                direction = "INVIATO"
                            else:
                                from_to = f"{from_acct} → {to_acct}"
                                direction = "ALTRO"
                            amount_str = f"{amount:.7f} {asset_code}"
                            break
                            
                        elif op_type == 'create_account':
                            amount = float(op.get('starting_balance', 0))
                            to_acct = op.get('account', '')
                            from_acct = op.get('funder', '')
                            if to_acct == address:
                                from_to = f"Da: {from_acct}"
                                direction = "RICEVUTO"
                            else:
                                from_to = f"A: {to_acct}"
                                direction = "INVIATO"
                            amount_str = f"{amount:.7f} XLM"
                            break
                            
                        elif op_type in ['path_payment_strict_send', 'path_payment_strict_receive']:
                            amount = float(op.get('amount', 0))
                            from_acct = op.get('from', '')
                            to_acct = op.get('to', '')
                            if to_acct == address:
                                from_to = f"Da: {from_acct}"
                                direction = "RICEVUTO"
                            else:
                                from_to = f"A: {to_acct}"
                                direction = "INVIATO"
                            amount_str = f"{amount:.7f} XLM"
                            break
                            
                        elif op_type == 'account_merge':
                            into_acct = op.get('into', '')
                            from_acct = op.get('account', '')
                            from_to = f"{from_acct} → {into_acct}"
                            direction = "MERGE"
                            amount_str = ""
                            break
                            
                        elif op_type in ['set_options', 'change_trust', 'allow_trust', 'manage_data']:
                            from_acct = op.get('source_account', '')
                            if from_acct == address:
                                from_to = f"Da: {from_acct}"
                                direction = "OPERAZIONE"
                            else:
                                from_to = f"Account: {from_acct}"
                                direction = "OPERAZIONE"
                            amount_str = ""
                            break
                            
                        else:
                            from_to = f"Operazione: {op_type.replace('_', ' ').title()}"
                            direction = "ALTRO"
                            amount_str = ""
                            break
                            
            except Exception as e:
                logger.debug(f"Errore recupero operations: {e}")
                from_to = tx_type.replace('_', ' ').title()
                direction = "ALTRO"
                amount_str = ""

            memo_text = ""
            memo_type = tx.get('memo_type', '')
            memo_value = tx.get('memo', '')
            
            if memo_value:
                if memo_type == 'text':
                    memo_text = f"📝 {memo_value}"
                elif memo_type == 'id':
                    memo_text = f"📝 ID: {memo_value}"
                elif memo_type == 'hash':
                    memo_text = f"📝 Hash: {memo_value}"
                else:
                    memo_text = f"📝 {memo_value}"

            # 🔥 FEE CORRETTA: da stroops a XLM
            fee_stroops = tx.get('fee_charged', 0)
            try:
                # 🔥 CONVERTI STROOPS → XLM (1 XLM = 10.000.000 stroops)
                fee_xlm = int(fee_stroops) / 10_000_000
                fee_display = f"{fee_xlm:.8f}".rstrip('0').rstrip('.')
                if not fee_display or fee_display == '':
                    fee_display = "0"
                fee_display += " XLM"
            except Exception as e:
                logger.debug(f"Errore conversione fee: {e}")
                fee_display = str(fee_stroops) + " stroops"

            from_to_display = from_to
            memo_display = memo_text

            print(f"│ {idx:<2} │ {date_str[:19]:<19} │ {direction:<10} │ {amount_str:<16} │ {fee_display:<15} │ {from_to_display:<100} │ {memo_display:<20} │")

        print("└────┴─────────────────────┴────────────┴──────────────────┴────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────┴──────────────────────┘")

        if manager.network == "mainnet":
            explorer = f"https://stellar.expert/explorer/public/account/{address}"
        else:
            explorer = f"https://stellar.expert/explorer/testnet/account/{address}"
        print(f"\n🔗 Visualizza tutto: {explorer}")

        try:
            balance = manager.get_balance()
            print(f"💰 Saldo attuale: {balance:.7f} XLM")
        except:
            pass

        print(f"📊 Mostrate {min(len(transactions), limit)} di {len(transactions)} transazioni")

    except requests.exceptions.Timeout:
        print("❌ Timeout nella richiesta a Horizon")
    except requests.exceptions.ConnectionError:
        print("❌ Errore di connessione a Horizon")
    except Exception as e:
        print(f"❌ Errore: {e}")
        logger.error(f"Errore storico XLM: {e}", exc_info=True)


def send_xlm(cli_instance, args):
    """Invia XLM (Stellar) con supporto memo"""
    if not _check_stellar_available():
        return
    
    manager = _get_manager(cli_instance)
    if not manager or not manager.is_loaded():
        print("❌ Nessun wallet caricato!")
        return

    if not args or len(args) < 2:
        print("❌ Specifica destinatario e importo.")
        print("Esempio: send G... 10")
        return

    dest_arg = args[0]

    try:
        amount = float(args[1])
        if amount <= 0:
            print("❌ L'importo deve essere maggiore di 0")
            return
    except ValueError:
        print("❌ Importo non valido.")
        return

    memo_text = ""
    memo_id = None
    parse_args = list(args)

    if len(parse_args) > 2:
        for arg in parse_args[2:]:
            if arg.startswith('"') and arg.endswith('"'):
                memo_text = arg[1:-1]
            elif arg.startswith("'") and arg.endswith("'"):
                memo_text = arg[1:-1]
            else:
                memo_text = arg

    destination = dest_arg

    try:
        source_address = manager.get_address()
        
        wallet_name = "nessun wallet"
        if hasattr(cli_instance, '_get_active_wallet_name'):
            wallet_name = cli_instance._get_active_wallet_name() or "nessun wallet"
        
        rete = "TESTNET" if manager.network == "testnet" else "MAINNET"

        print(f"\n📤 INVIO XLM ({rete})")
        print("=" * 60)
        print(f"Wallet:    {wallet_name}")
        print(f"Da:        {source_address}")
        print(f"A:         {destination}")
        print(f"Importo:   {amount} XLM")
        if memo_text:
            print(f"📝 Memo:    {memo_text}")
        print("=" * 60)

        manager._init_stellar()
        if not manager.stellar_manager:
            print("❌ Manager Stellar non inizializzato")
            return

        balance = manager.stellar_manager.get_balance(source_address)
        base_fee = 100
        total_needed = amount + (base_fee / 10_000_000)
        
        if balance < total_needed:
            print(f"❌ Saldo insufficiente (inclusa fee minima)!")
            print(f"   Hai:      {balance:.7f} XLM")
            print(f"   Servono:  {total_needed:.7f} XLM (importo + fee)")
            return

        keypair = Keypair.from_secret(manager.base_seed_stellar)
        source_account = manager.stellar_manager.server.load_account(keypair.public_key)

        builder = TransactionBuilder(
            source_account=source_account,
            network_passphrase=manager.stellar_manager.network_passphrase,
            base_fee=base_fee
        )
        builder.set_timeout(300)

        builder.append_payment_op(
            destination=destination,
            amount=str(amount),
            asset=Asset.native()
        )

        if memo_id is not None:
            builder.add_memo(IdMemo(memo_id))
        elif memo_text:
            builder.add_memo(TextMemo(memo_text[:64]))

        transaction = builder.build()
        transaction.sign(keypair)
        response = manager.stellar_manager.server.submit_transaction(transaction)

        if response.get('hash'):
            print("\n✅ TRANSAZIONE INVIATA!")
            print("=" * 60)
            print(f"Hash:   {response.get('hash', 'unknown')}")
            print(f"Ledger: {response.get('ledger', 0)}")
            print("=" * 60)

            new_balance = manager.stellar_manager.get_balance(source_address)
            print(f"💰 Nuovo saldo: {new_balance:.7f} XLM")
        else:
            print(f"❌ Errore nella transazione: {response}")

    except BadRequestError as e:
        print(f"❌ Errore richiesta: {e}")
        if "insufficient balance" in str(e):
            print("   Saldo insufficiente per la transazione (inclusa la fee)")
    except Exception as e:
        print(f"❌ Errore: {e}")
        logger.error(f"Errore invio XLM: {e}", exc_info=True)


def info_xlm(cli_instance, args):
    """Info wallet per XLM (Stellar)"""
    if not _check_stellar_available():
        return
    
    manager = _get_manager(cli_instance)
    if not manager or not manager.is_loaded():
        print("❌ Nessun wallet caricato!")
        return

    info = manager.get_seed_info()
    rete = "TESTNET" if manager.network == "testnet" else "MAINNET"
    
    wallet_name = "nessun wallet"
    if hasattr(cli_instance, '_get_active_wallet_name'):
        wallet_name = cli_instance._get_active_wallet_name() or "nessun wallet"

    try:
        address = manager.get_address()
    except Exception as e:
        address = f"❌ {e}"

    print("\n📋 INFO WALLET XLM")
    print("=" * 60)
    print(f"Wallet:    {wallet_name}")
    print(f"Rete:      {rete}")
    print(f"Crypto:    XLM")
    print(f"Tipo seed: {info.get('seed_type')}")
    print(f"🏠 Indirizzo: {address}")

    if address and not str(address).startswith("❌"):
        try:
            balance = manager.get_balance()
            print(f"💰 Saldo:   {balance:.7f} XLM")
        except Exception as e:
            print(f"💰 Saldo:   ❌ {e}")

    if info.get('seed_type') == 'bip39':
        print(f"Parole: {info.get('word_count')}")
        print(f"Frase: {info.get('seed_phrase')}")
        if info.get('passphrase'):
            print(f"🔐 Passphrase: {info.get('passphrase')}")
    elif info.get('seed_type') == 'stellar_seed':
        print(f"Seed Stellar: {info.get('seed_stellar')}")

    try:
        manager._init_stellar()
        if manager.stellar_manager:
            account_info = manager.stellar_manager.get_account_info(address)
            if 'error' not in account_info:
                print(f"\n📊 Info Account Stellar:")
                print(f"   Sequence: {account_info.get('sequence', 'N/A')}")
                print(f"   Signers: {len(account_info.get('signers', []))}")
                thresholds = account_info.get('thresholds', {})
                if thresholds:
                    print(f"   Thresholds: low={thresholds.get('low_threshold')}, "
                          f"med={thresholds.get('med_threshold')}, "
                          f"high={thresholds.get('high_threshold')}")
    except Exception as e:
        logger.warning(f"Errore info account: {e}")

    derived = manager.list_derived()
    print(f"\nIndirizzi derivati: {len(derived)}")

    print("\n" + "=" * 60)


def faucet_xlm(cli_instance):
    """Faucet per XLM (Stellar Testnet)"""
    if not _check_stellar_available():
        return
    
    manager = _get_manager(cli_instance)
    if not manager or not manager.is_loaded():
        print("❌ Nessun wallet caricato!")
        return

    if manager.network != "testnet":
        print("❌ Il faucet XLM funziona SOLO su TESTNET!")
        return

    try:
        address = manager.get_address()
        if not address:
            print("❌ Nessun wallet caricato. Crea un wallet prima.")
            return

        print(f"\n💰 FAUCET XLM - RICHIESTA XLM DI TEST")
        print("=" * 60)
        print(f"📤 Richiesta per: {address}")

        response = requests.get(
            f"https://friendbot.stellar.org/?addr={address}",
            timeout=30
        )

        if response.status_code == 200:
            print("✅ XLM DI TEST RICEVUTI!")
            
            manager._init_stellar()
            if manager.stellar_manager:
                balance = manager.stellar_manager.get_balance(address)
                print(f"💰 Nuovo saldo: {balance:.7f} XLM")
            else:
                print("💰 Controlla il saldo con 'balance'")
        else:
            print(f"❌ Errore: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Dettaglio: {error_data.get('detail', 'N/A')}")
            except:
                print(f"   Risposta: {response.text[:200]}")
                
    except requests.exceptions.Timeout:
        print("❌ Timeout nella richiesta a Friendbot")
    except requests.exceptions.ConnectionError:
        print("❌ Errore di connessione a Friendbot")
    except Exception as e:
        print(f"❌ Errore: {e}")
        logger.error(f"Errore faucet XLM: {e}", exc_info=True)


__all__ = ['send_xlm', 'history_xlm', 'info_xlm', 'faucet_xlm']