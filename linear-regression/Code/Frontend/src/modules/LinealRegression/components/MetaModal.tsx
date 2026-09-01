import type { RegressionMeta } from "../types";
import { FaRegCopy, FaTimes } from "react-icons/fa";

type Props = {
  meta?: RegressionMeta;
  open: boolean;
  onClose: () => void;
};

export const MetaModal = ({ meta, open, onClose }: Props) => {
  if (!meta) return null;

  const copyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(meta, null, 2));
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4
      ${open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"}`}
    >
      <div className="bg-white w-full max-w-2xl rounded-xl shadow-lg overflow-hidden">
        {/* header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-gray-100">
          <h3 className="text-lg font-semibold text-gray-800">
            Informe del filtrado de datos
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={copyJson}
              className="text-sm px-3 py-1 bg-gray-200 rounded flex items-center gap-2 hover:bg-gray-300"
              title="Copiar JSON"
            >
              <FaRegCopy /> copiar
            </button>
            <button
              onClick={onClose}
              className="text-xl px-2 py-1 text-gray-600 hover:text-gray-800"
              aria-label="cerrar"
            >
              <FaTimes />
            </button>
          </div>
        </div>

        {/* contenido */}
        <div className="p-5 space-y-5 max-h-[60vh] overflow-y-auto text-gray-700">
          {/* advertencias */}
          <div>
            <p className="text-sm font-medium text-gray-600">Advertencias</p>
            {meta.warnings && meta.warnings.length ? (
              <ul className="list-disc ml-5 mt-2 text-sm text-orange-700">
                {meta.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-500 mt-1">
                No se encontraron advertencias.
              </p>
            )}
          </div>

          {/* columnas descartadas */}
          <div>
            <p className="text-sm font-medium text-gray-600">
              Las siguientes columnas no se tomaron en cuenta para el análisis
            </p>
            {meta.dropped_columns && meta.dropped_columns.length > 0 ? (
              <ul className="list-disc ml-5 mt-2 text-sm">
                {meta.dropped_columns.map((c) => (
                  <li key={c} className="text-gray-700">
                    {c}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-500 mt-1">-</p>
            )}
          </div>

          {/* dummies automáticas */}
          <div>
            <p className="text-sm font-medium text-gray-600">
              Categorías convertidas en variables
            </p>
            {meta.auto_dummies && meta.auto_dummies.length > 0 ? (
              <ul className="list-disc ml-5 mt-2 text-sm">
                {meta.auto_dummies.map((c) => (
                  <li key={c} className="text-gray-700">
                    {c}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-500 mt-1">
                No se aplicaron conversiones.
              </p>
            )}
          </div>

          {/* valores rellenados automáticamente */}
          <div>
            <p className="text-sm font-medium text-gray-600">
              Valores rellenados automáticamente
            </p>
            {meta.imputed_columns &&
            Object.keys(meta.imputed_columns).length > 0 ? (
              <table className="w-full text-sm mt-2">
                <thead>
                  <tr className="text-left text-xs text-gray-500 border-b">
                    <th>Columna</th>
                    <th>Valor promedio usado</th>
                    <th>Registros modificados</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(meta.imputed_columns).map(([col, val]) => (
                    <tr key={col} className="border-b">
                      <td className="py-1">{col}</td>
                      <td className="py-1">{val.mean ?? "—"}</td>
                      <td className="py-1">{val.count ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-gray-500 mt-1">
                No se rellenaron valores automáticamente.
              </p>
            )}
          </div>

          {/* registros antes y después */}
          <div className="grid grid-cols-2 gap-4 mt-2 text-sm">
            <div>
              <p className="text-gray-600 font-medium">
                Registros antes del filtrado
              </p>
              <p className="font-medium text-gray-800">
                {meta.rows_before ?? "—"}
              </p>
            </div>
            <div>
              <p className="text-gray-600 font-medium">
                Registros después del filtrado
              </p>
              <p className="font-medium text-gray-800">
                {meta.rows_after ?? "—"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
