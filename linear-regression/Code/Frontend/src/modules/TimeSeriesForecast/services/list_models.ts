import { forecastApi } from "@/services/axios";
import type { ModelsResponse } from "../types";

export const list_models = async (): Promise<ModelsResponse> => {
  const res = await forecastApi.get("/list_models");
  return res.data;
};
