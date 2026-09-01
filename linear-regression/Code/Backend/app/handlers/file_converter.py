import os
import math
import tempfile
import pandas as pd
import pyreadstat

PREVIEW_ROWS = 100


def file_converter(file, page=1, page_size=PREVIEW_ROWS):
    ext = os.path.splitext(file.filename)[1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        file.save(temp_file.name)
        temp_path = temp_file.name

    try:
        # =========================
        # lectura archivo
        # =========================

        if ext == ".sav":
            df, meta = pyreadstat.read_sav(temp_path)

        elif ext == ".csv":
            df = pd.read_csv(temp_path)

        elif ext == ".xlsx":
            df = pd.read_excel(
                temp_path,
                engine="openpyxl"
            )

        elif ext == ".xls":
            df = pd.read_excel(
                temp_path,
                engine="xlrd"
            )

        elif ext == ".ods":
            df = pd.read_excel(
                temp_path,
                engine="odf"
            )

        elif ext == ".data":
            try:
                df = pd.read_csv(temp_path)

                if df.shape[1] == 1:
                    raise ValueError(
                        "posible separador incorrecto"
                    )

            except Exception:
                df = pd.read_csv(
                    temp_path,
                    sep=None,
                    engine="python"
                )

        else:
            raise ValueError(
                f"Tipo de archivo no soportado: {ext}"
            )

        # =========================
        # validaciones
        # =========================

        if df.empty:
            raise ValueError(
                "El archivo fue leído pero no contiene datos."
            )

        # =========================
        # limpiar NaN
        # =========================

        df = df.fillna("")

        # =========================
        # paginación
        # =========================

        total_rows = len(df)
        total_columns = len(df.columns)

        total_pages = max(
            1,
            math.ceil(total_rows / page_size)
        )

        page = max(1, min(page, total_pages))

        start = (page - 1) * page_size
        end = start + page_size

        paginated_df = df.iloc[start:end]

        # =========================
        # metadata
        # =========================

        approx_memory_mb = round(
            df.memory_usage(deep=True).sum() / (1024 * 1024),
            2
        )

        # =========================
        # respuesta
        # =========================

        return {
            "ok": True,

            "columns": df.columns.tolist(),

            "data": paginated_df.values.tolist(),

            "meta": {
                "page": page,
                "page_size": page_size,

                "total_rows": total_rows,
                "total_columns": total_columns,

                "total_pages": total_pages,

                "memory_mb": approx_memory_mb,

                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)