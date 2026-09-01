import { forecastApi } from "@/services/axios";

export const download_model = async (modelName: string): Promise<Blob> => {
  const res = await forecastApi.post(
    "/download_model",
    { model_name: modelName },
    { responseType: "blob" }
  );

  return new Blob([res.data], { type: "application/zip" });
};
