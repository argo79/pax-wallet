#!/usr/bin/env python3
"""
gateway_daemon.py - Gateway Reticulum come servizio indipendente cross-platform
"""

import os
import sys
import json
import time
import socket
import threading
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List

import RNS
from RNS import Destination, Packet, Identity

# ============================================================
# CONFIGURAZIONE CROSS-PLATFORM
# ============================================================

GATEWAY_PORT = 38427

if sys.platform == 'win32':
    BASE_DIR = Path(os.environ.get('TEMP', os.environ.get('TMP', '.')))
else:
    BASE_DIR = Path('/tmp')

GATEWAY_INFO_FILE = BASE_DIR / 'reticulum_gateway.json'
IDENTITY_FILE = Path("gateway_identity.rid")
CACHE_DB = Path("gateway_cache.db")

# ============================================================
# CACHE
# ============================================================

class GatewayCache:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _get_conn(self):
        return sqlite3.connect(str(self.db_path), check_same_thread=False)
    
    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS gateways (
                gateway_id TEXT PRIMARY KEY,
                gateway_name TEXT,
                last_seen INTEGER,
                services TEXT,
                fee TEXT,
                fee_asset TEXT,
                reputation INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                wallet_aspect TEXT PRIMARY KEY,
                ledger_address TEXT,
                network TEXT,
                assets TEXT,
                gateway_id TEXT,
                last_seen INTEGER
            )
        """)
        conn.commit()
        conn.close()
    
    def add_gateway(self, gateway: Dict):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO gateways 
            (gateway_id, gateway_name, last_seen, services, fee, fee_asset, reputation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            gateway.get("gateway_id"),
            gateway.get("gateway_name", "Unknown"),
            int(time.time()),
            json.dumps(gateway.get("services", [])),
            gateway.get("fee", "0.00001"),
            gateway.get("fee_asset", "XRP"),
            gateway.get("reputation", 50)
        ))
        conn.commit()
        conn.close()
    
    def get_all_gateways(self) -> List[Dict]:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT gateway_id, gateway_name, last_seen, services, fee, fee_asset, reputation FROM gateways ORDER BY last_seen DESC")
        rows = c.fetchall()
        conn.close()
        return [{
            "gateway_id": row[0],
            "gateway_name": row[1],
            "last_seen": row[2],
            "services": json.loads(row[3]) if row[3] else [],
            "fee": row[4],
            "fee_asset": row[5],
            "reputation": row[6]
        } for row in rows]
    
    def get_all_wallets(self) -> List[Dict]:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT wallet_aspect, ledger_address, network, assets, gateway_id, last_seen FROM wallets ORDER BY last_seen DESC")
        rows = c.fetchall()
        conn.close()
        return [{
            "wallet_aspect": row[0],
            "ledger_address": row[1],
            "network": row[2],
            "assets": json.loads(row[3]) if row[3] else [],
            "gateway_id": row[4],
            "last_seen": row[5]
        } for row in rows]

# ============================================================
# 🔥 ANNOUNCE HANDLER - IDENTICO AL TEST CHE FUNZIONA!
# ============================================================

class AnnounceHandler:
    def __init__(self, cache):
        self.cache = cache
        self.count = 0

    def received_announce(self, destination_hash, announced_identity, app_data):
        """Riceve TUTTI gli annunci - ESATTAMENTE come il test che funziona"""
        self.count += 1
        peer_hash = destination_hash.hex()
        
        print(f"\n📢 ANNUNCIO #{self.count} RICEVUTO")
        print(f"   Hash: {peer_hash[:16]}...")
        
        if announced_identity:
            print(f"   Identity: {announced_identity.hash.hex()[:16]}...")
        
        if app_data:
            try:
                name = app_data.decode("utf-8")
                print(f"   Data: {name}")
            except:
                print(f"   Data: {app_data.hex()[:32]}...")
        else:
            print(f"   Data: None")
        
        # 🔥 SALVA NEL DATABASE
        self.cache.add_gateway({
            "gateway_id": peer_hash,
            "gateway_name": name if app_data else "UNKNOWN",
            "services": ["xrpl_mainnet"],
            "fee": "0.00001",
            "fee_asset": "XRP",
            "reputation": 50,
            "last_seen": int(time.time())
        })
        
        print("   " + "-" * 40)

# ============================================================
# DAEMON
# ============================================================

class GatewayDaemon:
    def __init__(self):
        self.running = True
        self.cache = GatewayCache(CACHE_DB)
        self.identity = None
        self.gateway_dest = None
        self.server = None
        self.handler = None
        self.port = GATEWAY_PORT
    
    def start(self):
        print("🚀 Avvio Gateway Daemon...")
        
        if self._is_running():
            print("⚠️ Gateway già in esecuzione")
            return
        
        self._write_info()
        
        # 1. AVVIA RETICULUM
        reticulum = RNS.Reticulum()
        print("📡 Reticulum avviato")
        
        # 2. CARICA IDENTITÀ
        self._load_identity()
        
        # 3. REGISTRA L'HANDLER (DOPO RETICULUM, COME NEL TEST!)
        self.handler = AnnounceHandler(self.cache)
        RNS.Transport.register_announce_handler(self.handler)
        print("📡 Handler annunci registrato (riceve TUTTO - come il test)")
        
        # 4. CREA DESTINAZIONE
        self.gateway_dest = Destination(
            self.identity,
            Destination.IN,
            Destination.SINGLE,
            "rns", "rec", "gateway"
        )
        self.gateway_dest.set_packet_callback(self._handle_packet)
        
        # 5. ANNUNCIA
        self.gateway_dest.announce(app_data=b"Gateway-Daemon")
        print("📢 Gateway annunciato: Gateway-Daemon")
        
        # 6. AVVIA SERVER TCP
        self._start_server()
        
        print(f"✅ Gateway Daemon avviato (PID: {os.getpid()})")
        print(f"   Porta: {self.port}")
        print("   Per fermarlo: python3 gateway_daemon.py stop")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def _is_running(self) -> bool:
        if GATEWAY_INFO_FILE.exists():
            try:
                with open(GATEWAY_INFO_FILE, 'r') as f:
                    info = json.load(f)
                    pid = info.get('pid')
                    if pid:
                        try:
                            os.kill(pid, 0)
                            return True
                        except:
                            pass
            except:
                pass
        return False
    
    def _write_info(self):
        try:
            with open(GATEWAY_INFO_FILE, 'w') as f:
                json.dump({
                    'pid': os.getpid(),
                    'port': self.port,
                    'started_at': time.time()
                }, f)
        except:
            pass
    
    def _remove_info(self):
        try:
            GATEWAY_INFO_FILE.unlink()
        except:
            pass
    
    def _load_identity(self):
        if IDENTITY_FILE.exists():
            self.identity = Identity.from_file(str(IDENTITY_FILE))
            print(f"✅ Identità caricata da {IDENTITY_FILE}")
        else:
            self.identity = Identity()
            self.identity.to_file(str(IDENTITY_FILE))
            print(f"✅ Nuova identità creata: {IDENTITY_FILE}")
    
    def _start_server(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        port = self.port
        while port < self.port + 10:
            try:
                self.server.bind(('127.0.0.1', port))
                self.port = port
                break
            except:
                port += 1
        
        self.server.listen(5)
        self.server.settimeout(1.0)
        
        self._write_info()
        
        thread = threading.Thread(target=self._accept_connections, daemon=True)
        thread.start()
        print(f"🔌 Server TCP in ascolto su 127.0.0.1:{self.port}")
    
    def _accept_connections(self):
        while self.running:
            try:
                conn, addr = self.server.accept()
                thread = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"⚠️ Errore server: {e}")
    
    def _handle_client(self, conn):
        try:
            data = conn.recv(4096)
            if not data:
                return
            
            request = json.loads(data.decode())
            response = self._process_request(request)
            conn.send(json.dumps(response).encode())
        except Exception as e:
            try:
                conn.send(json.dumps({"error": str(e)}).encode())
            except:
                pass
        finally:
            conn.close()
    
    def _process_request(self, request: Dict) -> Dict:
        cmd = request.get("command")
        
        if cmd == "discover":
            return {
                "success": True,
                "gateways": self.cache.get_all_gateways(),
                "wallets": self.cache.get_all_wallets()
            }
        
        elif cmd == "send":
            tx_data = request.get("data", {})
            gateway_id = request.get("gateway_id")
            
            try:
                dest_hash = bytes.fromhex(gateway_id)
                packet = Packet(dest_hash, json.dumps(tx_data).encode())
                packet.send()
                return {"success": True, "status": "sent", "gateway": gateway_id}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        elif cmd == "status":
            return {
                "success": True,
                "running": self.running,
                "pid": os.getpid(),
                "port": self.port,
                "gateway_address": self.gateway_dest.hash.hex() if self.gateway_dest else None,
                "announces_received": self.handler.count if self.handler else 0,
                "cache_size": len(self.cache.get_all_gateways())
            }
        
        elif cmd == "stop":
            self.running = False
            return {"success": True, "message": "Gateway in arresto..."}
        
        else:
            return {"success": False, "error": f"Comando sconosciuto: {cmd}"}
    
    def _handle_packet(self, packet):
        try:
            data = json.loads(packet.data.decode())
            print(f"📥 Pacchetto ricevuto: {data.get('type', 'unknown')}")
        except:
            pass
    
    def stop(self):
        self.running = False
        if self.server:
            try:
                self.server.close()
            except:
                pass
        self._remove_info()
        print("✅ Gateway Daemon fermato")

# ============================================================
# CLIENT PER IL WALLET
# ============================================================

class GatewayClient:
    @staticmethod
    def _get_info() -> Optional[Dict]:
        if GATEWAY_INFO_FILE.exists():
            try:
                with open(GATEWAY_INFO_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return None
    
    @staticmethod
    def request(command: str, data: Dict = None, gateway_id: str = None) -> Dict:
        info = GatewayClient._get_info()
        if not info:
            return {"success": False, "error": "Gateway non in esecuzione"}
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect(('127.0.0.1', info['port']))
            
            request = {"command": command}
            if data:
                request["data"] = data
            if gateway_id:
                request["gateway_id"] = gateway_id
            
            sock.send(json.dumps(request).encode())
            response = json.loads(sock.recv(4096).decode())
            sock.close()
            return response
        except socket.timeout:
            return {"success": False, "error": "Timeout connessione al gateway"}
        except ConnectionRefusedError:
            return {"success": False, "error": "Gateway non in esecuzione"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def status() -> Dict:
        return GatewayClient.request("status")
    
    @staticmethod
    def discover() -> Dict:
        return GatewayClient.request("discover")
    
    @staticmethod
    def send(tx_data: Dict, gateway_id: str) -> Dict:
        return GatewayClient.request("send", tx_data, gateway_id)
    
    @staticmethod
    def stop() -> Dict:
        return GatewayClient.request("stop")

# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "stop":
            response = GatewayClient.stop()
            if response.get("success"):
                print(response.get("message", "Gateway fermato"))
            else:
                print(f"❌ {response.get('error', 'Errore sconosciuto')}")
            return
        
        elif sys.argv[1] == "status":
            response = GatewayClient.status()
            if response.get("success"):
                print("\n📊 STATO GATEWAY")
                print("=" * 40)
                for key, value in response.items():
                    if key != "success":
                        print(f"   {key}: {value}")
                print("=" * 40)
            else:
                print(f"❌ {response.get('error', 'Errore')}")
            return
        
        elif sys.argv[1] == "foreground":
            daemon = GatewayDaemon()
            daemon.start()
            return
    
    daemon = GatewayDaemon()
    daemon.start()

if __name__ == "__main__":
    main()