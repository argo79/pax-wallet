# 🕊️ PAX Wallet

> **Peace Through Free Money**

[![Version](https://img.shields.io/badge/version-v0.9.0b-blue.svg)]()
[![License](https://img.shields.io/badge/license-GPLv3-green.svg)]()
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

---

# 🔧 Technical Specifications

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

# 🛡️ Security & Cryptography

## Rust Core

- ✅ Memory-safe architecture
- ✅ Ownership model prevents memory corruption
- ✅ Compile-time type safety
- ✅ High-performance cryptographic operations
- ✅ Safe Python bindings through FFI

---

## Cryptographic Standards

| Standard | Purpose |
|----------|---------|
| **BIP32** | Hierarchical Deterministic wallets |
| **BIP39** | 12/24-word mnemonic recovery |
| **ECDSA** | Digital signatures |
| **SHA-256** | Secure hashing |
| **Base58** | Address encoding |
| **AES-256** | Optional encrypted wallet storage |

---

## Network Security

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

# 🚀 Features

## Wallet Management

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
```

or

```text
legal winner thank year wave sausage worth useful
legal winner thank year wave sausage worth useful
legal winner thank year wave sausage worth title
```

---

#### 🔑 XRP Private Key

```text
E4A1F8B3C29D6E7F80123456789ABCDEF0123456789ABCDEF0123456789ABCD
```

---

#### ⭐ Stellar Private Key

```text
SA4KQ7M9X2Y5N8P3R6T1V4W7Z0B2C5D8E1F4G7H0J3K6L9M2N5P8Q1R4T7V
```

---

#### 📱 Xaman Numeric Backup

```text
123456-654321-987654-112233-445566-778899-123456-654321
```

> **⚠️ All values shown above are examples only and cannot access any real wallet.**

---

## Transactions

| Feature | Status |
|---------|--------|
| Send XRP | ✅ |
| Send XLM | ✅ |
| Token Transfers | ✅ |
| Trustlines | ✅ |
| Transaction Memos | ✅ |

---

## Reticulum Integration

| Feature | Status |
|---------|--------|
| Gateway Mode | ✅ |
| Peer Discovery | ✅ |
| Gateway Metrics | ✅ |
| Mesh Routing | ✅ |
| Offline Store & Forward | ✅ |

---

## Security

| Feature | Status |
|---------|--------|
| Encrypted Wallet Storage | ✅ |
| Backup & Restore | ✅ |
| Mnemonic Recovery | ✅ |
| Multi-Signature Wallets | 🚧 Planned |
| Cold Storage Signing | 🚧 Planned |

---

# 🏗️ Architecture

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

---

# 🌍 Philosophy

PAX Wallet is more than a cryptocurrency wallet.

It is an experiment in **free, decentralized, and resilient digital finance**, where:

- Individuals own their money.
- Networks operate without centralized control.
- Payments remain possible even without Internet infrastructure.
- Privacy and freedom are considered fundamental rights.

---

# 📜 Roadmap

## v1.0

- [ ] Multi-signature wallets
- [ ] Cold storage support
- [ ] Hardware wallet integration
- [ ] QR-code transactions
- [ ] Plugin system

## Future

- [ ] Additional blockchain support
- [ ] Atomic swaps
- [ ] Lightning-style payment channels
- [ ] Mesh-native payment protocol
- [ ] Distributed contact directory

---

# 🤝 Contributing

Contributions are welcome.

Feel free to:

- Open an issue
- Submit a pull request
- Suggest new features
- Improve documentation

---

# 📄 License

Released under the **GNU GPL v3** License.

Freedom is a feature.

