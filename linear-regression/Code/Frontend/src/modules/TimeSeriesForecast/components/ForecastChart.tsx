import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ForecastRow } from "../types";

type Props = {
  history?: ForecastRow[];
  forecast: ForecastRow[];
};

const META_KEYS = new Set([
  "date",
  "datetime",
  "timestamp",
  "time",
  "id",
  "__label",
  "__source",
]);

const isNumeric = (value: unknown) => {
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "string" && value.trim() !== "") {
    return Number.isFinite(Number(value));
  }
  return false;
};

const getLabel = (row: ForecastRow) => {
  const keys = ["date", "datetime", "timestamp", "time"];

  for (const key of keys) {
    const value = row[key];
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      const parsed = new Date(String(value));
      if (!Number.isNaN(parsed.getTime())) {
        return parsed.toLocaleString();
      }
      return String(value);
    }
  }

  return String(row.id ?? "");
};

const toNumber = (value: unknown) =>
  typeof value === "number" ? value : Number(value);

export const ForecastChart = ({ history = [], forecast }: Props) => {
  const [selectedSeries, setSelectedSeries] = useState<string>("");

  const numericKeys = useMemo(() => {
    const set = new Set<string>();

    [...history, ...forecast].forEach((row) => {
      Object.entries(row).forEach(([key, value]) => {
        if (META_KEYS.has(key.toLowerCase())) return;
        if (isNumeric(value)) set.add(key);
      });
    });

    return [...set];
  }, [history, forecast]);

  const series = selectedSeries || numericKeys[0] || "";

  const chartData = useMemo(() => {
    return [...history, ...forecast].map((row) => {
      const value = row[series];

      return {
        __label: getLabel(row),
        __value: isNumeric(value) ? toNumber(value) : null,
      };
    });
  }, [history, forecast, series]);

  if (!numericKeys.length) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 p-6 text-sm text-gray-500">
        no se encontraron series numéricas para graficar
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h4 className="text-base font-semibold text-gray-800">
            gráfica del forecast
          </h4>
          <p className="text-sm text-gray-500">
            visualización de la serie seleccionada
          </p>
        </div>

        <label className="flex flex-col text-sm text-gray-600">
          serie
          <select
            value={series}
            onChange={(e) => setSelectedSeries(e.target.value)}
            className="mt-1 rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-500"
          >
            {numericKeys.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="h-[420px] w-full rounded-lg border border-gray-200 bg-white p-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="__label" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="__value"
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
