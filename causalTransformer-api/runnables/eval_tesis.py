#!/usr/bin/env python
"""Evalúa un run CT de la tesis vs persistencia sobre el split de validación.

Correcciones Fase 3:
- La predicción se ancla correctamente: para predecir `x[k]` se envía una
  ventana de longitud `k` y se toma la **última** posición de salida. (La
  versión anterior enviaba `x_hist + y_future` completo y comparaba la salida
  de 6 pasos adelante contra el valor real a 1 paso.)
- Soporta rollout autoregresivo para `--horizon 2..h`.
- Soporta objetivos `delta`: reconstruye `x_{t+1} = x_t + Δ`.

Uso:
    .venv/bin/python runnables/eval_tesis.py \
        --dataset /ruta/files/tesis_world.ndjson \
        --run-id tesis-ct-003 --horizon 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config import RUNS_DIR  # noqa: E402
from api.services.predictor import get_predictor  # noqa: E402
from runnables.train_tesis import split_indices  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument(
        "--split", choices=["tail", "interleaved", "blocked"], default=None,
        help="por defecto usa el guardado en metadata.yaml",
    )
    p.add_argument("--val-fraction", type=float, default=0.15)
    p.add_argument("--blocks", type=int, default=5)
    p.add_argument("--block-index", type=int, default=0)
    p.add_argument("--horizon", type=int, default=1)
    p.add_argument("--write-metrics", action="store_true")
    return p.parse_args()


def _data(
    x_win: np.ndarray,
    u_win: np.ndarray,
    d_win: np.ndarray,
    static: np.ndarray,
    means: np.ndarray,
    stds: np.ndarray,
) -> dict:
    return {
        "prev_outputs": ((x_win - means) / stds)[None, ...],
        "prev_treatments": u_win[:-1][None, ...],
        "current_treatments": u_win[1:][None, ...],
        "vitals": d_win[1:][None, ...],
        "static_features": static,
        "active_entries": np.ones((1, len(x_win), 1)),
    }


def main() -> None:
    args = parse_args()
    run_dir = RUNS_DIR / args.run_id
    with (run_dir / "scaling_params.yaml").open() as fh:
        scaling = yaml.safe_load(fh)
    with (run_dir / "metadata.yaml").open() as fh:
        run_meta = yaml.safe_load(fh)

    means = np.asarray(scaling["input_means"])
    stds = np.asarray(scaling["input_stds"])
    phases = list(scaling["phases"])
    target_mode = scaling.get("target_mode", "absolute")

    with open(args.dataset) as fh:
        meta = json.loads(fh.readline())
        samples = [json.loads(line) for line in fh if line.strip()]

    split = args.split or run_meta.get("split", "tail")
    _, val_idx = split_indices(
        len(samples), split, args.val_fraction,
        run_meta.get("blocks", args.blocks),
        run_meta.get("block_index", args.block_index),
    )
    val = [samples[i] for i in val_idx]

    metrics = list(meta["metrics"])
    predictor = get_predictor(args.run_id, "ct")
    static = np.asarray(
        [[1.0 if s.get("phase") == p else 0.0 for p in phases] for s in val],
        dtype=np.float64,
    )[:, None, :]

    abs_err = np.zeros((len(val), args.horizon, len(metrics)))
    abs_pers = np.zeros((len(val), args.horizon, len(metrics)))

    for i, sample in enumerate(val):
        x_hist = np.asarray(sample["x_hist"], dtype=np.float64)
        u_full = np.asarray(sample["u_hist"] + sample["u_future"], dtype=np.float64)
        d_full = np.asarray(sample["d_hist"] + sample["d_future"], dtype=np.float64)
        y_future = np.asarray(sample["y_future"], dtype=np.float64)
        k = len(x_hist)

        x_run = x_hist.copy()
        for s in range(args.horizon):
            end = k + s                      # índice del estado a predecir
            start = end - k
            data = _data(
                x_run[-k:], u_full[start:end + 1],
                d_full[start:end + 1], static[i], means, stds,
            )
            pred = np.asarray(predictor.predict(data))[0, -1]
            if target_mode == "delta":
                pred = pred + x_run[-1]
            abs_err[i, s] = np.abs(pred - y_future[s])
            abs_pers[i, s] = np.abs(x_run[-1] - y_future[s])
            x_run = np.vstack([x_run, pred[None, :]])

    # Resumen: horizonte solicitado y global sobre todos los pasos.
    def summary(err: np.ndarray) -> dict:
        return {
            m: {
                "mae": float(err[:, :, j].mean()),
                "persistence": float(abs_pers[:, :, j].mean()),
            }
            for j, m in enumerate(metrics)
        }

    mae = abs_err[:, -1, :]
    pers = abs_pers[:, -1, :]
    print(f"split={split} horizon={args.horizon} target={target_mode} "
          f"n={len(val)}")
    print(f"{'metric':16} {'MAE':>10} {'persist':>10} {'MASE':>8} {'mejora':>9}")
    print("-" * 58)
    mases = []
    for j, metric in enumerate(metrics):
        m, p = mae[:, j].mean(), pers[:, j].mean()
        gain = (p - m) / p * 100 if p else 0.0
        mase = m / p if p else float("nan")
        mases.append(mase)
        print(f"{metric:16} {m:10.4f} {p:10.4f} {mase:8.3f} {gain:8.1f}%")
    print("-" * 58)
    mases_arr = np.asarray(mases, dtype=np.float64)
    global_gain = (pers.mean() - mae.mean()) / pers.mean() * 100 if pers.mean() else 0.0
    print(f"{'GLOBAL':16} {mae.mean():10.4f} {pers.mean():10.4f} "
          f"{np.nanmean(mases_arr):8.3f} {global_gain:8.1f}%")

    if args.write_metrics:
        payload = {
            "run_id": args.run_id,
            "split": split,
            "horizon": args.horizon,
            "target_mode": target_mode,
            "n": len(val),
            "global": {
                "mae": float(mae.mean()),
                "persistence": float(pers.mean()),
                "gain_pct": float(global_gain),
                "mean_mase": float(np.nanmean(mases_arr)),
            },
            "by_metric": summary(abs_err),
            "by_step": {
                str(s + 1): float(abs_err[:, s, :].mean()) for s in range(args.horizon)
            },
        }
        out = run_dir / f"metrics_h{args.horizon}_{split}.yaml"
        with out.open("w") as fh:
            yaml.safe_dump(payload, fh, allow_unicode=True)
        print(f"[eval_tesis] métricas escritas en {out}")


if __name__ == "__main__":
    main()
