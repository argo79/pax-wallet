#!/usr/bin/env python3
"""
gateway_metrics.py - Gestione metriche tra gateway (AUTONOMA)
"""

import sqlite3
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
import RNS
from dataclasses import dataclass


# ============================================================
# DEFINIZIONI MESSAGGI (INCORPORATE QUI)
# ============================================================

class MessageType:
    INFO_REQUEST = "info_request"
    INFO_RESPONSE = "info_response"


@dataclass
class GatewayInfoRequest:
    from_gateway: str
    timestamp: int
    signature: str = ""
    
    def to_json(self) -> str:
        return json.dumps({
            "type": MessageType.INFO_REQUEST,
            "from_gateway": self.from_gateway,
            "timestamp": self.timestamp,
            "signature": self.signature
        })
    
    @classmethod
    def from_json(cls, data: Dict) -> 'GatewayInfoRequest':
        return cls(
            from_gateway=data.get("from_gateway", ""),
            timestamp=data.get("timestamp", int(time.time())),
            signature=data.get("signature", "")
        )


@dataclass
class GatewayInfoResponse:
    gateway_id: str
    name: str
    identity_hash: str
    networks: List[str]
    assets: List[str]
    fee: str
    fee_asset: str
    version: str
    has_internet: bool
    reputation: int
    uptime: int
    timestamp: int
    signature: str = ""
    
    def to_json(self) -> str:
        return json.dumps({
            "type": MessageType.INFO_RESPONSE,
            "gateway_id": self.gateway_id,
            "name": self.name,
            "identity_hash": self.identity_hash,
            "networks": self.networks,
            "assets": self.assets,
            "fee": self.fee,
            "fee_asset": self.fee_asset,
            "version": self.version,
            "has_internet": self.has_internet,
            "reputation": self.reputation,
            "uptime": self.uptime,
            "timestamp": self.timestamp,
            "signature": self.signature
        })
    
    @classmethod
    def from_json(cls, data: Dict) -> 'GatewayInfoResponse':
        return cls(
            gateway_id=data.get("gateway_id", ""),
            name=data.get("name", "UNKNOWN"),
            identity_hash=data.get("identity_hash", ""),
            networks=data.get("networks", []),
            assets=data.get("assets", []),
            fee=data.get("fee", "0.00001"),
            fee_asset=data.get("fee_asset", "XRP"),
            version=data.get("version", "1.0.0"),
            has_internet=data.get("has_internet", False),
            reputation=data.get("reputation", 50),
            uptime=data.get("uptime", 0),
            timestamp=data.get("timestamp", int(time.time())),
            signature=data.get("signature", "")
        )


# ============================================================
# FUNZIONI DI FIRMA
# ============================================================

def sign_message(message: dict, identity) -> str:
    """Firma un messaggio con l'identity Reticulum"""
    msg_copy = {k: v for k, v in message.items() if k != "signature"}
    msg_json = json.dumps(msg_copy, sort_keys=True)
    signature = identity.sign(msg_json.encode())
    return signature.hex()


# ============================================================
# GATEWAY METRICS
# ============================================================

