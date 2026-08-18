"""
Reticulum View - TUTTI i comandi Reticulum
"""

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from wallet_backend import VERSION


class ReticulumView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Titolo
        title = QLabel("◈ RETICULUM")
        title.setObjectName("view_title")
        layout.addWidget(title)
        
        # Split orizzontale: sinistra (status) + destra (azioni)
        split = QHBoxLayout()
        
        # ======================== SINISTRA: STATUS ========================
        left = QVBoxLayout()
        
        status_group = QGroupBox("◈ STATO GATEWAY")
        status_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        status_layout = QFormLayout(status_group)
        
        self.name_label = QLabel("N/A")
        self.status_label = QLabel("?")
        self.gateway_id_label = QLabel("N/A")
        self.wallet_id_label = QLabel("N/A")
        self.peers_label = QLabel("?")
        self.announces_label = QLabel("?")
        self.tor_label = QLabel("?")
        self.internet_label = QLabel("?")
        
        status_layout.addRow("NOME:", self.name_label)
        status_layout.addRow("STATO:", self.status_label)
        status_layout.addRow("GATEWAY ID:", self.gateway_id_label)
        status_layout.addRow("WALLET ID:", self.wallet_id_label)
        status_layout.addRow("PEER CONOSCIUTI:", self.peers_label)
        status_layout.addRow("ANNOUNCE RICEVUTI:", self.announces_label)
        status_layout.addRow("TOR:", self.tor_label)
        status_layout.addRow("INTERNET:", self.internet_label)
        
        left.addWidget(status_group)
        
        # Bottoni di controllo gateway
        gw_btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("◈ AVVIA GATEWAY")
        self.start_btn.clicked.connect(self.start_gateway)
        self.stop_btn = QPushButton("◈ FERMA GATEWAY")
        self.stop_btn.clicked.connect(self.stop_gateway)
        gw_btn_layout.addWidget(self.start_btn)
        gw_btn_layout.addWidget(self.stop_btn)
        left.addLayout(gw_btn_layout)
        
        # Bottoni discovery
        disc_btn_layout = QHBoxLayout()
        self.discover_gw_btn = QPushButton("◈ SCOPRI GATEWAY")
        self.discover_gw_btn.clicked.connect(self.discover_gateways)
        self.discover_w_btn = QPushButton("◈ SCOPRI WALLET")
        self.discover_w_btn.clicked.connect(self.discover_wallets)
        disc_btn_layout.addWidget(self.discover_gw_btn)
        disc_btn_layout.addWidget(self.discover_w_btn)
        left.addLayout(disc_btn_layout)
        
        # Bottoni test
        test_btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("◈ TESTA TUTTI")
        self.test_btn.clicked.connect(self.test_all_gateways)
        self.best_btn = QPushButton("◈ MIGLIOR GATEWAY")
        self.best_btn.clicked.connect(self.best_gateway)
        test_btn_layout.addWidget(self.test_btn)
        test_btn_layout.addWidget(self.best_btn)
        left.addLayout(test_btn_layout)
        
        # Bottoni altri
        other_btn_layout = QHBoxLayout()
        self.metrics_btn = QPushButton("◈ PEER METRICHE")
        self.metrics_btn.clicked.connect(self.peer_metrics)
        self.request_btn = QPushButton("◈ RICHIEDI INFO")
        self.request_btn.clicked.connect(self.request_info)
        other_btn_layout.addWidget(self.metrics_btn)
        other_btn_layout.addWidget(self.request_btn)
        left.addLayout(other_btn_layout)
        
        # Rimuovi gateway
        rm_btn_layout = QHBoxLayout()
        self.remove_btn = QPushButton("◈ RIMUOVI GATEWAY")
        self.remove_btn.clicked.connect(self.remove_gateway)
        rm_btn_layout.addWidget(self.remove_btn)
        left.addLayout(rm_btn_layout)
        
        # Status messaggi
        self.status_label2 = QLabel()
        self.status_label2.setObjectName("status")
        self.status_label2.setWordWrap(True)
        left.addWidget(self.status_label2)
        
        left.addStretch()
        split.addLayout(left, 1)
        
        # ======================== DESTRA: OUTPUT / METRICHE ========================
        right = QVBoxLayout()
        
        # Output text area
        self.output_area = QTextEdit()
        self.output_area.setObjectName("output_area")
        self.output_area.setReadOnly(True)
        self.output_area.setFont(QFont("Courier New", 10))
        self.output_area.setMinimumHeight(400)
        right.addWidget(self.output_area)
        
        # Pulsante copia
        copy_btn = QPushButton("◈ COPIA OUTPUT")
        copy_btn.clicked.connect(self.copy_output)
        right.addWidget(copy_btn)
        
        split.addLayout(right, 2)
        layout.addLayout(split)
        
        # Carica status
        self.update_status()
        self.output("▶ PAX WALLET v" + VERSION + " - Reticulum Management")
        self.output("▶ Per aggiornare lo stato, usare i pulsanti qui sopra.")
    
    # ============================================================
    # UTILITY
    # ============================================================
    
    def output(self, text):
        """Aggiunge testo all'area di output"""
        self.output_area.append(text)
    
    def clear_output(self):
        """Pulisce l'area di output"""
        self.output_area.clear()
    
    def copy_output(self):
        """Copia l'output negli appunti"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.output_area.toPlainText())
        self.status_label2.setText("✅ Output copiato")
    
    def show_status(self, msg, is_error=False):
        """Mostra messaggio di stato"""
        if is_error:
            self.status_label2.setText(f"❌ {msg}")
        else:
            self.status_label2.setText(f"✅ {msg}")
    
    def update_status(self):
        """Aggiorna status gateway"""
        if not self.main.backend:
            return
        try:
            status = self.main.backend.get_gateway_status()
            if status.get("success"):
                s = status.get("status", {})
                self.name_label.setText(s.get("name", "N/A"))
                self.status_label.setText("✅ ATTIVO" if s.get("is_gateway") else "❌ FERMO")
                self.gateway_id_label.setText(s.get("gateway_address", "N/A")[:32] + "...")
                self.wallet_id_label.setText(s.get("wallet_address", "N/A")[:32] + "...")
                self.peers_label.setText(str(s.get("gateway_count", 0)))
                self.announces_label.setText(str(s.get("announces_received", 0)))
                self.tor_label.setText("🧅 ON" if s.get("use_tor") else "OFF")
                self.internet_label.setText("🌐 ON" if s.get("internet_on") else "📡 OFF")
                
                # Aggiorna stato gateway
                if s.get("is_gateway"):
                    self.start_btn.setEnabled(False)
                    self.stop_btn.setEnabled(True)
                else:
                    self.start_btn.setEnabled(True)
                    self.stop_btn.setEnabled(False)
            else:
                self.show_status(status.get("message", "Errore"), True)
        except Exception as e:
            self.show_status(f"Errore: {e}", True)
    
    # ============================================================
    # COMANDI GATEWAY
    # ============================================================
    
    def start_gateway(self):
        """Avvia gateway"""
        self.status_label2.setText("⏳ Avvio gateway...")
        result = self.main.backend.start_gateway()
        if result.get("success"):
            self.show_status("Gateway avviato")
            self.output("▶ ✅ Gateway avviato con successo")
        else:
            self.show_status(result.get("message", "Errore"), True)
            self.output(f"▶ ❌ Errore: {result.get('message', 'Sconosciuto')}")
        self.update_status()
    
    def stop_gateway(self):
        """Ferma gateway"""
        self.status_label2.setText("⏳ Fermo gateway...")
        result = self.main.backend.stop_gateway()
        if result.get("success"):
            self.show_status("Gateway fermato")
            self.output("▶ ✅ Gateway fermato")
        else:
            self.show_status(result.get("message", "Errore"), True)
            self.output(f"▶ ❌ Errore: {result.get('message', 'Sconosciuto')}")
        self.update_status()
    
    def discover_gateways(self):
        """Scopri gateway"""
        self.clear_output()
        self.status_label2.setText("⏳ Ricerca gateway...")
        self.output("▶ 🔍 CERCO GATEWAY SU RETICULUM...")
        self.output("=" * 60)
        
        result = self.main.backend.discover_gateways()
        if result.get("success"):
            gateways = result.get("gateways", [])
            self.show_status(f"Trovati {len(gateways)} gateway")
            self.output(f"▶ Trovati {len(gateways)} gateway:")
            for i, gw in enumerate(gateways, 1):
                name = gw.get('name', 'Sconosciuto')
                gw_id = gw.get('gateway_id', '?')
                hops = gw.get('hops', '?')
                self.output(f"  {i}. {name} ({gw_id[:16]}...) Hops:{hops}")
        else:
            self.show_status(result.get("message", "Errore"), True)
            self.output(f"▶ ❌ Errore: {result.get('message', 'Sconosciuto')}")
    
    def discover_wallets(self):
        """Scopri wallet"""
        self.clear_output()
        self.status_label2.setText("⏳ Ricerca wallet...")
        self.output("▶ 🔍 CERCO WALLET SU RETICULUM...")
        self.output("=" * 60)
        
        result = self.main.backend.discover_wallets()
        if result.get("success"):
            wallets = result.get("wallets", [])
            self.show_status(f"Trovati {len(wallets)} wallet")
            self.output(f"▶ Trovati {len(wallets)} wallet:")
            for i, w in enumerate(wallets, 1):
                name = w.get('name', 'Sconosciuto')
                w_id = w.get('wallet_id', '?')
                hops = w.get('hops', '?')
                self.output(f"  {i}. {name} ({w_id[:16]}...) Hops:{hops}")
        else:
            self.show_status(result.get("message", "Errore"), True)
            self.output(f"▶ ❌ Errore: {result.get('message', 'Sconosciuto')}")
    
    def test_all_gateways(self):
        """Testa tutti i gateway"""
        self.clear_output()
        self.status_label2.setText("⏳ Test in corso...")
        self.output("▶ 📡 TEST DI TUTTI I GATEWAY")
        self.output("=" * 60)
        self.output("▶ Questo aggiornerà i dati dei peer nel database.")
        
        result = self.main.backend.test_all_gateways()
        if result.get("success"):
            results = result.get("results", [])
            self.show_status(f"Test completato: {result.get('successful', 0)}/{result.get('tested', 0)} risposte")
            self.output(f"\n▶ Test completato: {result.get('successful', 0)}/{result.get('tested', 0)} gateway hanno risposto")
            self.output("\n📋 RISULTATI:")
            self.output("-" * 80)
            self.output(f"{'#':<3} {'Nome':<20} {'Stato':<15} {'Internet':<10} {'TOR':<8}")
            self.output("-" * 80)
            for r in results:
                stato = r.get('status', 'UNKNOWN')
                internet = "🌐 SI" if r.get('has_internet') else "📡 NO"
                tor = r.get('tor_status', '—')
                self.output(f"{r.get('idx', 0):<3} {r.get('name', 'UNKNOWN'):<20} {stato:<15} {internet:<10} {tor:<8}")
        else:
            self.show_status(result.get("message", "Errore"), True)
            self.output(f"▶ ❌ Errore: {result.get('message', 'Sconosciuto')}")
    
    def best_gateway(self):
        """Miglior gateway"""
        asset, ok = QInputDialog.getText(self, "Miglior Gateway", "Asset (es. RLUSD):")
        if not ok or not asset:
            return
        
        self.clear_output()
        self.status_label2.setText("⏳ Ricerca...")
        self.output(f"▶ 🏆 MIGLIOR GATEWAY PER {asset.upper()}")
        self.output("=" * 60)
        
        result = self.main.backend.get_best_gateway(asset)
        if result.get("success"):
            gw = result.get("gateway", {})
            if gw:
                self.show_status(f"Trovato: {gw.get('name', 'UNKNOWN')}")
                self.output(f"  Nome:           {gw.get('name', 'UNKNOWN')}")
                self.output(f"  Gateway ID:     {gw.get('gateway_id', 'N/A')}")
                self.output(f"  Hops:           {gw.get('hops', '?')}")
                self.output(f"  RTT:            {gw.get('latency_ms', '?')}ms")
                self.output(f"  Reputazione:    {gw.get('reputation', 50)}")
                self.output(f"  Affidabilità:   {gw.get('reliability', 0):.2f}")
                self.output(f"  Internet:       {'✅' if gw.get('has_internet') else '❌'}")
                self.output(f"  XRP:            {'✅' if gw.get('xrp_reachable') else '❌'} ({gw.get('xrp_latency_ms', '?')}ms)")
                self.output(f"  Stellar:        {'✅' if gw.get('stellar_reachable') else '❌'} ({gw.get('stellar_latency_ms', '?')}ms)")
                if gw.get('assets'):
                    self.output(f"  Assets:         {', '.join(gw.get('assets', []))}")
                if gw.get('fee') != 'N/A':
                    self.output(f"  Fee:            {gw.get('fee')} {gw.get('fee_asset', '')}")
            else:
                self.show_status(f"Nessun gateway trovato per {asset}", True)
                self.output(f"▶ ❌ Nessun gateway trovato per {asset}")
        else:
            self.show_status(result.get("message", "Errore"), True)
            self.output(f"▶ ❌ Errore: {result.get('message', 'Sconosciuto')}")
    
    def peer_metrics(self):
        """Peer metriche - TABELLA COMPLETA"""
        self.clear_output()
        self.status_label2.setText("⏳ Caricamento metriche...")
        self.output("▶ 📊 PEER METRICHE")
        self.output("=" * 100)
        
        result = self.main.backend.get_peer_metrics()
        if result.get("success"):
            peers = result.get("peers", [])
            stats = result.get("stats", {})
            
            if not peers:
                self.show_status("Nessun peer trovato")
                self.output("▶ Nessun peer disponibile")
                return
            
            self.show_status(f"Trovati {len(peers)} peer")
            
            # Intestazione tabella
            self.output(f"{'#':<3} {'Nome':<20} {'Score':<6} {'Rel':<6} {'Hops':<5} {'RTT':<8} {'XRP':<10} {'Stellar':<10} {'Internet':<9} {'TOR':<6}")
            self.output("-" * 100)
            
            for idx, p in enumerate(peers, 1):
                name = str(p.get('name', 'UNKNOWN'))[:16]
                sc = round(p.get('_score', 0))
                rel = round(p.get('reliability', 0), 2)
                hops = str(p.get('hops', '?'))
                rtt = f"{p.get('latency_ms', '?')}ms"
                xrp = "✅" if p.get('xrp_reachable') else "❌"
                stellar = "✅" if p.get('stellar_reachable') else "❌"
                internet = "🌐" if p.get('has_internet') else "📡"
                
                tor_enabled = p.get('tor_enabled', False)
                tor_reachable = p.get('tor_reachable', False)
                tor_str = "🧅✅" if (tor_enabled and tor_reachable) else "🧅❌" if tor_enabled else "—"
                
                self.output(f"{idx:<3} {name:<20} {sc:<6} {rel:<6} {hops:<5} {rtt:<8} {xrp:<10} {stellar:<10} {internet:<9} {tor_str:<6}")
            
            self.output("-" * 100)
            
            if stats:
                self.output(f"\n📊 Statistiche:")
                self.output(f"  Totale peer: {stats.get('total_peers', 0)}")
                self.output(f"  Online: {stats.get('online_peers', 0)}")
                if stats.get('tor_peers', 0) > 0:
                    self.output(f"  Gateway con TOR: {stats.get('tor_peers')}")
                if stats.get('xrp_peers', 0) > 0:
                    self.output(f"  Gateway con XRP: {stats.get('xrp_peers')}")
                if stats.get('stellar_peers', 0) > 0:
                    self.output(f"  Gateway con Stellar: {stats.get('stellar_peers')}")
                if stats.get('avg_latency_ms'):
                    self.output(f"  Latenza media: {round(stats.get('avg_latency_ms'), 0)}ms")
            
            if peers:
                b = peers[0]
                self.output(f"\n🏆 MIGLIOR PEER: {b.get('name', 'UNKNOWN')}")
                self.output(f"  Score: {round(b.get('_score', 0))} | Rel: {b.get('reliability', 0):.2f}")
                self.output(f"  XRP: {'✅' if b.get('xrp_reachable') else '❌'} | Stellar: {'✅' if b.get('stellar_reachable') else '❌'}")
                if b.get('assets'):
                    self.output(f"  Assets: {', '.join(b.get('assets', []))}")
        else:
            self.show_status(result.get("message", "Errore"), True)
            self.output(f"▶ ❌ Errore: {result.get('message', 'Sconosciuto')}")
    
    def request_info(self):
        """Richiedi info a un gateway specifico"""
        result = self.main.backend.discover_gateways()
        if not result.get("success"):
            self.show_status(result.get("message", "Errore"), True)
            return
        
        gateways = result.get("gateways", [])
        if not gateways:
            self.show_status("Nessun gateway trovato", True)
            return
        
        # Mostra lista e chiedi scelta
        items = [f"{gw.get('name', 'UNKNOWN')} ({gw.get('gateway_id', '?')[:16]}...)" for gw in gateways]
        choice, ok = QInputDialog.getItem(self, "Scegli Gateway", "Seleziona gateway:", items, 0, False)
        if not ok:
            return
        
        idx = items.index(choice)
        gateway_id = gateways[idx].get('gateway_id')
        
        self.clear_output()
        self.status_label2.setText("⏳ Richiesta info...")
        self.output(f"▶ 📡 RICHIEDO INFO A {gateways[idx].get('name', 'UNKNOWN')}")
        self.output("=" * 60)
        
        result = self.main.backend.request_gateway_info(gateway_id)
        if result.get("success"):
            peer = result.get("peer")
            if peer:
                self.show_status("Info ricevute")
                self.output(f"  Nome:           {peer.get('name', 'UNKNOWN')}")
                self.output(f"  Gateway ID:     {peer.get('gateway_id', 'N/A')}")
                self.output(f"  Hops:           {peer.get('hops', '?')}")
                self.output(f"  RTT:            {peer.get('latency_ms', '?')}ms")
                self.output(f"  Reputazione:    {peer.get('reputation', 50)}")
                self.output(f"  Internet:       {'✅' if peer.get('has_internet') else '❌'}")
                self.output(f"  XRP:            {'✅' if peer.get('xrp_reachable') else '❌'}")
                self.output(f"  Stellar:        {'✅' if peer.get('stellar_reachable') else '❌'}")
                self.output(f"  TOR:            {'✅' if peer.get('tor_reachable') else '❌'}")
                if peer.get('assets'):
                    self.output(f"  Assets:         {', '.join(peer.get('assets', []))}")
            else:
                self.show_status("Richiesta inviata, ma peer non trovato in cache")
                self.output("▶ Richiesta inviata, ma peer non trovato in cache")
        else:
            self.show_status(result.get("message", "Errore"), True)
            self.output(f"▶ ❌ Errore: {result.get('message', 'Sconosciuto')}")
    
    def remove_gateway(self):
        """Rimuovi gateway manualmente"""
        result = self.main.backend.discover_gateways()
        if not result.get("success"):
            self.show_status(result.get("message", "Errore"), True)
            return
        
        gateways = result.get("gateways", [])
        if not gateways:
            self.show_status("Nessun gateway trovato", True)
            return
        
        items = [f"{gw.get('name', 'UNKNOWN')} ({gw.get('gateway_id', '?')[:16]}...)" for gw in gateways]
        choice, ok = QInputDialog.getItem(self, "Rimuovi Gateway", "Seleziona gateway da rimuovere:", items, 0, False)
        if not ok:
            return
        
        idx = items.index(choice)
        gateway_id = gateways[idx].get('gateway_id')
        name = gateways[idx].get('name', 'UNKNOWN')
        
        confirm = QMessageBox.question(self, "Conferma", f"Rimuovere {name}?", QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        
        self.status_label2.setText("⏳ Rimozione...")
        result = self.main.backend.remove_gateway(gateway_id)
        if result.get("success"):
            self.show_status(f"Gateway {name} rimosso")
            self.output(f"▶ ✅ Gateway {name} rimosso")
            if result.get("removed_from_announce"):
                self.output("  ✅ Rimosso da announce_cache.db")
            if result.get("removed_from_peers"):
                self.output("  ✅ Rimosso da gateway_peers.db")
        else:
            self.show_status(result.get("message", "Errore"), True)
            self.output(f"▶ ❌ Errore: {result.get('message', 'Sconosciuto')}")