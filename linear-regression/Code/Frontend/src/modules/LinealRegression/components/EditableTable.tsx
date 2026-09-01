import type { TableFile } from "@/@types";

import { useRef } from "react";

import { FiTrash2 } from "react-icons/fi";
import { AiOutlineInsertRowRight } from "react-icons/ai";
import { AiOutlineInsertRowBelow } from "react-icons/ai";

interface EditableTableProps {
  table: TableFile;

  setData: (data: TableFile) => void;

  onPageChange: (page: number) => void;
}

export const EditableTable = ({
  table,
  setData,
  onPageChange,
}: EditableTableProps) => {
  const columnName = useRef<HTMLInputElement>(null);

  const { columns, data, pagination, meta } = table;

  /* =========================
     editar celda
  ========================= */

  const handleCellChange = (
    rowIndex: number,
    colIndex: number,
    value: string | number
  ) => {
    const updated = [...data];

    updated[rowIndex][colIndex] = value;

    setData({
      ...table,
      data: updated,
    });
  };

  /* =========================
     editar nombre columna
  ========================= */

  const handleColumnNameChange = (colIndex: number, value: string) => {
    const trimmed = value.trim();

    if (!trimmed) return;

    if (columns.some((c, i) => c === trimmed && i !== colIndex)) {
      return;
    }

    const newColumns = [...columns];

    newColumns[colIndex] = trimmed;

    setData({
      ...table,
      columns: newColumns,
    });
  };

  /* =========================
     añadir fila
  ========================= */

  const addRow = () => {
    if (columns.length === 0) {
      alert("Añada al menos una columna antes de añadir filas.");

      return;
    }

    const newRow = Array(columns.length).fill("");

    setData({
      ...table,

      data: [...data, newRow],
    });
  };

  /* =========================
     añadir columna
  ========================= */

  const addColumn = () => {
    const newColumnName = columnName.current?.value.trim() || "";

    if (!newColumnName) {
      alert("Introduzca un nombre para la columna.");

      return;
    }

    if (columns.includes(newColumnName)) {
      alert("Ese nombre de columna ya existe.");

      return;
    }

    const newColumns = [...columns, newColumnName];

    const newData = data.map((row) => [...row, ""]);

    if (columnName.current) {
      columnName.current.value = "";
    }

    setData({
      ...table,

      columns: newColumns,

      data: newData,
    });
  };

  /* =========================
     eliminar columna
  ========================= */

  const deleteColumn = (colIndex: number) => {
    const confirmDelete = confirm(`¿Eliminar columna "${columns[colIndex]}"?`);

    if (!confirmDelete) return;

    const newColumns = columns.filter((_, i) => i !== colIndex);

    const newData = data.map((row) => row.filter((_, i) => i !== colIndex));

    setData({
      ...table,

      columns: newColumns,

      data: newData,
    });
  };

  /* =========================
     eliminar fila
  ========================= */

  const deleteRow = (rowIndex: number) => {
    const confirmDelete = confirm(`¿Eliminar fila ${rowIndex + 1}?`);

    if (!confirmDelete) return;

    const newData = data.filter((_, i) => i !== rowIndex);

    setData({
      ...table,

      data: newData,
    });
  };

  return (
    <div className="p-6 bg-white shadow-md rounded-lg space-y-6">
      {/* controles */}

      <div className="flex flex-col gap-4">
        <button
          onClick={addRow}
          className="
            flex items-center justify-center gap-2
            bg-gray-900 text-white px-5 py-2 rounded
            hover:bg-gray-700 transition font-semibold
            w-full sm:w-fit
          "
        >
          <AiOutlineInsertRowBelow />
          Añadir fila
        </button>

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            placeholder="Nombre columna"
            ref={columnName}
            className="
              border border-gray-300 rounded
              px-4 py-2
              w-full sm:w-64
            "
          />

          <button
            onClick={addColumn}
            className="
              flex items-center justify-center gap-2
              bg-gray-900 text-white
              px-4 py-2 rounded
              hover:bg-gray-700 transition
            "
          >
            <AiOutlineInsertRowRight />
            Añadir columna
          </button>
        </div>
      </div>

      {/* info dataset */}

      <div className="text-sm text-gray-500 flex flex-wrap gap-4">
        <span>filas totales: {pagination.total_rows}</span>

        <span>columnas: {meta.total_columns}</span>

        <span>memoria aprox: {meta.memory_mb} MB</span>

        <span>
          página {pagination.page} de {pagination.total_pages}
        </span>
      </div>

      {/* tabla */}

      <div className="overflow-auto border border-gray-200 rounded">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-100 sticky top-0">
            <tr>
              <th className="px-3 py-2 text-left">#</th>

              {columns.map((col, i) => (
                <th
                  key={i}
                  className="
                    px-3 py-2 text-left
                    min-w-[180px]
                  "
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={col}
                      onChange={(e) =>
                        handleColumnNameChange(i, e.target.value)
                      }
                      className="
                        w-full border border-gray-300
                        rounded px-2 py-1 text-sm
                      "
                    />

                    <button
                      onClick={() => deleteColumn(i)}
                      className="
                        text-red-500
                        hover:text-red-700
                      "
                    >
                      <FiTrash2 />
                    </button>
                  </div>
                </th>
              ))}

              <th />
            </tr>
          </thead>

          <tbody className="divide-y divide-gray-200">
            {data.map((row, rowIndex) => {
              const realIndex =
                (pagination.page - 1) * pagination.page_size + rowIndex;

              return (
                <tr key={realIndex} className="hover:bg-gray-50">
                  <td className="px-3 py-2 text-sm">{realIndex}</td>

                  {row.map((cell, colIndex) => (
                    <td key={colIndex} className="px-2 py-1">
                      <input
                        type="text"
                        value={cell ?? ""}
                        onChange={(e) =>
                          handleCellChange(rowIndex, colIndex, e.target.value)
                        }
                        className="
                          w-full border border-gray-300
                          rounded px-2 py-1 text-sm
                        "
                      />
                    </td>
                  ))}

                  <td className="px-2 py-1">
                    <button
                      onClick={() => deleteRow(rowIndex)}
                      className="
                        text-red-500
                        hover:text-red-700
                      "
                    >
                      <FiTrash2 />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* navegación */}

      <div className="flex items-center justify-center gap-4">
        <button
          disabled={!pagination.has_prev}
          onClick={() => onPageChange(pagination.page - 1)}
          className="
            px-4 py-2 rounded
            bg-gray-200 hover:bg-gray-300
            disabled:opacity-50
          "
        >
          anterior
        </button>

        <span className="text-sm text-gray-600">
          página {pagination.page} de {pagination.total_pages}
        </span>

        <button
          disabled={!pagination.has_next}
          onClick={() => onPageChange(pagination.page + 1)}
          className="
            px-4 py-2 rounded
            bg-gray-200 hover:bg-gray-300
            disabled:opacity-50
          "
        >
          siguiente
        </button>
      </div>
    </div>
  );
};
