import { forecastApi } from "@/services/axios";
import type { TrainResponse } from "../types";

export interface TrainPayload {
  model_name: string;
  data: Record<string, unknown>[];
}

export const train_model = async (
  payload: TrainPayload
): Promise<TrainResponse> => {
  const res = await forecastApi.post("/train", payload);
  return res.data;
};
