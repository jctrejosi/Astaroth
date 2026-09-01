import pandas as pd

from app.schemas.train import TrainRequest
from app.utils.validation import validate_dataframe


class DataService:

    @staticmethod
    def to_dataframe(
        request: TrainRequest
    ) -> pd.DataFrame:

        rows = [
            record.model_dump()
            for record in request.data
        ]

        df = pd.DataFrame(rows)

        validate_dataframe(
            df=df,
            target_column=request.target_column
        )

        df["date"] = pd.to_datetime(
            df["date"],
            errors="raise"
        )

        df = df.sort_values(
            by="date"
        )

        df = df.drop_duplicates(
            subset=["date"],
            keep="last"
        )

        df = df.reset_index(
            drop=True
        )

        return df

    @staticmethod
    def get_feature_columns(
        df: pd.DataFrame,
        target_column: str
    ) -> list[str]:

        excluded_columns = {
            "date",
            target_column
        }

        return [
            column
            for column in df.columns
            if column not in excluded_columns
        ]

    @staticmethod
    def get_target_series(
        df: pd.DataFrame,
        target_column: str
    ) -> pd.Series:

        return df[target_column]

    @staticmethod
    def get_date_series(
        df: pd.DataFrame
    ) -> pd.Series:

        return df["date"]