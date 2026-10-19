#!/usr/bin/env python
"""Entrena un Causal Transformer (CT) sobre el dataset NDJSON de la tesis.

Produce un run **local** compatible con `api/utils/model_loader.load_model_from_path`:

    api/storage/runs/<run_id>/
        .hydra/config.yaml      # args completos (los usa load_from_checkpoint)
        checkpoints/*.ckpt      # pesos
        scaling_params.yaml     # input/output means+stds
        metadata.yaml           # metadatos del job

No usa Hydra, MLflow ni Celery: entrena en CPU y deja los artefactos listos
para que `causalTransformer-api` los cargue desde disco.

Uso (desde causalTransformer-api/):
    .venv/bin/python runnables/train_tesis.py \
        --dataset /ruta/files/tesis_world.ndjson \
        --run-id tesis-ct-001 --epochs 30
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import yaml
from omegaconf import OmegaConf
from pytorch_lightning import Trainer, seed_everything
from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint
from torch.utils.data import Dataset

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.ct import CT  # noqa: E402

DEFAULT_PHASES = ("Vegetativa", "Floración", "Cosecha")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True, help="NDJSON de build_dataset.js")
    p.add_argument("--run-id", default=None)
    p.add_argument("--run-dir", default=None)
    p.add_argument("--phases", default=",".join(DEFAULT_PHASES))
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--hidden", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--dropout", type=float, default=0.1)
    p.add_argument("--weight-decay", type=float, default=0.0)
    p.add_argument("--val-fraction", type=float, default=0.15)
    p.add_argument(
        "--split",
        choices=["tail", "interleaved", "blocked"],
        default="tail",
        help="tail: último tramo; interleaved: 1 de cada N; blocked: bloque contiguo",
    )
    p.add_argument("--blocks", type=int, default=5)
    p.add_argument("--block-index", type=int, default=0)
    p.add_argument(
        "--target",
        choices=["absolute", "delta"],
        default="absolute",
        help="delta: predecir x_{t+1}-x_t (paridad con persistencia)",
    )
    p.add_argument("--patience", type=int, default=0, help="0 = sin early stopping")
    p.add_argument("--no-val", action="store_true", help="desactiva validación")
    p.add_argument("--seed", type=int, default=100)
    p.add_argument("--smoke", action="store_true", help="1 epoch y pocos datos")
    return p.parse_args()


def load_ndjson(path: Path) -> tuple[dict, list[dict]]:
    with path.open() as fh:
        meta = json.loads(fh.readline())
        samples = [json.loads(line) for line in fh if line.strip()]
    return meta, samples


def build_arrays(
    samples: list[dict], phases: list[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Concatena historia + futuro en una trayectoria de longitud k+h."""
    xs, us, ds, statics = [], [], [], []
    for s in samples:
        xs.append(np.asarray(s["x_hist"] + s["y_future"], dtype=np.float64))
        us.append(np.asarray(s["u_hist"] + s["u_future"], dtype=np.float64))
        ds.append(np.asarray(s["d_hist"] + s["d_future"], dtype=np.float64))
        phase = s.get("phase")
        statics.append([1.0 if phase == p else 0.0 for p in phases])
    return (
        np.stack(xs),
        np.stack(us),
        np.stack(ds),
        np.asarray(statics, dtype=np.float64),
    )


