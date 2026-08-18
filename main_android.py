"""
PAX Wallet - Android Frontend (Kivy)
Usa lo stesso backend di wallet_backend.py
"""

import sys
import os
from pathlib import Path

# Aggiungi il percorso del progetto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.properties import StringProperty, ObjectProperty, ListProperty
from kivy.clock import Clock

from wallet_backend import WalletBackend, create_backend, format_time_ago


class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior, RecycleBoxLayout):
    """Aggiunge selezione al RecycleView"""
    pass


class HomeScreen(Screen):
    """Schermata principale"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.balance = StringProperty("--.--")
        self.address = StringProperty("")
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Header
        header = BoxLayout(size_hint_y=0.1)
        header.add_widget(Label(text="💰 PAX WALLET", font_size='24sp', bold=True))
        layout.add_widget(header)
        
        # Balance
        balance_card = BoxLayout(orientation='vertical', size_hint_y=0.3, padding=10, spacing=5)
        self.balance_label = Label(text=self.balance, font_size='32sp', bold=True)
        self.address_label = Label(text=self.address, font_size='12sp', color=(0.5, 0.5, 0.5, 1))
        balance_card.add_widget(self.balance_label)
        balance_card.add_widget(self.address_label)
        layout.add_widget(balance_card)
        
        # Actions
        actions = BoxLayout(orientation='vertical', size_hint_y=0.2, spacing=5)
        btn_send = Button(text="📤 Send", size_hint_y=0.5)
        btn_send.bind(on_press=lambda x: setattr(self.app, 'current_screen', 'send'))
        btn_history = Button(text="📜 History", size_hint_y=0.5)
        btn_history.bind(on_press=lambda x: setattr(self.app, 'current_screen', 'history'))
        actions.add_widget(btn_send)
        actions.add_widget(btn_history)
        layout.add_widget(actions)
        
        # Navigation
        nav = BoxLayout(size_hint_y=0.08)
        nav_buttons = [
            ("🏠", "home"),
            ("👛", "wallet"),
            ("📇", "address_book"),
            ("📡", "reticulum"),
            ("⚙️", "settings"),
        ]
        for text, screen in nav_buttons:
            btn = Button(text=text, font_size='18sp')
            btn.bind(on_press=lambda x, s=screen: setattr(self.app, 'current_screen', s))
            nav.add_widget(btn)
        layout.add_widget(nav)
        self.add_widget(layout)
    
    def update_balance(self, balance, crypto):
        self.balance = f"{balance:.6f} {crypto}"
        self.balance_label.text = self.balance
    
    def update_address(self, address):
        self.address = address
        self.address_label.text = address


class WalletScreen(Screen):
    """Gestione wallet"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Header
        header = BoxLayout(size_hint_y=0.08)
        header.add_widget(Label(text="👛 Wallet", font_size='20sp', bold=True))
        back_btn = Button(text="⬅️", size_hint_x=0.15)
        back_btn.bind(on_press=lambda x: setattr(self.app, 'current_screen', 'home'))
        header.add_widget(back_btn)
        layout.add_widget(header)
        
        # Lista wallet
        self.wallet_list = RecycleView(
            size_hint_y=0.7,
            viewclass='SelectableLabel',
            selected_index=None,
            data=[],
            RecycleBoxLayout=SelectableRecycleBoxLayout,
        )
        layout.add_widget(self.wallet_list)
        
        # Actions
        actions = BoxLayout(orientation='vertical', size_hint_y=0.2, spacing=5)
        btn_create = Button(text="➕ Create Wallet")
        btn_create.bind(on_press=self.create_wallet)
        btn_switch = Button(text="🔄 Switch Wallet")
        btn_switch.bind(on_press=self.switch_wallet)
        actions.add_widget(btn_create)
        actions.add_widget(btn_switch)
        layout.add_widget(actions)
        
        self.add_widget(layout)
        self.refresh_wallets()
    
    def refresh_wallets(self):
        if not self.app.backend:
            return
        wallets = self.app.backend.list_wallets()
        data = []
        for w in wallets:
            marker = "▶ " if w.get("is_active") else "  "
            data.append({
                "text": f"{marker}{w['name']} ({w['crypto']} - {w['network']})",
                "selectable": True,
            })
        self.wallet_list.data = data
    
    def create_wallet(self, instance):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput
        
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        name_input = TextInput(hint_text="Wallet name", multiline=False)
        crypto_input = TextInput(text="XRP", hint_text="XRP/XLM", multiline=False)
        network_input = TextInput(text="testnet", hint_text="testnet/mainnet", multiline=False)
        
        content.add_widget(Label(text="Create Wallet"))
        content.add_widget(name_input)
        content.add_widget(Label(text="Crypto:"))
        content.add_widget(crypto_input)
        content.add_widget(Label(text="Network:"))
        content.add_widget(network_input)
        
        btn_box = BoxLayout(size_hint_y=0.3, spacing=5)
        btn_create = Button(text="Create")
        btn_cancel = Button(text="Cancel")
        btn_box.add_widget(btn_create)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)
        
        popup = Popup(title="Create Wallet", content=content, size_hint=(0.8, 0.6))
        
        def do_create(instance):
            name = name_input.text or "default"
            crypto = crypto_input.text.upper() or "XRP"
            network = network_input.text.lower() or "testnet"
            result = self.app.backend.create_wallet(name, crypto, network)
            if result.get("success"):
                popup.dismiss()
                self.refresh_wallets()
                self.app.home_screen.update_address(result.get('address', ''))
            else:
                content.add_widget(Label(text=f"❌ {result.get('error', 'Error')}", color=(1, 0, 0, 1)))
        
        btn_create.bind(on_press=do_create)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()
    
    def switch_wallet(self, instance):
        idx = self.wallet_list.selected_index
        if idx is None:
            return
        wallets = self.app.backend.list_wallets()
        if idx < len(wallets):
            name = wallets[idx]['name']
            result = self.app.backend.switch_wallet(name)
            if result.get("success"):
                self.refresh_wallets()
                active = self.app.backend.get_active_wallet()
                self.app.home_screen.update_address(active.get('address', ''))


