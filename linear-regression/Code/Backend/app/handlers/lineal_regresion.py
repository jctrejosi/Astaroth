from pandas.api.types import (
    is_numeric_dtype,
    is_bool_dtype
)
import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.diagnostic import het_breuschpagan, het_white
from statsmodels.stats.stattools import durbin_watson, jarque_bera
from scipy.stats import shapiro, kstest

def safe_round(value):
    return round(value, 2) if value is not None else None

def is_serial_by_sort(s, tol=0.99):
    s = s.dropna()
    if not pd.api.types.is_numeric_dtype(s):
        return False
    diffs = s.sort_values().diff().dropna()
    # fracción de diferencias iguales
    most_common_ratio = diffs.value_counts(normalize=True).max()
    return most_common_ratio >= tol

# Clasificación automática de columnas para saber cuáles no usar en la regresión
def classify_columns(df, dependent=None, max_categories=15):
    info = {
        "other": [],
        "categorical": [],
        "datetime": [],
        "boolean": [],
        "constant": [],
        "id_like": [],
        "invalid": [],
        "serial": [],
    }

    n_rows = len(df)

    for col in df.columns:
        if col == dependent:
            continue

        s = df[col]
        nunique = s.nunique(dropna=True)

        # 1) constante
        if nunique <= 1:
            info["constant"].append(col)
            continue

        # 2) booleanos
        if is_bool_dtype(s) or set(s.dropna().unique()).issubset({0, 1, "0", "1", True, False}):
            info["boolean"].append(col)
            continue

        # 3) Comprobar si es una serie
        if is_numeric_dtype(s):
            if nunique == n_rows and pd.api.types.is_integer_dtype(s):
                if is_serial_by_sort(s):
                    info["serial"] = info.get("serial", []) + [col]
                else:
                    info["id_like"].append(col)

        # 4) datetime SOLO si es texto
        if s.dtype == "object":
            parsed = pd.to_datetime(s.dropna(), dayfirst=True, errors="coerce")

            # además exigimos separadores típicos de fecha
            has_date_tokens = s.dropna().astype(str).str.contains(r"[./\-:]").mean()

            if (
                len(parsed) > 0
                and parsed.notna().mean() >= 0.8
                and has_date_tokens >= 0.8
            ):
                info["datetime"].append(col)
                continue

        # 5) categóricos
        if nunique <= max_categories:
            info["categorical"].append(col)
            continue

        # 6) otros

        info["other"].append(col)

    return info

