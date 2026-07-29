#!/usr/bin/env python3
"""
gateway_cache.py - Cache per gateway e wallet
"""

import sqlite3
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, List, Any


class GatewayCache:
    """Cache per gateway e wallet"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
    def _get_conn(self):
        """Ottiene una connessione per il thread corrente"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 🔥 AGGIUNTA COLONNA gateway_name
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gateways (
                gateway_id TEXT PRIMARY KEY,
                wallet_aspect TEXT,
                services TEXT,
                fee TEXT,
                fee_asset TEXT,
                reputation INTEGER,
                latency INTEGER,
                supported_assets TEXT,
                last_seen INTEGER,
                version INTEGER DEFAULT 1,
                gateway_name TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                wallet_aspect TEXT PRIMARY KEY,
                ledger_address TEXT,
                network TEXT,
                assets TEXT,
                gateway_id TEXT,
                online BOOLEAN DEFAULT 1,
                first_seen INTEGER,
                last_seen INTEGER,
                version INTEGER DEFAULT 1
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS offline_tx (
                tx_id TEXT PRIMARY KEY,
                tx_data TEXT,
                created INTEGER,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 5,
                last_attempt INTEGER,
                status TEXT DEFAULT 'pending'
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_trustlines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_wallet TEXT,
                to_wallet TEXT,
                asset_network TEXT,
                asset_code TEXT,
                asset_issuer TEXT,
                limit_amount TEXT,
                created INTEGER,
                status TEXT DEFAULT 'pending'
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gateways_last_seen ON gateways(last_seen)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_last_seen ON wallets(last_seen)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_offline_status ON offline_tx(status)")
        
        conn.commit()
    
    def add_gateway(self, gateway: Dict) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO gateways (
                    gateway_id, wallet_aspect, services, fee, fee_asset,
                    reputation, latency, supported_assets, last_seen, version, gateway_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                gateway.get("gateway_id"),
                gateway.get("wallet_aspect"),
                json.dumps(gateway.get("services", [])),
                gateway.get("fee", "0.00001"),
                gateway.get("fee_asset", "XRP"),
                gateway.get("reputation", 50),
                gateway.get("latency", 0),
                json.dumps(gateway.get("supported_assets", [])),
                int(time.time()),
                gateway.get("version", 1),
                gateway.get("gateway_name", "Sconosciuto")  # 🔥 NUOVO!
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ Errore aggiunta gateway: {e}")
            return False
    
    def get_gateway(self, gateway_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT gateway_id, wallet_aspect, services, fee, fee_asset, reputation, latency, supported_assets, last_seen, gateway_name FROM gateways WHERE gateway_id = ?",
            (gateway_id,)
        )
        
        row = cursor.fetchone()
        
        if row:
            return {
                "gateway_id": row[0],
                "wallet_aspect": row[1],
                "services": json.loads(row[2]) if row[2] else [],
                "fee": row[3],
                "fee_asset": row[4],
                "reputation": row[5],
                "latency": row[6],
                "supported_assets": json.loads(row[7]) if row[7] else [],
                "last_seen": row[8],
                "gateway_name": row[9]  # 🔥 NUOVO!
            }
        return None
    
    def get_all_gateways(self, limit: int = 100) -> List[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT gateway_id, wallet_aspect, services, fee, fee_asset, reputation, latency, supported_assets, last_seen, gateway_name FROM gateways ORDER BY reputation DESC, latency ASC LIMIT ?",
            (limit,)
        )
        
        gateways = []
        for row in cursor.fetchall():
            gateways.append({
                "gateway_id": row[0],
                "wallet_aspect": row[1],
                "services": json.loads(row[2]) if row[2] else [],
                "fee": row[3],
                "fee_asset": row[4],
                "reputation": row[5],
                "latency": row[6],
                "supported_assets": json.loads(row[7]) if row[7] else [],
                "last_seen": row[8],
                "gateway_name": row[9]  # 🔥 NUOVO!
            })
        
        return gateways
    
    def update_gateway_ping(self, gateway_id: str, latency: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE gateways SET latency = ?, last_seen = ? WHERE gateway_id = ?",
            (latency, int(time.time()), gateway_id)
        )
        
        conn.commit()
    
    def add_wallet(self, wallet: Dict) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO wallets (
                    wallet_aspect, ledger_address, network, assets,
                    gateway_id, online, first_seen, last_seen, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                wallet.get("wallet_aspect"),
                wallet.get("ledger_address"),
                wallet.get("network", "XRPL"),
                json.dumps(wallet.get("assets", [])),
                wallet.get("gateway_id"),
                wallet.get("online", True),
                wallet.get("first_seen", int(time.time())),
                int(time.time()),
                wallet.get("version", 1)
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ Errore aggiunta wallet: {e}")
            return False
    
    def get_wallet(self, wallet_aspect: str) -> Optional[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT wallet_aspect, ledger_address, network, assets, gateway_id, online, first_seen, last_seen FROM wallets WHERE wallet_aspect = ?",
            (wallet_aspect,)
        )
        
        row = cursor.fetchone()
        
        if row:
            return {
                "wallet_aspect": row[0],
                "ledger_address": row[1],
                "network": row[2],
                "assets": json.loads(row[3]) if row[3] else [],
                "gateway_id": row[4],
                "online": bool(row[5]),
                "first_seen": row[6],
                "last_seen": row[7]
            }
        return None
    
    def get_all_wallets(self, limit: int = 100) -> List[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT wallet_aspect, ledger_address, network, assets, gateway_id, online, first_seen, last_seen FROM wallets ORDER BY last_seen DESC LIMIT ?",
            (limit,)
        )
        
        wallets = []
        for row in cursor.fetchall():
            wallets.append({
                "wallet_aspect": row[0],
                "ledger_address": row[1],
                "network": row[2],
                "assets": json.loads(row[3]) if row[3] else [],
                "gateway_id": row[4],
                "online": bool(row[5]),
                "first_seen": row[6],
                "last_seen": row[7]
            })
        
        return wallets
    
    def add_offline_tx(self, tx_id: str, tx_data: Dict) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO offline_tx (
                    tx_id, tx_data, created, status
                ) VALUES (?, ?, ?, ?)
            """, (
                tx_id,
                json.dumps(tx_data),
                int(time.time()),
                "pending"
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ Errore aggiunta offline tx: {e}")
            return False
    
    def get_pending_offline_tx(self, limit: int = 10) -> List[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT tx_id, tx_data, created, retry_count, max_retries, last_attempt FROM offline_tx WHERE status = 'pending' AND retry_count < max_retries ORDER BY created ASC LIMIT ?",
            (limit,)
        )
        
        txs = []
        for row in cursor.fetchall():
            txs.append({
                "tx_id": row[0],
                "tx_data": json.loads(row[1]) if row[1] else {},
                "created": row[2],
                "retry_count": row[3],
                "max_retries": row[4],
                "last_attempt": row[5]
            })
        
        return txs
    
    def update_offline_tx_status(self, tx_id: str, status: str, retry_count: int = None):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        if retry_count is not None:
            cursor.execute(
                "UPDATE offline_tx SET status = ?, retry_count = ?, last_attempt = ? WHERE tx_id = ?",
                (status, retry_count, int(time.time()), tx_id)
            )
        else:
            cursor.execute(
                "UPDATE offline_tx SET status = ?, last_attempt = ? WHERE tx_id = ?",
                (status, int(time.time()), tx_id)
            )
        
        conn.commit()
    
    def size(self) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM gateways")
        count = cursor.fetchone()[0]
        return count
    
    def clear(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM gateways")
        cursor.execute("DELETE FROM wallets")
        cursor.execute("DELETE FROM offline_tx")
        cursor.execute("DELETE FROM pending_trustlines")
        
        conn.commit()