class SendScreen(Screen):
    """Invia pagamento"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        header = BoxLayout(size_hint_y=0.08)
        header.add_widget(Label(text="📤 Send", font_size='20sp', bold=True))
        back_btn = Button(text="⬅️", size_hint_x=0.15)
        back_btn.bind(on_press=lambda x: setattr(self.app, 'current_screen', 'home'))
        header.add_widget(back_btn)
        layout.add_widget(header)
        
        form = BoxLayout(orientation='vertical', spacing=10)
        self.address_input = TextInput(hint_text="Address", multiline=False)
        self.amount_input = TextInput(hint_text="Amount", multiline=False, input_filter='float')
        self.memo_input = TextInput(hint_text="Memo (optional)", multiline=False)
        form.add_widget(self.address_input)
        form.add_widget(self.amount_input)
        form.add_widget(self.memo_input)
        
        self.send_btn = Button(text="📤 Send Payment", size_hint_y=0.15)
        self.send_btn.bind(on_press=self.send_payment)
        form.add_widget(self.send_btn)
        
        self.status_label = Label(text="", size_hint_y=0.1)
        form.add_widget(self.status_label)
        layout.add_widget(form)
        self.add_widget(layout)
    
    def send_payment(self, instance):
        address = self.address_input.text.strip()
        if not address:
            self.status_label.text = "❌ Address required"
            return
        try:
            amount = float(self.amount_input.text.strip())
        except:
            self.status_label.text = "❌ Invalid amount"
            return
        memo = self.memo_input.text.strip()
        
        self.send_btn.disabled = True
        self.status_label.text = "⏳ Sending..."
        
        try:
            result = self.app.backend.send_payment(address, amount, memo, encrypt_memo=False)
            if result.get("success"):
                self.status_label.text = f"✅ Sent! Hash: {result.get('tx_hash', 'N/A')[:16]}..."
                self.address_input.text = ""
                self.amount_input.text = ""
                self.memo_input.text = ""
            else:
                self.status_label.text = f"❌ {result.get('message', 'Error')}"
        except Exception as e:
            self.status_label.text = f"❌ {str(e)[:50]}"
        finally:
            self.send_btn.disabled = False


class HistoryScreen(Screen):
    """Storico transazioni"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        header = BoxLayout(size_hint_y=0.08)
        header.add_widget(Label(text="📜 History", font_size='20sp', bold=True))
        back_btn = Button(text="⬅️", size_hint_x=0.15)
        back_btn.bind(on_press=lambda x: setattr(self.app, 'current_screen', 'home'))
        header.add_widget(back_btn)
        layout.add_widget(header)
        
        self.history_list = RecycleView(
            size_hint_y=0.8,
            viewclass='SelectableLabel',
            selected_index=None,
            data=[],
            RecycleBoxLayout=SelectableRecycleBoxLayout,
        )
        layout.add_widget(self.history_list)
        
        refresh_btn = Button(text="🔄 Refresh", size_hint_y=0.08)
        refresh_btn.bind(on_press=self.refresh_history)
        layout.add_widget(refresh_btn)
        
        self.add_widget(layout)
        self.refresh_history()
    
    def refresh_history(self, instance=None):
        if not self.app.backend:
            return
        result = self.app.backend.get_history(10)
        if not result.get("success"):
            return
        transactions = result.get("transactions", [])
        crypto = result.get("crypto", "XRP")
        data = []
        for tx in transactions:
            if crypto == "XLM":
                created_at = tx.get('created_at', '')
                date_str = created_at.replace('T', ' ').replace('Z', '')[:16] if created_at else 'N/A'
                ops = tx.get('_embedded', {}).get('records', [])
                if ops:
                    op = ops[0]
                    amount = float(op.get('amount', 0)) if op.get('amount') else 0
                    asset = "XLM" if op.get('asset_type') == 'native' else op.get('asset_code', '?')
                    from_acct = op.get('from', '')
                    to_acct = op.get('to', '')
                    direction = "📥" if to_acct == result.get('address') else "📤"
                    data.append({
                        "text": f"{direction} {date_str} {amount:.7f} {asset}",
                        "selectable": False,
                    })
            else:
                tx_json = tx.get('tx_json', {})
                if tx_json:
                    amount = tx_json.get("Amount", "0")
                    date_str = "N/A"
                    if "date" in tx_json:
                        try:
                            ledger_time = tx_json.get("date", 0)
                            if ledger_time:
                                from datetime import datetime
                                date_obj = datetime.fromtimestamp(ledger_time + 946684800)
                                date_str = date_obj.strftime("%Y-%m-%d %H:%M")
                        except:
                            pass
                    if isinstance(amount, dict):
                        amount_val = float(amount.get('value', 0))
                        currency = amount.get('currency', '???')
                        amount_str = f"{amount_val:.6f} {currency}"
                    else:
                        try:
                            amount_xrp = int(amount) / 1_000_000
                            amount_str = f"{amount_xrp:.6f} XRP"
                        except:
                            amount_str = str(amount)
                    sender = tx_json.get("Account", "unknown")
                    destination = tx_json.get("Destination", "unknown")
                    direction = "📥" if destination == result.get('address') else "📤"
                    data.append({
                        "text": f"{direction} {date_str} {amount_str}",
                        "selectable": False,
                    })
        self.history_list.data = data


