#!/usr/bin/env python3
"""
announce_cache.py - Cache SQLite per annunci gateway e wallet
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
import threading


class AnnounceCache:
    """Cache SQLite per annunci gateway e wallet"""
    
    def __init__(self, db_path: Path = Path("announce_cache.db")):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Inizializza le tabelle"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Tabella per annunci gateway (rns.rec.gateway)
            c.execute('''
                CREATE TABLE IF NOT EXISTS gateway_announces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gateway_id TEXT NOT NULL UNIQUE,     -- destination_hash (hex)
                    name TEXT,                           -- app_data decodificato
                    identity_hash TEXT,                  -- announced_identity.hash.hex()
                    hops INTEGER,                        -- hops dal path table
                    interface TEXT,                      -- nome interfaccia
                    rssi REAL,                           -- metadato RSSI
                    snr REAL,                            -- metadato SNR
                    quality REAL,                        -- metadato Qualità
                    first_seen INTEGER NOT NULL,         -- timestamp
                    last_seen INTEGER NOT NULL           -- timestamp
                )
            ''')
            
            # Tabella per annunci wallet (rns.rec.wallet)
            c.execute('''
                CREATE TABLE IF NOT EXISTS wallet_announces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_id TEXT NOT NULL UNIQUE,      -- destination_hash (hex)
                    name TEXT,                           -- app_data decodificato
                    identity_hash TEXT,                  -- announced_identity.hash.hex()
                    hops INTEGER,                        -- hops dal path table
                    interface TEXT,                      -- nome interfaccia
                    rssi REAL,                           -- metadato RSSI
                    snr REAL,                            -- metadato SNR
                    quality REAL,                        -- metadato Qualità
                    first_seen INTEGER NOT NULL,         -- timestamp
                    last_seen INTEGER NOT NULL           -- timestamp
                )
            ''')
            
            # Indici per query veloci
            c.execute('CREATE INDEX IF NOT EXISTS idx_gateway_id ON gateway_announces(gateway_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_gateway_last ON gateway_announces(last_seen)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_wallet_id ON wallet_announces(wallet_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_wallet_last ON wallet_announces(last_seen)')
            
            conn.commit()
            conn.close()
            
            print(f"✅ Cache SQLite inizializzata: {self.db_path}")

    # ============================================================
    # METODI PER GATEWAY
    # ============================================================
    
    def add_gateway_announce(self, gateway_id: str, name: str, identity_hash: str = None,
                            hops: int = None, interface: str = None,
                            rssi: float = None, snr: float = None, quality: float = None):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            now = int(time.time())  # <-- TIMESTAMP ATTUALE!
            
            c.execute('SELECT first_seen FROM gateway_announces WHERE gateway_id = ?', (gateway_id,))
            row = c.fetchone()
            first_seen = row[0] if row else now
            
            c.execute('''
                INSERT OR REPLACE INTO gateway_announces 
                (gateway_id, name, identity_hash, hops, interface, rssi, snr, quality, last_seen, first_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (gateway_id, name, identity_hash, hops, interface, rssi, snr, quality, now, first_seen))
            conn.commit()
    
    def get_gateway_announces(self, limit: int = 100, since: int = None) -> List[Dict]:
        """Recupera gli annunci gateway"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                query = '''
                    SELECT gateway_id, name, identity_hash, hops, interface, 
                           rssi, snr, quality, first_seen, last_seen
                    FROM gateway_announces
                '''
                params = []
                
                if since:
                    query += ' WHERE last_seen >= ?'
                    params.append(since)
                
                query += ' ORDER BY last_seen DESC LIMIT ?'
                params.append(limit)
                
                c.execute(query, params)
                rows = c.fetchall()
                conn.close()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            print(f"⚠️ Errore lettura gateway annunci: {e}")
            return []
    
    def get_gateway_by_id(self, gateway_id: str) -> Optional[Dict]:
        """Recupera un gateway specifico per ID"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                c.execute('''
                    SELECT gateway_id, name, identity_hash, hops, interface, 
                           rssi, snr, quality, first_seen, last_seen
                    FROM gateway_announces
                    WHERE gateway_id = ?
                ''', (gateway_id,))
                
                row = c.fetchone()
                conn.close()
                
                return dict(row) if row else None
                
        except Exception as e:
            print(f"⚠️ Errore lettura gateway: {e}")
            return None
    
    def count_gateway_announces(self) -> int:
        """Conta gli annunci gateway"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM gateway_announces')
                count = c.fetchone()[0]
                conn.close()
                return count
        except:
            return 0

    # ============================================================
    # METODI PER WALLET
    # ============================================================
    
    def add_wallet_announce(self, wallet_id: str, name: str, identity_hash: str = None,
                           hops: int = None, interface: str = None,
                           rssi: float = None, snr: float = None, quality: float = None) -> bool:
        """Aggiunge o aggiorna un annuncio wallet"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                
                now = int(time.time())
                
                c.execute('''
                    INSERT OR REPLACE INTO wallet_announces 
                    (wallet_id, name, identity_hash, hops, interface, rssi, snr, quality, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT first_seen FROM wallet_announces WHERE wallet_id = ?), ?), ?)
                ''', (
                    wallet_id,
                    name,
                    identity_hash,
                    hops,
                    interface,
                    rssi,
                    snr,
                    quality,
                    wallet_id,
                    now,
                    now
                ))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            print(f"⚠️ Errore salvataggio wallet annuncio: {e}")
            return False
    
    def get_wallet_announces(self, limit: int = 100, since: int = None) -> List[Dict]:
        """Recupera gli annunci wallet"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                query = '''
                    SELECT wallet_id, name, identity_hash, hops, interface, 
                           rssi, snr, quality, first_seen, last_seen
                    FROM wallet_announces
                '''
                params = []
                
                if since:
                    query += ' WHERE last_seen >= ?'
                    params.append(since)
                
                query += ' ORDER BY last_seen DESC LIMIT ?'
                params.append(limit)
                
                c.execute(query, params)
                rows = c.fetchall()
                conn.close()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            print(f"⚠️ Errore lettura wallet annunci: {e}")
            return []
    
    def get_wallet_by_id(self, wallet_id: str) -> Optional[Dict]:
        """Recupera un wallet specifico per ID"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                c.execute('''
                    SELECT wallet_id, name, identity_hash, hops, interface, 
                           rssi, snr, quality, first_seen, last_seen
                    FROM wallet_announces
                    WHERE wallet_id = ?
                ''', (wallet_id,))
                
                row = c.fetchone()
                conn.close()
                
                return dict(row) if row else None
                
        except Exception as e:
            print(f"⚠️ Errore lettura wallet: {e}")
            return None
    
    def count_wallet_announces(self) -> int:
        """Conta gli annunci wallet"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM wallet_announces')
                count = c.fetchone()[0]
                conn.close()
                return count
        except:
            return 0

    # ============================================================
    # METODI GENERALI
    # ============================================================
    
    def get_stats(self) -> Dict:
        """Statistiche della cache"""
        return {
            "gateway_count": self.count_gateway_announces(),
            "wallet_count": self.count_wallet_announces(),
            "db_path": str(self.db_path),
            "db_size": self.db_path.stat().st_size if self.db_path.exists() else 0
        }
    
    def cleanup_old(self, days: int = 7):
        """Rimuove annunci più vecchi di N giorni"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                
                cutoff = int(time.time()) - (days * 86400)
                
                c.execute('DELETE FROM gateway_announces WHERE last_seen < ?', (cutoff,))
                deleted_gateway = c.rowcount
                
                c.execute('DELETE FROM wallet_announces WHERE last_seen < ?', (cutoff,))
                deleted_wallet = c.rowcount
                
                conn.commit()
                conn.close()
                
                print(f"🧹 Puliti {deleted_gateway} gateway e {deleted_wallet} wallet annunci (più vecchi di {days} giorni)")
                return deleted_gateway + deleted_wallet
                
        except Exception as e:
            print(f"⚠️ Errore cleanup: {e}")
            return 0
    
    def clear(self):
        """Pulisce tutte le tabelle"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute('DELETE FROM gateway_announces')
                c.execute('DELETE FROM wallet_announces')
                conn.commit()
                conn.close()
                print("🧹 Cache pulita")
                return True
        except Exception as e:
            print(f"⚠️ Errore clear: {e}")
            return False
    
    def vacuum(self):
        """Ottimizza il database"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                conn.execute('VACUUM')
                conn.close()
                print("✅ Database ottimizzato")
                return True
        except Exception as e:
            print(f"⚠️ Errore vacuum: {e}")
            return False