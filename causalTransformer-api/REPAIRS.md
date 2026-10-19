# Reparaciones locales (Fase 3 — tesis)

Estos cambios **no** vienen del upstream y se perderían al actualizar el repo
desde git. Reaplicarlos si eso ocurre.

1. **`src/models/`** — vendorizado desde
   `Valentyn1997/CausalTransformer@c49a24f` (ver `src/models/VENDORED.md`).
2. **`src/models/time_varying_model.py`** — compatibilidad Lightning 2.x:
   - `training_step` sin `optimizer_idx` (mono-optimizador).
   - `optimizer_step` usa `optimizer_closure`.
   - `domain_confusion` con dos optimizadores no es compatible con
     `automatic_optimization` de PL 2.x; se usa `grad_reverse`.
   - **`validation_step` añadido** (el upstream no lo define): loguea
     `multi_val_loss` para poder monitorizar y hacer early stopping.
3. **`api/services/predictor.py`**:
   - carga runs locales (`api/storage/runs/<run_id>`) si existen, sin MLflow;
   - usa `_predict_forward` cuando el modelo no está adjunto a un `Trainer`;
   - convierte `data` JSON → `numpy.float64`;
   - castea el batch al dtype del modelo.
4. **`api/utils/model_loader.py`**:
   - `torch.set_default_dtype(torch.double)`;
   - pasa `autoregressive`, `has_vitals` y `projection_horizon` a
     `load_from_checkpoint` (el checkpoint no los guarda).
5. **`api/routers/predict.py`**:
   - `GET /predict/scaling/{run_id}` expone el scaler del run (para que el
     cliente normalice las entradas; la API solo desnormaliza la salida).
6. **`.gitignore`** — `models/` → `api/storage/models/` para no ignorar
   `src/models/`.
7. **`runnables/train_tesis.py`** — entrenamiento local de la tesis (CT en CPU,
   sin Hydra/MLflow/Celery): objetivo `absolute|delta`, splits
   `tail|interleaved|blocked`, `weight_decay`, early stopping y checkpoint del
   mejor epoch (`ct.ckpt`). El z-score de entradas y de objetivos se ajusta por
   separado en train (en `delta`, media≈0 y escala menor).
8. **`runnables/eval_tesis.py`** — evaluación offline vs persistencia por
   horizonte y split, con **MASE**. La versión anterior comparaba la salida de
   un paso de 6 min adelante contra el valor a 1 min; corregido (ventana de
   longitud `k`, última posición de salida).