class ReticulumScreen(Screen):
    """Reticulum management"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        header = BoxLayout(size_hint_y=0.08)
        header.add_widget(Label(text="📡 Reticulum", font_size='20sp', bold=True))
        back_btn = Button(text="⬅️", size_hint_x=0.15)
        back_btn.bind(on_press=lambda x: setattr(self.app, 'current_screen', 'home'))
        header.add_widget(back_btn)
        layout.add_widget(header)
        
        self.status_label = Label(text="Status: Loading...", size_hint_y=0.08)
        layout.add_widget(self.status_label)
        
        self.peer_list = RecycleView(
            size_hint_y=0.5,
            viewclass='SelectableLabel',
            selected_index=None,
            data=[],
            RecycleBoxLayout=SelectableRecycleBoxLayout,
        )
        layout.add_widget(self.peer_list)
        
        actions = BoxLayout(orientation='vertical', size_hint_y=0.3, spacing=5)
        btn_discover = Button(text="🔍 Discover Peers")
        btn_discover.bind(on_press=self.discover_peers)
        btn_start = Button(text="▶️ Start Gateway")
        btn_start.bind(on_press=self.start_gateway)
        btn_stop = Button(text="⏹️ Stop Gateway")
        btn_stop.bind(on_press=self.stop_gateway)
        actions.add_widget(btn_discover)
        actions.add_widget(btn_start)
        actions.add_widget(btn_stop)
        layout.add_widget(actions)
        
        self.add_widget(layout)
    
    def discover_peers(self, instance):
        if not self.app.backend:
            return
        result = self.app.backend.discover_gateways()
        gateways = result.get("gateways", [])
        data = []
        for gw in gateways:
            data.append({
                "text": f"{gw.get('name', 'Unknown')} (hops: {gw.get('hops', '?')})",
                "selectable": False,
            })
        self.peer_list.data = data
        self.status_label.text = f"Found {len(gateways)} peers"
    
    def start_gateway(self, instance):
        result = self.app.backend.start_gateway()
        if result.get("success"):
            self.status_label.text = "✅ Gateway started"
        else:
            self.status_label.text = f"❌ {result.get('message', 'Error')}"
    
    def stop_gateway(self, instance):
        result = self.app.backend.stop_gateway()
        if result.get("success"):
            self.status_label.text = "✅ Gateway stopped"
        else:
            self.status_label.text = f"❌ {result.get('message', 'Error')}"


class AddressBookScreen(Screen):
    """Rubrica indirizzi"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        header = BoxLayout(size_hint_y=0.08)
        header.add_widget(Label(text="📇 Address Book", font_size='20sp', bold=True))
        back_btn = Button(text="⬅️", size_hint_x=0.15)
        back_btn.bind(on_press=lambda x: setattr(self.app, 'current_screen', 'home'))
        header.add_widget(back_btn)
        layout.add_widget(header)
        
        self.contact_list = RecycleView(
            size_hint_y=0.7,
            viewclass='SelectableLabel',
            selected_index=None,
            data=[],
            RecycleBoxLayout=SelectableRecycleBoxLayout,
        )
        layout.add_widget(self.contact_list)
        
        actions = BoxLayout(orientation='vertical', size_hint_y=0.2, spacing=5)
        btn_add = Button(text="➕ Add Contact")
        btn_add.bind(on_press=self.add_contact)
        btn_delete = Button(text="🗑️ Delete Contact")
        btn_delete.bind(on_press=self.delete_contact)
        actions.add_widget(btn_add)
        actions.add_widget(btn_delete)
        layout.add_widget(actions)
        
        self.add_widget(layout)
        self.refresh_contacts()
    
    def refresh_contacts(self):
        if not self.app.backend:
            return
        result = self.app.backend.get_contacts()
        contacts = result.get("contacts", [])
        data = []
        for c in contacts:
            star = "⭐ " if c.get("is_favorite") else "   "
            data.append({
                "text": f"{star}{c.get('name', 'N/A')} ({c.get('crypto', 'XRP')})",
                "selectable": True,
                "address": c.get('address', ''),
            })
        self.contact_list.data = data
    
    def add_contact(self, instance):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput
        
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        address_input = TextInput(hint_text="Address", multiline=False)
        name_input = TextInput(hint_text="Name", multiline=False)
        crypto_input = TextInput(text="XRP", hint_text="XRP/XLM", multiline=False)
        
        content.add_widget(Label(text="Add Contact"))
        content.add_widget(address_input)
        content.add_widget(name_input)
        content.add_widget(Label(text="Crypto:"))
        content.add_widget(crypto_input)
        
        btn_box = BoxLayout(size_hint_y=0.3, spacing=5)
        btn_add = Button(text="Add")
        btn_cancel = Button(text="Cancel")
        btn_box.add_widget(btn_add)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)
        
        popup = Popup(title="Add Contact", content=content, size_hint=(0.8, 0.6))
        
        def do_add(instance):
            address = address_input.text.strip()
            name = name_input.text.strip() or address[:12]
            crypto = crypto_input.text.upper() or "XRP"
            if not address:
                content.add_widget(Label(text="❌ Address required", color=(1, 0, 0, 1)))
                return
            result = self.app.backend.add_contact(address, name, crypto)
            if result.get("success"):
                popup.dismiss()
                self.refresh_contacts()
            else:
                content.add_widget(Label(text=f"❌ {result.get('message', 'Error')}", color=(1, 0, 0, 1)))
        
        btn_add.bind(on_press=do_add)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()
    
    def delete_contact(self, instance):
        idx = self.contact_list.selected_index
        if idx is None:
            return
        data = self.contact_list.data[idx]
        address = data.get('address')
        if address:
            self.app.backend.delete_contact(address)
            self.refresh_contacts()


