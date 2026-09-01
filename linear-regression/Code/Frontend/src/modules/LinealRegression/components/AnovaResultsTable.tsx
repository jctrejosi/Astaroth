import type { TableFile } from "@/@types";
import type { AnovaResult } from "../types";

type Props = {
  result: AnovaResult | null;
  data: TableFile | undefined;
};

export const AnovaResultsTable = ({ result, data }: Props) => {
  if (!result || !data) {
    return <p className="text-gray-500">No hay resultados para mostrar.</p>;
  }

  // Transponer data.data (filas → columnas)
  const numColumns = data.columns.length;
  const columnas: (string | number | null)[][] = Array.from(
    { length: numColumns },
    () => []
  );

  data.data.forEach((fila) => {
    fila.forEach((valor, colIndex) => {
      columnas[colIndex].push(valor);
    });
  });

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border border-gray-300 divide-y divide-gray-200 rounded-lg">
        <thead className="bg-gray-100">
          <tr>
            <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">
              Variable
            </th>
            <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">
              Datos de la variable
            </th>
            <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">
              Media
            </th>
            <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">
              SSE
            </th>
            <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">
              SSB
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {/* regresión */}
          <tr className="hover:bg-gray-50 transition">
            <td className="px-4 py-2 text-sm text-gray-700">
              regresión (modelo)
            </td>
            <td className="px-4 py-2 text-sm text-gray-700">
              variables explicativas
            </td>
            <td className="px-4 py-2 text-sm text-gray-700">
              {result.ms_regression}
            </td>
            <td className="px-4 py-2 text-sm text-gray-700">
              {result.ss_regression}
            </td>
            <td className="px-4 py-2 text-sm text-gray-700">—</td>
          </tr>

          {/* error */}
          <tr className="hover:bg-gray-50 transition">
            <td className="px-4 py-2 text-sm text-gray-700">
              error (residuos)
            </td>
            <td className="px-4 py-2 text-sm text-gray-700">
              variabilidad no explicada
            </td>
            <td className="px-4 py-2 text-sm text-gray-700">
              {result.ms_error}
            </td>
            <td className="px-4 py-2 text-sm text-gray-700">
              {result.ss_error}
            </td>
            <td className="px-4 py-2 text-sm text-gray-700">—</td>
          </tr>

          {/* total */}
          <tr className="bg-gray-50 font-semibold">
            <td className="px-4 py-2">total</td>
            <td className="px-4 py-2"></td>
            <td className="px-4 py-2">—</td>
            <td className="px-4 py-2">{result.ss_total}</td>
            <td className="px-4 py-2">—</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};
