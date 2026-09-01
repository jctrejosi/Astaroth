// services/api.ts

import axios from "axios";

export const statsApi = axios.create({
  baseURL: import.meta.env.VITE_STATS_API,
});

export const forecastApi = axios.create({
  baseURL: import.meta.env.VITE_FORECAST_API,
});
