"""Configuración global del servicio iTransformer.

Antes el código hacía `from api.main import config`, pero el paquete se llama
`apis` y `config` no existía: los endpoints morían con ImportError/500.
Aquí se define explícitamente (lo que esperan `Model`, `JSONDataset` y
`WeatherPredictor`).
"""

from __future__ import annotations

from types import SimpleNamespace

config = SimpleNamespace(
    # Ventana de entrada / salida (deben coincidir en train y predict).
    seq_len=24,
    pred_len=6,
    # Arquitectura.
    d_model=64,
    n_heads=4,
    e_layers=2,
    d_ff=128,
    factor=1,
    dropout=0.1,
    activation="gelu",
    embed="timeF",
    freq="h",
    # Comportamiento.
    output_attention=False,
    use_norm=True,
    class_strategy="projection",
)
