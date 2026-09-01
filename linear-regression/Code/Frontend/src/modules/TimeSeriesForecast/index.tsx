import type { TableFile } from "@/@types";
import { useMemo, useState } from "react";
import { FaDownload, FaPlus, FaPlay, FaSyncAlt, FaTrash } from "react-icons/fa";

import { useTimeSeriesForecast } from "./hooks/useTimeseriesForecast";

type Props = {
  data: TableFile | undefined;
};

const formatDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
};

export const TimeSeriesForecast = ({ data }: Props) => {
  const [showTrainModal, setShowTrainModal] = useState(false);
  const [showModelsModal, setShowModelsModal] = useState(false);
  const [showResultModal, setShowResultModal] = useState(false);
  const [trainModelName, setTrainModelName] = useState("");
  const [uploading, setUploading] = useState(false);

  const {
    rows,
    models,
    selectedModel,
    setSelectedModel,
    points,
    setPoints,
    result,
    status,
    error,
    loadingModels,
    loadingForecast,
    loadingTraining,
    refreshModels,
    predict,
    trainAndPredict,
    removeModel,
    downloadModelFile,
    importModel,
    fineTune,
    clearResult,
  } = useTimeSeriesForecast({ data });

  const columns = useMemo(() => data?.columns ?? [], [data]);

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      await importModel(file);
      alert("modelo importado correctamente");
    } catch (err) {
      console.error(err);
      alert("No se pudo importar el modelo");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const handleRunForecast = async () => {
    if (!selectedModel) {
      alert("Selecciona un modelo primero");
      return;
    }

    try {
      await predict(selectedModel);
      setShowResultModal(true);
    } catch (err) {
      console.error(err);
      alert("No se pudo generar el forecast");
    }
  };

  const handleTrainAndForecast = async () => {
    if (!trainModelName.trim()) {
      alert("Escribe un nombre para el modelo");
      return;
    }

    try {
      await trainAndPredict(trainModelName.trim());
      setShowTrainModal(false);
      setShowResultModal(true);
      setTrainModelName("");
    } catch (err) {
      console.error(err);
      alert("No se pudo entrenar y predecir");
    }
  };

  return (
    <div className="w-full rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-5 flex flex-col gap-2">
        <h2 className="text-xl font-semibold text-gray-800">
          forecast de series temporales
        </h2>
        <p className="text-sm text-gray-500">
          entrena, predice, descarga y administra modelos desde aquí
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-gray-200 p-4">
          <p className="text-sm font-semibold text-gray-700">dataset</p>
          <div className="mt-2 space-y-1 text-sm text-gray-600">
            <p>columnas: {columns.length}</p>
            <p>registros: {rows.length}</p>
            <p>modelo activo: {selectedModel || "ninguno"}</p>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 p-4">
          <p className="text-sm font-semibold text-gray-700">
            horizonte de predicción
          </p>

          <input
            type="number"
            min={1}
            value={points}
            onChange={(e) => setPoints(Number(e.target.value))}
            className="mt-2 w-full rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
          />

          <p className="mt-2 text-xs text-gray-500">puntos futuros a generar</p>
        </div>

        <div className="rounded-lg border border-gray-200 p-4">
          <p className="text-sm font-semibold text-gray-700">acciones</p>

          <div className="mt-3 flex flex-col gap-2">
            <button
              onClick={handleRunForecast}
              disabled={loadingForecast || loadingTraining}
              className={`inline-flex items-center justify-center gap-2 rounded px-3 py-2 text-sm font-semibold text-white transition ${
                loadingForecast || loadingTraining
                  ? "cursor-not-allowed bg-green-300"
                  : "bg-green-600 hover:bg-green-700"
              }`}
            >
              <FaPlay />
              {loadingForecast ? "prediciendo..." : "generar forecast"}
            </button>

            <button
              onClick={() => setShowTrainModal(true)}
              className="inline-flex items-center justify-center gap-2 rounded border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 transition hover:bg-blue-100"
            >
              <FaPlus />
              entrenar nuevo modelo
            </button>

            <button
              onClick={() => setShowModelsModal(true)}
              className="inline-flex items-center justify-center gap-2 rounded border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-50"
            >
              administrar modelos
            </button>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          onClick={refreshModels}
          disabled={loadingModels}
          className={`inline-flex items-center gap-2 rounded px-3 py-2 text-sm font-medium text-white transition ${
            loadingModels
              ? "cursor-not-allowed bg-gray-400"
              : "bg-gray-800 hover:bg-gray-700"
          }`}
        >
          <FaSyncAlt />
          {loadingModels ? "cargando..." : "refrescar modelos"}
        </button>

        <label className="inline-flex cursor-pointer items-center gap-2 rounded border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100">
          {uploading ? "importando..." : "importar modelo .zip"}
          <input
            type="file"
            accept=".zip"
            className="hidden"
            onChange={handleFileUpload}
          />
        </label>
      </div>

      {status && (
        <p className="mt-4 rounded border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600">
          estado: {status}
        </p>
      )}

      {error && (
        <p className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {result && (
        <div className="mt-5 rounded-lg border border-gray-200 bg-gray-50 p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-800">
                último forecast
              </h3>
              <p className="text-sm text-gray-500">
                modelo usado: {result.model_used}
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setShowResultModal(true)}
                className="rounded bg-gray-800 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700"
              >
                ver resultado
              </button>
              <button
                onClick={clearResult}
                className="rounded border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-white"
              >
                limpiar
              </button>
            </div>
          </div>
        </div>
      )}

      {showTrainModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-5 shadow-xl">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-gray-800">
                  entrenar nuevo modelo
                </h3>
                <p className="text-sm text-gray-500">
                  el modelo se entrena con el dataset cargado
                </p>
              </div>

              <button
                onClick={() => setShowTrainModal(false)}
                className="rounded px-2 py-1 text-gray-600 hover:bg-gray-100"
              >
                ×
              </button>
            </div>

            <div className="mt-4 space-y-4">
              <label className="block text-sm font-medium text-gray-700">
                nombre del modelo
                <input
                  value={trainModelName}
                  onChange={(e) => setTrainModelName(e.target.value)}
                  placeholder="ej: energia_v1"
                  className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
                />
              </label>

              <div className="rounded border border-gray-200 bg-gray-50 p-3 text-sm text-gray-600">
                registros: {rows.length}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleTrainAndForecast}
                  disabled={loadingTraining}
                  className={`rounded px-4 py-2 text-sm font-semibold text-white transition ${
                    loadingTraining
                      ? "cursor-not-allowed bg-blue-300"
                      : "bg-blue-600 hover:bg-blue-700"
                  }`}
                >
                  {loadingTraining ? "entrenando..." : "entrenar y predecir"}
                </button>

                <button
                  onClick={() => setShowTrainModal(false)}
                  className="rounded border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                >
                  cancelar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showModelsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-5xl rounded-xl bg-white p-5 shadow-xl">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-gray-800">
                  administración de modelos
                </h3>
                <p className="text-sm text-gray-500">
                  seleccionar, ajustar, descargar o borrar
                </p>
              </div>

              <button
                onClick={() => setShowModelsModal(false)}
                className="rounded px-2 py-1 text-gray-600 hover:bg-gray-100"
              >
                ×
              </button>
            </div>

            <div className="mt-4 mb-4 flex flex-wrap gap-2">
              <button
                onClick={refreshModels}
                className="inline-flex items-center gap-2 rounded bg-gray-800 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700"
              >
                <FaSyncAlt />
                refrescar
              </button>

              <label className="inline-flex cursor-pointer items-center gap-2 rounded border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100">
                importar .zip
                <input
                  type="file"
                  accept=".zip"
                  className="hidden"
                  onChange={handleFileUpload}
                />
              </label>
            </div>

            {models.length === 0 ? (
              <div className="rounded border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
                no hay modelos disponibles
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {models.map((model) => {
                  const active = selectedModel === model.model_name;

                  return (
                    <div
                      key={model.model_name}
                      className={`rounded-xl border p-4 shadow-sm transition ${
                        active
                          ? "border-green-400 bg-green-50"
                          : "border-gray-200 bg-white"
                      }`}
                    >
                      <div className="mb-3">
                        <h4 className="text-sm font-semibold text-gray-800">
                          {model.model_name}
                        </h4>
                        <p className="mt-1 text-xs text-gray-500">
                          modificado: {formatDate(model.last_modified)}
                        </p>
                        <p className="text-xs text-gray-500">
                          tamaño: {model.size_kb.toFixed(1)} kb
                        </p>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => setSelectedModel(model.model_name)}
                          className="rounded bg-gray-800 px-3 py-2 text-xs font-medium text-white hover:bg-gray-700"
                        >
                          usar
                        </button>

                        <button
                          onClick={() => fineTune(model.model_name)}
                          className="rounded border border-blue-300 bg-blue-50 px-3 py-2 text-xs font-medium text-blue-700 hover:bg-blue-100"
                        >
                          fine tuning
                        </button>

                        <button
                          onClick={() => downloadModelFile(model.model_name)}
                          className="inline-flex items-center gap-1 rounded border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
                        >
                          <FaDownload />
                          descargar
                        </button>

                        <button
                          onClick={() => removeModel(model.model_name)}
                          className="inline-flex items-center gap-1 rounded border border-red-300 bg-red-50 px-3 py-2 text-xs font-medium text-red-700 hover:bg-red-100"
                        >
                          <FaTrash />
                          borrar
                        </button>
                      </div>

                      {active && (
                        <p className="mt-3 text-xs font-semibold text-green-700">
                          modelo activo
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {showResultModal && result && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-6xl rounded-xl bg-white shadow-xl">
            <div className="sticky top-0 flex items-center justify-between border-b border-gray-200 bg-white px-5 py-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-800">
                  resultado del forecast
                </h3>
                <p className="text-sm text-gray-500">
                  modelo usado: {result.model_used}
                </p>
              </div>

              <button
                onClick={() => setShowResultModal(false)}
                className="rounded px-2 py-1 text-gray-600 hover:bg-gray-100"
              >
                ×
              </button>
            </div>

            <div className="max-h-[80vh] overflow-y-auto p-5">
              <div className="mb-4 rounded border border-gray-200 bg-gray-50 p-4">
                <p className="text-sm text-gray-700">estado: {result.status}</p>
                <p className="text-sm text-gray-700">
                  puntos generados: {result.forecast.length}
                </p>
              </div>

              <div className="overflow-x-auto rounded border border-gray-200">
                <table className="min-w-full divide-y divide-gray-200 bg-white">
                  <thead className="bg-gray-50">
                    <tr>
                      {Object.keys(result.forecast[0] ?? {}).map((key) => (
                        <th
                          key={key}
                          className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-600"
                        >
                          {key}
                        </th>
                      ))}
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-gray-100">
                    {result.forecast.map((row, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        {Object.values(row).map((value, idx) => (
                          <td
                            key={idx}
                            className="px-4 py-3 text-sm text-gray-700"
                          >
                            {typeof value === "number"
                              ? value.toFixed(6)
                              : String(value ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
