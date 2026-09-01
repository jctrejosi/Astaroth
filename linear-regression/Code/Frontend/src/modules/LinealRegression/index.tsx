import type { TableFile } from "@/@types";
import { useState, useEffect } from "react";
import { FaEye } from "react-icons/fa";
import { FiFilter } from "react-icons/fi";

import { type RegressionMeta, type RegressionResponse } from "./types";
import axios from "axios";
import { MetaModal } from "./components/MetaModal";
import { AnovaResultsTable } from "./components/AnovaResultsTable";
import { set_regression } from "./services/lineal_regression";
import { IaAnalysisModal } from "./components/IaAnalysisModal";
import { HiOutlineDocumentReport } from "react-icons/hi";
import { query_llm } from "./services/query_llm";

type props = {
  data: TableFile | undefined;
};

export const LinealRegresion = ({ data }: props) => {
  const [view, setView] = useState<boolean>(false);
  const [result, setResult] = useState<RegressionResponse>(
    {} as RegressionResponse,
  );
  const [dependent, setDependent] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [showMetaModal, setShowMetaModal] = useState(false);
  const [showIaModal, setShowIaModal] = useState(false);
  const [iaResult, setIaResult] = useState<null | string>(null);

  const fmt = (v?: number) =>
    v !== undefined && Number.isFinite(v) ? v.toFixed(4) : "—";

  // Inicializar dependent con la primera columna disponible
  useEffect(() => {
    if (data?.columns && data.columns.length > 0) {
      setDependent(data.columns[0]);
    }
  }, [data]);

  const handleSend = async () => {
    if (!data || !data.columns || !data.data) {
      alert("No hay datos para enviar.");
      return;
    }
    if (!dependent) {
      alert("Seleccione la columna a analizar.");
      return;
    }
    setLoading(true);
    try {
      const response = await set_regression({
        columns: data.columns,
        data: data.data,
        dependent,
      });
      setResult(response);
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        const data = error.response?.data as {
          error?: string;
          details?: Record<string, unknown>;
          meta: RegressionMeta;
        };
        setShowMetaModal(true);

        console.error("Error regresión:", data);

        alert(data?.error ?? "Error en el servidor");
      } else if (error instanceof Error) {
        alert(error.message);
      } else {
        alert("Error desconocido");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    async function fetchIaResult() {
      if (!result?.ok) return;
      setView(true);

      try {
        const ia_consult = await query_llm(result);
        setIaResult(ia_consult);
      } catch (err) {
        console.error("error consultando IA", err);
        setIaResult("Error generando la explicación. Intenta nuevamente.");
      }
    }

    if (result.meta) setShowMetaModal(true);
    setShowIaModal(true);

    fetchIaResult();
  }, [result]);

  const closeModal = () => setView(false);

  return (
    <div>
      {/* Botón + select */}
      <div className="flex flex-col sm:flex-row sm:items-end gap-4">
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <button
            onClick={handleSend}
            disabled={loading}
            className={`
        px-5 py-2 rounded text-white font-semibold transition
        w-full sm:w-[15rem]
        ${
          loading
            ? "bg-blue-300 animate-pulse cursor-not-allowed"
            : "bg-blue-600 hover:bg-blue-700"
        }
      `}
          >
            {loading ? "Ejecutando..." : "Ejecutar regresión lineal"}
          </button>

          {result.ok && (
            <button
              onClick={() => setView(true)}
              className="
          bg-gray-200 hover:bg-gray-300
          px-3 py-2 rounded transition text-gray-700
          flex items-center justify-center gap-1
          w-full sm:w-auto
        "
              title="Ver último resultado"
            >
              <FaEye /> Resultado anterior
            </button>
          )}
        </div>

        <label className="flex flex-col text-sm text-gray-500 underline font-bold w-full sm:w-auto">
          Variable dependiente
          <select
            value={dependent}
            onChange={(e) => setDependent(e.target.value)}
            className="border border-gray-300 rounded px-2 py-2 text-sm mt-1 w-full"
          >
            {data?.columns.map((col) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/*-----------------------------------
      --------- Modal de resultados --------
      --------------------------------------*/}

      {view && result?.ok && (
        <div
          id="results-modal"
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 gap-3"
        >
          {/* Meta - Informe de limpieza de datos */}
          <MetaModal
            meta={result.meta}
            open={showMetaModal}
            onClose={() => setShowMetaModal(false)}
          />

          {/* IA - Interpretación de VIF*/}
          <IaAnalysisModal
            open={showIaModal}
            onClose={() => setShowIaModal(false)}
            content={iaResult}
          />
          <div
            id="result-text"
            className="relative bg-white w-full max-w-6xl max-h-[90vh] overflow-y-auto rounded-lg shadow-lg p-6 pt-0"
          >
            {/* Botón de cerrar modal */}
            <div className="sticky top-0 z-10 flex justify-end mb-4">
              <button
                onClick={closeModal}
                className="text-gray-700 hover:text-gray-900 font-bold text-xl"
              >
                ×
              </button>
            </div>

            {/* Título y botones para ver información adicional */}
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-6">
              <h1 className="text-2xl font-semibold md:mr-4">
                Resultados de la regresión lineal
              </h1>

              {/* Botón para ver el filtrado de los datos */}
              <button
                onClick={() => setShowMetaModal(true)}
                className="
      flex items-center justify-center gap-2
      px-3 py-2 text-sm
      text-yellow-700 bg-yellow-50 border border-yellow-200
      rounded hover:bg-yellow-100
      w-full md:w-auto
    "
                title="ver informe de limpieza de datos"
              >
                <FiFilter size={18} />
                Filtrado de datos
              </button>

              <button
                onClick={() => setShowIaModal(true)}
                className="
      flex items-center justify-center gap-2
      px-3 py-2 text-sm
      text-blue-700 bg-blue-50 border border-blue-200
      rounded hover:bg-blue-100
      w-full md:w-auto
    "
                title="ver interpretación de resultados"
              >
                <HiOutlineDocumentReport size={18} />
                Explicación de resultados
              </button>
            </div>

            {/* ecuación del modelo */}
            <div className="bg-white p-4 rounded-lg shadow mb-4">
              <h2 className="text-lg font-semibold mb-2">
                Ecuación del modelo
              </h2>

              <p className="text-gray-800 text-sm">
                <strong>
                  (Y) Variable dependiente = {result.dependent_variable}
                </strong>
              </p>

              <p className="mt-2 bg-gray-100 p-3 rounded font-mono text-sm text-gray-800">
                Y = β₀
                {result.coefficients
                  .filter((c) => c.variable !== "const")
                  .map((c) => ` + (${c.coef})·${c.variable}`)
                  .join("")}
              </p>
            </div>

            {/* interpretación de la ecuación del modelo */}
            <div className="bg-orange-50 p-4 rounded-lg border border-orange-200 shadow-sm mt-4 text-sm text-gray-700 space-y-2">
              <p>
                <strong>Y (valor estimado):</strong> resultado que el modelo
                predice para la variable dependiente.
                <br />
                <em>Ejemplo:</em> si <em>'Y'</em> representa el ingreso mensual,
                el modelo devuelve el ingreso esperado dadas ciertas
                características.
              </p>

              <p>
                <strong>β₀ (intercepto):</strong> valor base de <em>'Y'</em>{" "}
                cuando todas las variables independientes son cero. No siempre
                tiene una interpretación práctica, pero sirve como punto de
                referencia del modelo.
                <br />
                <em>Ejemplo:</em> ingreso estimado cuando experiencia, educación
                y edad valen cero.
              </p>

              <p>
                <strong>coeficientes (βᵢ):</strong> miden cuánto cambia{" "}
                <em>'Y'</em> en promedio cuando la variable correspondiente
                aumenta una unidad, manteniendo las demás constantes (efecto
                marginal).
                <br />
                <em>Ejemplo:</em> si β₁ = 250, un aumento de 1 unidad en
                experiencia aumenta
                <em>'Y'</em> en 250 unidades, sin cambiar el resto de variables.
              </p>

              <p>
                <strong>signo del coeficiente:</strong> indica la dirección del
                efecto sobre
                <em>'Y'</em>.
                <br />
                <em>Ejemplo:</em> un coeficiente positivo sugiere que al
                aumentar la variable, <em>'Y'</em> también aumenta; uno negativo
                indica el efecto opuesto.
              </p>

              <p>
                <strong>significancia estadística:</strong> determina si el
                efecto observado es confiable o podría deberse al azar. La
                interpretación es válida solo si el valor p del coeficiente es
                pequeño (típicamente &lt; 0.05).
                <br />
                <em>Ejemplo:</em> un coeficiente grande pero con p = 0.40 no
                aporta evidencia sólida y debe interpretarse con cautela.
              </p>
            </div>

            {/* Sección de resultados generales */}
            <div className="bg-gray-50 p-6 rounded-xl shadow-md space-y-6">
              {/* título principal */}
              <h2 className="text-xl font-bold text-gray-800 border-b pb-2 mb-4">
                Resultados generales del análisis
              </h2>

              {/* Hipótesis */}
              <div className="bg-white p-4 rounded-lg border-l-4 border-blue-500 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-700 mb-2">
                  Hipótesis
                </h3>

                <p className="text-gray-700">
                  <span className="font-semibold">H0:</span> todos los
                  coeficientes del modelo (excepto el intercepto) son cero.
                </p>

                <p className="text-gray-700">
                  <span className="font-semibold">H1:</span> al menos uno de los
                  coeficientes del modelo es distinto de cero.
                </p>
              </div>

              {/* Significado de las hipótesis */}
              <div className="bg-blue-50 p-4 rounded-lg border border-blue-200 shadow-sm">
                <h4 className="text-md font-semibold text-blue-800 mb-2">
                  ¿Qué significan estas hipótesis?
                </h4>

                <p className="text-gray-700 text-sm mb-2">
                  <span className="font-semibold">Si no se rechaza H0:</span> no
                  hay evidencia estadística suficiente para afirmar que el
                  modelo de regresión explique la variable dependiente. En la
                  práctica, el modelo no mejora de forma significativa la
                  predicción frente a usar únicamente la media de <em>y</em>.
                </p>

                <p className="text-gray-700 text-sm">
                  <span className="font-semibold">
                    Si se rechaza H0 (se acepta H1):
                  </span>{" "}
                  existe evidencia estadística de que el modelo es globalmente
                  significativo. Esto implica que al menos una de las variables
                  independientes aporta información relevante para explicar la
                  variable dependiente.
                </p>
              </div>

              {/* métricas generales del modelo */}
              <div className="bg-white p-4 rounded-lg border-l-4 border-green-500 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-700 mb-2">
                  Métricas del modelo
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-gray-700 text-sm">
                  <p>
                    <span className="font-semibold">Observaciones:</span>{" "}
                    {result.n_obs}
                  </p>
                  <p>
                    <span className="font-semibold">Variable dependiente:</span>{" "}
                    {result.dependent_variable}
                  </p>
                  <p>
                    <span className="font-semibold">R²:</span> {result.r2}
                  </p>
                  <p>
                    <span className="font-semibold">R² ajustado:</span>{" "}
                    {result.r2_adj}
                  </p>
                  <p>
                    <span className="font-semibold">Estadístico F:</span>{" "}
                    {result.f_statistic}
                  </p>
                  <p>
                    <span className="font-semibold">Valor p del modelo:</span>{" "}
                    {result.f_pvalue}
                  </p>
                  <p className="col-span-full bg-green-100 p-2 rounded text-gray-800 font-medium">
                    <span className="font-semibold">Conclusión:</span>{" "}
                    {result.conclusion}
                  </p>
                </div>
              </div>

              {/* Interpretación de las métricas del modelo */}
              <div className="bg-green-50 p-4 rounded-lg border border-green-200 shadow-sm">
                <h4 className="text-md font-semibold text-green-800 mb-2">
                  ¿Cómo interpretar estas métricas?
                </h4>

                <p className="text-gray-700 text-sm mb-2">
                  <span className="font-semibold">R²:</span> indica qué
                  proporción de la variabilidad de la variable dependiente es
                  explicada por el conjunto de variables independientes. Un
                  valor más alto implica mayor capacidad explicativa del modelo,
                  pero no garantiza causalidad.
                </p>

                <p className="text-gray-700 text-sm mb-2">
                  <span className="font-semibold">R² ajustado:</span> corrige el
                  R² penalizando la inclusión de variables innecesarias. Si es
                  significativamente menor que el R², sugiere que algunas
                  variables aportan poco o nada al modelo.
                </p>

                <p className="text-gray-700 text-sm mb-2">
                  <span className="font-semibold">
                    Estadístico F y valor p del modelo:
                  </span>{" "}
                  evalúan si el modelo completo explica mejor los datos que un
                  modelo sin predictores. Un valor p pequeño (por ejemplo, &lt;
                  0.05) indica que el modelo es globalmente significativo.
                </p>

                <p className="text-gray-700 text-sm">
                  <span className="font-semibold">Conclusión:</span> resume la
                  decisión estadística global. Si el modelo es significativo, se
                  justifica analizar los coeficientes individuales; si no lo es,
                  las predicciones y conclusiones deben tomarse con cautela.
                </p>
              </div>
            </div>

            {/* ANOVA */}
            {view && result.anova.ok && (
              <div className="relative w-full mt-5">
                <h2 className="text-2xl font-bold text-gray-800 mb-4">
                  análisis de varianza del modelo (anova de regresión)
                </h2>

                <div className="space-y-4">
                  <AnovaResultsTable data={data} result={result.anova} />

                  <div className="bg-gray-50 p-4 rounded border border-gray-200 space-y-2 text-sm">
                    <p className="text-gray-700">
                      <span className="font-semibold">
                        grados de libertad del modelo:
                      </span>{" "}
                      {result.anova.n_predictors} (número de variables
                      explicativas)
                    </p>

                    <p className="text-gray-700">
                      <span className="font-semibold">
                        grados de libertad del error:
                      </span>{" "}
                      {result.anova.n_obs - result.anova.n_predictors - 1}{" "}
                      (variabilidad no explicada por el modelo)
                    </p>

                    <p className="text-gray-700">
                      <span className="font-semibold">
                        variación media explicada por el modelo (MSR):
                      </span>{" "}
                      {result.anova.ms_regression}
                    </p>

                    <p className="text-gray-700">
                      <span className="font-semibold">
                        variación media del error (MSE):
                      </span>{" "}
                      {result.anova.ms_error}
                    </p>

                    <p className="text-gray-700">
                      <span className="font-semibold">
                        estadístico F del modelo:
                      </span>{" "}
                      {result.anova.f_statistic}
                    </p>

                    <p className="text-gray-700">
                      <span className="font-semibold">
                        valor p asociado al test F:
                      </span>{" "}
                      {result.anova.p_value}
                    </p>

                    {result.anova.conclusion && (
                      <p className="mt-2 text-green-700 font-semibold">
                        conclusión: {result.anova.conclusion}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Interpretación del ANOVA del modelo */}
            <div className="bg-blue-50 p-4 rounded-lg border border-blue-200 shadow-sm mt-4">
              <h4 className="text-md font-semibold text-blue-800 mb-2">
                ¿Qué indica el modelo ANOVA?
              </h4>

              <p className="text-gray-700 text-sm mb-2">
                Esta tabla ANOVA evalúa el modelo de regresión de forma global.
                Compara la variabilidad explicada por las variables
                independientes con la variabilidad que permanece sin explicar
                (error residual).
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">
                  grados de libertad del modelo:
                </span>{" "}
                corresponden al número de predictores incluidos. Más predictores
                implican mayor capacidad explicativa, pero también mayor
                complejidad.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">
                  grados de libertad del error:
                </span>{" "}
                reflejan la cantidad de información disponible para estimar la
                variabilidad no explicada. Valores más altos suelen indicar
                estimaciones del error más estables.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">
                  variación media explicada (MSR):
                </span>{" "}
                mide cuánta variabilidad promedio explica el modelo. Cuanto
                mayor sea en relación con el MSE, mejor es el desempeño global
                del modelo.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">
                  variación media del error (MSE):
                </span>{" "}
                cuantifica la variabilidad que el modelo no logra explicar.
                Valores elevados pueden indicar ruido, variables poco
                informativas o incumplimiento de supuestos del modelo.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">estadístico F y valor p:</span>{" "}
                contrastan si el conjunto de predictores aporta información
                relevante frente a un modelo sin variables explicativas. Un
                valor p pequeño (típicamente p &lt; 0.05) indica que el modelo
                es globalmente significativo.
              </p>

              <p className="text-gray-700 text-sm">
                <span className="font-semibold">interpretación final:</span> si
                el ANOVA es significativo, tiene sentido analizar e interpretar
                los coeficientes individuales. Si no lo es, cualquier
                interpretación puntual de los coeficientes carece de respaldo
                estadístico.
              </p>
            </div>

            {/* Coeficientes */}
            <div className="overflow-x-auto bg-white p-4 rounded-lg shadow mb-4">
              <h2 className="text-lg font-semibold mb-2">Coeficientes</h2>
              <table className="min-w-full border border-gray-300 divide-y divide-gray-200">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Variable
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Coeficiente
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Valor p
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {result.coefficients.map((c) => (
                    <tr
                      key={c.variable}
                      className="hover:bg-gray-50 transition"
                    >
                      <td className="px-4 py-2 text-sm text-gray-700">
                        {c.variable}
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-700">
                        {c.coef}
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-700">
                        {c.p_value}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Interpretación de los coeficientes */}
            <div className="bg-purple-50 p-4 rounded-lg border border-purple-200 shadow-sm mt-4">
              <h4 className="text-md font-semibold text-purple-800 mb-2">
                ¿Cómo interpretar estos coeficientes?
              </h4>

              <p className="text-gray-700 text-sm mb-2">
                Cada coeficiente representa el cambio promedio esperado en la
                variable dependiente cuando la variable correspondiente aumenta
                una unidad, manteniendo constantes todas las demás variables del
                modelo.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">Signo del coeficiente:</span> un
                valor positivo indica una relación directa (aumenta X, aumenta
                Y). Un valor negativo indica una relación inversa (aumenta X,
                disminuye Y).
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">Magnitud:</span> indica la
                intensidad del efecto. Coeficientes grandes (en valor absoluto)
                sugieren mayor impacto, siempre que las variables estén en
                escalas comparables.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">Valor p:</span> evalúa si el
                efecto observado es estadísticamente distinto de cero. Valores p
                menores a 0.05 indican que la variable aporta información
                significativa al modelo.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                Variables con valor p alto pueden no ser relevantes
                individualmente, incluso si el modelo global es significativo.
                Esto suele deberse a colinealidad, bajo poder estadístico o
                ruido en los datos.
              </p>

              <p className="text-gray-700 text-sm">
                <span className="font-semibold">Recomendación:</span> interpreta
                primero los coeficientes significativos, revisa VIF antes de
                eliminar variables y evita conclusiones causales si el análisis
                es observacional.
              </p>
            </div>

            {/* Pruebas de supuestos (normality) */}
            <div className="bg-gray-50 p-4 rounded-lg shadow">
              <h2 className="text-lg font-semibold mb-2">
                Pruebas de Supuestos
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm text-gray-700">
                <p>
                  <strong>Shapiro-Wilk p:</strong> {result.normality.shapiro_p}
                </p>
                <p>
                  <strong>Kolmogorov-Smirnov p:</strong> {result.normality.ks_p}
                </p>
                <p>
                  <strong>Jarque-Bera p:</strong>{" "}
                  {result.normality.jarque_bera_p}
                </p>
                <p>
                  <strong>Skewness:</strong> {result.normality.skewness}
                </p>
                <p>
                  <strong>Kurtosis:</strong> {result.normality.kurtosis}
                </p>
                <p>
                  <strong>Durbin-Watson:</strong> {result.durbin_watson}
                </p>
              </div>
            </div>

            {/* Interpretación de las pruebas de supuestos */}
            <div className="bg-yellow-50 p-4 rounded-lg border border-yellow-200 shadow-sm mt-4">
              <h4 className="text-md font-semibold text-yellow-800 mb-2">
                ¿Qué indican estas pruebas?
              </h4>

              <p className="text-gray-700 text-sm mb-2">
                Estas pruebas evalúan si los supuestos clásicos de la regresión
                lineal se cumplen, principalmente la normalidad e independencia
                de los residuos. Su validez afecta la confiabilidad de los
                intervalos de confianza y pruebas de hipótesis.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">
                  Shapiro-Wilk y Kolmogorov-Smirnov:
                </span>
                contrastan si los residuos siguen una distribución normal.
                Valores p mayores a 0.05 indican que no hay evidencia suficiente
                para rechazar la normalidad.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">Jarque-Bera:</span> evalúa
                normalidad a partir de la asimetría (skewness) y curtosis. Un
                valor p alto sugiere residuos compatibles con una distribución
                normal.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">Skewness:</span> mide la
                simetría de los residuos. Valores cercanos a 0 indican simetría.
                <span className="font-semibold"> Kurtosis:</span> mide el peso
                de las colas; valores cercanos a 3 son típicos de una
                distribución normal.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">Durbin-Watson:</span> evalúa
                autocorrelación de residuos. Valores cercanos a 2 indican
                independencia; valores cercanos a 0 o 4 sugieren autocorrelación
                positiva o negativa.
              </p>

              <p className="text-gray-700 text-sm">
                <span className="font-semibold">
                  Si algún supuesto se viola:
                </span>{" "}
                las estimaciones pueden seguir siendo útiles, pero los valores p
                y los intervalos de confianza pueden ser poco fiables. En ese
                caso, se recomienda usar errores robustos, transformar variables
                o considerar modelos alternativos.
              </p>
            </div>

            {/* Breusch-Pagan y White - Test de Heterocedasticidad */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white p-4 rounded-lg shadow">
                <h2 className="text-lg font-semibold mb-2">Breusch-Pagan</h2>
                <p>
                  <strong>LM p:</strong> {result.breusch_pagan["LM_p"]}
                </p>
                <p>
                  <strong>F p:</strong> {result.breusch_pagan["F_p"]}
                </p>
              </div>
              <div className="bg-white p-4 rounded-lg shadow">
                <h2 className="text-lg font-semibold mb-2">
                  White (Heterocedasticidad)
                </h2>
                {typeof result.white_test?.stat === "number" ? (
                  <>
                    <p>
                      <strong>Estadístico:</strong> {result.white_test.stat}
                    </p>
                    <p>
                      <strong>p-valor:</strong> {result.white_test.p_value}
                    </p>
                    <p>
                      <strong>F-stat:</strong> {result.white_test.f_stat}
                    </p>
                    <p>
                      <strong>F p-valor:</strong> {result.white_test.f_p_value}
                    </p>
                  </>
                ) : (
                  <p>
                    <strong>Error:</strong>{" "}
                    {result.white_test?.error ?? "No disponible"}
                  </p>
                )}
              </div>
            </div>

            {/* Interpretación de Breusch-Pagan y White - Test de heterocedasticidad */}
            <div className="bg-orange-50 p-4 rounded-lg border border-orange-200 shadow-sm mt-4">
              <h4 className="text-md font-semibold text-orange-800 mb-2">
                ¿Qué indican estas pruebas de Breusch-Pagan y White?
              </h4>

              <p className="text-gray-700 text-sm mb-2">
                Estas pruebas evalúan si la varianza de los errores del modelo
                es constante (homocedasticidad). Si la varianza cambia a lo
                largo de los valores predichos, se dice que existe
                heterocedasticidad.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">Breusch-Pagan:</span> detecta si
                la varianza de los residuos depende linealmente de las variables
                explicativas. Valores p mayores a 0.05 indican que no hay
                evidencia suficiente de heterocedasticidad.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">White:</span> es una prueba más
                general, sensible a relaciones no lineales y a interacciones. Un
                valor p alto sugiere que la varianza de los errores es
                aproximadamente constante.
              </p>

              <p className="text-gray-700 text-sm mb-2">
                <span className="font-semibold">
                  Si se rechaza la homocedasticidad:
                </span>
                los coeficientes del modelo siguen siendo insesgados, pero los
                errores estándar y los valores p pueden ser incorrectos.
              </p>

              <p className="text-gray-700 text-sm">
                <span className="font-semibold">Acciones recomendadas:</span>
                usar errores estándar robustos, transformar la variable
                dependiente (por ejemplo logaritmos) o replantear el modelo
                incluyendo variables omitidas relevantes.
              </p>
            </div>

            {/* VIF */}
            <div className="overflow-x-auto bg-white p-4 rounded-lg shadow">
              <h2 className="text-lg font-semibold mb-2">
                VIF (Multicolinealidad)
              </h2>
              <table className="min-w-full border border-gray-300 divide-y divide-gray-200">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Variable
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      VIF
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {result.vif.map((v) => (
                    <tr
                      key={v.variable}
                      className="hover:bg-gray-50 transition"
                    >
                      <td className="px-4 py-2 text-sm text-gray-700">
                        {v.variable}
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-700">
                        {v.VIF}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Interpretación de VIF */}
            <div className="bg-orange-50 p-4 rounded-lg border border-orange-200 shadow-sm mt-4 text-sm text-gray-700">
              <p className="mb-1">
                <strong>qué evalúa el VIF:</strong> mide cuánto se explica una
                variable independiente a partir de las demás variables del
                modelo.
              </p>
              <p className="mb-1">
                <strong>VIF ≈ 1:</strong> no hay multicolinealidad.
              </p>
              <p className="mb-1">
                <strong>VIF &gt; 5:</strong> multicolinealidad moderada; los
                coeficientes pierden estabilidad.
              </p>
              <p>
                <strong>VIF &gt; 10:</strong> multicolinealidad severa; el
                modelo se vuelve poco confiable y debe ajustarse.
              </p>
            </div>

            {/* Tabla de residuos */}
            <div className="overflow-x-auto bg-white p-4 rounded-lg shadow mb-4">
              <h2 className="text-lg font-semibold mb-2">
                Tabla de Residuos y Diagnóstico
              </h2>
              <table className="min-w-full border border-gray-300 divide-y divide-gray-200">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      #
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Y observado
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Y predicho
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Residuo
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Residuo estandarizado
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Leverage
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Cook's distance
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">
                      Outlier
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {result.results_table?.map((row, index) => {
                    return (
                      <tr key={index} className="hover:bg-gray-50 transition">
                        <td className="px-4 py-2 text-sm text-gray-700">
                          {row.id}
                        </td>

                        <td className="px-4 py-2 text-sm text-gray-700">
                          {fmt(row.Y_observado)}
                        </td>

                        <td className="px-4 py-2 text-sm text-gray-700">
                          {fmt(row.Y_predicho)}
                        </td>

                        <td className="px-4 py-2 text-sm text-gray-700">
                          {fmt(row.Residuo)}
                        </td>

                        <td className="px-4 py-2 text-sm text-gray-700">
                          {fmt(row.Residuo_estandarizado)}
                        </td>

                        <td className="px-4 py-2 text-sm text-gray-700">
                          {fmt(row.Leverage)}
                        </td>

                        <td className="px-4 py-2 text-sm text-gray-700">
                          {fmt(row.Cooks_distance)}
                        </td>

                        <td
                          className={`px-4 py-2 text-sm font-semibold ${
                            row.Outlier ? "text-red-500" : "text-gray-700"
                          }`}
                        >
                          {row.Outlier ? "Sí" : "No"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Interpretación de la tabla de residuos */}
            <div className="bg-orange-50 p-4 rounded-lg border border-orange-200 shadow-sm mt-4 text-sm text-gray-700">
              <p className="mb-1">
                <strong>y observado:</strong> valor real de la variable
                dependiente en cada observación.
              </p>
              <p className="mb-1">
                <strong>y predicho:</strong> valor estimado por el modelo de
                regresión.
              </p>
              <p className="mb-1">
                <strong>residuo:</strong> diferencia entre el valor observado y
                el valor predicho. idealmente debe oscilar alrededor de cero.
              </p>
              <p className="mb-1">
                <strong>residuo estandarizado:</strong> residuo ajustado por su
                desviación estándar. valores absolutos mayores a 2 (o 3) indican
                posibles observaciones atípicas.
              </p>
              <p className="mb-1">
                <strong>leverage:</strong> mide cuánto influye una observación
                en la estimación de los coeficientes. valores altos indican
                puntos con capacidad de alterar el modelo.
              </p>
              <p className="mb-1">
                <strong>cook&apos;s distance:</strong> evalúa la influencia
                conjunta del residuo y el leverage. valores elevados indican
                observaciones influyentes que pueden distorsionar el ajuste.
              </p>
              <p>
                <strong>outlier:</strong> indica si la observación fue
                identificada como atípica o influyente según los criterios
                estadísticos definidos.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
