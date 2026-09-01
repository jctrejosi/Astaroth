import os
import uuid
import pandas as pd

DATASET_DIR = "temp_datasets"

os.makedirs(DATASET_DIR, exist_ok=True)


def save_dataset(df: pd.DataFrame) -> str:
    dataset_id = str(uuid.uuid4())

    path = os.path.join(
        DATASET_DIR,
        f"{dataset_id}.parquet"
    )

    df.to_parquet(path)

    return dataset_id


def load_dataset(dataset_id: str) -> pd.DataFrame:
    path = os.path.join(
        DATASET_DIR,
        f"{dataset_id}.parquet"
    )

    if not os.path.exists(path):
        raise FileNotFoundError(
            "dataset no encontrado"
        )

    return pd.read_parquet(path)


def delete_dataset(dataset_id: str):
    path = os.path.join(
        DATASET_DIR,
        f"{dataset_id}.parquet"
    )

    if os.path.exists(path):
        os.remove(path)