class GatewayMetrics:
    """Gestisce metriche e interrogazione dei gateway"""
    
    def __init__(self, identity, db_path: Path = Path("gateway_peers.db")):
        self.identity = identity
        self.db_path = db_path
        self.lock = threading.Lock()
        self._my_gateway_id = None
        self._running = False
        self._query_thread = None
        self._init_db()
    
    def _init_db(self):
        """Inizializza tabella gateway_peers"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS gateway_peers (
                    gateway_id TEXT PRIMARY KEY,
                    name TEXT,
                    identity_hash TEXT,
                    networks TEXT,
                    assets TEXT,
                    fee TEXT,
                    fee_asset TEXT,
                    version TEXT,
                    has_internet BOOLEAN,
                    reputation INTEGER,
                    hops INTEGER,
                    latency_ms INTEGER,
                    reliability REAL,
                    last_seen INTEGER,
                    last_updated INTEGER,
                    is_online BOOLEAN DEFAULT 1,
                    query_attempts INTEGER DEFAULT 0,
                    query_success INTEGER DEFAULT 0
                )
            ''')
            
            c.execute('CREATE INDEX IF NOT EXISTS idx_hops ON gateway_peers(hops)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_last_seen ON gateway_peers(last_seen)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_reputation ON gateway_peers(reputation)')
            
            conn.commit()
            conn.close()
            print(f"✅ GatewayMetrics inizializzato: {self.db_path}")
    
    def set_my_gateway_id(self, gateway_id: str):
        self._my_gateway_id = gateway_id
    
    # ============================================================
    # AGGIORNAMENTO DA ANNUNCI
    # ============================================================
    
    def update_from_announce(self, gateway_id: str, name: str, identity_hash: str = None,
                            hops: int = None, interface: str = None,
                            rssi: float = None, snr: float = None, quality: float = None):
        """Aggiorna un peer dai dati di un annuncio"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            now = int(time.time())
            
            c.execute('SELECT gateway_id FROM gateway_peers WHERE gateway_id = ?', (gateway_id,))
            exists = c.fetchone()
            
            if exists:
                c.execute('''
                    UPDATE gateway_peers 
                    SET name = COALESCE(?, name),
                        identity_hash = COALESCE(?, identity_hash),
                        hops = COALESCE(?, hops),
                        last_seen = ?,
                        is_online = 1
                    WHERE gateway_id = ?
                ''', (name, identity_hash, hops, now, gateway_id))
            else:
                c.execute('''
                    INSERT INTO gateway_peers 
                    (gateway_id, name, identity_hash, hops, first_seen, last_seen, is_online)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (gateway_id, name, identity_hash, hops, now, now))
            
            conn.commit()
            conn.close()
    
    # ============================================================
    # COSTRUZIONE RISPOSTA
    # ============================================================
    
    def build_info_response(self) -> GatewayInfoResponse:
        return GatewayInfoResponse(
            gateway_id=self._my_gateway_id or self.identity.hash.hex(),
            name="Gateway",
            identity_hash=self.identity.hash.hex(),
            networks=["xrpl", "stellar"],
            assets=["XRP", "RLUSD", "XLM"],
            fee="0.00001",
            fee_asset="RLUSD",
            version="1.0.0",
            has_internet=True,
            reputation=85,
            uptime=int(time.time()),
            timestamp=int(time.time())
        )
    
    # ============================================================
    # PROCESSO RICHIESTE/RISPOSTE
    # ============================================================
    
    def process_info_request(self, request_data: dict) -> Optional[GatewayInfoResponse]:
        """Processa una info_request ricevuta e restituisce la risposta"""
        try:
            response = self.build_info_response()
            response_dict = json.loads(response.to_json())
            response.signature = sign_message(response_dict, self.identity)
            return response
        except Exception as e:
            print(f"⚠️ Errore processing info_request: {e}")
            return None
    
    def process_info_response(self, response_data: dict) -> bool:
        """Processa una info_response ricevuta e aggiorna il database"""
        try:
            info = GatewayInfoResponse.from_json(response_data)
            now = int(time.time())
            
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                
                c.execute('''
                    INSERT OR REPLACE INTO gateway_peers 
                    (gateway_id, name, identity_hash, networks, assets, fee, fee_asset,
                     version, has_internet, reputation, last_updated, query_success, 
                     query_attempts, is_online)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1)
                ''', (
                    info.gateway_id,
                    info.name,
                    info.identity_hash,
                    json.dumps(info.networks),
                    json.dumps(info.assets),
                    info.fee,
                    info.fee_asset,
                    info.version,
                    1 if info.has_internet else 0,
                    info.reputation,
                    now
                ))
                
                c.execute('''
                    UPDATE gateway_peers 
                    SET reliability = CAST(query_success AS REAL) / query_attempts
                    WHERE query_attempts > 0 AND gateway_id = ?
                ''', (info.gateway_id,))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            print(f"⚠️ Errore processing info_response: {e}")
            return False
    
    # ============================================================
    # INVIO RICHIESTA ATTIVA
    # ============================================================
    
    def request_gateway_info(self, gateway_id: str, timeout_seconds: int = 5) -> bool:
        """Invia info_request a un gateway e aspetta risposta"""
        try:
            from RNS import Link
            
            request = {
                "type": MessageType.INFO_REQUEST,
                "from_gateway": self._my_gateway_id or self.identity.hash.hex(),
                "timestamp": int(time.time())
            }
            request["signature"] = sign_message(request, self.identity)
            
            dest_hash = bytes.fromhex(gateway_id)
            link = Link(dest_hash)
            link.send(json.dumps(request).encode())
            time.sleep(timeout_seconds)
            link.close()
            return True
            
        except Exception as e:
            print(f"⚠️ Errore richiesta info a {gateway_id}: {e}")
            return False
    
    # ============================================================
    # RECUPERO PEER
    # ============================================================
    
    def get_all_peers(self) -> List[Dict]:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''
                SELECT gateway_id, name, hops, reputation, networks, assets, has_internet, last_seen
                FROM gateway_peers
                WHERE is_online = 1
                ORDER BY reputation DESC, hops ASC
            ''')
            rows = c.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    def get_best_gateway(self, asset: str = None) -> Optional[Dict]:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            query = '''
                SELECT gateway_id, name, hops, latency_ms, reputation, 
                       networks, assets, fee, fee_asset, reliability, has_internet
                FROM gateway_peers
                WHERE is_online = 1
            '''
            params = []
            
            if asset:
                query += ' AND assets LIKE ?'
                params.append(f'%"{asset}"%')
            
            query += '''
                ORDER BY 
                    COALESCE(hops, 999) ASC,
                    COALESCE(latency_ms, 99999) ASC,
                    reputation DESC,
                    reliability DESC
                LIMIT 1
            '''
            
            c.execute(query, params)
            row = c.fetchone()
            conn.close()
            return dict(row) if row else None
    
    # ============================================================
    # QUERY LOOP PERIODICO
    # ============================================================
    
    def start_query_loop(self, interval: int = 3600, max_peers: int = 10, max_hops: int = 3):
        if self._running:
            return
        
        self._running = True
        self._query_thread = threading.Thread(
            target=self._query_loop,
            args=(interval, max_peers, max_hops),
            daemon=True
        )
        self._query_thread.start()
        print(f"📡 Query loop avviato (interval: {interval}s)")
    
    def stop_query_loop(self):
        self._running = False
        if self._query_thread:
            self._query_thread.join(timeout=2)
        print("📡 Query loop fermato")
    
    def _query_loop(self, interval: int, max_peers: int, max_hops: int):
        while self._running:
            try:
                time.sleep(interval)
                
                with self.lock:
                    conn = sqlite3.connect(self.db_path)
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    c.execute('''
                        SELECT gateway_id 
                        FROM gateway_peers
                        WHERE is_online = 1
                          AND (last_updated IS NULL OR last_updated < UNIX_TIMESTAMP() - 86400)
                        ORDER BY last_updated ASC
                        LIMIT ?
                    ''', (max_peers,))
                    rows = c.fetchall()
                    conn.close()
                
                for row in rows:
                    gateway_id = row["gateway_id"]
                    if gateway_id == self._my_gateway_id:
                        continue
                    
                    success = self.request_gateway_info(gateway_id)
                    
                    with self.lock:
                        conn = sqlite3.connect(self.db_path)
                        c = conn.cursor()
                        c.execute('''
                            UPDATE gateway_peers 
                            SET query_attempts = query_attempts + 1,
                                query_success = query_success + ?,
                                is_online = ?
                            WHERE gateway_id = ?
                        ''', (1 if success else 0, 1 if success else 0, gateway_id))
                        
                        c.execute('''
                            UPDATE gateway_peers 
                            SET reliability = CAST(query_success AS REAL) / query_attempts
                            WHERE query_attempts > 0 AND gateway_id = ?
                        ''', (gateway_id,))
                        conn.commit()
                        conn.close()
                    
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"⚠️ Errore nel query loop: {e}")
    
    # ============================================================
    # UTILITY
    # ============================================================
    
    def get_stats(self) -> Dict:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM gateway_peers')
            total = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM gateway_peers WHERE is_online = 1')
            online = c.fetchone()[0]
            c.execute('SELECT AVG(reputation) FROM gateway_peers WHERE is_online = 1')
            avg_reputation = c.fetchone()[0] or 0
            conn.close()
            
            return {
                "total_peers": total,
                "online_peers": online,
                "avg_reputation": round(avg_reputation, 2)
            }