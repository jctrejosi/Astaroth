import { useState } from "react";
import { FaTimes } from "react-icons/fa";

import type { ForecastResponse, ForecastRow } from "../types";
import { ForecastChart } from "./ForecastChart";
import { ForecastTable } from "./ForecastTable";

type Props = {
  open: boolean;
  onClose: () => void;
  result: ForecastResponse;
  history?: ForecastRow[];
};

export const ForecastResultsModal = ({
  open,
  onClose,
  result,
  history = [],
}: Props) => {
  const [tab, setTab] = useState<"chart" | "table">("chart");

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-6xl rounded-xl bg-white shadow-xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-gray-200 bg-white px-5 py-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-800">
              resultados del forecast
            </h3>
            <p className="text-sm text-gray-500">
              modelo usado: {result.model_used}
            </p>
          </div>

          <button
            onClick={onClose}
            className="rounded p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900"
          >
            <FaTimes />
          </button>
        </div>

        <div className="flex gap-2 border-b border-gray-200 px-5 pt-4">
          <button
            onClick={() => setTab("chart")}
            className={`rounded-t px-4 py-2 text-sm font-medium ${
              tab === "chart"
                ? "border border-b-white bg-white text-gray-800"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            gráfica
          </button>

          <button
            onClick={() => setTab("table")}
            className={`rounded-t px-4 py-2 text-sm font-medium ${
              tab === "table"
                ? "border border-b-white bg-white text-gray-800"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            tabla
          </button>
        </div>

        <div className="max-h-[80vh] overflow-y-auto p-5">
          {tab === "chart" && (
            <ForecastChart history={history} forecast={result.forecast} />
          )}

          {tab === "table" && <ForecastTable data={result.forecast} />}
        </div>
      </div>
    </div>
  );
};
