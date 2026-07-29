# 🕊️ PAX Wallet

> **Peace Through Free Money**

[![Version](https://img.shields.io/badge/version-v0.9.0b-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)]()
[![Rust](https://img.shields.io/badge/Rust-stable-orange?logo=rust)]()
[![Reticulum](https://img.shields.io/badge/Network-Reticulum-red)]()

---

## 📖 Overview

**PAX Wallet** is a free, decentralized, human-centric wallet for peer-to-peer payments over the **Reticulum** mesh network.

Built with **Rust** and **Python**, it combines the speed and safety of compiled code with the flexibility of Python scripting.

Part of the **HOPE Ecosystem** (Human Open Payment Ecosystem), PAX Wallet promotes a vision of:

- 🌍 Borderless finance
- 🔓 Permissionless payments
- 🤝 Peer-to-peer networking
- 🕊️ Human sovereignty
- 💸 Free and open money

---

## 🛡️ Security & Cryptography

### Rust Core
- ✅ Memory-safe architecture
- ✅ Ownership model prevents memory corruption
- ✅ Compile-time type safety
- ✅ High-performance cryptographic operations
- ✅ Safe Python bindings through FFI

### Cryptographic Standards
| Standard | Purpose |
|----------|---------|
| **BIP32** | Hierarchical Deterministic wallets |
| **BIP39** | 12/24-word mnemonic recovery |
| **ECDSA** | Digital signatures |
| **SHA-256** | Secure hashing |
| **Base58** | Address encoding |
| **AES-256** | Optional encrypted wallet storage |

### Network Security (Reticulum)
- 🔐 End-to-end encryption
- 🌐 Fully decentralized networking
- 🔄 Automatic mesh routing
- 🆔 Cryptographic node identities
- 🚫 No central servers, DNS, or public IP required
- 📡 Works over radio, Wi-Fi, Ethernet, LoRa
- 🔀 Multi-hop packet forwarding
- 🛡️ Resistant to censorship and infrastructure failures
- 📦 Store-and-forward messaging for offline nodes

---

## 🚀 Features

### Wallet Management
| Feature | Status |
|---------|--------|
| Create HD Wallet | ✅ |
| Import Wallet (Mnemonic/Seed/Xaman) | ✅ |
| Multi-Wallet Support | ✅ |
| Child Address Derivation (XRP) | ✅ |
| Balance Check | ✅ |

### Transactions
| Feature | Status |
|---------|--------|
| Send XRP | ✅ |
| Send XLM | ✅ |
| Token Transfers | ✅ |
| Trustlines | ✅ |
| Transaction Memos | ✅ |

### Reticulum Integration
| Feature | Status |
|---------|--------|
| Gateway Mode | ✅ |
| Peer Discovery | ✅ |
| Gateway Metrics | ✅ |
| Mesh Routing | ✅ |
| Offline Store & Forward | ✅ |

---

## 🏗️ Architecture

```text
+-------------------------+
|      Python CLI/TUI     |
+-----------+-------------+
            |
            |
+-----------v-------------+
|     Rust Core Engine    |
|   Cryptography / Wallet |
+-----------+-------------+
            |
    +-------+-------+
    |               |
+---v---------+ +---v---------+
|     XRP     | |     XLM     |
|   xrpl-py   | | stellar-sdk |
+-------------+ +-------------+
            |
    +-------v--------+
    |    Reticulum   |
    | Mesh Networking|
    +----------------+
```

📦 Installation
From Release (Recommended)

Linux

```bash
wget https://github.com/argo79/pax-wallet/releases/download/v0.9.0b/wallet
chmod +x wallet
./wallet interactive
```

Windows

Download wallet.exe and run:
```
wallet.exe interactive
```

From Source
```bash
git clone https://github.com/argo79/pax-wallet.git
cd pax-wallet
pip install -r requirements.txt
./build_rust_core.sh  # optional
python3 wallet_cli.py interactive
```

🖥️ CLI Commands

Command Description
interactive Launch interactive menu
create --name NAME  Create new wallet
import --seed SEED  Import wallet from seed
balance Show wallet balance
address Show wallet address
send --to ADDR --amount X   Send payment
history Show transaction history
info    Show wallet details
list-wallets    List all saved wallets
switch NAME Switch active wallet
trustlines  Show trustlines (XRP)
trustline-set ASSET ISSUER  Create trustline
send-token --token TOKEN    Send custom token


## 🌍 Philosophy

> **"Money is freedom. Freedom is human. Human is hope."**

PAX Wallet is not just a wallet — it's a statement.

We believe in:

- 🌍 **Decentralization** — No single point of failure, no central authority.
- 🔒 **Privacy** — Your transactions are your business.
- 🕊️ **Freedom** — Permissionless, borderless, open.
- 👤 **Humanity** — Technology serving humans, not the other way around.

> **HOPE is the vision. PAX is the tool.**

---

## 📜 Roadmap

| Version | Features |
|---------|----------|
| **v1.0.0** | TUI, GUI, (WEBUI?), Full XRP/XLM support, Trustlines, Tokens, Stable Reticulum Gateway, Peer Discovery |
| **v1.1.0** | Multi-language support (IT, EN, RU, CN), CSV/JSON export, Automatic wallet backup |
| **v1.2.0** | Native mobile client (Android/iOS), Multi-signature, Cold storage signing |
| **v2.0.0** | Nomad Network integration, XRP smart contracts, Full HOPE Ecosystem |

---

## 🐛 Known Issues

- ⚠️ Reticulum gateway in propagation mode (`-p`) can consume significant resources. Use without `-p` for lightweight usage.
- 🔎 Initial peer discovery may take a few seconds.
- ⏱️ On slow networks, information requests may timeout. Timeout values are configurable.

---

## 🤝 Contributing

Contributions are welcome!

```bash
git clone https://github.com/argo79/pax-wallet.git

cd pax-wallet

git checkout -b feature/your-feature
```
# Make changes
```bash
git add .

git commit -m "Add your feature"

git push origin feature/your-feature
```

Then open a Pull Request on GitHub.

📄 License

Distributed under the MIT License.
https://img.shields.io/badge/License-MIT-yellow.svg

🙏 Acknowledgments

PAX Wallet would not be possible without the following projects, developers and communities:

🌐 Reticulum Network Stack
💻 Reticulum on GitHub
👤 Mark Qvist — Creator of Reticulum
💧 XRP Ledger
⭐ Stellar Development Foundation
🤝 The Reticulum and HOPE communities
📧 Contact
Email: arg0netds@gmail.com
GitHub: argo79/pax-wallet
RNS Identity: 04511923b68ae34e0fda5721d82f596f
☕ Support Development

If PAX Wallet is useful to you, consider supporting the project with a donation.

Cryptocurrency  Address
XRP rBKbetm51vuQQfg4Yo8fvweRya7gedcr9J
ETH 0xd2d85288df96B4162814Ca7492039620371b9D81
XMR 87jacZEtYvXcgnvEp7wu45gLwRBYpvwMr3N9dqhNipPWV69XwQX658tS73VEdghLopG1wA4STEdMPcGF8Tc3e18eJyQ4kMA

⚠️ Always verify the destination address before sending funds.

<p align="center"> <i>🌍 In a divided world, HOPE is the dream of a better future. PAX is the tool to build it.</i> </p> <p align="center"> <strong>PAX Wallet — Peace Through Free Money</strong><br> <strong>HOPE Ecosystem — Human Open Payment Ecosystem</strong> </p> <p align="center"> <a href="https://github.com/argo79/pax-wallet">🏠 Repository</a> · <a href="https://github.com/argo79/pax-wallet/issues">🐛 Report Bug</a> · <a href="https://github.com/argo79/pax-wallet/discussions">💬 Discussions</a> </p> ```