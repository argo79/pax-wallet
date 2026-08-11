#!/usr/bin/env python3
"""
address_book.py - Rubrica indirizzi cifrata per PAX Wallet
UNICO FILE - gestito dal backend, usa core_wrapper per cifratura
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from core_wrapper import encrypt_wallet, decrypt_wallet, is_encrypted_wallet


class AddressBook:
    """Rubrica indirizzi cifrata - UNICO FILE gestito dal backend"""
    
    VERSION = "1.0"
    
    def __init__(self, password: str, data_file: str = "address_book.json"):
        self.password = password
        self.data_file = Path(data_file)
        self.contacts: Dict[str, Dict] = {}
        self._modified = False
        self.load()
    
    def _encrypt_data(self, data: Dict) -> str:
        """Cifra i dati della rubrica"""
        json_str = json.dumps(data, indent=2, default=str)
        return encrypt_wallet(json_str, self.password)
    
    def _decrypt_data(self, content: str) -> Optional[Dict]:
        """Decifra i dati della rubrica"""
        if not content or not self.password:
            return None
        if is_encrypted_wallet(content):
            json_str = decrypt_wallet(content, self.password)
            return json.loads(json_str)
        return json.loads(content)
    
    def load(self):
        """Carica la rubrica dal file cifrato"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    content = f.read().strip()
                if content:
                    data = self._decrypt_data(content)
                    if data:
                        self.contacts = data.get("contacts", {})
                        print(f"📖 Rubrica caricata: {len(self.contacts)} contatti")
                    else:
                        self.contacts = {}
                else:
                    self.contacts = {}
            except Exception as e:
                print(f"⚠️ Errore caricamento rubrica: {e}")
                self.contacts = {}
        else:
            self.contacts = {}
            self.save()
    
    def save(self):
        """Salva la rubrica cifrata"""
        try:
            data = {
                "version": self.VERSION,
                "updated_at": int(time.time()),
                "contacts": self.contacts
            }
            encrypted = self._encrypt_data(data)
            with open(self.data_file, 'w') as f:
                f.write(encrypted)
            self._modified = False
            print(f"💾 Rubrica salvata: {len(self.contacts)} contatti")
        except Exception as e:
            print(f"❌ Errore salvataggio rubrica: {e}")
    
    def get_contact(self, address: str) -> Optional[Dict]:
        return self.contacts.get(address)
    
    def get_all_contacts(self, sort_by: str = "name") -> List[Dict]:
        contacts = list(self.contacts.values())
        
        if sort_by == "name":
            contacts.sort(key=lambda x: x.get("name", "").lower())
        elif sort_by == "last_used":
            contacts.sort(key=lambda x: x.get("last_used", 0), reverse=True)
        elif sort_by == "tx_count":
            contacts.sort(key=lambda x: x.get("tx_count", 0), reverse=True)
        
        return contacts
    
    def get_favorites(self) -> List[Dict]:
        return [c for c in self.contacts.values() if c.get("is_favorite", False)]
    
    def search(self, query: str) -> List[Dict]:
        query = query.lower().strip()
        if not query:
            return self.get_all_contacts()
        
        results = []
        for addr, contact in self.contacts.items():
            name = contact.get("name", "").lower()
            if query in name or query in addr.lower():
                results.append(contact)
        return results
    
    def add_contact(self, address: str, name: str = None, crypto: str = None, 
                    network: str = None, tags: List[str] = None, 
                    notes: str = "", is_favorite: bool = False) -> bool:
        if not address:
            return False
        
        existing = self.contacts.get(address)
        if existing:
            if name is not None:
                existing["name"] = name
            if crypto is not None:
                existing["crypto"] = crypto
            if network is not None:
                existing["network"] = network
            if tags is not None:
                existing["tags"] = tags
            if notes:
                existing["notes"] = notes
            if is_favorite is not None:
                existing["is_favorite"] = is_favorite
            existing["updated_at"] = int(time.time())
        else:
            self.contacts[address] = {
                "address": address,
                "name": name or address[:12],
                "crypto": crypto or "XRP",
                "network": network or "mainnet",
                "is_favorite": is_favorite,
                "tags": tags or [],
                "notes": notes,
                "source": "manual",
                "first_seen": int(time.time()),
                "last_used": 0,
                "tx_count": 0,
                "created_at": int(time.time()),
                "updated_at": int(time.time())
            }
        
        self._modified = True
        self.save()
        return True
    
    def update_from_transaction(self, address: str, crypto: str = "XRP") -> bool:
        if not address:
            return False
        
        existing = self.contacts.get(address)
        if existing:
            existing["last_used"] = int(time.time())
            existing["tx_count"] = existing.get("tx_count", 0) + 1
            if not existing.get("first_seen"):
                existing["first_seen"] = int(time.time())
            if crypto:
                existing["crypto"] = crypto
            existing["updated_at"] = int(time.time())
        else:
            self.contacts[address] = {
                "address": address,
                "name": address[:12],
                "crypto": crypto or "XRP",
                "network": "mainnet",
                "is_favorite": False,
                "tags": [],
                "notes": "",
                "source": "auto",
                "first_seen": int(time.time()),
                "last_used": int(time.time()),
                "tx_count": 1,
                "created_at": int(time.time()),
                "updated_at": int(time.time())
            }
        
        self._modified = True
        return True
    
    def delete_contact(self, address: str) -> bool:
        if address in self.contacts:
            del self.contacts[address]
            self._modified = True
            self.save()
            return True
        return False
    
    def toggle_favorite(self, address: str) -> bool:
        if address in self.contacts:
            current = self.contacts[address].get("is_favorite", False)
            self.contacts[address]["is_favorite"] = not current
            self._modified = True
            self.save()
            return True
        return False
    
    def get_stats(self) -> Dict:
        contacts = list(self.contacts.values())
        return {
            "total": len(contacts),
            "auto": sum(1 for c in contacts if c.get("source") == "auto"),
            "manual": sum(1 for c in contacts if c.get("source") == "manual"),
            "favorites": sum(1 for c in contacts if c.get("is_favorite", False)),
            "xrp": sum(1 for c in contacts if c.get("crypto") == "XRP"),
            "xlm": sum(1 for c in contacts if c.get("crypto") == "XLM")
        }
    
    def get_addresses(self) -> List[str]:
        return list(self.contacts.keys())
    
    def flush(self):
        if self._modified:
            self.save()