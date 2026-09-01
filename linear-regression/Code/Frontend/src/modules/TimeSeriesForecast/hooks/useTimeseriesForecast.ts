import type { TableFile } from "@/@types";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { ForecastResponse, ForecastRow, ModelItem } from "../types";

import { delete_model } from "../services/delete_model";
import { download_model } from "../services/download_model";
import { fine_tuning } from "../services/fine_tuning";
import { list_models } from "../services/list_models";
import { predict_forecast } from "../services/predict_forecast";
import { train_model } from "../services/train_model";
import { upload_model } from "../services/upload_model";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const normalizeCell = (value: unknown): string | number | boolean | null => {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "boolean") return value;

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed === "") return "";
    const asNumber = Number(trimmed);
    return Number.isFinite(asNumber) ? asNumber : value;
  }

  return String(value);
};

const normalizeRows = (rows: Record<string, unknown>[]): ForecastRow[] =>
  rows.map((row) => {
    const normalized: ForecastRow = {};

    Object.entries(row).forEach(([key, value]) => {
      normalized[key] = normalizeCell(value);
    });

    return normalized;
  });

type UseTimeSeriesForecastParams = {
  data: TableFile | undefined;
};

export const useTimeSeriesForecast = ({
  data,
}: UseTimeSeriesForecastParams) => {
  const [models, setModels] = useState<ModelItem[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [points, setPoints] = useState<number>(24);

  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [loadingTraining, setLoadingTraining] = useState(false);

  const [result, setResult] = useState<ForecastResponse | null>(null);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const rows = useMemo(() => {
    return normalizeRows(
      (data?.data ?? []) as unknown as Record<string, unknown>[]
    );
  }, [data]);

  const refreshModels = useCallback(async () => {
    try {
      setLoadingModels(true);
      setError(null);

      const response = await list_models();
      const loaded = response.models ?? [];

      setModels(loaded);

      setSelectedModel((current) => {
        if (current && loaded.some((m) => m.model_name === current)) {
          return current;
        }

        return loaded[0]?.model_name ?? "";
      });
    } catch (err) {
      console.error("error cargando modelos", err);
      setError("No se pudieron cargar los modelos");
    } finally {
      setLoadingModels(false);
    }
  }, []);

  useEffect(() => {
    refreshModels();
  }, [refreshModels]);

  const waitForModel = useCallback(
    async (modelName: string, timeoutMs = 10 * 60 * 1000) => {
      const started = Date.now();

      while (Date.now() - started < timeoutMs) {
        try {
          const response = await list_models();
          const loaded = response.models ?? [];

          setModels(loaded);

          if (loaded.some((m) => m.model_name === modelName)) {
            return true;
          }
        } catch (err) {
          console.error("error verificando modelo", err);
        }

        await sleep(3000);
      }

      return false;
    },
    []
  );

  const predict = useCallback(
    async (modelName: string = selectedModel) => {
      if (!rows.length) {
        throw new Error("No hay datos cargados.");
      }

      if (!modelName) {
        throw new Error("Seleccione un modelo.");
      }

      setLoadingForecast(true);
      setError(null);
      setStatus("generando predicción...");

      try {
        const response = await predict_forecast({
          model_name: modelName,
          points,
          data: rows,
        });

        setResult(response);
        setStatus("predicción lista");
        return response;
      } catch (err) {
        console.error("error en predict", err);

        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Error generando predicción");
        }

        throw err;
      } finally {
        setLoadingForecast(false);
      }
    },
    [points, rows, selectedModel]
  );

  const train = useCallback(
    async (modelName: string) => {
      if (!modelName.trim()) {
        throw new Error("Debe indicar un nombre de modelo.");
      }

      if (!rows.length) {
        throw new Error("No hay datos para entrenar.");
      }

      setLoadingTraining(true);
      setError(null);
      setStatus(`iniciando entrenamiento de ${modelName}...`);

      try {
        await train_model({
          model_name: modelName.trim(),
          data: rows as Record<string, unknown>[],
        });

        setSelectedModel(modelName.trim());
        setStatus(`entrenamiento iniciado para ${modelName.trim()}`);

        const available = await waitForModel(modelName.trim());

        if (available) {
          setStatus(`modelo ${modelName.trim()} disponible`);
          await refreshModels();
          return true;
        }

        setStatus(`el modelo ${modelName.trim()} no apareció a tiempo`);
        return false;
      } catch (err) {
        console.error("error entrenando", err);

        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Error iniciando entrenamiento");
        }

        throw err;
      } finally {
        setLoadingTraining(false);
      }
    },
    [refreshModels, rows, waitForModel]
  );

  const trainAndPredict = useCallback(
    async (modelName: string) => {
      const ready = await train(modelName);
      if (!ready) return null;
      return predict(modelName);
    },
    [predict, train]
  );

  const removeModel = useCallback(
    async (modelName: string) => {
      setError(null);
      setStatus(`eliminando ${modelName}...`);

      try {
        await delete_model(modelName);
        await refreshModels();

        if (selectedModel === modelName) {
          setSelectedModel("");
        }

        if (result?.model_used === modelName) {
          setResult(null);
        }

        setStatus(`modelo ${modelName} eliminado`);
      } catch (err) {
        console.error("error eliminando modelo", err);

        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("No se pudo eliminar el modelo");
        }

        throw err;
      }
    },
    [refreshModels, result?.model_used, selectedModel]
  );

  const downloadModelFile = useCallback(async (modelName: string) => {
    setError(null);

    try {
      const blob = await download_model(modelName);
      const url = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;
      link.download = `${modelName}_complete.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(url);
      setStatus(`descarga generada para ${modelName}`);
    } catch (err) {
      console.error("error descargando modelo", err);

      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("No se pudo descargar el modelo");
      }

      throw err;
    }
  }, []);

  const importModel = useCallback(
    async (file: File) => {
      setError(null);
      setStatus(`importando ${file.name}...`);

      try {
        await upload_model(file);
        await refreshModels();
        setStatus(`modelo ${file.name} importado`);
      } catch (err) {
        console.error("error importando modelo", err);

        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("No se pudo importar el modelo");
        }

        throw err;
      }
    },
    [refreshModels]
  );

  const fineTune = useCallback(
    async (modelName: string) => {
      if (!modelName.trim()) {
        throw new Error("Debe indicar un modelo para fine tuning.");
      }

      if (!rows.length) {
        throw new Error("No hay datos para ajustar el modelo.");
      }

      setStatus(`ajustando ${modelName}...`);
      setError(null);

      try {
        await fine_tuning({
          model_name: modelName.trim(),
          data: rows as Record<string, unknown>[],
        });

        setStatus(`fine tuning iniciado para ${modelName.trim()}`);
      } catch (err) {
        console.error("error haciendo fine tuning", err);

        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("No se pudo iniciar el fine tuning");
        }

        throw err;
      }
    },
    [rows]
  );

  const clearResult = useCallback(() => {
    setResult(null);
  }, []);

  return {
    rows,
    models,
    selectedModel,
    setSelectedModel,
    points,
    setPoints,
    result,
    setResult,
    status,
    error,
    loadingModels,
    loadingForecast,
    loadingTraining,
    refreshModels,
    predict,
    train,
    trainAndPredict,
    removeModel,
    downloadModelFile,
    importModel,
    fineTune,
    clearResult,
  };
};
