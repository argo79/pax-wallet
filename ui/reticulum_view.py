"""
Reticulum View - Gestione Reticulum con lista cliccabile e dettagli
"""

import json
import time
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from .base_view import ListViewWithDetail
from wallet_backend import format_time_ago


class ReticulumView(ListViewWithDetail):
    def __init__(self, main_window):
        self.main = main_window
        super().__init__()
        self.setup_controls()
        
        self.output_list = QListWidget()
        self.output_list.setObjectName("output_list")
        self.output_list.setFont(QFont("Courier New", 10))
        self.output_list.itemClicked.connect(self.on_output_item_clicked)
        self.output_layout.addWidget(self.output_list)
        
        self.output("▶ PAX WALLET - Reticulum Management")
        self.output("▶ Usa i pulsanti qui sopra per le operazioni.")
        self.update_status()

    def setup_controls(self):
        layout = self.controls_layout

        title = QLabel("◈ RETICULUM")
        title.setObjectName("view_title")
        layout.addWidget(title)

        # ============================================================
        # STATUS GROUP - MOSTRA IP, TOR, INTERNET (SOLO LETTURA)
        # ============================================================
        status_group = QGroupBox("◈ STATO CONNESSIONE")
        status_layout = QGridLayout(status_group)
        
        # Riga 1: Nome Gateway e Stato
        status_layout.addWidget(QLabel("GATEWAY:"), 0, 0)
        self.name_label = QLabel("N/A")
        self.name_label.setObjectName("status_value")
        status_layout.addWidget(self.name_label, 0, 1)
        
        status_layout.addWidget(QLabel("STATO:"), 0, 2)
        self.status_label = QLabel("?")
        self.status_label.setObjectName("status_value")
        status_layout.addWidget(self.status_label, 0, 3)
        
        # Riga 2: IP Pubblico
        status_layout.addWidget(QLabel("IP:"), 1, 0)
        self.ip_label = QLabel("N/A")
        self.ip_label.setObjectName("ip_label")
        status_layout.addWidget(self.ip_label, 1, 1, 1, 3)
        
        # Riga 3: TOR e Internet
        status_layout.addWidget(QLabel("TOR:"), 2, 0)
        self.tor_label = QLabel("?")
        self.tor_label.setObjectName("tor_label")
        status_layout.addWidget(self.tor_label, 2, 1)
        
        status_layout.addWidget(QLabel("INTERNET:"), 2, 2)
        self.internet_label = QLabel("?")
        self.internet_label.setObjectName("internet_label")
        status_layout.addWidget(self.internet_label, 2, 3)
        
        # Riga 4: Peers
        status_layout.addWidget(QLabel("PEER:"), 3, 0)
        self.peers_label = QLabel("?")
        self.peers_label.setObjectName("status_value")
        status_layout.addWidget(self.peers_label, 3, 1, 1, 3)
        
        layout.addWidget(status_group)

        # ============================================================
        # BOTTONI CONTROLLI (senza toggle Internet/TOR)
        # ============================================================
        row1 = QHBoxLayout()
        self.start_btn = QPushButton("◈ AVVIA GATEWAY")
        self.start_btn.clicked.connect(self.start_gateway)
        self.stop_btn = QPushButton("◈ FERMA GATEWAY")
        self.stop_btn.clicked.connect(self.stop_gateway)
        row1.addWidget(self.start_btn)
        row1.addWidget(self.stop_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.discover_gw_btn = QPushButton("◈ SCOPRI GATEWAY")
        self.discover_gw_btn.clicked.connect(self.discover_gateways)
        self.discover_w_btn = QPushButton("◈ SCOPRI WALLET")
        self.discover_w_btn.clicked.connect(self.discover_wallets)
        row2.addWidget(self.discover_gw_btn)
        row2.addWidget(self.discover_w_btn)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.test_btn = QPushButton("◈ TESTA TUTTI")
        self.test_btn.clicked.connect(self.test_all_gateways)
        self.best_btn = QPushButton("◈ MIGLIOR GATEWAY")
        self.best_btn.clicked.connect(self.best_gateway)
        self.metrics_btn = QPushButton("◈ PEER METRICHE")
        self.metrics_btn.clicked.connect(self.peer_metrics)
        row3.addWidget(self.test_btn)
        row3.addWidget(self.best_btn)
        row3.addWidget(self.metrics_btn)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        self.request_btn = QPushButton("◈ RICHIEDI INFO")
        self.request_btn.clicked.connect(self.request_info)
        self.remove_btn = QPushButton("◈ RIMUOVI GATEWAY")
        self.remove_btn.clicked.connect(self.remove_gateway)
        row4.addWidget(self.request_btn)
        row4.addWidget(self.remove_btn)
        layout.addLayout(row4)

        self.status_label2 = QLabel()
        self.status_label2.setObjectName("status")
        self.status_label2.setWordWrap(True)
        layout.addWidget(self.status_label2)

    # ============================================================
    # METODI OUTPUT
    # ============================================================
    
    def output(self, text):
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, None)
        self.output_list.addItem(item)
        self.output_list.scrollToBottom()

    def clear_output(self):
        self.output_list.clear()

    def show_status(self, msg, is_error=False):
        if is_error:
            self.status_label2.setText(f"❌ {msg}")
        else:
            self.status_label2.setText(f"✅ {msg}")

    def on_output_item_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return

        if data.get("type") == "gateway":
            gw = data.get("data")
            html = f"""
            <b>Nome:</b> {gw.get('name', 'N/A')}<br>
            <b>Gateway ID:</b> {gw.get('gateway_id', 'N/A')}<br>
            <b>Hops:</b> {gw.get('hops', '?')}<br>
            <b>RSSI:</b> {gw.get('rssi', 'N/A')} dBm<br>
            <b>SNR:</b> {gw.get('snr', 'N/A')} dB<br>
            <b>Quality:</b> {gw.get('quality', 'N/A')}%<br>
            <b>Interface:</b> {gw.get('interface', 'N/A')}<br>
            <b>First Seen:</b> {gw.get('first_seen', 'N/A')}<br>
            <b>Last Seen:</b> {format_time_ago(gw.get('last_seen', 0))}
            """
            self.set_detail_html(html)

        elif data.get("type") == "peer":
            peer = data.get("data")
            
            xrp_status = "✅" if peer.get('xrp_reachable') else "❌"
            stellar_status = "✅" if peer.get('stellar_reachable') else "❌"
            internet_status = "✅" if peer.get('has_internet') else "❌"
            
            tor_enabled = peer.get('tor_enabled', False)
            tor_reachable = peer.get('tor_reachable', False)
            if tor_enabled and tor_reachable:
                tor_status = "✅ Attivo e raggiungibile"
            elif tor_enabled:
                tor_status = "⚠️ Attivo ma non raggiungibile"
            else:
                tor_status = "❌ Non attivo"
            
            xrp_lat = peer.get('xrp_latency_ms')
            xrp_lat_str = f"{xrp_lat:.2f}ms" if xrp_lat is not None else "N/A"
            
            stellar_lat = peer.get('stellar_latency_ms')
            stellar_lat_str = f"{stellar_lat:.2f}ms" if stellar_lat is not None else "N/A"
            
            rtt = peer.get('latency_ms')
            rtt_str = f"{rtt:.2f}ms" if rtt is not None else "N/A"
            
            assets = peer.get('assets', [])
            assets_str = ', '.join(assets) if assets else "Nessuno"
            
            networks = peer.get('networks', [])
            networks_str = ', '.join(networks) if networks else "N/A"
            
            html = f"""
            <b>🏷️ Nome:</b> {peer.get('name', 'N/A')}<br>
            <b>🆔 Gateway ID:</b> {peer.get('gateway_id', 'N/A')}<br>
            <hr>
            <b>📊 Score:</b> {peer.get('_score', 0)}<br>
            <b>📈 Reliability:</b> {peer.get('reliability', 0):.2f}<br>
            <b>⭐ Reputation:</b> {peer.get('reputation', 50)}<br>
            <b>🔗 Hops:</b> {peer.get('hops', '?')}<br>
            <b>⏱️ RTT Reticulum:</b> {rtt_str}<br>
            <hr>
            <b>💎 XRP Reachable:</b> {xrp_status} ({xrp_lat_str})<br>
            <b>💎 Stellar Reachable:</b> {stellar_status} ({stellar_lat_str})<br>
            <b>🌐 Internet:</b> {internet_status}<br>
            <b>🧅 TOR:</b> {tor_status}<br>
            <hr>
            <b>📦 Assets:</b> {assets_str}<br>
            <b>🌍 Networks:</b> {networks_str}<br>
            <b>💰 Fee:</b> {peer.get('fee', 'N/A')} {peer.get('fee_asset', '')}<br>
            <hr>
            <b>🕐 Ultimo visto:</b> {format_time_ago(peer.get('last_seen', 0))}
            """
            self.set_detail_html(html)

        elif data.get("type") == "wallet":
            w = data.get("data")
            html = f"""
            <b>Nome:</b> {w.get('name', 'N/A')}<br>
            <b>Wallet ID:</b> {w.get('wallet_id', 'N/A')}<br>
            <b>Hops:</b> {w.get('hops', '?')}<br>
            <b>Interface:</b> {w.get('interface', 'N/A')}<br>
            <b>Last Seen:</b> {format_time_ago(w.get('last_seen', 0))}
            """
            self.set_detail_html(html)

        else:
            self.set_detail_text("Nessun dettaglio disponibile")

    def add_gateway_item(self, gw):
        name = gw.get('name', 'Sconosciuto')
        gw_id = gw.get('gateway_id', '?')
        hops = gw.get('hops', '?')
        rssi = gw.get('rssi')
        rssi_str = f" RSSI:{rssi:.1f}dBm" if rssi is not None else ""
        text = f"{name} ({gw_id[:16]}...) Hops:{hops}{rssi_str}"
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, {"type": "gateway", "data": gw})
        self.output_list.addItem(item)

    def add_peer_item(self, peer):
        name = str(peer.get('name', 'UNKNOWN'))[:16]
        sc = round(peer.get('_score', 0))
        hops = str(peer.get('hops', '?'))
        rtt = peer.get('latency_ms')
        rtt_str = f"{rtt:.0f}ms" if rtt is not None else "?ms"
        
        xrp = "✅" if peer.get('xrp_reachable') else "❌"
        stellar = "✅" if peer.get('stellar_reachable') else "❌"
        internet = "🌐" if peer.get('has_internet') else "📡"
        
        tor_enabled = peer.get('tor_enabled', False)
        tor_reachable = peer.get('tor_reachable', False)
        tor_str = "🧅✅" if (tor_enabled and tor_reachable) else "🧅❌" if tor_enabled else "—"
        
        assets = peer.get('assets', [])
        assets_str = ', '.join(assets[:3]) if assets else ""
        if len(assets) > 3:
            assets_str += f" +{len(assets)-3}"
        
        text = f"{name} Score:{sc} Hops:{hops} RTT:{rtt_str} XRP:{xrp} Stellar:{stellar} {internet} {tor_str} Assets:{assets_str}"
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, {"type": "peer", "data": peer})
        self.output_list.addItem(item)

    def add_wallet_item(self, w):
        name = w.get('name', 'Sconosciuto')
        w_id = w.get('wallet_id', '?')
        hops = w.get('hops', '?')
        text = f"{name} ({w_id[:16]}...) Hops:{hops}"
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, {"type": "wallet", "data": w})
        self.output_list.addItem(item)

    def update_status(self):
        if not self.main.backend:
            return
        try:
            # Gateway status
            status = self.main.backend.get_gateway_status()
            if status.get("success"):
                s = status.get("status", {})
                self.name_label.setText(s.get("name", "N/A"))
                self.status_label.setText("✅ ATTIVO" if s.get("is_gateway") else "❌ FERMO")
                self.peers_label.setText(str(s.get("gateway_count", 0)))
                
                # ============================================================
                # IP PUBBLICO (SOLO LETTURA)
                # ============================================================
                use_internet = self.main.backend.use_internet
                if use_internet:
                    try:
                        ip_info = self.main.backend.get_ip_status()
                        ip = ip_info.get("ip", "N/A")
                        if ip and ip != "N/A":
                            self.ip_label.setText(f"🌍 {ip}")
                            self.ip_label.setStyleSheet("color: #00ff41;")
                        else:
                            self.ip_label.setText("🌐 Ricerca IP...")
                            self.ip_label.setStyleSheet("color: #ffaa00;")
                    except:
                        self.ip_label.setText("🌐 N/A")
                        self.ip_label.setStyleSheet("color: #ff6b6b;")
                else:
                    self.ip_label.setText("📡 Reticulum Mode")
                    self.ip_label.setStyleSheet("color: #ffaa00;")
                
                # ============================================================
                # TOR STATUS (SOLO LETTURA)
                # ============================================================
                use_tor = self.main.backend.use_tor
                tor_reachable = self.main.backend._test_tor() if hasattr(self.main.backend, '_test_tor') else False
                
                if use_tor and tor_reachable:
                    self.tor_label.setText("🧅 ON ✅")
                    self.tor_label.setStyleSheet("color: #00ff41;")
                elif use_tor and not tor_reachable:
                    self.tor_label.setText("🧅 ON ⚠️")
                    self.tor_label.setStyleSheet("color: #ffaa00;")
                else:
                    self.tor_label.setText("🧅 OFF")
                    self.tor_label.setStyleSheet("color: #ff6b6b;")
                
                # ============================================================
                # INTERNET STATUS (SOLO LETTURA)
                # ============================================================
                if use_internet:
                    self.internet_label.setText("🌐 ON")
                    self.internet_label.setStyleSheet("color: #00ff41;")
                else:
                    self.internet_label.setText("📡 OFF (Reticulum)")
                    self.internet_label.setStyleSheet("color: #ffaa00;")
                
                # Bottoni start/stop
                if s.get("is_gateway"):
                    self.start_btn.setEnabled(False)
                    self.stop_btn.setEnabled(True)
                    self.start_btn.setStyleSheet("")
                    self.stop_btn.setStyleSheet("background-color: #5a1a1a;")
                else:
                    self.start_btn.setEnabled(True)
                    self.stop_btn.setEnabled(False)
                    self.start_btn.setStyleSheet("background-color: #1a4a1a;")
                    self.stop_btn.setStyleSheet("")
            else:
                self.output(f"⚠️ {status.get('message', 'Errore')}")
        except Exception as e:
            self.output(f"⚠️ Errore: {e}")

    def start_gateway(self):
        self.output("⏳ Avvio gateway...")
        result = self.main.backend.start_gateway()
        if result.get("success"):
            self.output("✅ Gateway avviato")
            self.show_status("Gateway avviato")
        else:
            self.output(f"❌ Errore: {result.get('message', 'Sconosciuto')}")
            self.show_status(result.get("message", "Errore"), True)
        self.update_status()

    def stop_gateway(self):
        self.output("⏳ Fermo gateway...")
        result = self.main.backend.stop_gateway()
        if result.get("success"):
            self.output("✅ Gateway fermato")
            self.show_status("Gateway fermato")
        else:
            self.output(f"❌ Errore: {result.get('message', 'Sconosciuto')}")
            self.show_status(result.get("message", "Errore"), True)
        self.update_status()

    def discover_gateways(self):
        self.clear_output()
        self.output("🔍 CERCO GATEWAY SU RETICULUM...")
        self.show_status("⏳ Ricerca gateway...")
        
        result = self.main.backend.discover_gateways()
        if result.get("success"):
            gateways = result.get("gateways", [])
            if not gateways:
                self.output("Nessun gateway trovato")
                self.show_status("Nessun gateway trovato")
                return
            self.output(f"Trovati {len(gateways)} gateway (escluso se stesso):")
            for gw in gateways:
                self.add_gateway_item(gw)
            self.show_status(f"Trovati {len(gateways)} gateway")
        else:
            self.output(f"❌ Errore: {result.get('message', 'Sconosciuto')}")
            self.show_status(result.get("message", "Errore"), True)

    def discover_wallets(self):
        self.clear_output()
        self.output("🔍 CERCO WALLET SU RETICULUM...")
        self.show_status("⏳ Ricerca wallet...")
        
        result = self.main.backend.discover_wallets()
        if result.get("success"):
            wallets = result.get("wallets", [])
            if not wallets:
                self.output("Nessun wallet trovato")
                self.show_status("Nessun wallet trovato")
                return
            self.output(f"Trovati {len(wallets)} wallet:")
            for w in wallets:
                self.add_wallet_item(w)
            self.show_status(f"Trovati {len(wallets)} wallet")
        else:
            self.output(f"❌ Errore: {result.get('message', 'Sconosciuto')}")
            self.show_status(result.get("message", "Errore"), True)

    def test_all_gateways(self):
        self.clear_output()
        self.output("📡 TEST DI TUTTI I GATEWAY")
        self.show_status("⏳ Test in corso...")
        
        result = self.main.backend.test_all_gateways()
        if result.get("success"):
            results = result.get("results", [])
            self.output(f"✅ Test completato: {result.get('successful', 0)}/{result.get('tested', 0)} risposte")
            if results:
                self.output("Risultati:")
                for r in results:
                    stato = r.get('status', 'UNKNOWN')
                    internet = "🌐 SI" if r.get('has_internet') else "📡 NO"
                    tor = r.get('tor_status', '—')
                    text = f"{r.get('name', 'UNKNOWN')} - {stato} Internet:{internet} TOR:{tor} Hops:{r.get('hops', '?')}"
                    item = QListWidgetItem(text)
                    item.setData(Qt.UserRole, {"type": "test_result", "data": r})
                    self.output_list.addItem(item)
            else:
                self.output("Nessun gateway testato")
            self.show_status(f"Test completato: {result.get('successful', 0)}/{result.get('tested', 0)} risposte")
        else:
            self.output(f"❌ Errore: {result.get('message', 'Sconosciuto')}")
            self.show_status(result.get("message", "Errore"), True)

    def best_gateway(self):
        asset, ok = QInputDialog.getText(self, "Miglior Gateway", "Asset (es. RLUSD):")
        if not ok or not asset:
            return
        
        self.clear_output()
        self.output(f"🏆 MIGLIOR GATEWAY PER {asset.upper()}")
        self.show_status("⏳ Ricerca...")
        
        result = self.main.backend.get_best_gateway(asset)
        if result.get("success"):
            gw = result.get("gateway", {})
            if gw:
                self.add_gateway_item(gw)
                self.show_status(f"Trovato: {gw.get('name', 'UNKNOWN')}")
            else:
                self.output(f"❌ Nessun gateway trovato per {asset}")
                self.show_status(f"Nessun gateway trovato per {asset}", True)
        else:
            self.output(f"❌ Errore: {result.get('message', 'Sconosciuto')}")
            self.show_status(result.get("message", "Errore"), True)

    def peer_metrics(self):
        self.clear_output()
        self.output("📊 PEER METRICHE")
        self.show_status("⏳ Caricamento metriche...")
        
        result = self.main.backend.get_peer_metrics()
        if result.get("success"):
            peers = result.get("peers", [])
            stats = result.get("stats", {})
            
            if not peers:
                self.output("❌ Nessun peer trovato")
                self.show_status("Nessun peer trovato")
                return
            
            # Mostra filtro applicato
            if self.main.backend.use_tor:
                self.output("🧅 TOR ON: gateway filtrati per TOR + Internet")
            else:
                self.output("🌐 TOR OFF: gateway filtrati per Internet")
            
            self.output(f"✅ Trovati {len(peers)} peer")
            self.output("=" * 220)
            self.output(f"{'#':<3} {'Nome':<20} {'Score':<6} {'Rel':<6} {'Hops':<5} {'RTT':<8} {'XRP':<14} {'Stellar':<14} {'Internet':<9} {'TOR':<6} {'Assets'}")
            self.output("-" * 220)
            
            for idx, p in enumerate(peers, 1):
                name = str(p.get('name', 'UNKNOWN'))[:16]
                sc = round(p.get('_score', 0))
                rel = round(p.get('reliability', 0), 2)
                hops = str(p.get('hops', '?'))
                rtt = p.get('latency_ms')
                rtt_str = f"{rtt:.0f}ms" if rtt is not None else "?ms"
                
                xrp_lat = p.get('xrp_latency_ms')
                if p.get('xrp_reachable') and xrp_lat is not None:
                    xrp_str = f"✅{xrp_lat:.0f}ms"
                elif p.get('xrp_reachable'):
                    xrp_str = "✅ OK"
                else:
                    xrp_str = "❌"
                
                stellar_lat = p.get('stellar_latency_ms')
                if p.get('stellar_reachable') and stellar_lat is not None:
                    stellar_str = f"✅{stellar_lat:.0f}ms"
                elif p.get('stellar_reachable'):
                    stellar_str = "✅ OK"
                else:
                    stellar_str = "❌"
                
                internet = "🌐" if p.get('has_internet') else "📡"
                
                tor_enabled = p.get('tor_enabled', False)
                tor_reachable = p.get('tor_reachable', False)
                tor_str = "🧅✅" if (tor_enabled and tor_reachable) else "🧅❌" if tor_enabled else "—"
                
                assets = p.get('assets', [])
                if isinstance(assets, list):
                    assets_str = ', '.join(assets[:3])
                    if len(assets) > 3:
                        assets_str += f" +{len(assets)-3}"
                else:
                    assets_str = str(assets)[:20]
                
                text = f"{idx:<3} {name:<20} {sc:<6} {rel:<6} {hops:<5} {rtt_str:<8} {xrp_str:<14} {stellar_str:<14} {internet:<9} {tor_str:<6} {assets_str}"
                
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, {"type": "peer", "data": p})
                self.output_list.addItem(item)
            
            self.output("=" * 220)
            
            if stats:
                self.output(f"\n📊 Statistiche:")
                self.output(f"   Totale peer: {stats.get('total_peers', 0)}")
                if stats.get('online_peers', 0) > 0:
                    self.output(f"   Online: {stats.get('online_peers', 0)}")
                if stats.get('tor_peers', 0) > 0:
                    self.output(f"   Gateway con TOR: {stats.get('tor_peers')}")
                if stats.get('xrp_peers', 0) > 0:
                    self.output(f"   Gateway con XRP: {stats.get('xrp_peers')}")
                if stats.get('stellar_peers', 0) > 0:
                    self.output(f"   Gateway con Stellar: {stats.get('stellar_peers')}")
                if stats.get('avg_latency_ms', 0) > 0:
                    self.output(f"   Latenza media: {round(stats.get('avg_latency_ms'), 0)}ms")
            
            if peers:
                b = peers[0]
                self.output(f"\n🏆 MIGLIOR PEER: {b.get('name', 'UNKNOWN')}")
                self.output(f"   Score: {round(b.get('_score', 0))} | Rel: {b.get('reliability', 0):.2f} | Rep: {b.get('reputation', 50)}")
                self.output(f"   Hops: {b.get('hops', '?')} | RTT: {b.get('latency_ms', '?')}ms")
                
                xrp_lat = b.get('xrp_latency_ms')
                if xrp_lat:
                    self.output(f"   XRP: {'✅' if b.get('xrp_reachable') else '❌'} ({xrp_lat:.0f}ms)")
                else:
                    self.output(f"   XRP: {'✅' if b.get('xrp_reachable') else '❌'}")
                
                stellar_lat = b.get('stellar_latency_ms')
                if stellar_lat:
                    self.output(f"   Stellar: {'✅' if b.get('stellar_reachable') else '❌'} ({stellar_lat:.0f}ms)")
                else:
                    self.output(f"   Stellar: {'✅' if b.get('stellar_reachable') else '❌'}")
                
                self.output(f"   Internet: {'✅' if b.get('has_internet') else '❌'}")
                tor_enabled = b.get('tor_enabled', False)
                tor_reachable = b.get('tor_reachable', False)
                if tor_enabled and tor_reachable:
                    self.output(f"   TOR: ✅ Attivo e raggiungibile")
                elif tor_enabled:
                    self.output(f"   TOR: ⚠️ Attivo ma non raggiungibile")
                else:
                    self.output(f"   TOR: ❌ Non attivo")
                
                if b.get('assets'):
                    self.output(f"   Assets: {', '.join(b.get('assets', []))}")
                if b.get('networks'):
                    self.output(f"   Networks: {', '.join(b.get('networks', []))}")
                if b.get('fee') and b.get('fee') != 'N/A':
                    self.output(f"   Fee: {b.get('fee')} {b.get('fee_asset', '')}")
            
            self.show_status(f"Trovati {len(peers)} peer")
        else:
            self.output(f"❌ Errore: {result.get('message', 'Sconosciuto')}")
            self.show_status(result.get("message", "Errore"), True)

    def request_info(self):
        result = self.main.backend.discover_gateways()
        if not result.get("success"):
            self.show_status(result.get("message", "Errore"), True)
            return
        
        gateways = result.get("gateways", [])
        if not gateways:
            self.show_status("Nessun gateway trovato", True)
            return
        
        items = [f"{gw.get('name', 'UNKNOWN')} ({gw.get('gateway_id', '?')[:16]}...)" for gw in gateways]
        choice, ok = QInputDialog.getItem(self, "Scegli Gateway", "Seleziona gateway:", items, 0, False)
        if not ok:
            return
        
        idx = items.index(choice)
        gateway_id = gateways[idx].get('gateway_id')
        
        self.clear_output()
        self.output(f"📡 RICHIEDO INFO A {gateways[idx].get('name', 'UNKNOWN')}")
        self.show_status("⏳ Richiesta info...")
        
        result = self.main.backend.request_gateway_info(gateway_id)
        if result.get("success"):
            peer = result.get("peer")
            if peer:
                self.add_peer_item(peer)
                self.show_status("Info ricevute")
            else:
                self.output("⚠️ Richiesta inviata, peer non trovato in cache")
                self.show_status("Richiesta inviata, peer non trovato in cache")
        else:
            self.output(f"❌ Errore: {result.get('message', 'Sconosciuto')}")
            self.show_status(result.get("message", "Errore"), True)

    def remove_gateway(self):
        result = self.main.backend.discover_gateways()
        if not result.get("success"):
            self.show_status(result.get("message", "Errore"), True)
            return
        
        gateways = result.get("gateways", [])
        if not gateways:
            self.show_status("Nessun gateway trovato", True)
            return
        
        items = [f"{gw.get('name', 'UNKNOWN')} ({gw.get('gateway_id', '?')[:16]}...)" for gw in gateways]
        choice, ok = QInputDialog.getItem(self, "Rimuovi Gateway", "Seleziona gateway:", items, 0, False)
        if not ok:
            return
        
        idx = items.index(choice)
        gateway_id = gateways[idx].get('gateway_id')
        name = gateways[idx].get('name', 'UNKNOWN')
        
        confirm = QMessageBox.question(self, "Conferma", f"Rimuovere {name}?", QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        
        self.clear_output()
        self.output(f"🗑️ RIMUOVO GATEWAY: {name}")
        self.show_status("⏳ Rimozione...")
        
        result = self.main.backend.remove_gateway(gateway_id)
        if result.get("success"):
            self.output(f"✅ Gateway {name} rimosso")
            if result.get("removed_from_announce"):
                self.output("  ✅ Rimosso da announce_cache.db")
            if result.get("removed_from_peers"):
                self.output("  ✅ Rimosso da gateway_peers.db")
            self.show_status(f"Gateway {name} rimosso")
        else:
            self.output(f"❌ Errore: {result.get('message', 'Sconosciuto')}")
            self.show_status(result.get("message", "Errore"), True)