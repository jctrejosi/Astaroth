import { forecastApi } from "@/services/axios";
import type { ForecastRequest, ForecastResponse } from "../types";

export const predict_forecast = async (
  payload: ForecastRequest
): Promise<ForecastResponse> => {
  const res = await forecastApi.post("/predict", payload);
  return res.data;
};
