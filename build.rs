// build.rs
fn main() {
    // Questo è necessario per PyO3 con abi3
    #[cfg(feature = "python")]
    {
        pyo3_build_config::use_pyo3_cfgs();
    }
    println!("cargo:rerun-if-changed=src/lib.rs");
    println!("cargo:rerun-if-changed=Cargo.toml");
}