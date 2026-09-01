import os
import requests

MAX_PROMPT_CHARS = 12_000

def ask_llm_un(prompt: str) -> str | None:
    un_url = os.getenv("LLM_UN_URL")
    if not un_url:
        print("[llm_un] url no configurada")
        return None

    try:
        r = requests.post(
            f"{un_url}/api/generate",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "python-backend",
                "ngrok-skip-browser-warning": "true",
            },
            json={
                "model": "deepseek-r1:8b",
                "prompt": prompt,
                "temperature": 0.2,
                "num_ctx": 4096,
                "stream": False,
            },
            timeout=30,
        )

        print(f"[llm_un] status: {r.status_code}")
        r.raise_for_status()

        text = r.json().get("response")
        return text.strip() if text else None

    except requests.HTTPError as e:
        print(f"[llm_un] http error: {e} | body: {r.text[:400]}")
        return None
    except Exception as e:
        print(f"[llm_un] error inesperado: {e}")
        return None

def ask_llm_groq(prompt: str) -> str | None:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        print("[groq] api key no configurada")
        return None

    try:
        r = requests.post(
            os.getenv("LLM_GROQ_URL"),
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-oss-120b",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
            },
            timeout=30
        )

        print(f"[groq] status: {r.status_code}")
        r.raise_for_status()

        content = r.json()["choices"][0]["message"]["content"]
        print(f"[groq] respuesta ok ({len(content)} chars)")
        return content

    except requests.HTTPError as e:
        print(f"[groq] http error: {e} | body: {r.text[:400]}")
        return None
    except Exception as e:
        print(f"[groq] error inesperado: {e}")
        return None

def ask_llm(prompt: str) -> str | None:
    local_url = os.getenv("LLM_LOCAL")
    if not local_url:
        return None

    r = requests.post(
        f"{local_url}/api/generate",
        json={
            "model": "qwen2.5:3b",
            "prompt": prompt,
            "temperature": 0.2,
            "num_ctx": 4096,
            "stream": False,
        },
        timeout=15,
    )
    r.raise_for_status()
    text = r.json().get("response")
    return text.strip() if text else None


def build_regression_prompt(result: dict) -> str:
    coefficients = result.get("coefficients", [])
    normality = result.get("normality", {})
    bp = result.get("breusch_pagan", {})
    white = result.get("white_test", {})
    anova = result.get("anova", {})
    vif = result.get("vif", [])

    coefs_str = ", ".join(
        f'{c.get("variable")}: coef={c.get("coef")}, p={c.get("p_value")}'
        for c in coefficients
    )

    vif_str = ", ".join(
        f'{v.get("variable")}: VIF={v.get("VIF")}'
        for v in vif
    )

    return f"""
Necesito explicar los resultados de un modelo de regresión lineal múltiple, de manera detallada y con ejemplos.
Te voy a dar los datos del modelo.

Datos clave:
- Observaciones usadas: {result.get("n_obs")}
- Variable dependiente: {result.get("dependent_variable")}
- Variables independientes: {[c.get("variable") for c in coefficients]}
- R²: {result.get("r2")}
- R² ajustado: {result.get("r2_adj")}
- Estadístico F del modelo: {result.get("f_statistic")}
- Valor p del modelo: {result.get("f_pvalue")}
- SSR (suma de cuadrados de la regresión): {anova.get("ss_regression")}
- SSE (suma de cuadrados del error): {anova.get("ss_error")}
- MSR: {anova.get("ms_regression")}
- MSE: {anova.get("ms_error")}
- Estadístico F: {anova.get("f_statistic")}
- Coeficientes: {coefs_str}
- Shapiro-Wilk p: {normality.get("shapiro_p")}
- Kolmogorov-Smirnov p: {normality.get("ks_p")}
- Jarque-Bera p: {normality.get("jarque_bera_p")}
- Skewness: {normality.get("skewness")}
- Kurtosis: {normality.get("kurtosis")}
- Durbin-Watson: {result.get("durbin_watson")}
- Breusch-Pagan: LM p = {bp.get("LM_p")}, F p = {bp.get("F_p")}
- White: p-value = {white.get("p_value")}
- VIFs: {vif_str}

La respuesta debe ser a modo de informe con la interpretación de cada dato importante.
Separa los párrafos y los títulos, y no uses tablas para explicar.
"""

def llm_handler(result: dict) -> str:
    if not isinstance(result, dict):
        return "no se encontró ningún modelo"

    prompt = build_regression_prompt(result)

    if len(prompt) > MAX_PROMPT_CHARS:
        return "no se encontró ningún modelo"

    try:
        if os.getenv("LLM_UN") == "true":
            response = ask_llm_un(prompt)
            return response or "[un] no se encontró ningún modelo"

        if os.getenv("LLM_GROQ") == "true":
            response = ask_llm_groq(prompt)
            return response or "[groq] no se encontró ningún modelo"

        response = ask_llm(prompt)
        return response or "[local] no se encontró ningún modelo"

    except requests.RequestException as e:
        print("[llm] error:", e)
        return "[error] no se encontró ningún modelo"

