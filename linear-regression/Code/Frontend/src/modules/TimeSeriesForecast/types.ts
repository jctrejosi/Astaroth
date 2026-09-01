export interface ForecastRow {
  [key: string]: string | number | boolean | null;
}

export interface ForecastRequest {
  model_name: string;
  points: number;
  data: ForecastRow[];
}

export interface ForecastResponse {
  status: string;
  model_used: string;
  forecast: ForecastRow[];
}

export interface ModelItem {
  model_name: string;
  last_modified: string;
  size_kb: number;
}

export interface ModelsResponse {
  models: ModelItem[];
  count: number;
}

export interface TrainResponse {
  status: string;
  message: string;
  assets?: string[];
  model_name?: string;
}

export interface FineTuningResponse {
  status: string;
  message: string;
}

export interface UploadModelResponse {
  status: string;
  message: string;
  files?: string[];
}

export interface DeleteModelResponse {
  status: string;
  message: string;
  deleted_files?: string[];
}
