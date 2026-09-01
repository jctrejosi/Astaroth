import type { TableFile } from "@/@types";
import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { FaPlay, FaPlus, FaSyncAlt, FaBoxOpen } from "react-icons/fa";

import type { ForecastResponse, ModelItem } from "../types";
import { ForecastResultsModal } from "./ForecastResultsModal";
import { ModelManager } from "./ModelManager";
import { TrainModelModal } from "./TrainModelModal";

type Props = {
  data: TableFile | undefined;
};

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const isNumericValue = (value: unknown) => {
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "string" && value.trim() !== "") {
    return Number.isFinite(Number(value));
  }
  return false;
};

import type { ForecastRow } from "../types";

const normalizeRows = (rows: Record<string, unknown>[]): ForecastRow[] =>
  rows.map((row) => {
    const normalized: ForecastRow = {};

    Object.entries(row).forEach(([key, value]) => {
      normalized[key] = isNumericValue(value) ? Number(value) : String(value);
    });

    return normalized;
  });

export const ForecastPanel = ({ data }: Props) => {
  const [models, setModels] = useState<ModelItem[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [points, setPoints] = useState<number>(24);

  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingForecast, setLoadingForecast] = useState(false);

  const [showResults, setShowResults] = useState(false);
  const [showTrainModal, setShowTrainModal] = useState(false);
  const [showModelManager, setShowModelManager] = useState(false);

  const [result, setResult] = useState<ForecastResponse | null>(null);
  const [status, setStatus] = useState<string>("");

  const rows = useMemo(() => {
    return normalizeRows(
      (data?.data ?? []) as unknown as Record<string, unknown>[]
    );
  }, [data]);

  const fetchModels = async () => {
    try {
      setLoadingModels(true);
      const res = await axios.get("/list_models");
      const loadedModels: ModelItem[] = res.data?.models ?? [];
      setModels(loadedModels);

      if (!selectedModel && loadedModels.length > 0) {
        setSelectedModel(loadedModels[0].model_name);
      }
    } catch (error) {
      console.error("error cargando modelos", error);
    } finally {
      setLoadingModels(false);
    }
  };

  useEffect(() => {
    fetchModels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const waitForModel = async (
    modelName: string,
    timeoutMs = 10 * 60 * 1000
  ) => {
    const started = Date.now();

    while (Date.now() - started < timeoutMs) {
      try {
        const res = await axios.get("/list_models");
        const available: ModelItem[] = res.data?.models ?? [];

        if (available.some((m) => m.model_name === modelName)) {
          setModels(available);
          return true;
        }
      } catch (error) {
        console.error("error esperando modelo", error);
      }

      await sleep(3000);
    }

    return false;
  };

  const runForecast = async (modelName: string) => {
    if (!rows.length) {
      alert("No hay datos cargados.");
      return;
    }

    try {
      setLoadingForecast(true);
      setStatus("generando predicción...");

      const res = await axios.post("/predict", {
        model_name: modelName,
        points,
        data: rows,
      });

      setResult(res.data as ForecastResponse);
      setShowResults(true);
      setStatus("predicción lista");
    } catch (error: unknown) {
      console.error("error ejecutando forecast", error);

      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail ??
          error.response?.data?.error ??
          "error generando predicción";

        alert(message);
      } else if (error instanceof Error) {
        alert(error.message);
      } else {
        alert("error desconocido");
      }
    } finally {
      setLoadingForecast(false);
    }
  };

  const handleForecast = async () => {
    if (!models.length) {
      setShowTrainModal(true);
      return;
    }

    if (!selectedModel) {
      alert("selecciona un modelo");
      return;
    }

    await runForecast(selectedModel);
  };

  const handleTrainSuccess = async (modelName: string) => {
    setStatus(`entrenamiento iniciado para ${modelName}`);
    setSelectedModel(modelName);

    const found = await waitForModel(modelName);

    if (found) {
      setStatus(`modelo ${modelName} disponible`);
      await runForecast(modelName);
    } else {
      setStatus(`el modelo ${modelName} no apareció a tiempo`);
      await fetchModels();
    }
  };

  const handleDelete = async (modelName: string) => {
    const ok = confirm(`¿Eliminar el modelo "${modelName}"?`);

    if (!ok) return;

    try {
      await axios.delete(`/delete_model/${encodeURIComponent(modelName)}`);
      await fetchModels();

      if (selectedModel === modelName) {
        setSelectedModel("");
      }

      if (result?.model_used === modelName) {
        setResult(null);
        setShowResults(false);
      }
    } catch (error) {
      console.error(error);

      if (axios.isAxiosError(error)) {
        alert(
          error.response?.data?.detail ??
            error.response?.data?.error ??
            "no se pudo eliminar el modelo"
        );
      } else {
        alert("no se pudo eliminar el modelo");
      }
    }
  };

  const handleDownload = async (modelName: string) => {
    try {
      const res = await axios.post(
        "/download_model",
        { model_name: modelName },
        { responseType: "blob" }
      );

      const blob = new Blob([res.data], { type: "application/zip" });
      const url = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;
      link.download = `${modelName}_complete.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error(error);
      alert("no se pudo descargar el modelo");
    }
  };

  return (
    <div className="w-full rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-2">
        <h2 className="text-xl font-semibold text-gray-800">
          predicción de series temporales
        </h2>
        <p className="text-sm text-gray-500">
          entrena un modelo nuevo, usa uno existente o genera forecast directo
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-gray-200 p-4">
          <p className="mb-2 text-sm font-semibold text-gray-700">
            modelo activo
          </p>

          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
          >
            <option value="">selecciona un modelo</option>
            {models.map((m) => (
              <option key={m.model_name} value={m.model_name}>
                {m.model_name}
              </option>
            ))}
          </select>

          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={fetchModels}
              disabled={loadingModels}
              className={`inline-flex items-center gap-2 rounded px-3 py-2 text-sm font-medium text-white transition ${
                loadingModels
                  ? "cursor-not-allowed bg-gray-400"
                  : "bg-gray-800 hover:bg-gray-700"
              }`}
            >
              <FaSyncAlt />
              {loadingModels ? "cargando..." : "refrescar"}
            </button>

            <button
              onClick={() => setShowModelManager(true)}
              className="inline-flex items-center gap-2 rounded border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              <FaBoxOpen />
              modelos
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 p-4">
          <p className="mb-2 text-sm font-semibold text-gray-700">
            horizonte de predicción
          </p>

          <input
            type="number"
            min={1}
            value={points}
            onChange={(e) => setPoints(Number(e.target.value))}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
          />

          <p className="mt-2 text-xs text-gray-500">puntos futuros a generar</p>
        </div>

        <div className="rounded-lg border border-gray-200 p-4">
          <p className="mb-2 text-sm font-semibold text-gray-700">acciones</p>

          <div className="flex flex-col gap-2">
            <button
              onClick={handleForecast}
              disabled={loadingForecast}
              className={`inline-flex items-center justify-center gap-2 rounded px-3 py-2 text-sm font-semibold text-white transition ${
                loadingForecast
                  ? "cursor-not-allowed bg-green-300"
                  : "bg-green-600 hover:bg-green-700"
              }`}
            >
              <FaPlay />
              {loadingForecast ? "ejecutando..." : "generar forecast"}
            </button>

            <button
              onClick={() => setShowTrainModal(true)}
              className="inline-flex items-center justify-center gap-2 rounded border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 transition hover:bg-blue-100"
            >
              <FaPlus />
              entrenar nuevo modelo
            </button>
          </div>

          {status && (
            <p className="mt-3 text-xs text-gray-500">estado: {status}</p>
          )}
        </div>
      </div>

      {showTrainModal && (
        <TrainModelModal
          open={showTrainModal}
          onClose={() => setShowTrainModal(false)}
          data={data}
          onTrained={handleTrainSuccess}
        />
      )}

      {showModelManager && (
        <ModelManager
          open={showModelManager}
          onClose={() => setShowModelManager(false)}
          models={models}
          selectedModel={selectedModel}
          onSelectModel={setSelectedModel}
          onRefresh={fetchModels}
          onDelete={handleDelete}
          onDownload={handleDownload}
        />
      )}

      {showResults && result && (
        <ForecastResultsModal
          open={showResults}
          onClose={() => setShowResults(false)}
          result={result}
          history={rows}
        />
      )}
    </div>
  );
};
