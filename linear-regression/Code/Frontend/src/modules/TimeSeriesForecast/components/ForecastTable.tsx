import type { ForecastRow } from "../types";

type Props = {
  data: ForecastRow[];
};

const isMetaKey = (key: string) => {
  const lower = key.toLowerCase();
  return (
    lower === "date" ||
    lower === "datetime" ||
    lower === "timestamp" ||
    lower === "time" ||
    lower === "id"
  );
};

export const ForecastTable = ({ data }: Props) => {
  if (!data.length) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 p-6 text-sm text-gray-500">
        no hay datos de forecast para mostrar
      </div>
    );
  }

  const columns = Array.from(
    new Set(
      data.flatMap((row) => Object.keys(row).filter((key) => !isMetaKey(key)))
    )
  );

  const metaColumns = Array.from(
    new Set(
      data.flatMap((row) => Object.keys(row).filter((key) => isMetaKey(key)))
    )
  );

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 bg-white">
        <thead className="bg-gray-50">
          <tr>
            {metaColumns.map((col) => (
              <th
                key={col}
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-600"
              >
                {col}
              </th>
            ))}
            {columns.map((col) => (
              <th
                key={col}
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-600"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>

        <tbody className="divide-y divide-gray-100">
          {data.map((row, index) => (
            <tr key={index} className="hover:bg-gray-50">
              {metaColumns.map((col) => (
                <td key={col} className="px-4 py-3 text-sm text-gray-700">
                  {String(row[col] ?? "")}
                </td>
              ))}

              {columns.map((col) => (
                <td key={col} className="px-4 py-3 text-sm text-gray-700">
                  {typeof row[col] === "number"
                    ? row[col].toFixed(6)
                    : String(row[col] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
