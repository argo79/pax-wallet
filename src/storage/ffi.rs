use pyo3::prelude::*;
use pyo3::types::PyDict;
use crate::{Database, Identity, Asset};

/// Modulo Python esportato come `wallet_core`
#[pymodule]
fn wallet_core(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyIdentity>()?;
    m.add_class::<PyAsset>()?;
    m.add_class::<PyDatabase>()?;
    m.add_function(wrap_pyfunction!(create_wallet, m)?)?;
    m.add_function(wrap_pyfunction!(sign_transaction, m)?)?;
    Ok(())
}

/// Classe Python per Identity
#[pyclass]
struct PyIdentity {
    inner: Identity,
}

#[pymethods]
impl PyIdentity {
    #[new]
    fn new(mnemonic: Option<&str>) -> Self {
        let mnemonic = mnemonic.unwrap_or(&Mnemonic::generate(12, Language::English).unwrap().to_string());
        Self {
            inner: Identity::new(mnemonic),
        }
    }

    fn fingerprint(&self) -> String {
        self.inner.fingerprint.clone()
    }

    fn derive_key(&self, network: &str, index: u32) -> PyResult<String> {
        let network = match network {
            "xrpl" => Network::XRPL,
            "stellar" => Network::Stellar,
            "bitcoin" => Network::Bitcoin,
            "ethereum" => Network::Ethereum,
            _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Unsupported network: {}", network)
            )),
        };
        
        let key = self.inner.derive_key(network, index);
        Ok(key.public_key)
    }
}

/// Classe Python per Asset
#[pyclass]
struct PyAsset {
    inner: Asset,
}

#[pymethods]
impl PyAsset {
    #[staticmethod]
    fn xrp() -> Self {
        Self { inner: Asset::xrp() }
    }

    #[staticmethod]
    fn xlm() -> Self {
        Self { inner: Asset::xlm() }
    }

    #[staticmethod]
    fn rlusd() -> Self {
        Self { inner: Asset::rlusd() }
    }

    fn __repr__(&self) -> String {
        format!("{}", self.inner)
    }
}

/// Classe Python per Database
#[pyclass]
struct PyDatabase {
    inner: Database,
}

#[pymethods]
impl PyDatabase {
    #[new]
    fn new(path: &str) -> PyResult<Self> {
        Ok(Self {
            inner: Database::new(path).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string())
            })?,
        })
    }

    fn save_identity(&self, identity: &PyIdentity) -> PyResult<()> {
        self.inner.save_identity(&identity.inner).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string())
        })
    }

    fn get_identity(&self, id: &str) -> PyResult<Option<PyIdentity>> {
        self.inner.get_identity(id).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string())
        }).map(|opt| opt.map(|id| PyIdentity { inner: id }))
    }
}

/// Funzione Python: crea un nuovo wallet
#[pyfunction]
fn create_wallet(name: Option<&str>, db_path: &str) -> PyResult<String> {
    let db = Database::new(db_path)?;
    let identity = Identity::new(&Mnemonic::generate(12, Language::English).unwrap().to_string());
    db.save_identity(&identity)?;
    Ok(identity.id)
}

/// Funzione Python: firma una transazione
#[pyfunction]
fn sign_transaction(_tx_data: &PyDict) -> PyResult<String> {
    // Qui il Core firma la transazione
    // La transazione arriva dal plugin Python come JSON
    // Il Core firma e restituisce la transazione firmata
    Ok("signed_transaction_hex".to_string())
}