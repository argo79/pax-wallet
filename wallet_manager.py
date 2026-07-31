#!/usr/bin/env python3
"""
wallet_manager.py - PAX Wallet Manager for XRP and XLM (Stellar)
Version loaded from version.py - FIX FOR TERMUX/ANDROID
"""

import json
import base58
import hashlib
import re
import subprocess
import os
import sys
import logging
import time
from typing import Optional, Dict, Any, List, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from enum import Enum

# 🔥 READ VERSION FROM version.py
try:
    from version import VERSION
except ImportError:
    VERSION = "1.1.1"

from mnemonic import Mnemonic
from bip32 import BIP32
from xrpl.core import keypairs
from xrpl.wallet import Wallet as XRPWallet
from xrpl.constants import CryptoAlgorithm
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import ecdsa

# Stellar imports with error handling
try:
    from stellar_sdk import Keypair, Server, TransactionBuilder, Network, Asset, Memo
    from stellar_sdk.exceptions import NotFoundError, BadRequestError
    from stellar_sdk.memo import IdMemo, TextMemo
    from stellar_sdk.sep.mnemonic import StellarMnemonic
    STELLAR_AVAILABLE = True
    STELLAR_IMPORT_ERROR = None
except ImportError as e:
    STELLAR_AVAILABLE = False
    STELLAR_IMPORT_ERROR = str(e)
    logging.warning(f"stellar-sdk not available: {e}")

# 🔥 CORE RUST IMPORTS
try:
    import wallet_core as _rust
    CORE_AVAILABLE = True
    CORE_IMPORT_ERROR = None
except ImportError as e:
    CORE_AVAILABLE = False
    CORE_IMPORT_ERROR = str(e)
    logging.warning(f"wallet_core not available: {e}")

# 🔥 DETERMINE EXECUTION DIRECTORY
def get_app_dir() -> Path:
    """Get the execution directory of the program"""
    if getattr(sys, 'frozen', False):
        return Path(os.path.dirname(sys.executable))
    else:
        return Path(os.path.dirname(os.path.abspath(__file__)))

def is_termux() -> bool:
    """Check if running on Termux/Android"""
    if os.path.exists("/data/data/com.termux"):
        return True
    if os.path.exists("/system/bin") and os.path.exists("/system/app"):
        return True
    return False

APP_DIR = get_app_dir()

if is_termux():
    DATA_DIR = APP_DIR
    print(f"📱 Termux detected - Using directory: {DATA_DIR}")
else:
    DATA_DIR = APP_DIR

