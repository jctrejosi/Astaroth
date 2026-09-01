import { forecastApi } from "@/services/axios";
import type { DeleteModelResponse } from "../types";

export const delete_model = async (
  modelName: string
): Promise<DeleteModelResponse> => {
  const res = await forecastApi.delete(
    `/delete_model/${encodeURIComponent(modelName)}`
  );
  return res.data;
};
