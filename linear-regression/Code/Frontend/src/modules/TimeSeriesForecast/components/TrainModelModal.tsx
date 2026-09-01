import type { TableFile } from "@/@types";
import axios from "axios";
import { useMemo, useState } from "react";
import { FaTimes, FaBrain } from "react-icons/fa";

type Props = {
  open: boolean;
  onClose: () => void;
  data: TableFile | undefined;
  onTrained: (modelName: string) => void;
};

const isNumericValue = (value: unknown) => {
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "string" && value.trim() !== "") {
    return Number.isFinite(Number(value));
  }
  return false;
};

const normalizeRows = (rows: Record<string, unknown>[]) =>
  rows.map((row) => {
    const normalized: Record<string, unknown> = {};

    Object.entries(row).forEach(([key, value]) => {
      normalized[key] = isNumericValue(value) ? Number(value) : value;
    });

    return normalized;
  });

export const TrainModelModal = ({ open, onClose, data, onTrained }: Props) => {
  const [modelName, setModelName] = useState("");
  const [loading, setLoading] = useState(false);

  const rows = useMemo(() => {
    return normalizeRows(
      (data?.data ?? []).map((row) =>
        Object.fromEntries(
          row.map((value, index) => [`column_${index}`, value])
        )
      ) as Record<string, unknown>[]
    );
  }, [data]);

  if (!open) return null;

  const handleTrain = async () => {
    if (!modelName.trim()) {
      alert("escribe un nombre para el modelo");
      return;
    }

    if (!rows.length) {
      alert("no hay datos para entrenar");
      return;
    }

    try {
      setLoading(true);

      await axios.post("/train", {
        model_name: modelName.trim(),
        data: rows,
      });

      onTrained(modelName.trim());
      onClose();
    } catch (error: unknown) {
      console.error("error entrenando modelo", error);

      if (axios.isAxiosError(error)) {
        alert(
          error.response?.data?.detail ??
            error.response?.data?.error ??
            "no se pudo iniciar el entrenamiento"
        );
      } else if (error instanceof Error) {
        alert(error.message);
      } else {
        alert("error desconocido");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-2xl rounded-xl bg-white p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-gray-800">
              entrenar nuevo modelo
            </h3>
            <p className="text-sm text-gray-500">
              el backend recibirá el dataset actual y creará el modelo base
            </p>
          </div>

          <button
            onClick={onClose}
            className="rounded p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900"
          >
            <FaTimes />
          </button>
        </div>

        <div className="space-y-4">
          <label className="block text-sm font-medium text-gray-700">
            nombre del modelo
            <input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="ej: energia_v1"
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
            />
          </label>

          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700">
            <p className="font-semibold">dataset detectado</p>
            <p className="mt-1">columnas: {data?.columns?.length ?? 0}</p>
            <p>registros: {rows.length}</p>
            <p className="mt-2 text-xs text-gray-500">
              el entrenamiento se inicia en segundo plano
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              onClick={handleTrain}
              disabled={loading}
              className={`inline-flex items-center justify-center gap-2 rounded px-4 py-2 text-sm font-semibold text-white transition ${
                loading
                  ? "cursor-not-allowed bg-blue-300"
                  : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              <FaBrain />
              {loading ? "iniciando..." : "entrenar modelo"}
            </button>

            <button
              onClick={onClose}
              className="rounded border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-50"
            >
              cancelar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