DATA_DIR = Path(os.environ.get('XRPWALLET_DATA_DIR', str(DATA_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


class CryptoType(Enum):
    XRP = "XRP"
    XLM = "XLM"


class NetworkType(Enum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    DEVNET = "devnet"


class SeedType(Enum):
    BIP39 = "bip39"
    NUMBERS = "numbers"
    PRIVATE_KEY = "private_key"
    XRP_SEED = "xrp_seed"
    STELLAR_SEED = "stellar_seed"


@dataclass
class WalletInfo:
    keyword: str
    index: int
    address: str
    private_key: str
    public_key: str
    seed_xrp: str
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WalletInfo':
        return cls(**data)


@dataclass
class CoreTrustlineInfo:
    """Rappresentazione Python di una trustline dal Core Rust"""
    id: str
    identity_id: str
    network: str
    asset_code: str
    asset_issuer: Optional[str]
    decimals: int
    limit: Optional[float]
    balance: Optional[float]
    authorized: bool
    peer_authorized: bool
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "identity_id": self.identity_id,
            "network": self.network,
            "asset_code": self.asset_code,
            "asset_issuer": self.asset_issuer,
            "decimals": self.decimals,
            "limit": self.limit,
            "balance": self.balance,
            "authorized": self.authorized,
            "peer_authorized": self.peer_authorized,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_rust(cls, rust_trustline) -> 'CoreTrustlineInfo':
        """Converte da PyTrustline a dataclass Python"""
        try:
            asset = rust_trustline.asset()
            return cls(
                id=rust_trustline.id(),
                identity_id=rust_trustline.identity_id(),
                network=str(asset.inner.network) if hasattr(asset, 'inner') else "XRPL",
                asset_code=asset.inner.code if hasattr(asset, 'inner') else "UNKNOWN",
                asset_issuer=asset.inner.issuer if hasattr(asset, 'inner') else None,
                decimals=asset.inner.decimals if hasattr(asset, 'inner') else 6,
                limit=rust_trustline.limit(),
                balance=rust_trustline.balance(),
                authorized=rust_trustline.authorized(),
                peer_authorized=rust_trustline.peer_authorized(),
                is_active=rust_trustline.is_active()
            )
        except Exception as e:
            logger.error(f"Error converting trustline: {e}")
            return cls(
                id="unknown",
                identity_id="unknown",
                network="XRPL",
                asset_code="UNKNOWN",
                asset_issuer=None,
                decimals=6,
                limit=None,
                balance=None,
                authorized=False,
                peer_authorized=False,
                is_active=False
            )


class XamanSecretNumbersBridge:
    """Bridge to convert Xaman secret numbers to XRP seed"""
    
    def __init__(self):
        self._use_python_fallback = False
        self._nodejs_available = self._check_nodejs()
        if self._nodejs_available:
            self._ensure_library()
        else:
            logger.warning("Node.js not available, using Python fallback")
            self._use_python_fallback = True
    
    def _get_node_modules_path(self) -> Optional[str]:
        """Find node_modules path"""
        possible_paths = [
            str(APP_DIR / "node_modules"),
            str(APP_DIR / "node_bundle" / "node_modules"),
            str(Path.cwd() / "node_modules"),
            "./node_modules",
            "../node_modules",
        ]
        
        if hasattr(sys, '_MEIPASS'):
            bundle_path = os.path.join(sys._MEIPASS, "node_modules")
            if os.path.exists(bundle_path):
                return bundle_path
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _check_nodejs(self) -> bool:
        try:
            result = subprocess.run(['node', '--version'], 
                                  capture_output=True, 
                                  check=True,
                                  timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _ensure_library(self) -> None:
        """Ensure library is available"""
        node_modules_path = self._get_node_modules_path()
        
        if node_modules_path is None:
            logger.warning("node_modules not found")
            self._use_python_fallback = True
            return
        
        pkg_new = os.path.join(node_modules_path, "@xrplf", "secret-numbers")
        pkg_old = os.path.join(node_modules_path, "xrpl-secret-numbers")
        
        if os.path.exists(pkg_new):
            logger.info(f"✅ @xrplf/secret-numbers found")
        elif os.path.exists(pkg_old):
            logger.info(f"✅ xrpl-secret-numbers found")
        else:
            logger.warning("No package found, using Python fallback")
            self._use_python_fallback = True
    
    def numbers_to_seed(self, numbers: List[str]) -> str:
        if self._use_python_fallback:
            return self._numbers_to_seed_python(numbers)
        return self._numbers_to_seed_nodejs(numbers)
    
    def numbers_to_address(self, numbers: List[str]) -> str:
        if self._use_python_fallback:
            seed = self._numbers_to_seed_python(numbers)
            public_key, _ = keypairs.derive_keypair(seed)
            return keypairs.derive_classic_address(public_key)
        return self._numbers_to_address_nodejs(numbers)
    
    def _numbers_to_seed_nodejs(self, numbers: List[str]) -> str:
        """Conversion via Node.js with input validation"""
        if not numbers or len(numbers) != 8:
            raise ValueError(f"Need 8 numbers, got {len(numbers)}")
        
        for num in numbers:
            if not re.match(r'^[0-9]{6}$', str(num).strip()):
                raise ValueError(f"Invalid number: {num} (must be 6 digits)")
        
        safe_numbers = []
        for num in numbers:
            clean_num = re.sub(r'[^0-9]', '', str(num))
            if len(clean_num) == 6:
                safe_numbers.append(clean_num)
            else:
                raise ValueError(f"Invalid number after sanitization: {num}")
        
        numbers_str = " ".join(safe_numbers)
        
        node_modules_path = self._get_node_modules_path()
        if node_modules_path is None:
            node_modules_path = "./node_modules"
        
        if not re.match(r'^[a-zA-Z0-9_./-]+$', node_modules_path):
            raise ValueError("Invalid node_modules path")
        
        script = f'''
        const path = require('path');
        const modulePath = path.resolve('{node_modules_path}');
        
        let Account;
        let useOld = false;
        
        try {{
            const pkg = require(path.join(modulePath, '@xrplf', 'secret-numbers'));
            Account = pkg.Account;
        }} catch (e) {{
            try {{
                const pkg = require(path.join(modulePath, 'xrpl-secret-numbers'));
                Account = pkg.Account;
                useOld = true;
            }} catch (e2) {{
                console.error('No package found');
                process.exit(1);
            }}
        }}
        
        const secret = '{numbers_str}';
        let account;
        
        if (useOld) {{
            account = new Account(secret);
        }} else {{
            try {{
                account = new Account(secret);
            }} catch (e) {{
                const numbersArray = secret.split(' ');
                account = new Account(numbersArray);
            }}
        }}
        
        console.log(JSON.stringify({{
            familySeed: account.getFamilySeed(),
            address: account.getAddress()
        }}));
        '''
        
        try:
            result = subprocess.run(
                ['node', '-e', script],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False
            )
            if result.returncode != 0:
                raise RuntimeError(f"Node.js error: {result.stderr}")
            data = json.loads(result.stdout)
            return data['familySeed']
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout converting numbers")
        except Exception as e:
            raise RuntimeError(f"Error converting numbers: {e}")
    
    def _numbers_to_address_nodejs(self, numbers: List[str]) -> str:
        """Conversion via Node.js for address with validation"""
        if not numbers or len(numbers) != 8:
            raise ValueError(f"Need 8 numbers, got {len(numbers)}")
        
        for num in numbers:
            if not re.match(r'^[0-9]{6}$', str(num).strip()):
                raise ValueError(f"Invalid number: {num}")
        
        safe_numbers = []
        for num in numbers:
            clean_num = re.sub(r'[^0-9]', '', str(num))
            if len(clean_num) == 6:
                safe_numbers.append(clean_num)
        
        numbers_str = " ".join(safe_numbers)
        
        node_modules_path = self._get_node_modules_path()
        if node_modules_path is None:
            node_modules_path = "./node_modules"
        
        if not re.match(r'^[a-zA-Z0-9_./-]+$', node_modules_path):
            raise ValueError("Invalid node_modules path")
        
        script = f'''
        const path = require('path');
        const modulePath = path.resolve('{node_modules_path}');
        
        let Account;
        let useOld = false;
        
        try {{
            const pkg = require(path.join(modulePath, '@xrplf', 'secret-numbers'));
            Account = pkg.Account;
        }} catch (e) {{
            try {{
                const pkg = require(path.join(modulePath, 'xrpl-secret-numbers'));
                Account = pkg.Account;
                useOld = true;
            }} catch (e2) {{
                console.error('No package found');
                process.exit(1);
            }}
        }}
        
        const secret = '{numbers_str}';
        let account;
        
        if (useOld) {{
            account = new Account(secret);
        }} else {{
            try {{
                account = new Account(secret);
            }} catch (e) {{
                const numbersArray = secret.split(' ');
                account = new Account(numbersArray);
            }}
        }}
        
        console.log(JSON.stringify({{
            familySeed: account.getFamilySeed(),
            address: account.getAddress()
        }}));
        '''
        
        try:
            result = subprocess.run(
                ['node', '-e', script],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False
            )
            if result.returncode != 0:
                raise RuntimeError(f"Node.js error: {result.stderr}")
            data = json.loads(result.stdout)
            return data['address']
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout converting address")
        except Exception as e:
            raise RuntimeError(f"Error converting numbers: {e}")
    
    def _numbers_to_seed_python(self, numbers: List[str]) -> str:
        """Python fallback - uses 3 bytes per number"""
        if len(numbers) != 8:
            raise ValueError(f"Need 8 numbers, got {len(numbers)}")
        
        for num in numbers:
            if not num.isdigit() or len(num) != 6:
                raise ValueError(f"Invalid number: {num}")
            if not (0 <= int(num) <= 999999):
                raise ValueError(f"Number out of range: {num}")
        
        entropy = bytearray()
        for num_str in numbers:
            num = int(num_str)
            entropy.extend(num.to_bytes(3, 'big'))
        
        full_bytes = bytes([0x01]) + bytes(entropy)
        return base58.b58encode(full_bytes).decode()


class StellarManager:
    """Stellar (XLM) wallet management"""
    
    def __init__(self, network: str = "testnet"):
        if not STELLAR_AVAILABLE:
            raise ImportError(f"stellar-sdk not installed: {STELLAR_IMPORT_ERROR}")
        
        self.network = network
        self._init_server(network)
    
    def _init_server(self, network: str) -> None:
        if network == "mainnet":
            self.server = Server("https://horizon.stellar.org")
            self.network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE
        else:
            self.server = Server("https://horizon-testnet.stellar.org")
            self.network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE
    
    def set_network(self, network: str) -> None:
        self.network = network
        self._init_server(network)
    
    def create_wallet(self) -> Dict[str, str]:
        keypair = Keypair.random()
        return {
            "public_key": keypair.public_key,
            "secret_key": keypair.secret,
            "seed": keypair.secret
        }
    
    def from_seed(self, seed: str) -> Dict[str, str]:
        try:
            keypair = Keypair.from_secret(seed)
            return {
                "public_key": keypair.public_key,
                "secret_key": keypair.secret,
                "address": keypair.public_key
            }
        except Exception as e:
            raise ValueError(f"Invalid Stellar seed: {e}")
    
    def get_balance(self, address: str) -> float:
        try:
            account = self.server.accounts().account_id(address).call()
            for balance in account.get('balances', []):
                if balance['asset_type'] == 'native':
                    return float(balance['balance'])
            return 0.0
        except NotFoundError:
            return 0.0
        except Exception as e:
            logger.error(f"Error getting Stellar balance: {e}")
            return 0.0
    
    def fund_testnet(self, address: str) -> bool:
        if self.network != "testnet":
            logger.error("Friendbot works only on TESTNET!")
            return False
        
        try:
            import requests
            url = f"https://friendbot.stellar.org?addr={address}"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                logger.info(f"✅ Wallet {address} funded on Testnet!")
                return True
            else:
                logger.error(f"Friendbot error: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
    
    def send_payment(self, from_secret: str, to_address: str, amount: float, 
                    memo_text: str = "", memo_id: int = None) -> Dict:
        try:
            keypair = Keypair.from_secret(from_secret)
            source_account = self.server.load_account(keypair.public_key)
            
            builder = TransactionBuilder(
                source_account=source_account,
                network_passphrase=self.network_passphrase,
                base_fee=100
            )
            builder.set_timeout(300)
            
            builder.append_payment_op(
                destination=to_address,
                amount=str(amount),
                asset=Asset.native()
            )
            
            if memo_id is not None:
                builder.add_memo(IdMemo(memo_id))
            elif memo_text:
                builder.add_memo(TextMemo(memo_text[:28]))
            
            transaction = builder.build()
            transaction.sign(keypair)
            response = self.server.submit_transaction(transaction)
            
            return {
                "success": True,
                "hash": response.get("hash", "unknown"),
                "ledger": response.get("ledger", 0)
            }
        except Exception as e:
            logger.error(f"Error sending XLM: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_account_info(self, address: str) -> Dict:
        try:
            account = self.server.accounts().account_id(address).call()
            return {
                "address": address,
                "balance": self.get_balance(address),
                "sequence": account.get('sequence', 0),
                "signers": account.get('signers', []),
                "thresholds": account.get('thresholds', {}),
                "flags": account.get('flags', {})
            }
        except NotFoundError:
            return {"error": "Account not found on this network"}
        except Exception as e:
            return {"error": str(e)}


class HybridXRPManager:
    """Main manager for XRP and XLM wallets - WITH RUST CORE INTEGRATION"""
    
    def __init__(self, data_file: str = "wallet_data.json"):
        # 🔥 USE ONLY EXECUTION DIRECTORY
        self.data_file = DATA_DIR / data_file
        self.mnemo = Mnemonic("english")
        
        # Wallet state
        self.seed_type: Optional[str] = None
        self.seed_phrase: Optional[str] = None
        self.seed_numbers: Optional[List[str]] = None
        self.passphrase: str = ""
        self.base_private: Optional[bytes] = None
        self.base_seed_xrp: Optional[str] = None
        self.base_seed_stellar: Optional[str] = None
        self._correct_address: Optional[str] = None
        self.network: str = "testnet"
        self.crypto_type: str = "XRP"
        
        # Cache and derived data
        self._derived_wallets: Dict[str, WalletInfo] = {}
        self._balance_cache: Dict[str, Tuple[float, float]] = {}
        self._cache_ttl: int = 60  # seconds
        
        # Managers
        self.stellar_manager: Optional[StellarManager] = None
        self._bridge: Optional[XamanSecretNumbersBridge] = None
        
        # 🔥 CORE RUST
        self._core: Optional[Any] = None
        self._core_identity_id: Optional[str] = None
        self._core_initialized: bool = False
        
        # 🔥 CREATE DIRECTORY IF NOT EXISTS
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load saved wallet
        self.load()
        
        # 🔥 INIT CORE RUST
        if CORE_AVAILABLE:
            self._init_core()
    
    @property
    def bridge(self) -> XamanSecretNumbersBridge:
        if self._bridge is None:
            self._bridge = XamanSecretNumbersBridge()
        return self._bridge
    
    # ============================================================
    # CORE RUST INTEGRATION
    # ============================================================
    
    def _init_core(self) -> None:
        """Initialize Rust core"""
        if not CORE_AVAILABLE:
            logger.warning("Core Rust not available")
            return
        
        if self._core_initialized:
            return
        
        try:
            # Import core wrapper
            from core_wrapper import create_core, CoreIntegration
            
            core_db_path = DATA_DIR / "wallet_core.db"
            self._core = create_core(str(core_db_path))
            self._core_integration = CoreIntegration(self._core)
            self._core_initialized = True
            
            # Create identity if wallet loaded
            if self.is_loaded():
                self._sync_core_identity()
            
            logger.info(f"✅ Core Rust initialized at {core_db_path}")
        except ImportError as e:
            logger.warning(f"Core wrapper not available: {e}")
            self._core_initialized = False
        except Exception as e:
            logger.error(f"Error initializing core: {e}")
            self._core_initialized = False
    
    def _sync_core_identity(self) -> Optional[str]:
        """Sync or create identity in core"""
        if not self._core_initialized or not CORE_AVAILABLE:
            return None
        
        try:
            # Generate fingerprint from seed
            fingerprint = self._get_core_fingerprint()
            
            if not fingerprint:
                # Create new identity
                identity_id = self._core.create_identity(f"Wallet_{int(time.time())}")
                self._core_identity_id = identity_id
                if hasattr(self, '_core_integration') and self._core_integration:
                    self._core_integration.set_identity(identity_id)
                return identity_id
            
            # Check if identity exists
            identities = self._core.list_identities()
            # 🔥 VERIFICA CHE identities SIA UNA LISTA
            if isinstance(identities, list):
                for ident in identities:
                    if isinstance(ident, dict) and ident.get("fingerprint") == fingerprint:
                        self._core_identity_id = ident["id"]
                        if hasattr(self, '_core_integration') and self._core_integration:
                            self._core_integration.set_identity(ident["id"])
                        return ident["id"]
            else:
                # Se identities non è una lista, logga e continua
                logger.warning(f"list_identities returned: {type(identities)}")
            
            # Create new identity with fingerprint
            identity_id = self._core.create_identity(f"Wallet_{fingerprint[:8]}")
            self._core_identity_id = identity_id
            if hasattr(self, '_core_integration') and self._core_integration:
                self._core_integration.set_identity(identity_id)
            return identity_id
            
        except Exception as e:
            logger.error(f"Error syncing core identity: {e}")
            return None
    
    def _get_core_fingerprint(self) -> Optional[str]:
        """Generate fingerprint for core identity"""
        if self.seed_phrase:
            return hashlib.sha256(self.seed_phrase.encode()).hexdigest()[:16]
        elif self.base_seed_xrp:
            return hashlib.sha256(self.base_seed_xrp.encode()).hexdigest()[:16]
        elif self.base_seed_stellar:
            return hashlib.sha256(self.base_seed_stellar.encode()).hexdigest()[:16]
        elif self.base_private:
            return hashlib.sha256(self.base_private).hexdigest()[:16]
        return None
    
    def get_core_identity(self) -> Optional[str]:
        """Get current core identity ID"""
        if not self._core_initialized:
            return None
        return self._core_identity_id
    
    def sync_trustlines_with_core(self) -> List[CoreTrustlineInfo]:
        """Sync trustlines from wallet_manager to core"""
        if not self._core_initialized or not CORE_AVAILABLE:
            return []
        
        identity_id = self.get_core_identity()
        if not identity_id:
            identity_id = self._sync_core_identity()
            if not identity_id:
                return []
        
        try:
            # Get trustlines from ledger
            trustlines = self.get_trustlines(force_refresh=True)
            
            # Delete existing trustlines
            existing = self._core.get_trustlines(identity_id)
            for tl in existing:
                self._core.delete_trustline(tl.id)
            
            # Create new trustlines
            results = []
            for tl_data in trustlines:
                network = tl_data.get("network", "XRPL")
                if network == "Stellar":
                    network = "Stellar"
                else:
                    network = "XRPL"
                
                asset_code = tl_data.get("currency") or tl_data.get("asset_code")
                issuer = tl_data.get("issuer") or tl_data.get("asset_issuer")
                limit = tl_data.get("limit")
                balance = tl_data.get("balance")
                
                if not asset_code or not issuer:
                    continue
                
                try:
                    rust_id = self._core.create_trustline(
                        identity_id,
                        network,
                        asset_code,
                        issuer,
                        limit
                    )
                    
                    # Update balance if available
                    if balance is not None:
                        self._core.update_trustline_balance(rust_id, float(balance))
                    
                    # Get trustline info
                    tl_info = self._core.get_trustline(rust_id)
                    if tl_info:
                        results.append(CoreTrustlineInfo.from_rust(tl_info))
                        
                except Exception as e:
                    logger.error(f"Error syncing trustline {asset_code}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error syncing trustlines: {e}")
            return []
    
    def get_core_trustlines(self) -> List[CoreTrustlineInfo]:
        """Get trustlines from core"""
        if not self._core_initialized or not CORE_AVAILABLE:
            return []
        
        identity_id = self.get_core_identity()
        if not identity_id:
            return []
        
        try:
            trustlines = self._core.get_trustlines(identity_id)
            return [CoreTrustlineInfo.from_rust(tl) for tl in trustlines]
        except Exception as e:
            logger.error(f"Error getting core trustlines: {e}")
            return []
    
    def create_trustline_with_core(self, asset_code: str, issuer: str, limit: float = None) -> Dict:
        """Create trustline and sync with core"""
        # Create on ledger
        result = self.set_trustline(asset_code, issuer, limit)
        
        if not result.get("success"):
            return result
        
        # Sync with core
        if self._core_initialized and CORE_AVAILABLE:
            identity_id = self.get_core_identity()
            if identity_id:
                try:
                    network = "Stellar" if self.crypto_type == "XLM" else "XRPL"
                    rust_id = self._core.create_trustline(
                        identity_id,
                        network,
                        asset_code,
                        issuer,
                        limit
                    )
                    result["core_id"] = rust_id
                    logger.info(f"Trustline saved to core: {rust_id}")
                except Exception as e:
                    logger.error(f"Error saving trustline to core: {e}")
                    result["core_error"] = str(e)
        
        return result
    
    def delete_trustline_from_core(self, asset_code: str, issuer: str) -> bool:
        """Delete trustline from core"""
        if not self._core_initialized or not CORE_AVAILABLE:
            return False
        
        identity_id = self.get_core_identity()
        if not identity_id:
            return False
        
        try:
            trustlines = self._core.get_trustlines(identity_id)
            for tl in trustlines:
                if tl.asset_code == asset_code and tl.asset_issuer == issuer:
                    self._core.delete_trustline(tl.id)
                    logger.info(f"Trustline deleted from core: {tl.id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error deleting trustline from core: {e}")
            return False
    
    # ============================================================
    # PRIVATE METHODS
    # ============================================================
    
    def _private_key_to_seed(self, private_key_hex: str) -> str:
        hash_bytes = hashlib.sha256(bytes.fromhex(private_key_hex)).digest()
        entropy = hash_bytes[:16].hex()
        return keypairs.generate_seed(entropy=entropy)
    
    def _private_key_to_keypair(self, private_key_hex: str) -> Tuple[str, str]:
        private_key_bytes = bytes.fromhex(private_key_hex)
        sk = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
        vk = sk.get_verifying_key()
        vk_bytes = vk.to_string()
        
        if vk_bytes[31] % 2 == 0:
            public_key_bytes = b'\x02' + vk_bytes[:32]
        else:
            public_key_bytes = b'\x03' + vk_bytes[:32]
        
        public_key_hex = public_key_bytes.hex()
        address = keypairs.derive_classic_address(public_key_hex)
        return public_key_hex, address
    
    def _format_numbers(self, numbers: List[str]) -> str:
        return " ".join(numbers)
    
    def _clean_numbers_input(self, raw_input: str) -> List[str]:
        """Clean and validate Xaman numbers input"""
        if not raw_input:
            return []
        
        cleaned = re.sub(r'[^0-9\s]', '', raw_input)
        parts = [p for p in cleaned.split() if p]
        
        valid_numbers = []
        for p in parts:
            if len(p) == 6 and p.isdigit():
                valid_numbers.append(p)
            elif len(p) > 6:
                for i in range(0, len(p), 6):
                    chunk = p[i:i+6]
                    if len(chunk) == 6 and chunk.isdigit():
                        valid_numbers.append(chunk)
        
        return valid_numbers[:8] if len(valid_numbers) >= 8 else []
    
    def _bip39_to_private_key(self, phrase: str, passphrase: str = "") -> str:
        seed_bytes = self.mnemo.to_seed(phrase, passphrase)
        bip32 = BIP32.from_seed(seed_bytes)
        child = bip32.get_privkey_from_path("m/44'/144'/0'/0/0")
        return child.hex()
    
    def _derive_private_key(self, keyword: str = "default", index: int = 0) -> bytes:
        if self.base_private is None:
            raise ValueError("❌ No wallet loaded!")
        
        salt = hashlib.sha256(f"hybrid_xrp_derivation_{self.crypto_type}".encode()).digest()
        
        hkdf = HKDF(
            algorithm=hashes.SHA512(),
            length=32,
            salt=salt,
            info=f"{keyword}:{index}:{self.crypto_type}".encode(),
            backend=default_backend()
        )
        return hkdf.derive(self.base_private)
    
    def _init_stellar(self) -> None:
        if self.stellar_manager is None:
            if not STELLAR_AVAILABLE:
                raise ImportError(f"stellar-sdk not installed: {STELLAR_IMPORT_ERROR}")
            self.stellar_manager = StellarManager(self.network)
        else:
            self.stellar_manager.set_network(self.network)
    
    def _get_xrp_balance(self, address: str) -> float:
        try:
            from xrpl.account import get_balance
            from xrpl.clients import JsonRpcClient
            
            if self.network == "mainnet":
                client = JsonRpcClient("https://s1.ripple.com:51234/")
            else:
                client = JsonRpcClient("https://s.altnet.rippletest.net:51234/")
            
            balance = get_balance(address, client)
            return balance / 1_000_000
        except Exception as e:
            logger.error(f"Error getting XRP balance: {e}")
            return 0.0
    
    def _numbers_to_seed_fallback(self, numbers: List[str]) -> str:
        seed_bytes = b""
        for num_str in numbers:
            num = int(num_str)
            if num < 0 or num > 999999:
                raise ValueError(f"Number out of range: {num}")
            seed_bytes += num.to_bytes(3, 'big')
        full_bytes = bytes([0x01]) + seed_bytes
        return base58.b58encode(full_bytes).decode()
    
    # ============================================================
    # PUBLIC METHODS - CONFIGURATION
    # ============================================================
    
    def set_network(self, network: str) -> None:
        if network not in [n.value for n in NetworkType]:
            raise ValueError(f"Network not supported: {network}")
        self.network = network
        if self.stellar_manager is not None:
            self.stellar_manager.set_network(network)
    
    def set_crypto(self, crypto_type: str) -> None:
        if crypto_type not in [c.value for c in CryptoType]:
            raise ValueError(f"Crypto not supported: {crypto_type}")
        
        self.crypto_type = crypto_type
        if crypto_type == "XLM" and STELLAR_AVAILABLE:
            self._init_stellar()
    
    # ============================================================
    # PUBLIC METHODS - WALLET CREATION
    # ============================================================
    
    def create_new_wallet_bip39(self, passphrase: str = "", strength: int = 128) -> Dict[str, Any]:
        if self.crypto_type == "XLM":
            return self.create_new_wallet_stellar(passphrase, strength)
        
        self.seed_type = SeedType.BIP39.value
        self.seed_phrase = self.mnemo.generate(strength=strength)
        self.seed_numbers = None
        self.passphrase = passphrase
        
        private_key_hex = self._bip39_to_private_key(self.seed_phrase, passphrase)
        public_key, address = self._private_key_to_keypair(private_key_hex)
        self.base_private = bytes.fromhex(private_key_hex)
        self._correct_address = address
        
        entropy = private_key_hex[:32]
        self.base_seed_xrp = keypairs.generate_seed(entropy=entropy)
        
        self.save()
        
        # Sync with core
        if CORE_AVAILABLE:
            self._sync_core_identity()
        
        return {
            "seed_type": SeedType.BIP39.value,
            "seed_phrase": self.seed_phrase,
            "passphrase": passphrase,
            "word_count": len(self.seed_phrase.split()),
            "first_address": address,
            "first_private_key": private_key_hex,
            "first_public_key": public_key,
            "first_seed_xrp": self.base_seed_xrp,
        }
    
    def create_new_wallet_stellar(self, passphrase: str = "", strength: int = 256) -> Dict[str, Any]:
        if not STELLAR_AVAILABLE:
            raise ImportError(f"stellar-sdk not installed: {STELLAR_IMPORT_ERROR}")
        
        mnemonic = StellarMnemonic("english")
        seed_phrase = mnemonic.generate(strength=strength)
        
        self.seed_phrase = seed_phrase
        self.seed_type = SeedType.BIP39.value
        self.seed_numbers = None
        self.passphrase = passphrase
        self.crypto_type = "XLM"
        
        keypair = Keypair.from_mnemonic_phrase(seed_phrase)
        
        self.base_seed_stellar = keypair.secret
        self._correct_address = keypair.public_key
        self.base_private = None
        self.base_seed_xrp = None
        
        self.save()
        
        # Sync with core
        if CORE_AVAILABLE:
            self._sync_core_identity()
        
        return {
            "seed_type": SeedType.BIP39.value,
            "seed_phrase": seed_phrase,
            "passphrase": passphrase,
            "word_count": len(seed_phrase.split()),
            "first_address": keypair.public_key,
            "first_private_key": keypair.secret,
            "first_public_key": keypair.public_key,
            "first_seed_stellar": keypair.secret,
        }
    
    def create_new_wallet_numbers(self) -> Dict[str, Any]:
        seed = keypairs.generate_seed(algorithm=CryptoAlgorithm.ED25519)
        public_key, private_key = keypairs.derive_keypair(seed)
        address = keypairs.derive_classic_address(public_key)
        
        decoded = base58.b58decode(seed)
        seed_bytes = decoded[1:]
        secret_numbers = [f"{int.from_bytes(seed_bytes[i:i+2], 'big'):06d}" 
                         for i in range(0, 16, 2)]
        
        self.seed_type = SeedType.NUMBERS.value
        self.seed_numbers = secret_numbers
        self.seed_phrase = None
        self.passphrase = ""
        self.base_private = bytes.fromhex(private_key)
        self.base_seed_xrp = seed
        self._correct_address = address
        
        self.save()
        
        # Sync with core
        if CORE_AVAILABLE:
            self._sync_core_identity()
        
        return {
            "seed_type": SeedType.NUMBERS.value,
            "secret_numbers": secret_numbers,
            "secret_numbers_formatted": " ".join(secret_numbers),
            "first_address": address,
            "first_seed_xrp": seed,
        }
    
    # ============================================================
    # PUBLIC METHODS - IMPORT
    # ============================================================
    
    def detect_input_type(self, seed_input: Union[str, List[str]]) -> str:
        if isinstance(seed_input, list):
            return SeedType.NUMBERS.value
        
        if isinstance(seed_input, str):
            seed_input = seed_input.strip()
            
            # 1. CONTROLLA SE È UNA MNEMONICA BIP39 (24 parole) PRIMA DI TUTTO!
            words = seed_input.split()
            if len(words) >= 12 and len(words) <= 24:
                try:
                    if self.mnemo.check(seed_input):
                        return SeedType.BIP39.value
                except:
                    pass
            
            # 2. STELLAR SEED (inizia con S, 56 caratteri)
            if seed_input.startswith("S") and len(seed_input) >= 56:
                return SeedType.STELLAR_SEED.value
            
            # 3. PRIVATE KEY (64 caratteri esadecimali)
            if len(seed_input) == 64 and all(c in "0123456789abcdefABCDEF" for c in seed_input):
                return SeedType.PRIVATE_KEY.value
            
            # 4. XRP SEED (inizia con s, MA NON è una mnemonica)
            if seed_input.startswith("s") and len(seed_input) < 40:
                return SeedType.XRP_SEED.value
            
            # 5. NUMERI XAMAN
            numbers = self._clean_numbers_input(seed_input)
            if len(numbers) == 8 and all(p.isdigit() and len(p) == 6 for p in numbers):
                return SeedType.NUMBERS.value
            
            return SeedType.BIP39.value
        
        return SeedType.BIP39.value
    
    def import_wallet(self, seed_input: Union[str, List[str]], 
                     passphrase: str = "", 
                     input_type: str = "auto") -> Dict[str, Any]:
        
        if isinstance(seed_input, str):
            seed_input = seed_input.strip()
            if not seed_input:
                raise ValueError("❌ Input seed is empty")
        
        if input_type == "auto":
            input_type = self.detect_input_type(seed_input)
        
        if input_type == SeedType.BIP39.value:
            if self.crypto_type == "XLM":
                result = self._import_bip39_as_stellar(seed_input, passphrase)
            else:
                result = self._import_bip39(seed_input, passphrase)
        elif input_type == SeedType.NUMBERS.value:
            result = self._import_numbers(seed_input)
        elif input_type == SeedType.PRIVATE_KEY.value:
            result = self._import_private_key(seed_input)
        elif input_type == SeedType.XRP_SEED.value:
            result = self._import_xrp_seed(seed_input)
        elif input_type == SeedType.STELLAR_SEED.value:
            result = self._import_stellar_seed(seed_input)
        else:
            raise ValueError(f"Unsupported type: {input_type}")
        
        # Sync with core after import
        if CORE_AVAILABLE:
            self._sync_core_identity()
        
        return result
    
    def _import_bip39(self, seed_phrase: str, passphrase: str = "") -> Dict[str, Any]:
        if not self.mnemo.check(seed_phrase):
            raise ValueError("❌ Invalid seed phrase!")
        
        self.seed_type = SeedType.BIP39.value
        self.seed_phrase = seed_phrase
        self.seed_numbers = None
        self.passphrase = passphrase
        
        private_key_hex = self._bip39_to_private_key(seed_phrase, passphrase)
        public_key, address = self._private_key_to_keypair(private_key_hex)
        self.base_private = bytes.fromhex(private_key_hex)
        self._correct_address = address
        
        entropy = private_key_hex[:32]
        self.base_seed_xrp = keypairs.generate_seed(entropy=entropy)
        
        self.save()
        
        return {
            "seed_type": SeedType.BIP39.value,
            "seed_phrase": seed_phrase,
            "passphrase": passphrase,
            "word_count": len(seed_phrase.split()),
            "first_address": address,
            "first_private_key": private_key_hex,
            "first_public_key": public_key,
            "first_seed_xrp": self.base_seed_xrp,
        }
    
    def _import_bip39_as_stellar(self, seed_phrase: str, passphrase: str = "") -> Dict[str, Any]:
        if not STELLAR_AVAILABLE:
            raise ImportError(f"stellar-sdk not installed: {STELLAR_IMPORT_ERROR}")
        
        mnemonic = StellarMnemonic("english")
        if not mnemonic.check(seed_phrase):
            raise ValueError("❌ Invalid seed phrase!")
        
        self.seed_type = SeedType.BIP39.value
        self.seed_phrase = seed_phrase
        self.seed_numbers = None
        self.passphrase = passphrase
        self.crypto_type = "XLM"
        
        keypair = Keypair.from_mnemonic_phrase(seed_phrase)
        
        self.base_seed_stellar = keypair.secret
        self._correct_address = keypair.public_key
        self.base_private = None
        self.base_seed_xrp = None
        
        self.save()
        
        return {
            "seed_type": SeedType.BIP39.value,
            "seed_phrase": seed_phrase,
            "passphrase": passphrase,
            "word_count": len(seed_phrase.split()),
            "first_address": keypair.public_key,
            "first_private_key": keypair.secret,
            "first_public_key": keypair.public_key,
            "first_seed_stellar": keypair.secret,
        }
    
    def _import_private_key(self, private_key_hex: str) -> Dict[str, Any]:
        try:
            public_key, address = self._private_key_to_keypair(private_key_hex)
            
            self.seed_type = SeedType.PRIVATE_KEY.value
            self.seed_phrase = None
            self.seed_numbers = None
            self.passphrase = ""
            self.base_private = bytes.fromhex(private_key_hex)
            self._correct_address = address
            
            entropy = private_key_hex[:32]
            self.base_seed_xrp = keypairs.generate_seed(entropy=entropy)
            
            self.save()
            
            return {
                "seed_type": SeedType.PRIVATE_KEY.value,
                "first_address": address,
                "first_private_key": private_key_hex,
                "first_public_key": public_key,
                "first_seed_xrp": self.base_seed_xrp,
            }
        except Exception as e:
            raise ValueError(f"Invalid private key: {e}")
    
    def _import_xrp_seed(self, xrp_seed: str) -> Dict[str, Any]:
        try:
            # Pulisci l'input (rimuovi spazi, newline)
            xrp_seed = xrp_seed.strip()
            
            # Se contiene spazi, è una mnemonica, non un seed XRP
            if ' ' in xrp_seed:
                raise ValueError("XRP seed cannot contain spaces. Did you mean to import a mnemonic?")
            
            wallet = XRPWallet.from_seed(xrp_seed)
            
            self.seed_type = SeedType.XRP_SEED.value
            self.seed_phrase = None
            self.seed_numbers = None
            self.passphrase = ""
            self.base_private = bytes.fromhex(wallet.private_key)
            self.base_seed_xrp = xrp_seed
            self._correct_address = wallet.classic_address
            
            self.save()
            
            return {
                "seed_type": SeedType.XRP_SEED.value,
                "first_address": wallet.classic_address,
                "first_private_key": wallet.private_key,
                "first_public_key": wallet.public_key,
                "first_seed_xrp": xrp_seed,
            }
        except Exception as e:
            raise ValueError(f"Invalid XRP seed: {e}")
    
    def _import_stellar_seed(self, stellar_seed: str) -> Dict[str, Any]:
        if not STELLAR_AVAILABLE:
            raise ImportError(f"stellar-sdk not installed: {STELLAR_IMPORT_ERROR}")
        
        try:
            self._init_stellar()
            wallet = self.stellar_manager.from_seed(stellar_seed)
            
            self.seed_type = SeedType.STELLAR_SEED.value
            self.seed_phrase = None
            self.seed_numbers = None
            self.passphrase = ""
            self.base_seed_stellar = stellar_seed
            self._correct_address = wallet["public_key"]
            self.crypto_type = "XLM"
            
            self.save()
            
            return {
                "seed_type": SeedType.STELLAR_SEED.value,
                "first_address": wallet["public_key"],
                "first_private_key": wallet["secret_key"],
                "first_seed_stellar": stellar_seed,
            }
        except Exception as e:
            raise ValueError(f"Invalid Stellar seed: {e}")
    
    def _import_numbers(self, numbers: Union[str, List[str]]) -> Dict[str, Any]:
        """Import wallet from Xaman numbers with validation"""
        if isinstance(numbers, str):
            numbers = self._clean_numbers_input(numbers)
        
        if len(numbers) != 8:
            raise ValueError(f"❌ Need 8 numbers, got {len(numbers)}")
        
        for num in numbers:
            if not re.match(r'^[0-9]{6}$', str(num).strip()):
                raise ValueError(f"❌ '{num}' invalid (need 6 digits)")
        
        try:
            xrp_seed = self.bridge.numbers_to_seed(numbers)
            address = self.bridge.numbers_to_address(numbers)
            wallet = XRPWallet.from_seed(xrp_seed)
            
            self.seed_type = SeedType.NUMBERS.value
            self.seed_numbers = numbers
            self.seed_phrase = None
            self.passphrase = ""
            self.base_private = bytes.fromhex(wallet.private_key)
            self.base_seed_xrp = xrp_seed
            self._correct_address = address
            
            self.save()
            
            return {
                "seed_type": SeedType.NUMBERS.value,
                "secret_numbers": numbers,
                "secret_numbers_formatted": " ".join(numbers),
                "first_address": address,
                "first_private_key": wallet.private_key,
                "first_public_key": wallet.public_key,
                "first_seed_xrp": xrp_seed,
            }
        except Exception as e:
            raise ValueError(f"Invalid numbers: {e}")
    
    def validate_seed(self, seed_input: Union[str, List[str]]) -> Dict[str, Any]:
        """Validate a seed and return information"""
        input_type = self.detect_input_type(seed_input)
        result = {
            "valid": False,
            "type": input_type,
            "details": ""
        }
        
        try:
            if input_type == SeedType.BIP39.value:
                if isinstance(seed_input, str):
                    result["valid"] = self.mnemo.check(seed_input)
                    if result["valid"]:
                        result["word_count"] = len(seed_input.split())
                        result["details"] = f"Valid BIP39 mnemonic with {result['word_count']} words"
                    else:
                        result["details"] = "Invalid BIP39 mnemonic"
            
            elif input_type == SeedType.NUMBERS.value:
                numbers = seed_input if isinstance(seed_input, list) else self._clean_numbers_input(seed_input)
                if len(numbers) == 8 and all(n.isdigit() and len(n) == 6 for n in numbers):
                    result["valid"] = True
                    result["details"] = f"Valid Xaman secret numbers: {len(numbers)} numbers"
                else:
                    result["details"] = "Invalid numbers format"
            
            elif input_type == SeedType.XRP_SEED.value:
                try:
                    XRPWallet.from_seed(seed_input)
                    result["valid"] = True
                    result["details"] = "Valid XRP seed"
                except:
                    result["details"] = "Invalid XRP seed"
            
            elif input_type == SeedType.STELLAR_SEED.value:
                try:
                    if STELLAR_AVAILABLE:
                        Keypair.from_secret(seed_input)
                        result["valid"] = True
                        result["details"] = "Valid Stellar seed"
                    else:
                        result["details"] = "stellar-sdk not available"
                except:
                    result["details"] = "Invalid Stellar seed"
            
            elif input_type == SeedType.PRIVATE_KEY.value:
                try:
                    bytes.fromhex(seed_input)
                    result["valid"] = True
                    result["details"] = "Valid private key (hex)"
                except:
                    result["details"] = "Invalid private key"
        
        except Exception as e:
            result["details"] = f"Error: {str(e)}"
        
        return result
    
    # ============================================================
    # PUBLIC METHODS - GET WALLET
    # ============================================================
    
    def get_wallet(self, keyword: str = "default", index: int = 0) -> Union[XRPWallet, Dict]:
        if self.crypto_type == "XLM":
            return self._get_stellar_wallet()
        return self._get_xrp_wallet(keyword, index)
    
    def _get_xrp_wallet(self, keyword: str = "default", index: int = 0) -> XRPWallet:
        if self.seed_type in [SeedType.NUMBERS.value, SeedType.XRP_SEED.value]:
            if self.base_seed_xrp is not None:
                return XRPWallet.from_seed(self.base_seed_xrp)
        
        if self.base_private is None:
            raise ValueError("❌ No wallet loaded!")
        
        if keyword == "default" and index == 0:
            private_key_hex = self.base_private.hex()
        else:
            private_key_bytes = self._derive_private_key(keyword, index)
            private_key_hex = private_key_bytes.hex()
        
        public_key, _ = self._private_key_to_keypair(private_key_hex)
        return XRPWallet(
            public_key=public_key,
            private_key=private_key_hex,
            algorithm=CryptoAlgorithm.SECP256K1
        )
    
    def _get_stellar_wallet(self, keyword: str = "default", index: int = 0) -> Dict[str, str]:
        if self.base_seed_stellar:
            self._init_stellar()
            return self.stellar_manager.from_seed(self.base_seed_stellar)
        
        if self.seed_phrase and self.crypto_type == "XLM":
            from stellar_sdk import Keypair
            
            if keyword == "default" and index == 0:
                keypair = Keypair.from_mnemonic_phrase(self.seed_phrase)
            else:
                passphrase = f"{keyword}:{index}"
                keypair = Keypair.from_mnemonic_phrase(self.seed_phrase, passphrase)
            
            self.base_seed_stellar = keypair.secret
            self._correct_address = keypair.public_key
            self.save()
            return {
                "public_key": keypair.public_key,
                "secret_key": keypair.secret,
                "address": keypair.public_key
            }
        
        raise ValueError("❌ No Stellar wallet loaded!")
    
    def get_address(self, keyword: str = "default", index: int = 0) -> str:
        if self._correct_address and keyword == "default" and index == 0:
            return self._correct_address
        
        wallet = self.get_wallet(keyword, index)
        if self.crypto_type == "XLM":
            return wallet.get("public_key", "")
        return wallet.classic_address
    
    def get_wallet_info(self, keyword: str = "default", index: int = 0) -> WalletInfo:
        wallet = self.get_wallet(keyword, index)
        
        if self.crypto_type == "XLM":
            return WalletInfo(
                keyword=keyword,
                index=index,
                address=wallet.get("public_key", ""),
                private_key=wallet.get("secret_key", ""),
                public_key=wallet.get("public_key", ""),
                seed_xrp=self.base_seed_stellar or "",
                created_at=datetime.now().isoformat()
            )
        
        return WalletInfo(
            keyword=keyword,
            index=index,
            address=wallet.classic_address,
            private_key=wallet.private_key,
            public_key=wallet.public_key,
            seed_xrp=self._private_key_to_seed(wallet.private_key),
            created_at=datetime.now().isoformat()
        )
    
    # ============================================================
    # PUBLIC METHODS - DERIVATION
    # ============================================================
    
    def derive_addresses(self, keyword: str = "default", count: int = 5) -> List[WalletInfo]:
        results = []
        
        if self.crypto_type == "XLM":
            for i in range(count):
                info = self.get_wallet_info(keyword, i)
                results.append(info)
                self._derived_wallets[f"{keyword}:{i}"] = info
            self.save()
            return results
        
        for i in range(count):
            info = self.get_wallet_info(keyword, i)
            results.append(info)
            self._derived_wallets[f"{keyword}:{i}"] = info
        self.save()
        return results
    
    def batch_derive_addresses(self, keywords: List[str], count: int = 5) -> Dict[str, List[WalletInfo]]:
        results = {}
        for keyword in keywords:
            results[keyword] = self.derive_addresses(keyword, count)
        return results
    
    def get_addresses_by_range(self, start: int = 0, end: int = 10, keyword: str = "default") -> List[str]:
        addresses = []
        for i in range(start, end):
            try:
                addr = self.get_address(keyword, i)
                addresses.append(addr)
            except:
                addresses.append(None)
        return addresses
    
    def list_derived(self) -> List[WalletInfo]:
        return list(self._derived_wallets.values())
    
    def get_derived_by_keyword(self, keyword: str) -> List[WalletInfo]:
        return [w for w in self._derived_wallets.values() if w.keyword == keyword]
    
    # ============================================================
    # PUBLIC METHODS - BALANCE AND TRANSACTIONS
    # ============================================================
    
    def get_balance(self, force_refresh: bool = False) -> float:
        address = self.get_address()
        
        if not force_refresh and address in self._balance_cache:
            balance, timestamp = self._balance_cache[address]
            if time.time() - timestamp < self._cache_ttl:
                return balance
        
        if self.crypto_type == "XLM":
            self._init_stellar()
            balance = self.stellar_manager.get_balance(address)
        else:
            balance = self._get_xrp_balance(address)
        
        self._balance_cache[address] = (balance, time.time())
        return balance
    
    def get_account_info(self) -> Dict:
        address = self.get_address()
        
        if self.crypto_type == "XLM":
            self._init_stellar()
            return self.stellar_manager.get_account_info(address)
        
        try:
            from xrpl.account import get_account_info
            from xrpl.clients import JsonRpcClient
            
            if self.network == "mainnet":
                client = JsonRpcClient("https://s1.ripple.com:51234/")
            else:
                client = JsonRpcClient("https://s.altnet.rippletest.net:51234/")
            
            info = get_account_info(address, client)
            return {
                "address": address,
                "balance": self.get_balance(),
                "sequence": info.get('Sequence', 0),
                "flags": info.get('Flags', 0)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def fund_testnet(self) -> bool:
        if self.crypto_type != "XLM":
            logger.error("Friendbot works only for XLM")
            return False
        
        address = self.get_address()
        self._init_stellar()
        return self.stellar_manager.fund_testnet(address)
    
    def send_payment(self, to_address: str, amount: float, 
                    memo_text: str = "", memo_id: int = None) -> Dict:
        if self.crypto_type == "XLM":
            self._init_stellar()
            from_secret = self.base_seed_stellar
            if not from_secret:
                raise ValueError("❌ No Stellar seed available")
            return self.stellar_manager.send_payment(
                from_secret, to_address, amount, memo_text, memo_id
            )
        
        raise NotImplementedError("Use CLI send method for XRP")
    

    # ============================================================
    # TRUSTLINE - METHODS FOR XRP AND XLM
    # ============================================================

    def get_trustlines(self, force_refresh: bool = False) -> List[Dict]:
        """List all trustlines of the wallet"""
        if self.crypto_type == "XRP":
            return self._get_xrp_trustlines(force_refresh)
        elif self.crypto_type == "XLM":
            return self._get_xlm_trustlines(force_refresh)
        return []

    def _get_xrp_trustlines(self, force_refresh: bool = False) -> List[Dict]:
        from xrpl.models.requests import AccountLines
        from xrpl.clients import JsonRpcClient
        
        urls = {
            "mainnet": "https://s1.ripple.com:51234/",
            "testnet": "https://s.altnet.rippletest.net:51234/",
            "devnet": "https://s.devnet.rippletest.net:51234/"
        }
        client = JsonRpcClient(urls.get(self.network, urls["testnet"]))
        
        address = self.get_address()
        request = AccountLines(account=address, limit=200)
        response = client.request(request)
        
        # 🔥 LOAD TOKEN MAP FROM LOCAL FILE
        token_names = self._load_token_names()
        
        trustlines = []
        for line in response.result.get("lines", []):
            currency_hex = line.get("currency", "")
            
            # 🔥 SEARCH FOR TOKEN NAME IN LOCAL MAP
            currency = token_names.get(currency_hex, currency_hex)
            
            # 🔥 IF NOT FOUND, TRY TO DECODE
            if currency == currency_hex:
                currency = self._decode_currency_hex(currency_hex)
            
            issuer = line.get("account", "")
            balance = float(line.get("balance", 0))
            limit = float(line.get("limit", 0))
            
            is_active = (line.get("authorized", False) and line.get("peer_authorized", False)) or (balance > 0)
            
            trustlines.append({
                "currency": currency,
                "currency_hex": currency_hex,
                "issuer": issuer,
                "balance": balance,
                "limit": limit,
                "limit_peer": float(line.get("limit_peer", 0)),
                "authorized": line.get("authorized", False),
                "peer_authorized": line.get("peer_authorized", False),
                "is_active": is_active,
                "network": "XRPL",
                "address": address,
            })
        return trustlines

    def _load_token_names(self) -> Dict[str, str]:
        """Load token map from local database"""
        token_file = DATA_DIR / "token_names.json"
        if token_file.exists():
            try:
                with open(token_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_token_name(self, currency_hex: str, token_name: str):
        """Save token name to local database"""
        token_file = DATA_DIR / "token_names.json"
        tokens = self._load_token_names()
        tokens[currency_hex] = token_name
        with open(token_file, 'w') as f:
            json.dump(tokens, f, indent=2)

    def _get_xlm_trustlines(self, force_refresh: bool = False) -> List[Dict]:
        """Get XLM (Stellar) trustlines from ledger"""
        self._init_stellar()
        if not self.stellar_manager:
            return []
        
        address = self.get_address()
        account = self.stellar_manager.server.accounts().account_id(address).call()
        
        trustlines = []
        for balance in account.get('balances', []):
            if balance['asset_type'] != 'native':
                trustlines.append({
                    "asset_code": balance.get('asset_code', ''),
                    "asset_issuer": balance.get('asset_issuer', ''),
                    "balance": float(balance.get('balance', 0)),
                    "limit": float(balance.get('limit', 0)),
                    "authorized": True,
                    "is_active": True,
                    "network": "Stellar",
                    "address": address,
                })
        return trustlines

    def set_trustline(self, asset_code: str, issuer: str, limit: float = None) -> Dict:
        """Create a new trustline on the ledger"""
        if self.crypto_type == "XRP":
            return self._set_xrp_trustline(asset_code, issuer, limit)
        elif self.crypto_type == "XLM":
            return self._set_xlm_trustline(asset_code, issuer, limit)
        return {"success": False, "error": "Crypto not supported"}

    def _set_xrp_trustline(self, asset_code: str, issuer: str, limit: float = None) -> Dict:
        from xrpl.models.transactions import TrustSet
        from xrpl.transaction import autofill, sign, submit_and_wait
        from xrpl.clients import JsonRpcClient
        
        try:
            urls = {
                "mainnet": "https://s1.ripple.com:51234/",
                "testnet": "https://s.altnet.rippletest.net:51234/",
                "devnet": "https://s.devnet.rippletest.net:51234/"
            }
            client = JsonRpcClient(urls.get(self.network, urls["testnet"]))
            
            wallet = self.get_wallet("default", 0)
            
            if len(asset_code) == 3:
                currency = asset_code
            else:
                currency_hex = asset_code.encode('utf-8').hex().upper()
                currency = currency_hex.ljust(40, '0')
            
            if limit is None:
                limit_value = "1000000000"
            elif limit == 0:
                limit_value = "0"
            else:
                limit_value = str(limit)
            
            trust_set = TrustSet(
                account=wallet.classic_address,
                limit_amount={
                    "currency": currency,
                    "issuer": issuer,
                    "value": limit_value
                },
                flags=0x00020000 if limit != 0 else 0
            )
            
            print(f"📤 Creating XRP trustline for {asset_code}")
            print(f"   Wallet: {wallet.classic_address}")
            print(f"   Issuer: {issuer}")
            print(f"   Currency: {currency}")
            print(f"   Limit: {limit_value}")
            print(f"   Network: {self.network.upper()}")
            
            tx = autofill(trust_set, client)
            signed_tx = sign(tx, wallet)
            response = submit_and_wait(signed_tx, client)
            
            tx_hash = response.result.get("hash", "unknown")
            
            return {
                "success": True,
                "hash": tx_hash,
                "asset": asset_code,
                "issuer": issuer,
                "limit": limit_value,
                "network": "XRPL",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _set_xlm_trustline(self, asset_code: str, issuer: str, limit: float = None) -> Dict:
        """Create trustline on Stellar (ChangeTrust)"""
        self._init_stellar()
        if not self.stellar_manager:
            return {"success": False, "error": "Stellar manager not initialized"}
        
        try:
            from stellar_sdk import Keypair, TransactionBuilder, Network, Asset
            from stellar_sdk.exceptions import BadRequestError
            
            keypair = Keypair.from_secret(self.base_seed_stellar)
            source_account = self.stellar_manager.server.load_account(keypair.public_key)
            
            asset = Asset(asset_code, issuer)
            limit_value = str(limit) if limit else "922337203685.4775807"
            
            builder = TransactionBuilder(
                source_account=source_account,
                network_passphrase=self.stellar_manager.network_passphrase,
                base_fee=100
            )
            builder.set_timeout(300)
            
            builder.append_change_trust_op(
                asset=asset,
                limit=limit_value
            )
            
            print(f"📤 Creating Stellar trustline for {asset_code}...")
            transaction = builder.build()
            transaction.sign(keypair)
            response = self.stellar_manager.server.submit_transaction(transaction)
            
            tx_hash = response.get("hash", "unknown")
            
            return {
                "success": True,
                "hash": tx_hash,
                "asset": asset_code,
                "issuer": issuer,
                "limit": limit_value,
                "network": "Stellar",
            }
        except BadRequestError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_trustline(self, asset_code: str, issuer: str) -> Dict:
        """Remove a trustline (set limit = 0)"""
        result = self.set_trustline(asset_code, issuer, 0)
        
        # Delete from core
        if result.get("success"):
            self.delete_trustline_from_core(asset_code, issuer)
        
        return result

    def get_trustline_balance(self, asset_code: str, issuer: str = None) -> Dict:
        """Get balance of a specific trustline"""
        trustlines = self.get_trustlines(force_refresh=True)
        for tl in trustlines:
            if self.crypto_type == "XRP":
                if tl.get("currency") == asset_code and (issuer is None or tl.get("issuer") == issuer):
                    return {
                        "asset": asset_code,
                        "issuer": tl.get("issuer"),
                        "balance": tl.get("balance", 0),
                        "limit": tl.get("limit", 0),
                        "is_active": tl.get("is_active", False),
                    }
            else:
                if tl.get("asset_code") == asset_code and (issuer is None or tl.get("asset_issuer") == issuer):
                    return {
                        "asset": asset_code,
                        "issuer": tl.get("asset_issuer"),
                        "balance": tl.get("balance", 0),
                        "limit": tl.get("limit", 0),
                        "is_active": tl.get("is_active", False),
                    }
        return {"error": f"Trustline {asset_code} not found"}

    def send_with_trustline_check(self, to_address: str, amount: float, 
                                  asset_code: str = None, issuer: str = None,
                                  memo_text: str = "") -> Dict:
        """Send with trustline verification"""
        if asset_code and issuer:
            try:
                from xrpl.models.requests import AccountLines
                from xrpl.clients import JsonRpcClient
                
                urls = {
                    "mainnet": "https://s1.ripple.com:51234/",
                    "testnet": "https://s.altnet.rippletest.net:51234/",
                    "devnet": "https://s.devnet.rippletest.net:51234/"
                }
                client = JsonRpcClient(urls.get(self.network, urls["testnet"]))
                
                request = AccountLines(account=to_address, limit=200)
                response = client.request(request)
                
                has_trustline = False
                for line in response.result.get("lines", []):
                    if line.get("currency") == asset_code and line.get("account") == issuer:
                        if line.get("authorized", False) and line.get("peer_authorized", False):
                            has_trustline = True
                            break
                
                if not has_trustline:
                    print(f"⚠️  Recipient does not have trustline for {asset_code}")
                    print("   Transaction may fail.")
                    confirm = input("   Continue anyway? (y/n): ")
                    if confirm.lower() != 'y':
                        return {"success": False, "error": "Transaction cancelled"}
            except Exception as e:
                print(f"⚠️  Cannot verify trustline: {e}")
        
        if self.crypto_type == "XRP":
            return self.send_payment(to_address, amount, memo_text)
        else:
            return self.send_payment(to_address, amount, memo_text)

    def _decode_currency_hex(self, currency_hex: str) -> str:
        """Decode XRP currency hex to readable code"""
        if len(currency_hex) == 3:
            return currency_hex
        
        try:
            bytes_data = bytes.fromhex(currency_hex)
            while bytes_data and bytes_data[-1] == 0:
                bytes_data = bytes_data[:-1]
            result = bytes_data.decode('utf-8', errors='ignore').strip()
            if result and all(32 <= ord(c) <= 126 for c in result):
                return result
        except:
            pass
        
        return currency_hex

    # ============================================================
    # PUBLIC METHODS - EXPORT/IMPORT
    # ============================================================
    
    def export_wallet(self, format: str = "json", include_private: bool = False) -> Union[str, Dict]:
        if not self.is_loaded():
            raise ValueError("No wallet loaded")
        
        data = {
            "type": self.crypto_type,
            "network": self.network,
            "seed_type": self.seed_type,
            "address": self._correct_address,
            "created_at": datetime.now().isoformat(),
            "version": VERSION
        }
        
        if include_private:
            if self.crypto_type == "XLM" and self.base_seed_stellar:
                data["seed"] = self.base_seed_stellar
            elif self.base_seed_xrp:
                data["seed"] = self.base_seed_xrp
            elif self.base_private:
                data["private_key"] = self.base_private.hex()
        
        if self.seed_type == SeedType.BIP39.value:
            data["mnemonic"] = self.seed_phrase
            data["passphrase"] = self.passphrase
        
        elif self.seed_type == SeedType.NUMBERS.value:
            data["numbers"] = self.seed_numbers
            data["numbers_formatted"] = " ".join(self.seed_numbers)
        
        if format == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)
        elif format == "dict":
            return data
        else:
            raise ValueError(f"Format not supported: {format}")
    
    def import_wallet_from_file(self, filepath: str) -> Dict[str, Any]:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if "type" in data:
            self.crypto_type = data["type"]
        
        if "network" in data:
            self.network = data["network"]
        
        if "mnemonic" in data:
            return self.import_wallet(
                data["mnemonic"], 
                passphrase=data.get("passphrase", ""),
                input_type=SeedType.BIP39.value
            )
        elif "numbers" in data:
            return self.import_wallet(
                data["numbers"], 
                input_type=SeedType.NUMBERS.value
            )
        elif "seed" in data:
            return self.import_wallet(data["seed"], input_type="auto")
        elif "private_key" in data:
            return self.import_wallet(
                data["private_key"], 
                input_type=SeedType.PRIVATE_KEY.value
            )
        else:
            raise ValueError("Unrecognized file format")
    
    # ============================================================
    # PUBLIC METHODS - STATUS AND PERSISTENCE
    # ============================================================
    
    def is_loaded(self) -> bool:
        return (self.base_private is not None or 
                self.base_seed_xrp is not None or 
                self.base_seed_stellar is not None)
    
    def get_seed_info(self) -> Dict[str, Any]:
        if not self.is_loaded():
            return {"loaded": False}
        
        info = {
            "loaded": True,
            "seed_type": self.seed_type,
            "crypto_type": self.crypto_type,
            "network": self.network,
            "address": self._correct_address,
            "has_balance": False,
            "has_core": CORE_AVAILABLE and self._core_initialized,
            "core_identity": self._core_identity_id
        }
        
        # ============================================================
        # 🔥 AGGIUNGI PRIVATE KEY OVUNQUE SIA DISPONIBILE
        # ============================================================
        if self.base_private:
            info["private_key"] = self.base_private.hex()
        elif self.base_seed_xrp:
            # Deriva dal seed XRP
            try:
                from xrpl.core import keypairs
                _, private_key = keypairs.derive_keypair(self.base_seed_xrp)
                info["private_key"] = private_key
            except:
                pass
        elif self.base_seed_stellar:
            # Per Stellar, il seed è la private key
            info["private_key"] = self.base_seed_stellar
        
        try:
            balance = self.get_balance()
            info["balance"] = balance
            info["has_balance"] = True
        except:
            pass
        
        if self.seed_type == SeedType.BIP39.value:
            info.update({
                "seed_phrase": self.seed_phrase,
                "word_count": len(self.seed_phrase.split()) if self.seed_phrase else 0,
                "passphrase": self.passphrase,
                "seed_xrp": self.base_seed_xrp,
                "seed_stellar": self.base_seed_stellar,
            })
        
        elif self.seed_type == SeedType.NUMBERS.value:
            info.update({
                "secret_numbers": self.seed_numbers,
                "formatted": self._format_numbers(self.seed_numbers) if self.seed_numbers else "",
                "seed_xrp": self.base_seed_xrp,
            })
        
        elif self.seed_type == SeedType.PRIVATE_KEY.value:
            info.update({
                "seed_xrp": self.base_seed_xrp,
            })
        
        elif self.seed_type == SeedType.XRP_SEED.value:
            info.update({
                "seed_xrp": self.base_seed_xrp,
            })
        
        elif self.seed_type == SeedType.STELLAR_SEED.value:
            info.update({
                "seed_stellar": self.base_seed_stellar,
            })
        
        # Add core trustlines count
        if CORE_AVAILABLE and self._core_initialized:
            try:
                core_tls = self.get_core_trustlines()
                info["core_trustlines"] = len(core_tls)
            except:
                pass
        
        return info
    
    def reset(self) -> None:
        self.seed_type = None
        self.seed_phrase = None
        self.seed_numbers = None
        self.passphrase = ""
        self.base_private = None
        self.base_seed_xrp = None
        self.base_seed_stellar = None
        self._correct_address = None
        self._derived_wallets = {}
        self._balance_cache = {}
        self.stellar_manager = None
        
        # Reset core
        self._core_identity_id = None
        
        if self.data_file.exists():
            self.data_file.unlink()
    
    def save(self) -> None:
        if not self.is_loaded():
            return
        
        current_address = self._correct_address
        if not current_address:
            try:
                current_address = self.get_address("default", 0)
            except:
                current_address = None
        
        data = {
            "seed_type": self.seed_type,
            "seed_phrase": self.seed_phrase,
            "seed_numbers": self.seed_numbers,
            "passphrase": self.passphrase,
            "base_private": self.base_private.hex() if self.base_private else None,
            "base_seed_xrp": self.base_seed_xrp,
            "base_seed_stellar": self.base_seed_stellar,
            "current_address": current_address,
            "crypto_type": self.crypto_type,
            "network": self.network,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "derived_wallets": [info.to_dict() for info in self._derived_wallets.values()]
        }
        
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"✅ Wallet saved to {self.data_file}")
    
    def load(self) -> bool:
        if not self.data_file.exists():
            return False
        
        try:
            with open(self.data_file) as f:
                data = json.load(f)
            
            self.seed_type = data.get("seed_type")
            self.seed_phrase = data.get("seed_phrase")
            self.seed_numbers = data.get("seed_numbers")
            self.passphrase = data.get("passphrase", "")
            self.base_seed_xrp = data.get("base_seed_xrp")
            self.base_seed_stellar = data.get("base_seed_stellar")
            self._correct_address = data.get("current_address")
            self.crypto_type = data.get("crypto_type", "XRP")
            self.network = data.get("network", "testnet")
            
            if self.crypto_type == "XLM" and STELLAR_AVAILABLE:
                self._init_stellar()
            
            base_private_hex = data.get("base_private")
            if base_private_hex:
                self.base_private = bytes.fromhex(base_private_hex)
            elif self.seed_type == SeedType.BIP39.value and self.seed_phrase:
                if self.crypto_type == "XLM":
                    from stellar_sdk import Keypair
                    keypair = Keypair.from_mnemonic_phrase(self.seed_phrase)
                    self.base_seed_stellar = keypair.secret
                    self._correct_address = keypair.public_key
                else:
                    private_key_hex = self._bip39_to_private_key(self.seed_phrase, self.passphrase)
                    self.base_private = bytes.fromhex(private_key_hex)
                    if not self._correct_address:
                        _, addr = self._private_key_to_keypair(private_key_hex)
                        self._correct_address = addr
                    if not self.base_seed_xrp:
                        entropy = private_key_hex[:32]
                        self.base_seed_xrp = keypairs.generate_seed(entropy=entropy)
            
            elif self.seed_type == SeedType.NUMBERS.value and self.seed_numbers:
                try:
                    xrp_seed = self.bridge.numbers_to_seed(self.seed_numbers)
                    self.base_seed_xrp = xrp_seed
                    wallet = XRPWallet.from_seed(xrp_seed)
                    self.base_private = bytes.fromhex(wallet.private_key)
                    if not self._correct_address:
                        self._correct_address = wallet.classic_address
                except Exception as e:
                    logger.error(f"Error loading numbers: {e}")
                    xrp_seed = self._numbers_to_seed_fallback(self.seed_numbers)
                    self.base_seed_xrp = xrp_seed
                    public_key, private_key = keypairs.derive_keypair(xrp_seed)
                    self.base_private = bytes.fromhex(private_key)
                    if not self._correct_address:
                        self._correct_address = keypairs.derive_classic_address(public_key)
            
            for wallet_data in data.get("derived_wallets", []):
                try:
                    info = WalletInfo.from_dict(wallet_data)
                    self._derived_wallets[f"{info.keyword}:{info.index}"] = info
                except Exception as e:
                    logger.warning(f"Error loading derived wallet: {e}")
            
            logger.info(f"✅ Wallet loaded from {self.data_file}")
            
            # Sync with core after load
            if CORE_AVAILABLE:
                self._init_core()
                self._sync_core_identity()
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading wallet: {e}")
            return False


# ============================================================
# UTILITY FUNCTION
# ============================================================

def create_manager(data_file: str = "wallet_data.json", 
                  crypto_type: str = "XRP", 
                  network: str = "testnet") -> HybridXRPManager:
    """Factory function to create a configured manager"""
    manager = HybridXRPManager(data_file)
    manager.set_crypto(crypto_type)
    manager.set_network(network)
    return manager


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    # Quick test
    manager = HybridXRPManager("test_wallet.json")
    
    print("=" * 60)
    print("🧪 WALLET MANAGER TEST")
    print("=" * 60)
    
    print("\n📤 Creating XRP wallet...")
    wallet = manager.create_new_wallet_bip39()
    print(f"✅ Address: {wallet['first_address']}")
    print(f"✅ Seed XRP: {wallet['first_seed_xrp']}")
    
    balance = manager.get_balance()
    print(f"💰 Balance: {balance} XRP")
    
    print("\n📤 Deriving addresses...")
    addresses = manager.derive_addresses("test", 3)
    for addr in addresses:
        print(f"  - {addr.address}")
    
    # Test core integration
    if CORE_AVAILABLE:
        print("\n🔗 Testing core integration...")
        identity = manager.get_core_identity()
        print(f"  Core Identity: {identity}")
        
        trustlines = manager.sync_trustlines_with_core()
        print(f"  Trustlines synced: {len(trustlines)}")
        
        core_tls = manager.get_core_trustlines()
        print(f"  Trustlines in core: {len(core_tls)}")
    
    print("\n✅ Test complete!")