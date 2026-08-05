#!/usr/bin/env python3
"""
crypto_memo.py - Cifratura memo per PAX Wallet
"""

import hashlib
import os
import base64
from typing import Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class MemoCrypto:
    """Cifratura/decifratura memo con chiavi XRP/Stellar"""
    
    @staticmethod
    def public_key_to_ec(public_key_hex: str) -> ec.EllipticCurvePublicKey:
        """Converte una chiave pubblica XRP in formato EC"""
        # XRP usa SECP256K1 (come Bitcoin)
        public_key_bytes = bytes.fromhex(public_key_hex)
        
        # Carica la chiave pubblica
        # Nota: ec è già importato, non serve re-importarlo
        return ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256K1(),
            public_key_bytes
        )
    
    @staticmethod
    def derive_shared_secret(public_key_hex: str, private_key_hex: str) -> bytes:
        """Deriva un segreto condiviso usando ECDH"""
        # Converte la chiave pubblica del destinatario
        peer_public_key = MemoCrypto.public_key_to_ec(public_key_hex)
        
        # Converte la chiave privata del mittente
        private_key_bytes = bytes.fromhex(private_key_hex)
        private_key = ec.derive_private_key(
            private_key_bytes,
            ec.SECP256K1(),
            default_backend()
        )
        
        # ECDH: deriva il segreto condiviso
        shared_secret = private_key.exchange(ec.ECDH(), peer_public_key)
        
        # Deriva una chiave AES usando HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'pax_wallet_memo_salt',
            info=b'memo_encryption',
            backend=default_backend()
        )
        return hkdf.derive(shared_secret)
    
    @staticmethod
    def encrypt_memo(memo: str, recipient_public_key_hex: str, 
                     sender_private_key_hex: str) -> str:
        """
        Cifra un memo usando la chiave pubblica del destinatario
        
        Args:
            memo: Testo del memo da cifrare
            recipient_public_key_hex: Chiave pubblica del destinatario (hex)
            sender_private_key_hex: Chiave privata del mittente (hex)
        
        Returns:
            str: Memo cifrato in formato base64 (pronto per essere messo nel campo MemoData)
        """
        if not memo:
            return ""
        
        # Deriva il segreto condiviso
        key = MemoCrypto.derive_shared_secret(
            recipient_public_key_hex,
            sender_private_key_hex
        )
        
        # Genera IV casuale
        iv = os.urandom(16)
        
        # Cifra il memo con AES-256-GCM
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        # Cifra il memo
        memo_bytes = memo.encode('utf-8')
        ciphertext = encryptor.update(memo_bytes) + encryptor.finalize()
        tag = encryptor.tag
        
        # Costruisci il payload: IV + Tag + Ciphertext
        payload = iv + tag + ciphertext
        
        # Converti in base64 per il MemoData
        return base64.b64encode(payload).decode('ascii')
    
    @staticmethod
    def decrypt_memo(encrypted_memo: str, recipient_private_key_hex: str,
                     sender_public_key_hex: str) -> Optional[str]:
        """
        Decifra un memo. Restituisce il testo decifrato o None in caso di errore.
        """
        if not encrypted_memo:
            return None
        try:
            # Decodifica base64 (con validate=True per controllare il padding)
            payload = base64.b64decode(encrypted_memo.strip(), validate=True)
            # Il payload deve essere almeno IV (16) + Tag (16) + 1 byte di ciphertext
            if len(payload) < 33:
                return None
            
            iv = payload[:16]
            tag = payload[16:32]
            ciphertext = payload[32:]
            
            key = MemoCrypto.derive_shared_secret(sender_public_key_hex, recipient_private_key_hex)
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(ciphertext) + decryptor.finalize()
            return decrypted.decode('utf-8')
        except Exception:
            # Silenziosamente fallisce
            return None