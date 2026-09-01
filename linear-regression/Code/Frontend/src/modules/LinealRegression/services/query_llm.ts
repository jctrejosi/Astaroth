import { statsApi } from "@/services/axios";
import type { RegressionResponse } from "../types";

type LlmApiResponse = {
  ok: boolean;
  response?: string;
  error?: string;
};

export async function query_llm(
  regressionResult: RegressionResponse
): Promise<string> {
  if (!regressionResult?.ok) {
    throw new Error("resultado de regresión inválido");
  }

  const res = await statsApi.post<LlmApiResponse>("/api/v1.0/llm", {
    result: regressionResult,
  });

  if (!res.data.ok || !res.data.response) {
    throw new Error(res.data.error ?? "error consultando el modelo");
  }

  return res.data.response;
}
