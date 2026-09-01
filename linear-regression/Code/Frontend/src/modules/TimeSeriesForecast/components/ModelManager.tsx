import axios from "axios";
import { useState } from "react";
import { FaTimes, FaSyncAlt } from "react-icons/fa";

import type { ModelItem } from "../types";
import { ModelCard } from "./ModelCard";

type Props = {
  open: boolean;
  onClose: () => void;
  models: ModelItem[];
  selectedModel: string;
  onSelectModel: (modelName: string) => void;
  onRefresh: () => void;
  onDelete: (modelName: string) => void;
  onDownload: (modelName: string) => void;
};

export const ModelManager = ({
  open,
  onClose,
  models,
  selectedModel,
  onSelectModel,
  onRefresh,
  onDelete,
  onDownload,
}: Props) => {
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const handleRefresh = async () => {
    try {
      setLoading(true);
      await onRefresh();
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".zip")) {
      alert("sube un archivo .zip");
      return;
    }

    const form = new FormData();
    form.append("file", file);

    try {
      await axios.post("/upload_model", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      await onRefresh();
      alert("modelo importado correctamente");
    } catch (error) {
      console.error(error);
      alert("no se pudo importar el modelo");
    } finally {
      event.target.value = "";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-4xl rounded-xl bg-white p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-gray-800">
              administración de modelos
            </h3>
            <p className="text-sm text-gray-500">
              seleccionar, descargar, borrar o importar modelos
            </p>
          </div>

          <button
            onClick={onClose}
            className="rounded p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900"
          >
            <FaTimes />
          </button>
        </div>

        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <button
            onClick={handleRefresh}
            disabled={loading}
            className={`inline-flex items-center gap-2 rounded px-3 py-2 text-sm font-medium text-white transition ${
              loading
                ? "cursor-not-allowed bg-gray-400"
                : "bg-gray-800 hover:bg-gray-700"
            }`}
          >
            <FaSyncAlt />
            {loading ? "refrescando..." : "refrescar lista"}
          </button>

          <label className="inline-flex cursor-pointer items-center gap-2 rounded border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100">
            importar modelo .zip
            <input
              type="file"
              accept=".zip"
              className="hidden"
              onChange={handleUpload}
            />
          </label>
        </div>

        {models.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
            no hay modelos guardados
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {models.map((model) => (
              <ModelCard
                key={model.model_name}
                model={model}
                selected={selectedModel === model.model_name}
                onUse={() => {
                  onSelectModel(model.model_name);
                  onClose();
                }}
                onDelete={() => onDelete(model.model_name)}
                onDownload={() => onDownload(model.model_name)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