def run_regression(data: list, columns: list, dependent: str, alpha: float = 0.05) -> dict:
    try:
        # 0) cargar datos en DataFrame
        df_raw = pd.DataFrame(data, columns=columns)
        MAX_ROWS = 1500  # Limitar rows de datos para que no cuelgue el back
        if len(df_raw) > MAX_ROWS:
            df_raw = df_raw.sample(MAX_ROWS, random_state=42)

        column_errors = {}         # detalles por columna (ejemplos/filas)
        meta = {
            "dropped_columns": [],   # columnas eliminadas automáticamente
            "auto_dummies": [],      # categóricas convertidas a dummies
            "warnings": [],          # avisos (e.g. dependent reasignado)
            "rows_before": len(df_raw),
            "rows_after": None,
            "imputed_columns": {},   # columnas imputadas: Llenar valores vacíos
        }

        # 1) clasificar columnas y eliminar las innecesarias
        info = classify_columns(df_raw, dependent)
        drop_cols = info["datetime"] + info["id_like"] + info["constant"] + info["serial"] + ['id']
        meta["dropped_columns"] = drop_cols.copy()
        meta["warnings"].append(
            f"Columnas eliminadas por tipo: {', '.join(drop_cols)}"
        )
        df = df_raw.drop(columns=drop_cols, errors="ignore")

        # 2) detectar columnas constantes resultantes y descartarlas
        constant_cols_after = [c for c in df.columns if df[c].nunique() <= 1]
        if constant_cols_after:
            df = df.drop(columns=constant_cols_after, errors="ignore")
            meta["dropped_columns"] += constant_cols_after
            meta["warnings"].append(
                f"Se quitaron columnas constantes tras limpieza: {', '.join(constant_cols_after)}"
            )

        # 3) descartar columnas con demasiados NaN parciales
        nan_ratio = df.isna().mean()
        PARTIAL_NAN_THRESHOLD = 0.10  # 10% de tolerancia para NaN parciales
        cols_with_too_many_nan = nan_ratio[nan_ratio > PARTIAL_NAN_THRESHOLD].index.tolist()
        if cols_with_too_many_nan:
            meta["dropped_columns"].extend(cols_with_too_many_nan)
            meta["warnings"].append(
                f"Columnas eliminadas por exceso de valores no numéricos (> {PARTIAL_NAN_THRESHOLD*100}% NaN): {cols_with_too_many_nan}"
            )
            df = df.drop(columns=cols_with_too_many_nan, errors="ignore")

        # 4) transformar categóricas a dummies y booleanos a 0/1 (si existen)
        cats_to_dummy = [c for c in info["categorical"] if c in df.columns]
        bool_cols = [c for c in info["boolean"] if c in df.columns]

        for col in cats_to_dummy:
            df[col] = df[col].fillna("missing")  # asigna missing a NaN antes de dummies

        if cats_to_dummy:
            df = pd.get_dummies(df, columns=cats_to_dummy, drop_first=True)  # aplicar dummies a categóricas

        for col in bool_cols:
            df[col] = df[col].map({True: 1, False: 0, "True": 1, "False": 0}) # Convertir booleanos a 0/1
            df[col] = df[col].fillna(0).astype(int)

        # 5) asegurarse de que los datos sean números luego de transformar dummies
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.astype(float)

        meta["auto_dummies"] = cats_to_dummy.copy()

        # 6) en los valores NaN colocar la media de la columna (imputación)
        for col in df.columns:
            if df[col].isna().any():
                mean_val = df[col].mean()
                if not np.isnan(mean_val):
                    count_nan = int(df[col].isna().sum())
                    df[col] = df[col].fillna(mean_val)
                    meta["imputed_columns"][col] = {
                        "mean": float(mean_val),
                        "count": count_nan
                    }

        # 7) validar que quedan filas y columnas suficientes
        meta["rows_after"] = len(df)

        MIN_OBS = 5
        if df.columns.size < 2:
            return {
                "ok": False,
                "error": "No quedaron columnas utilizables después de la limpieza.",
                "details": column_errors,
                "meta": meta
            }

        if len(df) < MIN_OBS:
            return {
                "ok": False,
                "error": f"Se requieren al menos {MIN_OBS} observaciones después de la limpieza.",
                "n_after_clean": len(df),
                "meta": meta,
                "details": column_errors
            }

        # 8) determinar variable dependiente final
        dependent_col = dependent if dependent in df.columns else df.columns[0]
        if dependent_col not in df.columns:
            return {
                "ok": False,
                "error": "No se pudo determinar una variable dependiente válida tras la limpieza.",
                "meta": meta,
                "details": column_errors
            }

        # 9) construir y, X desde df_valid (ya limpio y con imputaciones)
        df_valid = df.copy()
        y = df_valid[dependent_col]
        X = df_valid.drop(columns=[dependent_col])

        if X.shape[1] == 0:
            return {
                "ok": False,
                "error": "No quedaron variables independientes después de la limpieza.",
                "meta": meta,
                "details": column_errors
            }

        # agregar constante
        X_const = sm.add_constant(X)

        # ajustar modelo
        model = sm.OLS(y, X_const).fit()

        # Métricas principales
        r2 = float(model.rsquared)
        r2_adj = float(model.rsquared_adj)
        f_stat = float(model.fvalue)
        f_pvalue = float(model.f_pvalue)

        # Tabla ANOVA
        # grados de libertad
        df_model = float(model.df_model)
        df_resid = float(model.df_resid)

        # sumas de cuadrados
        ss_regression = float(model.ess)            # SSR
        ss_error = float(model.ssr)                  # SSE
        ss_total = float(model.centered_tss)         # SST

        # cuadrados medios
        ms_regression = ss_regression / df_model
        ms_error = ss_error / df_resid

        # coeficientes del modelo
        coefficients = {
            var: {
                "coef": float(model.params[var]),
                "p_value": float(model.pvalues[var]),
                "std_err": float(model.bse[var]),
            }
            for var in model.params.index
        }

        # residuos

        resid = model.resid

        # Normalidad
        sw_stat, sw_p = shapiro(resid)
        ks_stat, ks_p = kstest((resid - resid.mean()) / resid.std(ddof=1), 'norm')
        jb_stat, jb_p, jb_skew, jb_kurt = jarque_bera(resid)

        # Heterocedasticidad
        bp_test = het_breuschpagan(resid, X_const)
        white_test = None
        white_result = {}

        MAX_WHITE_FEATURES = 8

        try:
            if X_const.shape[1] <= MAX_WHITE_FEATURES:
                white_test = het_white(resid, X_const)
                white_result = {
                    "stat": safe_round(white_test[0]),
                    "p_value": safe_round(white_test[1]),
                    "f_stat": safe_round(white_test[2]),
                    "f_p_value": safe_round(white_test[3]),
                }
            else:
                white_result = {
                    "skipped": True,
                    "reason": f"White test omitido: demasiadas variables ({X_const.shape[1]})"
                }
        except Exception:
            white_result = {
                "error": "White test falló por colinealidad o límites de memoria"
            }

        # Durbin-Watson
        dw = durbin_watson(resid)

        # VIF
        vif = []
        for i, col in enumerate(X_const.columns):
            if col == "const":
                continue
            try:
                v = variance_inflation_factor(X_const.values, i)
                vif.append({
                    "variable": col,
                    "VIF": float(v) if np.isfinite(v) else None
                })
            except Exception:
                vif.append({
                    "variable": col,
                    "VIF": None
                })

        # Cook's distance y otros valores diagnósticos
        if model.mse_resid is None or model.mse_resid <= 0 or np.isnan(model.mse_resid):
            return {
                "ok": False,
                "error": "Varianza residual inválida (modelo degenerado)",
                "meta": meta
            }

        influence = model.get_influence()
        summary_frame = influence.summary_frame()

        summary_frame["hat_diag"] = np.clip(
            summary_frame["hat_diag"], 0, 0.999999
        )
        summary_frame["standard_resid"] = (
            summary_frame["standard_resid"]
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0)
        )
        summary_frame["cooks_d"] = (
            summary_frame["cooks_d"]
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0)
        )

        results_table = pd.DataFrame({
            "id": df.index,
            "Y_observado": model.model.endog,
            "Y_predicho": model.fittedvalues,
            "Residuo": model.resid,
            "Residuo_estandarizado": summary_frame["standard_resid"],
            "Leverage": summary_frame["hat_diag"],
            "Cooks_distance": summary_frame["cooks_d"],
            "Outlier": np.abs(summary_frame["standard_resid"]) > 2
        })

        results_table = results_table.replace([np.inf, -np.inf], np.nan)
        results_table = results_table.fillna(0)

        # Conclusión global
        conclusion = (
            "Rechazamos H0: el modelo es significativo"
            if f_pvalue < alpha else
            "No rechazamos H0: el modelo no es significativo"
        )

        # Cadena de coeficientes y VIF para el prompt
        coefs_str = "\n".join([
            f"{var}\t{coef['coef']}\t{coef['p_value']}"
            for var, coef in coefficients.items()
        ])
        coefficients_list = [
            {
                "variable": var,
                "coef": safe_round(coef["coef"]),
                "p_value": safe_round(coef["p_value"]),
                "std_err": safe_round(coef["std_err"]),
            }
            for var, coef in coefficients.items()
        ]

        conclusion = (
            "Se rechaza H0: el modelo es globalmente significativo"
            if model.f_pvalue < alpha
            else "No se rechaza H0: el modelo no es globalmente significativo"
        )

        return {
            "ok": True,
            "meta": meta,
            "n_obs": int(model.nobs),
            "dependent_variable": dependent_col,
            "r2": safe_round(r2),
            "r2_adj": safe_round(r2_adj),
            "f_statistic": safe_round(f_stat),
            "f_pvalue": safe_round(f_pvalue),

            # anova
            "anova": {
                "ok": True,

                # tamaños
                "n_obs": int(model.nobs),
                "n_predictors": int(X.shape[1]),  # sin constante

                # sumas de cuadrados
                "ss_regression": safe_round(ss_regression),
                "ss_error": safe_round(ss_error),
                "ss_total": safe_round(
                    ss_regression + ss_error
                    if ss_regression is not None and ss_error is not None
                    else None
                ),


                # cuadrados medios
                "ms_regression": safe_round(ms_regression),
                "ms_error": safe_round(ms_error),                 # MSE

                # test global
                "f_statistic": safe_round(model.fvalue),
                "p_value": safe_round(model.f_pvalue),

                # decisión
                "conclusion": conclusion,
            },

            # coeficientes
            "coefficients": coefficients_list,

            # supuestos / normalidad
            "normality": {
                "shapiro_p": safe_round(sw_p),
                "ks_p": safe_round(ks_p),
                "jarque_bera_p": safe_round(jb_p),
                "skewness": safe_round(jb_skew),
                "kurtosis": safe_round(jb_kurt)
            },

            # heterocedasticidad
            "breusch_pagan": {
                "LM_p": safe_round(bp_test[1]),
                "F_p": safe_round(bp_test[3])
            },
            "white_test": white_result,

            "durbin_watson": safe_round(dw),
            "vif": vif,
            "conclusion": conclusion,
            "results_table": results_table.round(4).to_dict(orient="records"),
        }


    except Exception as e:
        import traceback
        return {
            "ok": False,
            "meta": meta,
            "error": str(e),
            "trace": traceback.format_exc()
        }