class SettingsScreen(Screen):
    """Impostazioni"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        header = BoxLayout(size_hint_y=0.08)
        header.add_widget(Label(text="⚙️ Settings", font_size='20sp', bold=True))
        back_btn = Button(text="⬅️", size_hint_x=0.15)
        back_btn.bind(on_press=lambda x: setattr(self.app, 'current_screen', 'home'))
        header.add_widget(back_btn)
        layout.add_widget(header)
        
        # Internet toggle
        internet_box = BoxLayout(size_hint_y=0.08)
        internet_box.add_widget(Label(text="Internet:"))
        self.internet_status = Label(text="ON")
        internet_box.add_widget(self.internet_status)
        btn_internet = Button(text="Toggle", size_hint_x=0.3)
        btn_internet.bind(on_press=self.toggle_internet)
        internet_box.add_widget(btn_internet)
        layout.add_widget(internet_box)
        
        # TOR toggle
        tor_box = BoxLayout(size_hint_y=0.08)
        tor_box.add_widget(Label(text="TOR:"))
        self.tor_status = Label(text="OFF")
        tor_box.add_widget(self.tor_status)
        btn_tor = Button(text="Toggle", size_hint_x=0.3)
        btn_tor.bind(on_press=self.toggle_tor)
        tor_box.add_widget(btn_tor)
        layout.add_widget(tor_box)
        
        # Password change
        layout.add_widget(Label(text="Change Password:", size_hint_y=0.05))
        btn_password = Button(text="🔐 Change Password", size_hint_y=0.08)
        btn_password.bind(on_press=self.change_password)
        layout.add_widget(btn_password)
        
        self.add_widget(layout)
    
    def toggle_internet(self, instance):
        if self.app.backend:
            current = self.app.backend.use_internet
            self.app.backend.set_use_internet(not current)
            self.internet_status.text = "ON" if not current else "OFF"
    
    def toggle_tor(self, instance):
        if self.app.backend:
            current = self.app.backend.use_tor
            self.app.backend.set_use_tor(not current)
            self.tor_status.text = "ON" if not current else "OFF"
    
    def change_password(self, instance):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput
        
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        old_input = TextInput(password=True, hint_text="Old password", multiline=False)
        new_input = TextInput(password=True, hint_text="New password", multiline=False)
        confirm_input = TextInput(password=True, hint_text="Confirm password", multiline=False)
        
        content.add_widget(Label(text="Change Password"))
        content.add_widget(old_input)
        content.add_widget(new_input)
        content.add_widget(confirm_input)
        
        btn_box = BoxLayout(size_hint_y=0.3, spacing=5)
        btn_change = Button(text="Change")
        btn_cancel = Button(text="Cancel")
        btn_box.add_widget(btn_change)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)
        
        popup = Popup(title="Change Password", content=content, size_hint=(0.8, 0.5))
        
        def do_change(instance):
            old = old_input.text
            new = new_input.text
            confirm = confirm_input.text
            if new != confirm:
                content.add_widget(Label(text="❌ Passwords don't match", color=(1, 0, 0, 1)))
                return
            result = self.app.backend.change_password(old, new)
            if result.get("success"):
                popup.dismiss()
                self.app._password = new
            else:
                content.add_widget(Label(text=f"❌ {result.get('message', 'Error')}", color=(1, 0, 0, 1)))
        
        btn_change.bind(on_press=do_change)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()


class PaxWalletApp(App):
    """Applicazione Android PAX Wallet"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.backend = None
        self._password = None
        self.current_screen = 'home'
    
    def build(self):
        self.sm = ScreenManager()
        
        self.home_screen = HomeScreen(name='home')
        self.wallet_screen = WalletScreen(name='wallet')
        self.send_screen = SendScreen(name='send')
        self.history_screen = HistoryScreen(name='history')
        self.reticulum_screen = ReticulumScreen(name='reticulum')
        self.address_book_screen = AddressBookScreen(name='address_book')
        self.settings_screen = SettingsScreen(name='settings')
        
        self.sm.add_widget(self.home_screen)
        self.sm.add_widget(self.wallet_screen)
        self.sm.add_widget(self.send_screen)
        self.sm.add_widget(self.history_screen)
        self.sm.add_widget(self.reticulum_screen)
        self.sm.add_widget(self.address_book_screen)
        self.sm.add_widget(self.settings_screen)
        
        Clock.schedule_once(self.unlock, 0.5)
        Clock.schedule_interval(self.update_status, 5)
        
        return self.sm
    
    def unlock(self, dt):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput
        
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        password_input = TextInput(password=True, hint_text="Enter password", multiline=False)
        content.add_widget(Label(text="🔐 PAX WALLET"))
        content.add_widget(password_input)
        
        btn_box = BoxLayout(size_hint_y=0.3, spacing=5)
        btn_unlock = Button(text="Unlock")
        btn_box.add_widget(btn_unlock)
        content.add_widget(btn_box)
        
        popup = Popup(title="Unlock", content=content, size_hint=(0.8, 0.4))
        
        def do_unlock(instance):
            password = password_input.text
            if not password:
                return
            self.backend = create_backend(password)
            self.backend.init()
            active = self.backend.get_active_wallet()
            if active.get("name") and active.get("loaded"):
                self._password = password
                popup.dismiss()
                address = active.get("address", "")
                self.home_screen.update_address(address)
                balance = self.backend.get_balance()
                if balance.get("success"):
                    self.home_screen.update_balance(balance.get("balance", 0), balance.get("crypto", "XRP"))
            else:
                content.add_widget(Label(text="❌ Wrong password", color=(1, 0, 0, 1)))
        
        btn_unlock.bind(on_press=do_unlock)
        password_input.bind(on_text_validate=do_unlock)
        popup.open()
    
    def update_status(self, dt):
        if not self.backend:
            return
        balance = self.backend.get_balance()
        if balance.get("success"):
            self.home_screen.update_balance(balance.get("balance", 0), balance.get("crypto", "XRP"))


def main():
    PaxWalletApp().run()


if __name__ == "__main__":
    main()