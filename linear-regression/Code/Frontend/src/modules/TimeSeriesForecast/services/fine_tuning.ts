import { forecastApi } from "@/services/axios";
import type { FineTuningResponse } from "../types";

export interface FineTuningPayload {
  model_name: string;
  data: Record<string, unknown>[];
}

export const fine_tuning = async (
  payload: FineTuningPayload
): Promise<FineTuningResponse> => {
  const res = await forecastApi.post("/fine_tuning", payload);
  return res.data;
};
