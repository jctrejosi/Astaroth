# Seguridad de dependencias

Auditoría realizada el **14 de octubre de 2026** con `pip-audit` (base de datos
OSV/PyPA) sobre todos los manifiestos Python del monorepo. Estado: **sin
vulnerabilidades conocidas en ningún manifiesto**.

## Estado por proyecto

| Manifiesto | Estado |
|---|---|
| `clustering-api/requirements.txt` | Sin vulnerabilidades (las versiones se resuelven a la última compatible) |
| `XGBoost-api/requirements.txt` | Sin vulnerabilidades |
| `uplift-api/requirements.txt` | Sin vulnerabilidades |
| `transformerApi/requirements.txt` | Sin vulnerabilidades (pins actualizados) |
| `causalTransformer-api/requirements.txt` | Sin vulnerabilidades (pins actualizados) |
| `linear-regression/Code/Backend/requirements.txt` | Sin vulnerabilidades (pins actualizados) |
| `highs/requirements.lock` | Sin vulnerabilidades |
| `core/pyproject.toml` | Sin dependencias externas |

## Cambios aplicados

### `transformerApi` (66 vulnerabilidades → 0)

| Paquete | Antes | Después |
|---|---|---|
| anyio | 4.12.1 | 4.14.2 |
| fastapi | 0.129.0 | 0.143.1 |
| fsspec | 2026.2.0 | 2026.6.0 |
| idna | 3.11 | 3.15 |
| pillow | 12.1.1 | 12.3.0 |
| python-dotenv | 1.2.1 | 1.2.2 |
| python-multipart | 0.0.22 | 0.0.31 |
| setuptools | 82.0.0 | 83.0.0 |
| starlette | 0.52.1 | 1.8.0 |
| torch | 2.10.0 | 2.13.0 |
| opentelemetry-api | — | 1.45.1 (nueva dependencia de FastAPI 0.143.1) |

### `causalTransformer-api` (107 vulnerabilidades → 0)

| Paquete | Antes | Después |
|---|---|---|
| fastapi | 0.116.1 | 0.143.1 |
| starlette (transitiva) | 0.47.3 | 1.8.0 (pin explícito) |
| python-multipart | 0.0.20 | 0.0.31 |
| python-dotenv | 1.1.1 | 1.2.2 |
| torch | 2.7.1 | 2.13.0 |
| pytorch-lightning | 2.5.3 | 2.6.6 |
| hydra-core | 1.3.2 | 1.3.7 |
| ray[tune] | 2.49.2 | 2.56.0 |
| mlflow | 3.2.0 | 3.17.1 |
| pytest | 8.4.1 | 9.0.3 |
| pyarrow (transitiva) | 21.0.0 | 23.0.1 (pin explícito) |
| cryptography (transitiva) | 49.0.0 | 50.0.0 (pin explícito, `mlflow` admite `<51`) |

### `linear-regression/Code/Backend` (8 vulnerabilidades → 0)

| Paquete | Antes | Después |
|---|---|---|
| Flask | 3.1.2 | 3.1.3 |
| Werkzeug | 3.1.4 | 3.1.9 |
| requests | 2.32.5 | 2.33.0 |
| urllib3 | 2.6.3 | 2.8.0 |
| idna | 3.11 | 3.15 |
| python-dotenv | 1.2.1 | 1.2.2 |
| anyio (transitiva) | 4.12.0 | 4.14.2 (pin explícito) |

### `highs`

Sin CVEs; se completó `requirements.lock` con `opentelemetry-api==1.45.1`
(dependencia runtime de FastAPI 0.143.1) para que el lock sea cerrado.

## Cómo reproducir la auditoría

```bash
python -m pip install pip-audit
python -m pip_audit -r clustering-api/requirements.txt
python -m pip_audit -r XGBoost-api/requirements.txt
python -m pip_audit -r uplift-api/requirements.txt
python -m pip_audit -r transformerApi/requirements.txt
python -m pip_audit -r causalTransformer-api/requirements.txt
python -m pip_audit -r linear-regression/Code/Backend/requirements.txt
python -m pip_audit -r highs/requirements.lock
```

## Compatibilidad y validación

- `pip-audit` resuelve el grafo completo de cada manifiesto y no reportó
  conflictos: las actualizaciones son consistentes entre sí (verificado también
  que existen wheels `cp311` para Linux y Windows de `torch 2.13.0`,
  `cryptography 50.0.0` y `pyarrow 23.0.1`).
- `transformerApi`, `causalTransformer-api` y `linear-regression` **no se
  ejecutaron** en esta máquina porque requieren modelos/artefactos y stacks
  pesados; sus APIs usadas son estables en los rangos actualizados
  (`FastAPI`/Starlette, `pytorch-lightning`, `MlflowClient`, `ray.tune`, `torch`).
  Antes de desplegarlos, ejecutar su smoke test habitual con los modelos
  reales (especialmente los runnables de entrenamiento de causal, que usan
  `pytorch-lightning`, y el flujo de subida/predicción de transformer).
- `highs` sí se validó completo: 84 tests, 95% de cobertura, Ruff/mypy limpios
  y contenedor con healthcheck.
- Las imágenes Docker usan etiquetas flotantes (`python:3.11-slim`,
  `python:3.12-slim`): cada rebuild incorpora los parches del sistema base.
  El sistema operativo de las imágenes no se audita con `pip-audit`; si se
  requiere, usar un escáner de imagen (Trivy/Grype) en CI.

## Política

1. **Dependabot** (`.github/dependabot.yml`) revisa semanalmente los
   manifiestos pip de cada servicio y los Dockerfiles raíz y de `highs`.
2. Antes de publicar una release (y antes de convertir `core` en librería
   instalable) ejecutar `pip-audit` sobre todos los manifiestos; bloquear la
   release si hay vulnerabilidades con parche disponible.
3. No se fijan avisos "sin versión de parche": si aparecen, se documentan aquí
   con su mitigación y se reevalúan al mes siguiente.
4. Los servicios sin lock (`clustering-api`, `XGBoost-api`, `uplift-api`)
   resuelven hoy a versiones limpias; para empaquetar Astaroth como librería
   instalable conviene fijarlas también (lock por servicio).
