# `src/models` — código vendorizado

Estos módulos provienen del proyecto original:

- **Repo:** https://github.com/Valentyn1997/CausalTransformer
- **Commit:** `c49a24faa57af966501e241f57a26b528f874a53` (2024-08-13)
- **Licencia:** MIT (ver `../../LICENSE`)

Se copiaron aquí porque el fork de Astaroth no incluía `src/models/`, aunque
`api/config.py` los referencia en `MODEL_CLASS_MAP` (carga dinámica por
`importlib`). Contiene `base`/`time_varying_model`, `crn`, `edct`, `ct`, `gnet`,
`rmsn`, `msm` y utilidades.

**No editar a mano sin documentarlo.** Si Astaroth se actualiza desde git, este
directorio debe re-vendorizarse desde el commit indicado (o uno más reciente).
