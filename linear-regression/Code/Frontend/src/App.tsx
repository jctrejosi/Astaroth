import { useEffect, useState } from "react";

import axios from "axios";

import type { TableFile } from "./@types";

import { EditableTable } from "@/modules/LinealRegression/components/EditableTable";

import { FileUpload } from "@/modules/LinealRegression/components/FileUpload";

import { LinealRegresion } from "./modules/LinealRegression";

import { TimeSeriesForecast } from "./modules/TimeSeriesForecast";

import { AiFillGithub, AiOutlinePaperClip } from "react-icons/ai";

import { convert_file } from "./modules/LinealRegression/services/convert_file";

import { statsApi } from "@/services/axios";

/* =========================
   servicio health
========================= */

const api_health = async (): Promise<boolean> => {
  try {
    const res = await axios.get("/health");

    return res.status === 200;
  } catch {
    return false;
  }
};

/* =========================
   obtener página dataset
========================= */

const getDatasetPage = async (
  file_id: string,
  page: number
): Promise<TableFile> => {
  const res = await statsApi.get<TableFile>(
    `/api/v1.0/dataset_page/${file_id}?page=${page}&page_size=50`
  );

  return res.data;
};

/* =========================
   loader
========================= */

const LoadingScreen = () => {
  return (
    <div
      className="
        min-h-screen
        flex flex-col
        items-center justify-center
        bg-gray-100 gap-4
      "
    >
      <div
        className="
          w-12 h-12
          border-4 border-gray-300
          border-t-black
          rounded-full animate-spin
        "
      />

      <p className="text-gray-600 text-sm">Iniciando backend, espere...</p>
    </div>
  );
};

export const App = () => {
  const [backendReady, setBackendReady] = useState(false);

  const [table, setTable] = useState<TableFile>();

  const [loadingPage, setLoadingPage] = useState(false);

  /* =========================
     polling health check
  ========================= */

  useEffect(() => {
    const checkBackend = async () => {
      const ok = await api_health();

      if (ok) {
        setBackendReady(true);
        clearInterval(interval);
      }
    };

    checkBackend();

    const interval = setInterval(checkBackend, 2000);

    return () => clearInterval(interval);
  }, []);

  /* =========================
     cambiar página
  ========================= */

  const handlePageChange = async (page: number) => {
    if (!table?.file_id) return;

    try {
      setLoadingPage(true);

      const newPage = await getDatasetPage(table.file_id, page);

      setTable(newPage);
    } catch (err) {
      console.error(err);

      alert("Error cargando página del dataset");
    } finally {
      setLoadingPage(false);
    }
  };

  /* =========================
     cargar ejemplo
  ========================= */

  const loadSample = async (path: string, filename: string) => {
    try {
      const res = await fetch(path);

      if (!res.ok) {
        throw new Error("No se pudo cargar ejemplo");
      }

      const blob = await res.blob();

      const file = new File([blob], filename);

      const dataset = await convert_file(file);

      setTable(dataset);
    } catch (err) {
      console.error(err);

      alert("Error cargando archivo ejemplo");
    }
  };

  /* =========================
     loading backend
  ========================= */

  if (!backendReady) {
    return <LoadingScreen />;
  }

  /* =========================
     app
  ========================= */

  return (
    <div className="bg-gray-100 min-h-screen p-6">
      <div
        className="
          relative mx-auto
          flex flex-col gap-6
          max-w-7xl
          2xl:max-w-[1600px]
          lg:pr-72
        "
      >
        {/* sidebar */}

        <div
          className="
            bg-white
            flex flex-col
            md:flex-row
            lg:flex-col
            gap-3 text-gray-500
            border border-gray-300
            p-4 rounded-lg
            lg:absolute lg:top-4 lg:right-4
          "
        >
          <a
            href="https://github.com/tu_usuario/tu_repo"
            target="_blank"
            rel="noopener"
            className="
              flex items-center gap-1
              text-white underline text-xs
              bg-gray-800 hover:bg-gray-700
              px-2 py-1 rounded
            "
          >
            <AiFillGithub size={16} />
            Ver repositorio
          </a>

          <h5 className="text-sm w-full">Seleccione un ejemplo</h5>

          <button
            onClick={() =>
              loadSample(
                "/samples/Regresion_example_1.sav",
                "Regresion_example_1.sav"
              )
            }
            className="
              hover:text-blue-600
              transition-colors
              flex gap-2 items-center
              text-left underline
            "
          >
            <AiOutlinePaperClip size={18} />
            Regresion_example_1.sav
          </button>

          <button
            onClick={() =>
              loadSample(
                "/samples/Regresion_example_2.xls",
                "Regresion_example_2.xls"
              )
            }
            className="
              hover:text-blue-600
              transition-colors
              flex gap-2 items-center
              text-left underline
            "
          >
            <AiOutlinePaperClip size={18} />
            Regresion_example_2.xls
          </button>
        </div>

        {/* upload */}

        <div
          className="
            bg-white p-6 rounded-lg shadow
            flex flex-col gap-6
          "
        >
          <FileUpload
            setData={(data) => {
              setTable(data);
            }}
          />

          <div
            className="
              flex flex-wrap
              gap-4 justify-center
            "
          >
            <LinealRegresion data={table} />

            <TimeSeriesForecast data={table} />
          </div>
        </div>

        {/* tabla */}

        {table && (
          <div
            className="
              bg-white
              p-6 rounded-lg shadow
              overflow-x-auto
            "
          >
            {loadingPage && (
              <div
                className="
                  mb-4 text-sm text-gray-500
                "
              >
                cargando página...
              </div>
            )}

            <EditableTable
              table={table}
              setData={setTable}
              onPageChange={handlePageChange}
            />
          </div>
        )}
      </div>
    </div>
  );
};
