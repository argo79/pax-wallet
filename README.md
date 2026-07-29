# 🕊️ PAX Wallet

> **Peace Through Free Money**

[![Version](https://img.shields.io/badge/version-v0.9.0b-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)]()
[![Rust](https://img.shields.io/badge/Rust-stable-orange?logo=rust)]()
[![Reticulum](https://img.shields.io/badge/Network-Reticulum-red)]()

---

## 📖 Overview

**PAX Wallet** is a free, decentralized, human-centric wallet designed for peer-to-peer payments over the **Reticulum** mesh network.

Built with **Rust** and **Python**, it combines the speed and safety of compiled code with the flexibility of Python scripting.

Part of the **HOPE Ecosystem (Human Open Payment Ecosystem)**, PAX Wallet promotes a vision of:

- 🌍 Borderless finance
- 🔓 Permissionless payments
- 🤝 Peer-to-peer networking
- 🕊️ Human sovereignty
- 💸 Free and open money


<img src="./img/mappa-generale.png" alt="Scenario" width="800">

---

## 🔧 Technical Specifications

| Component | Technology |
|-----------|------------|
| **Core Engine** | Rust (`wallet_core.so` / `wallet_core.dll`) |
| **CLI Framework** | Python 3.11+ |
| **Networking** | Reticulum |
| **Database** | SQLite3 |
| **Cryptography** | ECDSA, SHA-256, Base58, BIP32, BIP39 |
| **XRP Support** | `xrpl-py` |
| **XLM Support** | `stellar-sdk` |

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

### Network Security

Reticulum provides:

- 🔐 End-to-end encryption
- 🌐 Fully decentralized networking
- 🔄 Automatic mesh routing
- 🆔 Cryptographic node identities
- 🚫 No central servers
- 🚫 No DNS infrastructure required
- 🚫 No public IP address required
- 📡 Works over radio, Wi-Fi, Ethernet, LoRa and other transports
- 🌍 Operates on local, mesh, or Internet-connected networks
- 🔀 Multi-hop packet forwarding
- 🛡️ Resistant to censorship and infrastructure failures
- ⚡ Self-organizing network topology
- 📦 Store-and-forward messaging for intermittently connected nodes
- 🔑 Self-sovereign cryptographic identities
- 📁 Secure transfer of files and documents
- 🪪 Private exchange of digital credentials and identity documents
- 🚗 Secure sharing of licenses, certificates, and permits
- 💬 Private peer-to-peer messaging
- 💳 Native support for decentralized payments
- 🔒 No trusted third party required
- 👤 Pseudonymous operation by design (no mandatory accounts or personal registration)

---

## 🚀 Features

### Wallet Management

| Feature | Status |
|---------|--------|
| Create HD Wallet | ✅ |
| Import Wallet | ✅ |
| Multi-Wallet Support | ✅ |
| Child Address Derivation (XRP) | ✅ |
| Balance Check | ✅ |

### 📥 Supported Import Formats

#### 🌱 BIP39 Mnemonic (12/24 words)

```text
abandon abandon abandon abandon abandon abandon
abandon abandon abandon abandon abandon about
legal winner thank year wave sausage worth useful
legal winner thank year wave sausage worth useful
legal winner thank year wave sausage worth title
```
🔑 XRP Private Key

```text
E4A1F8B3C29D6E7F80123456789ABCDEF0123456789ABCDEF0123456789ABCD
```
⭐ Stellar Private Key

```text
SA4KQ7M9X2Y5N8P3R6T1V4W7Z0B2C5D8E1F4G7H0J3K6L9M2N5P8Q1R4T7V
```
📱 Xaman Numeric Backup

```text
123456-654321-987654-112233-445566-778899-123456-654321
```

###    ⚠️ All values shown above are examples only and cannot access any real wallet.

Transactions
Feature Status
Send XRP    ✅
Send XLM    ✅
Token Transfers ✅
Trustlines  ✅
Transaction Memos   ✅
Reticulum Integration
Feature Status
Gateway Mode    ✅
Peer Discovery  ✅
Gateway Metrics ✅
Mesh Routing    ✅
Offline Store & Forward ✅
Security
Feature Status
Encrypted Wallet Storage    ✅
Backup & Restore    ✅
Mnemonic Recovery   ✅
Multi-Signature Wallets 🚧 Planned
Cold Storage Signing    🚧 Planned

## 🏗️ Architecture

```text

                +-------------------------+
                |      Python CLI/TUI     |
                +-----------+-------------+
                            |
                            |
                +-----------v-------------+
                |      Rust Core Engine   |
                |  Cryptography / Wallet  |
                +-----------+-------------+
                            |
          +-----------------+-----------------+
          |                                   |
+---------v---------+               +---------v---------+
|       XRP         |               |        XLM        |
|     xrpl-py       |               |   stellar-sdk     |
+-------------------+               +-------------------+
                            |
                    +-------v--------+
                    |   Reticulum    |
                    | Mesh Networking|
                    +----------------+
```

📦 Installation
From Release (Recommended)
```bash

# Linux
wget https://github.com/argo79/pax-wallet/releases/download/v0.9.0b/wallet
chmod +x wallet
./wallet interactive
```

# Windows
# Download wallet.exe and run
```test
wallet.exe interactive
```

From Source
```bash

# Clone repository
git clone https://github.com/argo79/pax-wallet.git
cd pax-wallet

# Install dependencies
pip install -r requirements.txt

# Build Rust core (optional, pre-built libs included)
./build_rust_core.sh

# Run
python3 wallet_cli.py interactive
```

### Dependencies
```txt

bip32>=3.0.0
mnemonic>=0.20
xrpl-py>=4.0.0
stellar-sdk>=10.0.0
cryptography>=41.0.0
ecdsa>=0.18.0
base58>=2.1.0
RNS>=0.5.0
colorama>=0.4.6
```

## 🖥️ CLI Commands

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
trustline-remove ASSET  Remove trustline
send-token --token TOKEN    Send custom token
Reticulum Commands (inside interactive)
Command Description
Status  Show gateway status
Avvia gateway   Start gateway mode
Ferma gateway   Stop gateway mode
Scopri gateway  Discover gateways on network
Scopri wallet   Discover wallets on network
Peer metriche   Show peer metrics table
Miglior gateway Find best gateway for asset
Richiedi info gateway   Request gateway info
Invia transazione   Send transaction via Reticulum

## 🌐 Network Architecture
```text

┌─────────────────────────────────────────────────────────────┐
│                    HOPE ECOSYSTEM                           │
│  (Human Open Payment Ecosystem)                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │  PAX Wallet  │◄───│  PAX Wallet  │◄───│  PAX Wallet  │    │
│  │  (Node 1)   │    │  (Node 2)   │    │  (Node 3)   │    │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    │
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Reticulum Network (Mesh)               │    │
│  │         Encrypted, Decentralized, P2P              │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   Gateway   │    │   Gateway   │    │   Gateway   │    │
│  │  (Relay 1)  │    │  (Relay 2)  │    │  (Relay 3)  │    │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    │
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         XRP / XLM Networks (Internet)              │    │
│  │         On-chain Settlement                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 🔐 Why PAX Wallet?

Feature PAX Wallet  Traditional Wallets
Decentralized   ✅ Yes (Reticulum)   ❌ Central servers
Privacy ✅ End-to-end encrypted  ❌ Metadata exposed
Control ✅ Self-custodial    ❌ Third-party custody
Network ✅ Mesh (offline-capable)    ❌ Internet only
Fees    ✅ Minimal   ❌ High (middlemen)
Freedom ✅ Permissionless    ❌ Gatekeepers
Speed   ✅ Rust/Core ❌ Slow (interpreted)
🛠️ Build from Source
Linux
```bash

./build_rust_core.sh
./build_wallet.sh
./dist/wallet interactive
```
Windows
```powershell
# Install prerequisites
pip install -r requirements.txt

# Build (requires wallet_core.dll)
pyinstaller --onefile --console --name wallet.exe wallet_cli.py

# Run
wallet.exe interactive
```

## 📚 Documentation

    Reticulum: https://reticulum.network/

    XRP Ledger: https://xrpl.org/

    Stellar Network: https://stellar.org/

    BIP32: https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki

    BIP39: https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki

## 🌍 Philosophy

    "Money is freedom. Freedom is human. Human is hope."

PAX Wallet is not just a wallet — it's a statement.

We believe in:

    Decentralization - No single point of failure, no central authority

    Privacy - Your transactions are your business

    Freedom - Permissionless, borderless, open

    Humanity - Technology serving humans, not the other way around

### HOPE is the vision. PAX is the tool.

## 📜 Roadmap
Version Features
v1.0.0  Full XRP/XLM support, Trustlines and custom tokens, Stable Reticulum gateway, Peer discovery and metrics
v1.1.0  Multi-language (IT, EN, RU, CN), CSV/JSON peer export, Automatic wallet backup
v1.2.0  Native mobile client (Android/iOS), Multi-signature support, Cold storage signing
v2.0.0  Nomad Network integration, XRP smart contracts (hooks), Full HOPE Ecosystem

## 🐛 Known Issues

    Reticulum gateway in propagation mode (-p) can consume significant resources. Use without -p for lightweight usage.

    Initial peer discovery may take a few seconds.

    On slow networks, info requests may timeout (configurable).

## 🤝 Contributing

Contributions welcome! Fork the repository, make your changes, and submit a pull request.
```bash

git clone https://github.com/argo79/pax-wallet.git
cd pax-wallet
git checkout -b feature/your-feature
# Make changes
git commit -m "Add your feature"
git push origin feature/your-feature
```

Feel free to:

    Open an issue

    Submit a pull request

    Suggest new features

    Improve documentation

<h3>📝 License</h3>

Distributed under the MIT License.

https://img.shields.io/badge/License-MIT-yellow.svg
https://img.shields.io/badge/python-3.11+-blue.svg
https://img.shields.io/badge/Rust-1.70+-orange.svg
https://img.shields.io/badge/Reticulum-0.5+-purple.svg
<h3>☕ Support Development</h3><p> If PAX Wallet is useful to you, consider buying me a virtual coffee! ☕ Every contribution, big or small, helps keep development alive. </p><div align="center">

## 💰 Donations

https://img.shields.io/badge/Donate-XRP-00A9FF?style=flat&logo=ripple
https://img.shields.io/badge/Donate-XLM-08B5E8?style=flat&logo=stellar
https://img.shields.io/badge/Donate-XMR-FF6600?style=flat&logo=monero
Cryptocurrency  Address
XRP (Ripple)    rBKbetm51vuQQfg4Yo8fvweRya7gedcr9J
ETH (Ethereum)   0xd2d85288df96B4162814Ca7492039620371b9D81
XMR (Monero)    87jacZEtYvXcgnvEp7wu45gLwRBYpvwMr3N9dqhNipPWV69XwQX658tS73VEdghLopG1wA4STEdMPcGF8Tc3e18eJyQ4kMA
</div><p align="center"> <i>🙏 Thank you for your support! Every donation is an incentive to improve and add new features.</i> </p>

## 📊 Project Stats

https://img.shields.io/github/stars/argo79/pax-wallet?style=social
https://img.shields.io/github/forks/argo79/pax-wallet?style=social
https://img.shields.io/github/issues/argo79/pax-wallet
https://img.shields.io/github/last-commit/argo79/pax-wallet

<h3>🙏 Acknowledgments</h3><p>This project would not have been possible without the work of:</p><ul> <li> <strong>Reticulum Network Stack</strong> — The amazing decentralized network stack that makes all of this possible.<br> <a href="https://reticulum.network/">🌐 reticulum.network</a> · <a href="https://github.com/markqvist/Reticulum">📦 GitHub</a> </li> <li> <strong>Mark Qvist</strong> — For creating Reticulum and the entire ecosystem around it. 🙌 </li> <li> <strong>XRPL Foundation</strong> — For the XRP Ledger protocol and its capabilities.<br> <a href="https://xrpl.org/">🌐 xrpl.org</a> · <a href="https://github.com/XRPLF">📦 GitHub</a> </li> <li> <strong>Stellar Development Foundation</strong> — For the Stellar network and its ecosystem.<br> <a href="https://stellar.org/">🌐 stellar.org</a> · <a href="https://github.com/stellar">📦 GitHub</a> </li> <li> <strong>The Reticulum Community</strong> — For support, testing, and ideas that shaped this tool. </li> <li> <strong>The HOPE Community</strong> — For the vision of a human and decentralized economy. </li> </ul><p align="center"> <i>❤️ Thank you to everyone who contributes to the project, reports bugs, and suggests improvements!</i> </p><h3>📧 Contact</h3><p> <strong>Email:</strong> arg0netds@gmail.com<br> <strong>GitHub:</strong> <a href="https://github.com/argo79/pax-wallet">https://github.com/argo79/pax-wallet</a><br> <strong>RNS Identity:</strong> <code>877c43067be84c0442a6c4d547332f33</code> </p><p align="center"> <i>📡 Reach me via Reticulum using the identity hash above!</i> </p><h3>🐛 Known Issues</h3> <ul> <li>Reticulum gateway in propagation mode (-p) can consume significant resources. Use without -p for lightweight usage.</li> <li>Initial peer discovery may take a few seconds.</li> <li>On slow networks, info requests may timeout (configurable).</li> </ul><h3>🔜 Roadmap</h3><ul> <li><strong>v1.0.0</strong> <ul> <li>Full XRP/XLM support</li> <li>Trustlines and custom tokens</li> <li>Stable Reticulum gateway</li> <li>Peer discovery and metrics</li> </ul> </li> <li><strong>v1.1.0</strong> <ul> <li>Multi-language (IT, EN, RU, CN)</li> <li>CSV/JSON peer export</li> <li>Automatic wallet backup</li> </ul> </li> <li><strong>v1.2.0</strong> <ul> <li>Native mobile client (Android/iOS)</li> <li>Multi-signature support</li> <li>Cold storage signing</li> </ul> </li> <li><strong>v2.0.0</strong> <ul> <li>Nomad Network integration</li> <li>XRP smart contracts (hooks)</li> <li>Full HOPE Ecosystem</li> </ul> </li> </ul><h3>🕊️ Philosophy</h3><blockquote> <p><em>"Money is freedom. Freedom is human. Human is hope."</em></p> </blockquote><p> <strong>PAX Wallet</strong> is not just a wallet — it's a statement. </p><p>We believe in:</p> <ul> <li><strong>Decentralization</strong> — No single point of failure, no central authority</li> <li><strong>Privacy</strong> — Your transactions are your business</li> <li><strong>Freedom</strong> — Permissionless, borderless, open</li> <li><strong>Humanity</strong> — Technology serving humans, not the other way around</li> </ul><p align="center"> <i><strong>HOPE</strong> is the vision. <strong>PAX</strong> is the tool.</i> </p><p align="center"> <i> 🌍 In a divided world, HOPE is the dream of a better future. PAX is the tool to build it. </i> </p><p align="center"> <strong>PAX Wallet - Peace Through Free Money</strong><br> <strong>HOPE Ecosystem - Human Open Payment Ecosystem</strong> </p><p align="center"> <a href="https://github.com/argo79/pax-wallet">🏠 Repository</a> · <a href="https://github.com/argo79/pax-wallet/issues">🐛 Report Bug</a> · <a href="https://github.com/argo79/pax-wallet/discussions">💬 Discussions</a> </p> ```


