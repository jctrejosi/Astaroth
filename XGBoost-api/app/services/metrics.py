from app.services.model_store import ModelStore


class MetricsService:

    @staticmethod
    def get_metrics(model_name: str) -> dict:
        metadata = ModelStore.load_metadata(model_name)

        response = {
            "status": "success",
            "model_name": metadata.get("model_name", model_name),
        }

        if "mae" in metadata:
            response.update({
                "mae": float(metadata["mae"]),
                "rmse": float(metadata["rmse"]),
                "r2": float(metadata["r2"]),
            })
        else:
            response.update({
                "problem_type": metadata.get("problem_type"),
                "metrics": metadata.get("metrics"),
            })

        return response