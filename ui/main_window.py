"""
PAX Wallet - Main Window
LOGICA: IDENTICA ALLA CLI - NESSUNA richiesta automatica!
L'utente decide cosa fare, cliccando sui pulsanti.
TUTTE le chiamate al backend usano gli STESSI metodi della CLI.
"""

import json
import time
import base64
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from wallet_backend import WalletBackend, create_backend, VERSION, format_time_ago
from .base_view import ListViewWithDetail
from .history_view import HistoryView
from .reticulum_view import ReticulumView
from .address_book_view import AddressBookView

# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PAX WALLET")
        self.setMinimumSize(1200, 750)
        
        self.backend = None
        self._password = None
        
        self.settings = QSettings("HOPE", "PAX Wallet")
        
        self.show_unlock()
    
    def show_unlock(self):
        self.unlock_widget = UnlockWidget(self)
        self.setCentralWidget(self.unlock_widget)
        self.unlock_widget.unlock_signal.connect(self.on_unlocked)
    
    def on_unlocked(self, backend, password):
        self.backend = backend
        self._password = password
        self.setup_main_ui()
    
    def setup_main_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.sidebar = self.create_sidebar()
        main_layout.addWidget(self.sidebar, 1)
        
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("content_stack")
        main_layout.addWidget(self.content_stack, 4)
        
        self.dashboard_view = DashboardView(self)
        self.send_view = SendView(self)
        self.history_view = HistoryView(self)
        self.wallet_view = WalletView(self)
        self.reticulum_view = ReticulumView(self)
        self.address_book_view = AddressBookView(self)
        self.settings_view = SettingsView(self)
        
        self.content_stack.addWidget(self.dashboard_view)
        self.content_stack.addWidget(self.send_view)
        self.content_stack.addWidget(self.history_view)
        self.content_stack.addWidget(self.wallet_view)
        self.content_stack.addWidget(self.reticulum_view)
        self.content_stack.addWidget(self.address_book_view)
        self.content_stack.addWidget(self.settings_view)
        
        self.content_stack.setCurrentIndex(0)
        self.highlight_sidebar(0)
    
    def create_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(5)
        
        logo = QLabel("⿻ PAX WALLET")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)
        layout.addSpacing(20)
        
        self.wallet_name_label = QLabel("Nessun wallet")
        self.wallet_name_label.setObjectName("wallet_name")
        self.balance_label = QLabel("--.--")
        self.balance_label.setObjectName("balance")
        
        wallet_info = QWidget()
        wallet_info.setObjectName("wallet_info")
        wi_layout = QVBoxLayout(wallet_info)
        wi_layout.addWidget(self.wallet_name_label)
        wi_layout.addWidget(self.balance_label)
        layout.addWidget(wallet_info)
        layout.addSpacing(20)
        
        nav_items = [
            ("◈ Dashboard", 0),
            ("◈ Invia", 1),
            ("◈ Storico", 2),
            ("◈ Wallet", 3),
            ("◈ Reticulum", 4),
            ("◈ Rubrica", 5),
            ("◈ Impostazioni", 6),
        ]
        
        self.nav_buttons = []
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("nav_button")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, i=index: self.switch_view(i))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        layout.addStretch()
        
        version = QLabel(f"v{VERSION}")
        version.setObjectName("version")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)
        
        return sidebar
    
    def switch_view(self, index):
        self.content_stack.setCurrentIndex(index)
        self.highlight_sidebar(index)
    
    def highlight_sidebar(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
    
    def reset_all_views(self):
        if hasattr(self, 'dashboard_view'):
            self.dashboard_view.balance_label.setText("--.-- XRP")
            self.dashboard_view.address_label.setText("")
            self.dashboard_view.tx_list.clear()
            self.dashboard_view.tx_list.addItem("Premi 'AGGIORNA' per caricare")
        
        if hasattr(self, 'history_view'):
            self.history_view.tx_list.clear()
            self.history_view.transactions = []
            self.history_view.filtered_transactions = []
            self.history_view.tx_list.addItem("📭 Clicca 'AGGIORNA' per caricare lo storico")
            self.history_view.clear_detail()
            self.history_view.count_label.setText("")
            self.history_view.status_label.setText("Pronto")
        
        if hasattr(self, 'reticulum_view'):
            self.reticulum_view.clear_output()
            self.reticulum_view.output("▶ PAX WALLET - Reticulum Management")
            self.reticulum_view.output("▶ Usa i pulsanti qui sopra per le operazioni.")
            self.reticulum_view.clear_detail()
            self.reticulum_view.status_label2.setText("")
        
        if hasattr(self, 'wallet_view'):
            self.wallet_view.wallet_list.clear()
            self.wallet_view.wallet_list.addItem("Clicca 'AGGIORNA' per caricare")
            self.wallet_view.clear_detail()
            self.wallet_view.status_label.setText("")
        
        if hasattr(self, 'address_book_view'):
            self.address_book_view.refresh_contacts()
        
        self.balance_label.setText("--.--")
        self.update_wallet_name()

    def apply_skin(self, skin_name: str):
        style_path = Path(__file__).parent.parent / "ui" / "resources" / "styles" / f"{skin_name}.qss"
        if style_path.exists():
            with open(style_path, 'r') as f:
                QApplication.instance().setStyleSheet(f.read())
            self.settings.setValue("skin", skin_name)
            return True
        return False
    
    def get_available_skins(self):
        styles_dir = Path(__file__).parent.parent / "ui" / "resources" / "styles"
        skins = []
        if styles_dir.exists():
            for f in styles_dir.glob("style_*.qss"):
                name = f.stem
                skins.append(name)
        if not skins:
            skins = ["style_dark"]
        return skins
    
    def update_wallet_name(self):
        if not self.backend:
            return
        try:
            active = self.backend.get_active_wallet()
            if active.get("name"):
                self.wallet_name_label.setText(f"{active['name']} ({active['network'].upper()})")
            else:
                self.wallet_name_label.setText("Nessun wallet")
                self.balance_label.setText("--.--")
        except Exception as e:
            self.wallet_name_label.setText("Errore")
    
    def update_balance_label(self, balance, crypto):
        if not self.backend:
            return
        try:
            self.balance_label.setText(f"{balance:.6f} {crypto}")
        except Exception as e:
            self.balance_label.setText(f"⚠️ Errore: {str(e)[:20]}")


# ============================================================
# UNLOCK WIDGET
# ============================================================

class UnlockWidget(QWidget):
    unlock_signal = Signal(object, object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        
        logo = QLabel("⿻ PAX WALLET")
        logo.setObjectName("unlock_logo")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)
        
        desc = QLabel("> INSERT PASSWORD TO UNLOCK")
        desc.setObjectName("unlock_desc")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("> password")
        self.password_input.setFixedWidth(300)
        self.password_input.returnPressed.connect(self.unlock)
        layout.addWidget(self.password_input, alignment=Qt.AlignCenter)
        
        self.unlock_btn = QPushButton("◈ UNLOCK")
        self.unlock_btn.setFixedWidth(300)
        self.unlock_btn.clicked.connect(self.unlock)
        layout.addWidget(self.unlock_btn, alignment=Qt.AlignCenter)
        
        self.error_label = QLabel()
        self.error_label.setObjectName("error")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.hide()
        layout.addWidget(self.error_label)
    
    def unlock(self):
        password = self.password_input.text()
        if not password:
            self.show_error("> ERROR: PASSWORD CANNOT BE EMPTY")
            return
        
        backend = create_backend(password)
        backend.init()
        
        active = backend.get_active_wallet()
        if active.get("name") and active.get("loaded"):
            self.error_label.hide()
            self.unlock_signal.emit(backend, password)
        else:
            self.show_error("> ERROR: INCORRECT PASSWORD")
            self.password_input.clear()
            self.password_input.setFocus()
    
    def show_error(self, msg):
        self.error_label.setText(f"❌ {msg}")
        self.error_label.show()


# ============================================================
# DASHBOARD VIEW
# ============================================================

class DashboardView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        header = QHBoxLayout()
        title = QLabel("◈ DASHBOARD")
        title.setObjectName("view_title")
        header.addWidget(title)
        header.addStretch()
        
        refresh_btn = QPushButton("◈ AGGIORNA")
        refresh_btn.setObjectName("quick_action")
        refresh_btn.clicked.connect(self.update_data)
        header.addWidget(refresh_btn)
        
        exit_btn = QPushButton("✕ ESCI")
        exit_btn.setObjectName("exit_btn")
        exit_btn.setFixedWidth(80)
        exit_btn.clicked.connect(self.exit_app)
        header.addWidget(exit_btn)
        
        layout.addLayout(header)
        
        welcome_label = QLabel("Benvenuto in PAX Wallet. Premi 'AGGIORNA' per caricare i tuoi dati.")
        welcome_label.setObjectName("welcome_label")
        welcome_label.setWordWrap(True)
        layout.addWidget(welcome_label)
        
        balance_widget = QWidget()
        balance_widget.setObjectName("balance_card")
        bal_layout = QVBoxLayout(balance_widget)
        
        self.balance_label = QLabel("--.-- XRP")
        self.balance_label.setObjectName("big_balance")
        bal_layout.addWidget(self.balance_label)
        
        self.address_label = QLabel("")
        self.address_label.setObjectName("usd_balance")
        bal_layout.addWidget(self.address_label)
        
        layout.addWidget(balance_widget)
        
        actions = QHBoxLayout()
        for text, index in [
            ("◈ INVIA", 1),
            ("◈ STORICO", 2),
            ("◈ WALLET", 3),
        ]:
            btn = QPushButton(text)
            btn.setObjectName("quick_action")
            btn.clicked.connect(lambda checked, i=index: self.main.switch_view(i))
            actions.addWidget(btn)
        layout.addLayout(actions)
        
        tx_label = QLabel("◈ ULTIME TRANSAZIONI")
        tx_label.setObjectName("section_title")
        layout.addWidget(tx_label)
        
        self.tx_list = QListWidget()
        self.tx_list.setObjectName("tx_list")
        self.tx_list.addItem("Premi 'AGGIORNA' per caricare")
        layout.addWidget(self.tx_list, 1)
    
    def update_data(self):
        if not self.main.backend:
            self.balance_label.setText("⚠️ Backend non disponibile")
            return
        
        try:
            result = self.main.backend.get_balance()
            if result.get("success"):
                balance = result.get('balance', 0)
                crypto = result.get('crypto', 'XRP')
                self.balance_label.setText(f"{balance:.6f} {crypto}")
                self.main.update_balance_label(balance, crypto)
            else:
                self.balance_label.setText(f"❌ {result.get('message', 'Errore')}")
        except Exception as e:
            self.balance_label.setText(f"⚠️ Errore: {str(e)[:30]}")
        
        try:
            result = self.main.backend.get_address()
            if result.get("success"):
                self.address_label.setText(f"📤 {result.get('address', 'N/A')}")
        except:
            pass
        
        try:
            result = self.main.backend.get_history(5)
            self.tx_list.clear()
            
            if not result.get("success"):
                self.tx_list.addItem(f"❌ {result.get('message', 'Errore')}")
                return
            
            transactions = result.get("transactions", [])
            if not transactions:
                self.tx_list.addItem("📭 Nessuna transazione recente")
                return
            
            address = result.get("address", "")
            
            header = f"{'#':<3} {'Data/Ora':<20} {'Tipo':<10} {'Importo':<18} {'Fee':<14} {'Da/A':<70} {'Memo':<30}"
            self.tx_list.addItem("=" * 180)
            self.tx_list.addItem(header)
            self.tx_list.addItem("-" * 180)
            
            for idx, tx_data in enumerate(transactions, 1):
                tx = tx_data.get("tx_json", {})
                if not tx:
                    continue
                
                date_str = self._parse_date(tx, tx_data)
                amount_str = self._parse_amount(tx)
                direction, da_a = self._parse_direction(tx, address)
                fee_str = self._parse_fee(tx)
                memo_str = self._parse_memo(tx)
                
                line = f"{idx:<3} {date_str[:19]:<20} {direction:<10} {amount_str:<18} {fee_str:<14} {da_a:<70} {memo_str:<30}"
                self.tx_list.addItem(line)
            
            self.tx_list.addItem("=" * 180)
            self.tx_list.addItem(f"📊 Ultime {len(transactions)} transazioni")
            
        except Exception as e:
            self.tx_list.clear()
            self.tx_list.addItem(f"⚠️ Errore: {str(e)[:30]}")
    
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
                memo_data = memos[0].get("Memo", {}).get("MemoData", "")
                if memo_data:
                    try:
                        memo_bytes = bytes.fromhex(memo_data)
                        memo_str = memo_bytes.decode('utf-8', errors='ignore')[:28]
                    except:
                        try:
                            while len(memo_data) % 4 != 0:
                                memo_data += '='
                            memo_bytes = base64.b64decode(memo_data)
                            memo_str = memo_bytes.decode('utf-8', errors='ignore')[:28]
                        except:
                            memo_str = memo_data[:28]
                    return ''.join(c for c in memo_str if c.isprintable() or c == ' ')
            except:
                pass
        return ""
    
    def exit_app(self):
        reply = QMessageBox.question(
            self, 
            "Conferma", 
            "Sei sicuro di voler uscire?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.main.close()


# ============================================================
# SEND VIEW
# ============================================================

class SendView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        title = QLabel("◈ INVIA PAGAMENTO")
        title.setObjectName("view_title")
        layout.addWidget(title)
        
        form = QWidget()
        form_layout = QFormLayout(form)
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("> r... o G...")
        form_layout.addRow("ADDRESS:", self.address_input)
        
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("> 0.00")
        form_layout.addRow("AMOUNT:", self.amount_input)
        
        self.memo_input = QLineEdit()
        self.memo_input.setPlaceholderText("> memo (optional)")
        form_layout.addRow("MEMO:", self.memo_input)
        
        layout.addWidget(form)
        
        net_group = QGroupBox("◈ MODALITÀ INVIO")
        net_layout = QHBoxLayout(net_group)
        self.internet_radio = QRadioButton("◈ INTERNET")
        self.reticulum_radio = QRadioButton("◈ RETICULUM")
        self.reticulum_radio.setChecked(True)
        net_layout.addWidget(self.internet_radio)
        net_layout.addWidget(self.reticulum_radio)
        layout.addWidget(net_group)
        
        self.send_btn = QPushButton("◈ INVIA")
        self.send_btn.setObjectName("send_btn")
        self.send_btn.clicked.connect(self.send_payment)
        layout.addWidget(self.send_btn)
        
        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def send_payment(self):
        address = self.address_input.text().strip()
        if not address:
            self.status_label.setText("❌ > INSERT ADDRESS")
            return
        
        try:
            amount = float(self.amount_input.text().strip())
        except:
            self.status_label.setText("❌ > INVALID AMOUNT")
            return
        
        memo = self.memo_input.text().strip()
        
        self.send_btn.setEnabled(False)
        self.status_label.setText("⏳ > SENDING...")
        
        try:
            result = self.main.backend.send_payment(address, amount, memo)
            if result.get("success"):
                self.status_label.setText(f"✅ > SENT! HASH: {result.get('tx_hash', 'N/A')[:16]}...")
                self.address_input.clear()
                self.amount_input.clear()
                self.memo_input.clear()
            else:
                self.status_label.setText(f"❌ > ERROR: {result.get('message', 'UNKNOWN')}")
        except Exception as e:
            self.status_label.setText(f"❌ > ERROR: {str(e)[:50]}")
        
        self.send_btn.setEnabled(True)


# ============================================================
# WALLET VIEW
# ============================================================

class WalletView(ListViewWithDetail):
    def __init__(self, main_window):
        self.main = main_window
        super().__init__()
        self.wallets = []
        self.setup_controls()
        self.wallet_list = QListWidget()
        self.wallet_list.setObjectName("wallet_list")
        self.wallet_list.itemClicked.connect(self.on_item_clicked)
        self.wallet_list.setFont(QFont("Courier New", 10))
        self.output_layout.addWidget(self.wallet_list)
        self.refresh_list()

    def setup_controls(self):
        layout = self.controls_layout

        title = QLabel("◈ GESTIONE WALLET")
        title.setObjectName("view_title")
        layout.addWidget(title)

        row = QHBoxLayout()
        refresh_btn = QPushButton("◈ AGGIORNA")
        refresh_btn.clicked.connect(self.refresh_list)
        row.addWidget(refresh_btn)
        row.addStretch()
        layout.addLayout(row)

        btn_layout = QHBoxLayout()
        for text, callback in [
            ("◈ CREA", self.create_wallet),
            ("◈ IMPORTA", self.import_wallet),
            ("◈ CAMBIA", self.switch_wallet),
            ("◈ RIMUOVI", self.remove_wallet),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        row2 = QHBoxLayout()
        for text, callback in [
            ("◈ DERIVA", self.derive_addresses),
            ("◈ INFO", self.wallet_info),
            ("◈ FUND TESTNET", self.fund_testnet),
            ("◈ ESPORTA", self.export_wallet),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            row2.addWidget(btn)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        net_label = QLabel("RETE:")
        row3.addWidget(net_label)
        
        self.network_combo = QComboBox()
        self.network_combo.addItems(["testnet", "mainnet"])
        self.network_combo.currentTextChanged.connect(self.change_network)
        row3.addWidget(self.network_combo)
        
        row3.addSpacing(20)
        
        crypto_label = QLabel("CRYPTO:")
        row3.addWidget(crypto_label)
        
        self.crypto_combo = QComboBox()
        self.crypto_combo.addItems(["XRP", "XLM"])
        self.crypto_combo.currentTextChanged.connect(self.change_crypto)
        row3.addWidget(self.crypto_combo)
        
        row3.addStretch()
        layout.addLayout(row3)

        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def refresh_list(self):
        self.wallet_list.clear()
        if not self.main.backend:
            self.wallet_list.addItem("⚠️ Backend non disponibile")
            return

        try:
            self.wallets = self.main.backend.list_wallets()
            if not self.wallets:
                self.wallet_list.addItem("Nessun wallet salvato")
                return
            for w in self.wallets:
                marker = "▶ " if w.get("is_active") else "  "
                self.wallet_list.addItem(f"{marker}{w['name']} ({w['crypto']} - {w['network']})")
            self.update_network_status()
            self.show_status(f"{len(self.wallets)} wallet trovati")
        except Exception as e:
            self.wallet_list.addItem(f"⚠️ Errore: {e}")
            self.show_status(f"Errore: {e}", True)

    def update_network_status(self):
        if not self.main.backend:
            return
        try:
            manager = self.main.backend.wallet._xrp_manager
            self.network_combo.setCurrentText(manager.network)
            self.crypto_combo.setCurrentText(manager.crypto_type)
        except:
            pass

    def get_selected_wallet(self):
        current = self.wallet_list.currentItem()
        if not current:
            return None
        text = current.text()
        if text.startswith("▶ "):
            text = text[2:]
        text = text.lstrip()
        pos = text.find(" (")
        if pos > 0:
            return text[:pos]
        return text

    def show_status(self, msg, is_error=False):
        if is_error:
            self.status_label.setText(f"❌ {msg}")
        else:
            self.status_label.setText(f"✅ {msg}")

    def on_item_clicked(self, item):
        name = self.get_selected_wallet()
        if not name:
            return
        for w in self.wallets:
            if w.get('name') == name:
                html = f"""
                <b>Nome:</b> {w.get('name', 'N/A')}<br>
                <b>Crypto:</b> {w.get('crypto', 'N/A')}<br>
                <b>Network:</b> {w.get('network', 'N/A').upper()}<br>
                <b>Address:</b> {w.get('address', 'N/A')}<br>
                <b>Status:</b> {'✅ Attivo' if w.get('is_active') else '⏳ Inattivo'}
                """
                self.set_detail_html(html)
                break

    def create_wallet(self):
        name, ok = QInputDialog.getText(self, "Crea Wallet", "Nome wallet:")
        if not ok or not name:
            return
        
        crypto, ok = QInputDialog.getItem(self, "Crypto", "Seleziona crypto:", ["XRP", "XLM"], 0, False)
        if not ok:
            return
        
        network, ok = QInputDialog.getItem(self, "Rete", "Seleziona rete:", ["testnet", "mainnet"], 0, False)
        if not ok:
            return
        
        strength_choice, ok = QInputDialog.getItem(self, "Sicurezza", "Numero parole:", ["12", "24"], 0, False)
        strength = 128 if strength_choice == "12" else 256
        
        passphrase, ok = QInputDialog.getText(self, "Passphrase", "Passphrase (opzionale - Invio per saltare):")
        if not ok:
            return
        
        result = self.main.backend.create_wallet(name, crypto, network, strength, passphrase)
        if result.get("success"):
            self.show_status(f"Wallet '{name}' creato! Address: {result.get('address', 'N/A')[:16]}...")
            self.refresh_list()
            self.main.update_wallet_name()
            self.main.reset_all_views()
        else:
            self.show_status(result.get("error", "Errore sconosciuto"), True)

    def import_wallet(self):
        seed, ok = QInputDialog.getText(self, "Importa Wallet", "Seed/Mnemonic/Numeri:")
        if not ok or not seed:
            return
        
        name, ok = QInputDialog.getText(self, "Nome", "Nome wallet (imported):")
        if not ok:
            return
        if not name:
            name = "imported"
        
        crypto, ok = QInputDialog.getItem(self, "Crypto", "Seleziona crypto:", ["auto", "XRP", "XLM"], 0, False)
        if not ok:
            return
        
        network, ok = QInputDialog.getItem(self, "Rete", "Seleziona rete:", ["testnet", "mainnet"], 0, False)
        if not ok:
            return
        
        words = seed.strip().split()
        is_mnemonic = len(words) in [12, 24]
        passphrase = ""
        if is_mnemonic:
            passphrase, ok = QInputDialog.getText(self, "Passphrase", "Passphrase (opzionale - Invio per saltare):")
            if not ok:
                return
        
        result = self.main.backend.import_wallet(seed, name, crypto, network, passphrase)
        if result.get("success"):
            self.show_status(f"Wallet '{name}' importato! Address: {result.get('address', 'N/A')[:16]}...")
            self.refresh_list()
            self.main.update_wallet_name()
            self.main.reset_all_views()
        else:
            self.show_status(result.get("error", "Errore sconosciuto"), True)

    def remove_wallet(self):
        name = self.get_selected_wallet()
        if not name:
            self.show_status("Seleziona un wallet dalla lista", True)
            return
        
        active = self.main.backend.get_active_wallet()
        if active.get("name") == name:
            self.show_status("Non puoi rimuovere il wallet attivo", True)
            return
        
        confirm = QMessageBox.question(self, "Conferma", f"Rimuovere '{name}'?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            result = self.main.backend.remove_wallet(name)
            if result.get("success"):
                self.show_status(f"Wallet '{name}' rimosso")
                self.refresh_list()
                self.main.update_wallet_name()
                self.main.reset_all_views()
            else:
                self.show_status(result.get("message", "Errore sconosciuto"), True)

    def switch_wallet(self):
        name = self.get_selected_wallet()
        if not name:
            self.show_status("Seleziona un wallet dalla lista", True)
            return
        
        result = self.main.backend.switch_wallet(name)
        if result.get("success"):
            self.show_status(f"Wallet cambiato a: {name}")
            self.refresh_list()
            self.main.reset_all_views()
        else:
            self.show_status(result.get("message", "Errore sconosciuto"), True)

    def derive_addresses(self):
        keyword, ok = QInputDialog.getText(self, "Deriva Indirizzi", "Keyword (default):")
        if not ok:
            return
        if not keyword:
            keyword = "default"
        
        count, ok = QInputDialog.getInt(self, "Deriva Indirizzi", "Numero:", 5, 1, 20, 1)
        if not ok:
            return
        
        result = self.main.backend.derive_addresses(keyword, count)
        if not result.get("success"):
            self.show_status(result.get("message", "Errore"), True)
            return
        
        addresses = result.get("addresses", [])
        if not addresses:
            self.show_status("Nessun indirizzo derivato", True)
            return
        
        msg = f"📤 INDIRIZZI DERIVATI ({keyword}: 0-{len(addresses)-1})\n"
        msg += "=" * 80 + "\n"
        for addr in addresses:
            idx = addr.get("index", 0)
            address = addr.get("address", "N/A")
            priv = addr.get("private_key", "")
            pub = addr.get("public_key", "")
            msg += f"{idx}: {address}\n"
            msg += f"   Priv: {priv[:30]}...\n"
            msg += f"   Pub:  {pub[:30]}...\n\n"
        
        QMessageBox.information(self, "Indirizzi Derivati", msg)
        self.show_status(f"Derivati {len(addresses)} indirizzi")

    def wallet_info(self):
        result = self.main.backend.get_wallet_info()
        if not result.get("success"):
            self.show_status(result.get("message", "Errore"), True)
            return
        
        msg = f"📊 INFO WALLET\n"
        msg += "=" * 60 + "\n"
        msg += f"  Nome:       {self.main.backend._get_active_wallet_name()}\n"
        msg += f"  Crypto:     {result.get('crypto', 'N/A')}\n"
        msg += f"  Network:    {result.get('network', 'N/A').upper()}\n"
        msg += f"  Address:    {result.get('address', 'N/A')}\n"
        msg += f"  Seed Type:  {result.get('seed_type', 'N/A')}\n"
        if result.get('balance') is not None:
            msg += f"  Balance:    {result.get('balance', 0):.6f} {result.get('crypto', 'XRP')}\n"
        
        show_private = QMessageBox.question(self, "Info Wallet", 
            "Mostrare anche chiavi private/seed?", 
            QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes
        
        if show_private:
            if result.get('mnemonic'):
                msg += f"\n  Mnemonic:   {result.get('mnemonic')}\n"
            if result.get('secret_numbers'):
                msg += f"  Secret Numbers: {result.get('secret_numbers')}\n"
            if result.get('xrp_seed'):
                msg += f"  XRP Seed:   {result.get('xrp_seed')}\n"
            if result.get('stellar_seed'):
                msg += f"  Stellar Seed: {result.get('stellar_seed')}\n"
            if result.get('private_key'):
                msg += f"  Private Key: {result.get('private_key')}\n"
        
        if result.get('derived_wallets'):
            msg += f"\n  📂 Wallet derivati: {len(result.get('derived_wallets', []))}\n"
            for w in result.get('derived_wallets', [])[:5]:
                msg += f"     - {w.get('address', 'N/A')} ({w.get('keyword', 'default')}:{w.get('index', 0)})\n"
        
        QMessageBox.information(self, "Info Wallet", msg)

    def fund_testnet(self):
        result = self.main.backend.fund_testnet()
        if result.get("success"):
            self.show_status(result.get("message", "Testnet funded!"))
        else:
            self.show_status(result.get("message", "Errore"), True)

    def export_wallet(self):
        include_private = QMessageBox.question(self, "Esporta", 
            "Includere chiave privata?", 
            QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes
        
        result = self.main.backend.export_wallet(include_private)
        if result.get("success"):
            data = result.get("data", {})
            msg = json.dumps(data, indent=2, default=str)
            QMessageBox.information(self, "Esporta Wallet", 
                f"📤 DATI WALLET\n\n{msg[:2000]}\n\n" + 
                ("... troncato" if len(msg) > 2000 else ""))
            self.show_status("Wallet esportato")
        else:
            self.show_status(result.get("message", "Errore"), True)

    def change_network(self, network):
        if not self.main.backend:
            return
        try:
            manager = self.main.backend.wallet._xrp_manager
            manager.set_network(network)
            self.show_status(f"Network cambiato a: {network.upper()}")
            self.main.update_wallet_name()
        except Exception as e:
            self.show_status(f"Errore: {e}", True)
            self.update_network_status()

    def change_crypto(self, crypto):
        if not self.main.backend:
            return
        try:
            manager = self.main.backend.wallet._xrp_manager
            manager.set_crypto(crypto)
            self.show_status(f"Crypto cambiata a: {crypto}")
            self.main.update_wallet_name()
        except Exception as e:
            self.show_status(f"Errore: {e}", True)
            self.update_network_status()


# ============================================================
# SETTINGS VIEW
# ============================================================

class SettingsView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        title = QLabel("◈ IMPOSTAZIONI")
        title.setObjectName("view_title")
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(15)
        
        # CAMBIA PASSWORD
        pwd_group = QGroupBox("◈ CAMBIA PASSWORD")
        pwd_layout = QFormLayout(pwd_group)
        
        self.old_pwd = QLineEdit()
        self.old_pwd.setEchoMode(QLineEdit.Password)
        self.old_pwd.setPlaceholderText("> old password")
        self.new_pwd = QLineEdit()
        self.new_pwd.setEchoMode(QLineEdit.Password)
        self.new_pwd.setPlaceholderText("> new password")
        self.confirm_pwd = QLineEdit()
        self.confirm_pwd.setEchoMode(QLineEdit.Password)
        self.confirm_pwd.setPlaceholderText("> confirm password")
        
        pwd_layout.addRow("OLD:", self.old_pwd)
        pwd_layout.addRow("NEW:", self.new_pwd)
        pwd_layout.addRow("CONFIRM:", self.confirm_pwd)
        
        change_btn = QPushButton("◈ CAMBIA")
        change_btn.clicked.connect(self.change_password)
        pwd_layout.addRow("", change_btn)
        scroll_layout.addWidget(pwd_group)
        
        # RETE
        net_group = QGroupBox("◈ RETE")
        net_layout = QVBoxLayout(net_group)
        
        internet_layout = QHBoxLayout()
        internet_layout.addWidget(QLabel("INTERNET:"))
        self.internet_status = QLabel("?")
        self.internet_status.setObjectName("status")
        internet_layout.addWidget(self.internet_status)
        internet_layout.addStretch()
        self.internet_toggle = QPushButton("◈ TOGGLE")
        self.internet_toggle.clicked.connect(self.toggle_internet)
        internet_layout.addWidget(self.internet_toggle)
        net_layout.addLayout(internet_layout)
        
        tor_layout = QHBoxLayout()
        tor_layout.addWidget(QLabel("TOR:"))
        self.tor_status = QLabel("?")
        self.tor_status.setObjectName("status")
        tor_layout.addWidget(self.tor_status)
        tor_layout.addStretch()
        self.tor_toggle = QPushButton("◈ TOGGLE")
        self.tor_toggle.clicked.connect(self.toggle_tor)
        tor_layout.addWidget(self.tor_toggle)
        net_layout.addLayout(tor_layout)
        
        tor_port_layout = QHBoxLayout()
        tor_port_layout.addWidget(QLabel("TOR PORT:"))
        self.tor_port_input = QLineEdit()
        self.tor_port_input.setPlaceholderText("9050")
        self.tor_port_input.setFixedWidth(80)
        tor_port_layout.addWidget(self.tor_port_input)
        tor_port_layout.addStretch()
        tor_port_btn = QPushButton("◈ APPLICA")
        tor_port_btn.clicked.connect(self.set_tor_port)
        tor_port_layout.addWidget(tor_port_btn)
        net_layout.addLayout(tor_port_layout)
        
        scroll_layout.addWidget(net_group)
        
        # GATEWAY CONFIG
        gw_group = QGroupBox("◈ CONFIGURAZIONE GATEWAY")
        gw_layout = QFormLayout(gw_group)
        
        self.gw_name = QLineEdit()
        self.gw_name.setPlaceholderText("gateway-TEST")
        gw_layout.addRow("Nome Gateway:", self.gw_name)
        
        self.announce_interval = QSpinBox()
        self.announce_interval.setRange(10, 3600)
        self.announce_interval.setSuffix(" sec")
        gw_layout.addRow("Announce Interval:", self.announce_interval)
        
        self.ledger_check_interval = QSpinBox()
        self.ledger_check_interval.setRange(60, 86400)
        self.ledger_check_interval.setSuffix(" sec")
        gw_layout.addRow("Ledger Check Interval:", self.ledger_check_interval)
        
        self.ledger_timeout = QSpinBox()
        self.ledger_timeout.setRange(1, 60)
        self.ledger_timeout.setSuffix(" sec")
        gw_layout.addRow("Ledger Timeout:", self.ledger_timeout)
        
        self.query_interval = QSpinBox()
        self.query_interval.setRange(60, 86400)
        self.query_interval.setSuffix(" sec")
        gw_layout.addRow("Query Interval:", self.query_interval)
        
        self.max_peers_to_query = QSpinBox()
        self.max_peers_to_query.setRange(1, 50)
        gw_layout.addRow("Max Peers to Query:", self.max_peers_to_query)
        
        self.max_hops_for_query = QSpinBox()
        self.max_hops_for_query.setRange(1, 10)
        gw_layout.addRow("Max Hops for Query:", self.max_hops_for_query)
        
        self.query_timeout = QSpinBox()
        self.query_timeout.setRange(5, 300)
        self.query_timeout.setSuffix(" sec")
        gw_layout.addRow("Query Timeout:", self.query_timeout)
        
        self.discover_since = QSpinBox()
        self.discover_since.setRange(60, 604800)
        self.discover_since.setSuffix(" sec")
        gw_layout.addRow("Discover Since:", self.discover_since)
        
        scroll_layout.addWidget(gw_group)
        
        # WALLET CONFIG
        w_group = QGroupBox("◈ CONFIGURAZIONE WALLET")
        w_layout = QFormLayout(w_group)
        
        self.wallet_name = QLineEdit()
        self.wallet_name.setPlaceholderText("wallet")
        w_layout.addRow("Nome Wallet:", self.wallet_name)
        
        self.wallet_announce = QSpinBox()
        self.wallet_announce.setRange(10, 3600)
        self.wallet_announce.setSuffix(" sec")
        w_layout.addRow("Wallet Announce Interval:", self.wallet_announce)
        
        self.wallet_discover = QSpinBox()
        self.wallet_discover.setRange(60, 604800)
        self.wallet_discover.setSuffix(" sec")
        w_layout.addRow("Wallet Discover Since:", self.wallet_discover)
        
        scroll_layout.addWidget(w_group)
        
        # SYNC CONFIG
        sync_group = QGroupBox("◈ SYNC")
        sync_layout = QFormLayout(sync_group)
        
        self.peers_per_cycle = QSpinBox()
        self.peers_per_cycle.setRange(1, 20)
        sync_layout.addRow("Peers per Cycle:", self.peers_per_cycle)
        
        self.sync_timeout = QSpinBox()
        self.sync_timeout.setRange(1, 60)
        self.sync_timeout.setSuffix(" sec")
        sync_layout.addRow("Sync Timeout:", self.sync_timeout)
        
        scroll_layout.addWidget(sync_group)
        
        # BACKGROUND
        bg_group = QGroupBox("◈ BACKGROUND")
        bg_layout = QHBoxLayout(bg_group)
        self.background_check = QCheckBox("Background mode")
        bg_layout.addWidget(self.background_check)
        bg_layout.addStretch()
        scroll_layout.addWidget(bg_group)
        
        # SKIN SELECTOR
        skin_group = QGroupBox("🎨 SKIN")
        skin_layout = QHBoxLayout(skin_group)
        self.skin_combo = QComboBox()

        available_skins = self.main.get_available_skins()
        for skin in available_skins:
            display_name = skin.capitalize()
            self.skin_combo.addItem(display_name, skin)

        current_skin = self.main.settings.value("skin", "dark")
        index = self.skin_combo.findData(current_skin)
        if index >= 0:
            self.skin_combo.setCurrentIndex(index)

        self.skin_combo.currentIndexChanged.connect(self.change_skin)
        skin_layout.addWidget(QLabel("Tema:"))
        skin_layout.addWidget(self.skin_combo)
        skin_layout.addStretch()
        scroll_layout.addWidget(skin_group)
        
        # LANGUAGE SELECTOR
        lang_group = QGroupBox("🌍 LINGUA")
        lang_layout = QHBoxLayout(lang_group)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["English", "Italiano", "Español"])
        self.lang_combo.setCurrentText("English")
        self.lang_combo.currentTextChanged.connect(self.change_language)
        lang_layout.addWidget(QLabel("Lingua:"))
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch()
        scroll_layout.addWidget(lang_group)
        
        # BOTTONI SALVA E RICARICA
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("◈ SALVA CONFIG")
        save_btn.clicked.connect(self.save_config)
        reload_btn = QPushButton("◈ RICARICA CONFIG")
        reload_btn.clicked.connect(self.load_config)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(reload_btn)
        scroll_layout.addLayout(btn_layout)
        
        # CONFIG DISPLAY - DENTRO LO SCROLL CON ALTEZZA FISSA
        self.config_display = QTextEdit()
        self.config_display.setReadOnly(True)
        self.config_display.setFont(QFont("Courier New", 9))
        self.config_display.setFixedHeight(400)
        scroll_layout.addWidget(self.config_display)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        layout.addWidget(self.status_label)
        
        self.load_config()
        self.update_network_status()
    
    def change_skin(self, index):
        skin_name = self.skin_combo.itemData(index)
        if skin_name:
            if self.main.apply_skin(skin_name):
                self.status_label.setText(f"✅ Skin cambiata: {skin_name}")
            else:
                self.status_label.setText(f"❌ Skin {skin_name} non trovata")
    
    def change_language(self, lang_name):
        self.status_label.setText(f"✅ Lingua cambiata: {lang_name}")
    
    def load_config(self):
        try:
            config_path = Path("annuncio_config.json")
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                
                gw = config.get("gateway", {})
                w = config.get("wallet", {})
                sync = config.get("sync", {})
                bg = config.get("background", False)
                
                self.gw_name.setText(gw.get("name", ""))
                self.announce_interval.setValue(gw.get("announce_interval", 300))
                self.ledger_check_interval.setValue(gw.get("ledger_check_interval", 1800))
                self.ledger_timeout.setValue(gw.get("ledger_timeout_seconds", 5))
                self.query_interval.setValue(gw.get("query_interval", 3600))
                self.max_peers_to_query.setValue(gw.get("max_peers_to_query", 10))
                self.max_hops_for_query.setValue(gw.get("max_hops_for_query", 7))
                self.query_timeout.setValue(gw.get("query_timeout_seconds", 30))
                self.discover_since.setValue(gw.get("discover_since_seconds", 86400))
                
                self.wallet_name.setText(w.get("name", ""))
                self.wallet_announce.setValue(w.get("announce_interval", 1800))
                self.wallet_discover.setValue(w.get("discover_since_seconds", 86400))
                
                self.peers_per_cycle.setValue(sync.get("peers_per_cycle", 2))
                self.sync_timeout.setValue(sync.get("timeout_seconds", 5))
                
                self.background_check.setChecked(bg)
                
                self.config_display.setText(json.dumps(config, indent=4))
                self.status_label.setText("✅ Config caricato")
            else:
                self.config_display.setText("⚠️ Config non trovato - usati valori di default")
                self.status_label.setText("⚠️ Config non trovato")
        except Exception as e:
            self.config_display.setText(f"❌ Errore: {e}")
            self.status_label.setText(f"❌ Errore: {e}")
    
    def save_config(self):
        try:
            config = {
                "gateway": {
                    "name": self.gw_name.text() or "gateway-TEST",
                    "announce_interval": self.announce_interval.value(),
                    "internet": "on" if self.main.backend.use_internet else "off",
                    "use_tor": "on" if self.main.backend.use_tor else "off",
                    "tor_socks_port": int(self.tor_port_input.text() or 9050),
                    "tor_timeout_seconds": 30,
                    "ledger_check_interval": self.ledger_check_interval.value(),
                    "ledger_timeout_seconds": self.ledger_timeout.value(),
                    "query_interval": self.query_interval.value(),
                    "max_peers_to_query": self.max_peers_to_query.value(),
                    "max_hops_for_query": self.max_hops_for_query.value(),
                    "query_timeout_seconds": self.query_timeout.value(),
                    "discover_since_seconds": self.discover_since.value()
                },
                "wallet": {
                    "name": self.wallet_name.text() or "wallet",
                    "announce_interval": self.wallet_announce.value(),
                    "discover_since_seconds": self.wallet_discover.value()
                },
                "sync": {
                    "peers_per_cycle": self.peers_per_cycle.value(),
                    "timeout_seconds": self.sync_timeout.value()
                },
                "background": self.background_check.isChecked()
            }
            
            config_path = Path("annuncio_config.json")
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            self.config_display.setText(json.dumps(config, indent=4))
            self.status_label.setText("✅ Config salvato!")
            
        except Exception as e:
            self.status_label.setText(f"❌ Errore salvataggio: {e}")
    
    def update_network_status(self):
        if not self.main.backend:
            return
        try:
            internet_on = self.main.backend.use_internet
            self.internet_status.setText("🌐 ON" if internet_on else "📡 OFF")
            self.internet_status.setStyleSheet("color: #00ff41;" if internet_on else "color: #ff6b6b;")
            
            tor_on = self.main.backend.use_tor
            self.tor_status.setText("🧅 ON" if tor_on else "OFF")
            self.tor_status.setStyleSheet("color: #00ff41;" if tor_on else "color: #ff6b6b;")
            
            self.tor_port_input.setText(str(self.main.backend.tor_socks_port))
            
        except Exception as e:
            self.status_label.setText(f"❌ Errore: {e}")
    
    def toggle_internet(self):
        if not self.main.backend:
            return
        current = self.main.backend.use_internet
        self.main.backend.set_use_internet(not current)
        self.update_network_status()
        if hasattr(self.main, 'reticulum_view'):
            QTimer.singleShot(500, self.main.reticulum_view.update_status)
        self.status_label.setText("🌐 Internet " + ("attivato" if not current else "disattivato"))
    
    def toggle_tor(self):
        if not self.main.backend:
            return
        current = self.main.backend.use_tor
        self.main.backend.set_use_tor(not current)
        self.update_network_status()
        if hasattr(self.main, 'reticulum_view'):
            QTimer.singleShot(500, self.main.reticulum_view.update_status)
        self.status_label.setText("🧅 TOR " + ("attivato" if not current else "disattivato"))
    
    def set_tor_port(self):
        if not self.main.backend:
            return
        try:
            port = int(self.tor_port_input.text())
            self.main.backend.tor_socks_port = port
            self.main.backend._update_proxy()
            self.status_label.setText(f"✅ TOR port impostato a {port}")
        except ValueError:
            self.status_label.setText("❌ Porta non valida")
    
    def change_password(self):
        old = self.old_pwd.text()
        new = self.new_pwd.text()
        confirm = self.confirm_pwd.text()
        
        if new != confirm:
            self.status_label.setText("❌ > PASSWORDS DO NOT MATCH")
            return
        
        if len(new) < 4:
            self.status_label.setText("❌ > PASSWORD TOO SHORT")
            return
        
        try:
            result = self.main.backend.change_password(old, new)
            if result.get("success"):
                self.status_label.setText("✅ > PASSWORD CHANGED!")
                self.old_pwd.clear()
                self.new_pwd.clear()
                self.confirm_pwd.clear()
            else:
                self.status_label.setText(f"❌ > {result.get('message', 'UNKNOWN ERROR')}")
        except Exception as e:
            self.status_label.setText(f"❌ > {e}")