def split_indices(
    n: int, mode: str, val_fraction: float, blocks: int, block_index: int
) -> tuple[np.ndarray, np.ndarray]:
    """Índices train/val. `blocked` deja un hueco temporal (sin fuga)."""
    idx = np.arange(n)
    if mode == "tail":
        cut = max(1, int(n * (1.0 - val_fraction)))
        return idx[:cut], idx[cut:]
    if mode == "interleaved":
        step = max(2, int(round(1.0 / max(val_fraction, 1e-6))))
        mask = idx % step == step - 1
        return idx[~mask], idx[mask]

    blocks = max(2, blocks)
    size = max(1, n // blocks)
    start = block_index * size
    end = n if block_index >= blocks - 1 else start + size
    val = idx[start:end]
    train = np.concatenate([idx[:start], idx[end:]])
    if len(train) == 0 or len(val) == 0:
        raise ValueError(f"split inválido: blocks={blocks} block_index={block_index}")
    return train, val


def make_data(
    x: np.ndarray,
    u: np.ndarray,
    d: np.ndarray,
    st: np.ndarray,
    target_mode: str = "absolute",
) -> dict[str, np.ndarray]:
    """Contrato del dataset causal (alineación del upstream)."""
    n, t, _ = x.shape
    if target_mode == "delta":
        targets = x[:, 1:, :] - x[:, :-1, :]
    else:
        targets = x[:, 1:, :]
    return {
        "sequence_lengths": np.full((n,), t - 1, dtype=np.float64),
        "prev_outputs": x[:, :-1, :],
        "outputs": targets,
        "unscaled_outputs": targets,
        "prev_treatments": u[:, :-1, :],
        "current_treatments": u[:, 1:, :],
        "vitals": d[:, 1:, :],
        "static_features": st,
        "active_entries": np.ones((n, t - 1, 1), dtype=np.float64),
    }


class DictDataset(Dataset):
    """Dataset mínimo sobre un dict de arrays ya procesados."""

    def __init__(self, data: dict, subset_name: str, scaling_params: dict | None = None):
        self.data = data
        self.subset_name = subset_name
        self.scaling_params = scaling_params
        self.norm_const = 1.0

    def __len__(self) -> int:
        return len(self.data["active_entries"])

    def __getitem__(self, index: int) -> dict:
        return {k: v[index] for k, v in self.data.items()}


class DictCollection:
    """Sustituto mínimo de RealDatasetCollection para CT."""

    def __init__(self, train_f, val_f, projection_horizon: int):
        self.train_f = train_f
        self.val_f = val_f
        self.has_vitals = True
        self.autoregressive = True
        self.projection_horizon = projection_horizon
        self.processed_data_multi = True
        self.train_scaling_params = train_f.scaling_params


def build_args(
    *,
    dim_x: int,
    dim_u: int,
    dim_d: int,
    dim_static: int,
    k: int,
    h: int,
    hidden: int,
    batch: int,
    lr: float,
    dropout: float,
    weight_decay: float,
    epochs: int,
) -> OmegaConf:
    seq_len = k + h
    return OmegaConf.create(
        {
            "exp": {
                "seed": 100,
                "gpus": [0],
                "max_epochs": epochs,
                "logging": False,
                "mlflow_uri": "http://127.0.0.1:5000",
                "unscale_rmse": True,
                "percentage_rmse": False,
                "alpha": 0.01,
                "update_alpha": False,
                "alpha_rate": "exp",
                "balancing": "grad_reverse",
                "bce_weight": False,
                "weights_ema": False,
                "beta": 0.99,
            },
            "model": {
                "name": "CT",
                "dim_treatments": dim_u,
                "dim_vitals": dim_d,
                "dim_static_features": dim_static,
                "dim_outcomes": dim_x,
                "multi": {
                    "max_seq_length": seq_len,
                    "seq_hidden_units": hidden,
                    "br_size": hidden,
                    "fc_hidden_units": hidden,
                    "dropout_rate": dropout,
                    "num_layer": 1,
                    "num_heads": 2,
                    "max_grad_norm": 1.0,
                    "batch_size": batch,
                    "attn_dropout": True,
                    "disable_cross_attention": False,
                    "isolate_subnetwork": "_",
                    "self_positional_encoding": {
                        "absolute": False,
                        "trainable": True,
                        "max_relative_position": seq_len,
                    },
                    "optimizer": {
                        "optimizer_cls": "adam",
                        "learning_rate": lr,
                        "weight_decay": weight_decay,
                        "lr_scheduler": False,
                    },
                    "augment_with_masked_vitals": True,
                    "tune_hparams": False,
                    "tune_range": 50,
                    "hparams_grid": None,
                    "resources_per_trial": None,
                },
            },
            "dataset": {
                "name": "tesis",
                "val_batch_size": batch,
                "treatment_mode": "multilabel",
                "projection_horizon": h,
                "max_seq_length": seq_len,
            },
        }
    )


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    torch.set_default_dtype(torch.double)

    phases = [p.strip() for p in args.phases.split(",") if p.strip()]
    meta, samples = load_ndjson(Path(args.dataset))
    k, h = int(meta["k"]), int(meta["h"])
    metrics = list(meta["metrics"])
    if args.smoke:
        samples = samples[: min(96, len(samples))]
        args.epochs = 1

    x, u, d, st = build_arrays(samples, phases)
    n = len(x)
    train_idx, val_idx = split_indices(
        n, args.split, args.val_fraction, args.blocks, args.block_index
    )
    train_data = make_data(
        x[train_idx], u[train_idx], d[train_idx], st[train_idx], args.target
    )
    val_data = make_data(
        x[val_idx], u[val_idx], d[val_idx], st[val_idx], args.target
    )
    dim_x = x.shape[-1]

    # z-score: entradas y objetivos con sus propias estadísticas.
    # En modo delta el objetivo tiene media ~0 y escala mucho menor que `x`
    # (decisión D12: scaler ajustado SOLO en train).
    in_flat = train_data["prev_outputs"].reshape(-1, dim_x)
    in_mean, in_std = in_flat.mean(axis=0), in_flat.std(axis=0)
    in_std[in_std < 1e-8] = 1.0

    out_flat = train_data["outputs"].reshape(-1, dim_x)
    if args.target == "delta":
        out_mean, out_std = out_flat.mean(axis=0), out_flat.std(axis=0)
        out_std[out_std < 1e-8] = 1.0
    else:
        out_mean, out_std = in_mean, in_std

    def normalize(arr: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
        return (arr - mean) / std

    for split_data in (train_data, val_data):
        split_data["prev_outputs"] = normalize(split_data["prev_outputs"], in_mean, in_std)
        split_data["outputs"] = normalize(split_data["outputs"], out_mean, out_std)

    scaling = {
        "input_means": in_mean.tolist(),
        "input_stds": in_std.tolist(),
        "output_means": out_mean.tolist(),
        "output_stds": out_std.tolist(),
        "target_mode": args.target,
        "metrics": metrics,
        "phases": phases,
    }
    train_f = DictDataset(train_data, "train_f", scaling)
    val_f = DictDataset(val_data, "val_f", scaling)
    collection = DictCollection(train_f, val_f, projection_horizon=h)

    cfg = build_args(
        dim_x=dim_x,
        dim_u=u.shape[-1],
        dim_d=d.shape[-1],
        dim_static=len(phases),
        k=k,
        h=h,
        hidden=args.hidden,
        batch=args.batch_size,
        lr=args.lr,
        dropout=args.dropout,
        weight_decay=args.weight_decay,
        epochs=args.epochs,
    )

    run_id = args.run_id or f"tesis-ct-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = Path(args.run_dir) if args.run_dir else ROOT / "api" / "storage" / "runs" / run_id
    (run_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
    (run_dir / ".hydra").mkdir(parents=True, exist_ok=True)
    OmegaConf.save(cfg, run_dir / ".hydra" / "config.yaml")

    model = CT(cfg, collection)
    use_val = not args.no_val
    monitor = "multi_val_loss"
    checkpoint = ModelCheckpoint(
        dirpath=run_dir / "checkpoints",
        filename="ct",
        auto_insert_metric_name=False,
        save_last=not use_val,
        save_top_k=1 if use_val else 0,
        monitor=monitor if use_val else None,
        mode="min",
    )
    callbacks = [checkpoint]
    if use_val and args.patience > 0:
        callbacks.append(
            EarlyStopping(monitor=monitor, patience=args.patience, mode="min")
        )
    trainer = Trainer(
        max_epochs=args.epochs,
        accelerator="cpu",
        devices=1,
        logger=False,
        enable_checkpointing=True,
        callbacks=callbacks,
        default_root_dir=str(run_dir),
        gradient_clip_val=1.0,
        limit_val_batches=1.0 if use_val else 0,
        enable_progress_bar=False,
    )
    trainer.fit(model)

    with (run_dir / "scaling_params.yaml").open("w") as fh:
        yaml.safe_dump(scaling, fh, allow_unicode=True)

    metadata = {
        "job_id": run_id,
        "model_type": "ct",
        "status": "finished",
        "run_dir": str(run_dir),
        "dataset": str(Path(args.dataset)),
        "samples": n,
        "train_samples": len(train_idx),
        "val_samples": len(val_idx),
        "split": args.split,
        "blocks": args.blocks,
        "block_index": args.block_index,
        "target": args.target,
        "weight_decay": args.weight_decay,
        "best_val_loss": float(checkpoint.best_model_score or float("nan")),
        "k": k,
        "h": h,
        "metrics": metrics,
        "phases": phases,
        "epochs": args.epochs,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with (run_dir / "metadata.yaml").open("w") as fh:
        yaml.safe_dump(metadata, fh, allow_unicode=True)

    print(f"[train_tesis] run listo: {run_dir}")
    print(f"[train_tesis] checkpoints: {sorted(p.name for p in (run_dir / 'checkpoints').glob('*.ckpt'))}")


if __name__ == "__main__":
    main()
