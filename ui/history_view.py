"""
History View - Storico transazioni con cache, filtri e feedback
"""

import base64
from datetime import datetime
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from .base_view import ListViewWithDetail


class HistoryView(ListViewWithDetail):
    def __init__(self, main_window):
        self.main = main_window
        super().__init__()
        self.transactions = []
        self.filtered_transactions = []
        self.is_loading = False
        self.setup_controls()
        
        self.tx_list = QListWidget()
        self.tx_list.setObjectName("tx_list")
        self.tx_list.itemClicked.connect(self.on_item_clicked)
        self.tx_list.setFont(QFont("Courier New", 10))
        self.output_layout.addWidget(self.tx_list)
        
        self.tx_list.addItem("📭 Clicca 'AGGIORNA' per caricare lo storico")

    def setup_controls(self):
        layout = self.controls_layout

        title = QLabel("◈ STORICO TRANSAZIONI")
        title.setObjectName("view_title")
        layout.addWidget(title)

        row = QHBoxLayout()
        limit_label = QLabel("LIMIT:")
        row.addWidget(limit_label)
        
        self.limit_input = QSpinBox()
        self.limit_input.setRange(5, 100)
        self.limit_input.setValue(10)
        row.addWidget(self.limit_input)
        
        self.refresh_btn = QPushButton("◈ AGGIORNA")
        self.refresh_btn.clicked.connect(self.load_history)
        row.addWidget(self.refresh_btn)
        row.addStretch()
        layout.addLayout(row)

        row2 = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Cerca (memo/indirizzo)...")
        self.search_input.textChanged.connect(self.apply_filters)
        row2.addWidget(self.search_input)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Tutte", "RICEVUTO", "INVIATO", "ALTRO"])
        self.filter_combo.currentTextChanged.connect(self.apply_filters)
        row2.addWidget(self.filter_combo)
        
        clear_btn = QPushButton("◈ PULISCI")
        clear_btn.clicked.connect(self.clear_filters)
        row2.addWidget(clear_btn)
        layout.addLayout(row2)

        self.status_layout = QHBoxLayout()
        self.loading_indicator = QLabel("●")
        self.loading_indicator.hide()
        self.status_layout.addWidget(self.loading_indicator)
        
        self.status_label = QLabel("Pronto")
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addStretch()
        
        self.count_label = QLabel("")
        self.status_layout.addWidget(self.count_label)
        
        layout.addLayout(self.status_layout)

    def set_loading(self, loading):
        self.is_loading = loading
        if loading:
            self.loading_indicator.show()
            self.refresh_btn.setEnabled(False)
            self.status_label.setText("⏳ Caricamento...")
        else:
            self.loading_indicator.hide()
            self.refresh_btn.setEnabled(True)
            self.status_label.setText("✅ Pronto")

    def load_history(self):
        if self.is_loading:
            return
        
        self.set_loading(True)
        self.tx_list.clear()
        self.tx_list.addItem("⏳ Caricamento in corso...")
        
        QTimer.singleShot(100, self._do_load_history)

    def _do_load_history(self):
        try:
            if not self.main.backend:
                self.tx_list.clear()
                self.tx_list.addItem("❌ Backend non disponibile")
                self.set_loading(False)
                return

            limit = self.limit_input.value()
            result = self.main.backend.get_history(limit)

            if not result.get("success"):
                self.tx_list.clear()
                self.tx_list.addItem(f"❌ {result.get('message', 'Errore')}")
                self.set_loading(False)
                return

            self.transactions = result.get("transactions", [])
            self.address = result.get("address", "")
            
            self.apply_filters()
            self.status_label.setText(f"✅ Caricato: {len(self.transactions)} transazioni")
            
        except Exception as e:
            self.tx_list.clear()
            self.tx_list.addItem(f"⚠️ Errore: {str(e)[:50]}")
            self.status_label.setText(f"❌ Errore: {str(e)[:30]}")
        finally:
            self.set_loading(False)

    def apply_filters(self):
        if not self.transactions:
            self.tx_list.clear()
            self.tx_list.addItem("📭 Carica prima i dati con 'AGGIORNA'")
            self.count_label.setText("")
            return
        
        filter_type = self.filter_combo.currentText()
        search = self.search_input.text().strip().lower()
        
        filtered = []
        for tx_data in self.transactions:
            tx = tx_data.get("tx_json", {})
            sender = tx.get("Account", "unknown")
            destination = tx.get("Destination", "unknown")
            memo = self._parse_memo(tx).lower()
            amount = self._parse_amount(tx).lower()
            tx_hash = tx_data.get('hash', '').lower()
            
            if filter_type == "RICEVUTO" and destination != self.address:
                continue
            if filter_type == "INVIATO" and sender != self.address:
                continue
            if filter_type == "ALTRO" and (destination == self.address or sender == self.address):
                continue
            
            if search:
                search_match = (
                    search in memo or
                    search in sender.lower() or
                    search in destination.lower() or
                    search in tx_hash or
                    search in amount
                )
                if not search_match:
                    continue
            
            filtered.append(tx_data)

        self.filtered_transactions = filtered
        self._display_transactions(filtered)
        
        total = len(self.transactions)
        shown = len(filtered)
        if total == shown:
            self.count_label.setText(f"📊 {shown} transazioni")
        else:
            self.count_label.setText(f"📊 {shown} / {total} transazioni")

    def _display_transactions(self, transactions):
        self.tx_list.clear()
        
        if not transactions:
            self.tx_list.addItem("📭 Nessuna transazione trovata")
            return

        header = f"{'#':<3} {'Data/Ora':<20} {'Tipo':<10} {'Importo':<18} {'Fee':<10} {'Da/A':<70} {'Memo':<25}"
        self.tx_list.addItem("=" * 170)
        self.tx_list.addItem(header)
        self.tx_list.addItem("-" * 170)

        for idx, tx_data in enumerate(transactions, 1):
            tx = tx_data.get("tx_json", {})
            if not tx:
                continue

            date_str = self._parse_date(tx, tx_data)
            amount_str = self._parse_amount(tx)
            direction, da_a = self._parse_direction(tx, self.address)
            fee_str = self._parse_fee(tx)
            memo_str = self._parse_memo(tx)[:25]

            line = f"{idx:<3} {date_str[:19]:<20} {direction:<10} {amount_str:<18} {fee_str:<10} {da_a:<70} {memo_str:<25}"
            self.tx_list.addItem(line)

        self.tx_list.addItem("=" * 170)

    def clear_filters(self):
        self.search_input.clear()
        self.filter_combo.setCurrentIndex(0)
        self.apply_filters()
        self.status_label.setText("✅ Filtri puliti")

    def _parse_date(self, tx, tx_data):
        if "date" in tx:
            try:
                ledger_time = tx.get("date", 0)
                if ledger_time:
                    date_obj = datetime.fromtimestamp(ledger_time + 946684800)
                    return date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        if "close_time_iso" in tx_data:
            try:
                return tx_data.get("close_time_iso", "").replace("T", " ").replace("Z", "")[:19]
            except:
                pass
        return "N/A"

    def _parse_amount(self, tx):
        amount = tx.get("Amount", tx.get("DeliverMax", "0"))
        if isinstance(amount, dict):
            token_value = amount.get('value', '0')
            token_currency = amount.get('currency', '???')
            
            # Decodifica il codice esadecimale del token
            if len(token_currency) > 3:
                try:
                    bytes_data = bytes.fromhex(token_currency)
                    # Rimuovi zeri finali
                    while bytes_data and bytes_data[-1] == 0:
                        bytes_data = bytes_data[:-1]
                    decoded = bytes_data.decode('utf-8', errors='ignore').strip()
                    if decoded and all(32 <= ord(c) <= 126 for c in decoded):
                        token_currency = decoded
                except:
                    pass
            
            try:
                return f"{float(token_value):.6f} {token_currency}"
            except:
                return f"{token_value[:8]} {token_currency}"
        try:
            return f"{int(amount) / 1_000_000:.6f} XRP"
        except:
            return f"{amount} drops"

    def _parse_direction(self, tx, address):
        sender = tx.get("Account", "unknown")
        destination = tx.get("Destination", "unknown")
        if destination == address:
            return "RICEVUTO", f"Da: {sender}"
        elif sender == address:
            return "INVIATO", f"A: {destination}"
        else:
            return "ALTRO", f"{sender} → {destination}"

    def _parse_fee(self, tx):
        fee_drops = tx.get("Fee", "0")
        try:
            return f"{int(fee_drops) / 1_000_000:.6f}"
        except:
            return fee_drops

    def _parse_memo(self, tx):
        memos = tx.get("Memos", [])
        if memos:
            try:
                memo_dict = memos[0].get("Memo", {})
                memo_data = memo_dict.get("MemoData", "")
                if memo_data:
                    try:
                        memo_bytes = bytes.fromhex(memo_data)
                        memo_str = memo_bytes.decode('utf-8', errors='ignore')
                    except:
                        try:
                            while len(memo_data) % 4 != 0:
                                memo_data += '='
                            memo_bytes = base64.b64decode(memo_data)
                            memo_str = memo_bytes.decode('utf-8', errors='ignore')
                        except:
                            memo_str = memo_data
                    memo_str = ''.join(c for c in memo_str if c.isprintable() or c == ' ')
                    return memo_str.strip()
            except:
                pass
        return ""

    def on_item_clicked(self, item):
        if not hasattr(self, 'filtered_transactions'):
            return
        idx = self.tx_list.currentRow() - 3
        if idx < 0 or idx >= len(self.filtered_transactions):
            return
        tx_data = self.filtered_transactions[idx]
        tx = tx_data.get("tx_json", {})
        
        html = f"""
        <b>Hash:</b> {tx_data.get('hash', 'N/A')}<br>
        <b>Da:</b> {tx.get('Account', 'N/A')}<br>
        <b>A:</b> {tx.get('Destination', 'N/A')}<br>
        <b>Importo:</b> {self._parse_amount(tx)}<br>
        <b>Fee:</b> {self._parse_fee(tx)} XRP<br>
        <b>Memo:</b> {self._parse_memo(tx)}<br>
        <b>Ledger:</b> {tx_data.get('ledger_index', 'N/A')}<br>
        <b>Data:</b> {tx_data.get('close_time_iso', 'N/A')}
        """
        self.set_detail_html(html)