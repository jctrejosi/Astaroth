import { statsApi } from "@/services/axios";
import type { RegressionResponse } from "../types";

type DataSend = {
  columns: string[];
  data: (string | number | null)[][];
  dependent: string;
};

export const set_regression = async (data: DataSend) => {
  try {
    const res = await statsApi.post<RegressionResponse>("api/v1.0/regression", {
      ...data,
    });
    return res.data;
  } catch (err) {
    console.error(err);
    throw err;
  }
};
