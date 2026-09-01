import type { ModelItem } from "../types";
import { FaDownload, FaTrash, FaCheck } from "react-icons/fa";

type Props = {
  model: ModelItem;
  selected: boolean;
  onUse: () => void;
  onDelete: () => void;
  onDownload: () => void;
};

const formatDate = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

export const ModelCard = ({
  model,
  selected,
  onUse,
  onDelete,
  onDownload,
}: Props) => {
  return (
    <div
      className={`rounded-xl border p-4 shadow-sm transition ${
        selected
          ? "border-green-400 bg-green-50"
          : "border-gray-200 bg-white hover:bg-gray-50"
      }`}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
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

        {selected && (
          <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-1 text-xs font-semibold text-green-700">
            <FaCheck />
            activo
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={onUse}
          className="rounded bg-gray-800 px-3 py-2 text-xs font-medium text-white hover:bg-gray-700"
        >
          usar
        </button>

        <button
          onClick={onDownload}
          className="inline-flex items-center gap-1 rounded border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
        >
          <FaDownload />
          descargar
        </button>

        <button
          onClick={onDelete}
          className="inline-flex items-center gap-1 rounded border border-red-300 bg-red-50 px-3 py-2 text-xs font-medium text-red-700 hover:bg-red-100"
        >
          <FaTrash />
          borrar
        </button>
      </div>
    </div>
  );
};
