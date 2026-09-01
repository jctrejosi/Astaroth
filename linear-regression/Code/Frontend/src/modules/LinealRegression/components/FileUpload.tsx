import type { TableFile } from "@/@types";
import axios from "axios";
import type { ChangeEvent, DragEvent } from "react";
import { AiOutlineCloudUpload } from "react-icons/ai";

interface FileUploadProps {
  setData: (data: TableFile) => void;
}

export const FileUpload = ({ setData }: FileUploadProps) => {
  const processFile = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post<TableFile>(
        "api/v1.0/converter_file",
        formData,
        {
          headers: { "Content-Type": "multipart/form-data" },
        }
      );

      setData(response.data);
    } catch (error) {
      console.error("Error procesando archivo:", error);
      alert("Ocurrió un error al procesar el archivo.");
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  const handleDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  };

  return (
    <label
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      className="flex flex-col items-center justify-center w-full max-w-xs p-6 mx-auto
                 border-2 border-dashed border-blue-300 rounded-lg cursor-pointer
                 hover:border-blue-500 hover:bg-blue-50 transition-all duration-200"
    >
      <AiOutlineCloudUpload size={60} className="text-blue-600" />

      <span className="text-gray-700 font-medium text-center mb-1">
        Arrastra o selecciona un archivo
      </span>

      <span className="text-gray-400 text-sm text-center">
        (.csv, .xlsx, .xls, .sav, .ods, .data)
      </span>

      <input
        type="file"
        accept=".csv,.sav,.xlsx,.xls,.ods,.data"
        onChange={handleFileChange}
        className="hidden"
      />
    </label>
  );
};
