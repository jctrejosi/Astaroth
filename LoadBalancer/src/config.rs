use std::env;

/// Configuración del servicio desde variables de entorno.
#[derive(Debug, Clone)]
pub struct Config {
    /// Puerto donde publica el balanceador (default 8016, siguiente libre del
    /// rango de Astaroth 8010-8015).
    pub port: u16,
    pub highs_url: String,
    pub highs_api_key: Option<String>,
}

impl Config {
    pub fn from_env() -> Self {
        Self {
            port: env::var("LOAD_BALANCER_PORT")
                .ok()
                .and_then(|p| p.parse().ok())
                .unwrap_or(8016),
            highs_url: env::var("HIGHS_URL").unwrap_or_else(|_| "http://127.0.0.1:8015".into()),
            highs_api_key: env::var("HIGHS_API_KEY").ok().filter(|k| !k.is_empty()),
        }
    }
}
