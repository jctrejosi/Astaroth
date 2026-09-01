import { forecastApi } from "@/services/axios";
import type { UploadModelResponse } from "../types";

export const upload_model = async (
  file: File
): Promise<UploadModelResponse> => {
  const form = new FormData();
  form.append("file", file);

  const res = await forecastApi.post("/upload_model", form, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return res.data;
};
