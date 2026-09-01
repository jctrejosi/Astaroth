export type AnovaResult = {
  ok: boolean;

  // tamaños
  n_obs: number; // número de observaciones
  n_predictors: number; // número de variables independientes (sin constante)

  // sumas de cuadrados
  ss_regression: number; // SSR
  ss_error: number; // SSE
  ss_total: number; // SST = SSR + SSE

  // cuadrados medios
  ms_regression: number; // MSR
  ms_error: number; // MSE

  // test F global del modelo
  f_statistic: number;
  p_value: number;

  // decisión estadística
  conclusion: string;

  // opcional en caso de error
  error?: string;
};

export type RegressionMeta = {
  dropped_columns?: string[];
  auto_dummies?: string[];
  warnings?: string[];
  rows_before?: number | null;
  rows_after?: number | null;
  imputed_columns?: Record<
    string,
    { mean: number; count: number } | { mean?: number; count?: number }
  >;
};

export type RegressionResponse = {
  ok: boolean;
  dependent_variable: string;
  meta?: RegressionMeta;
  n_obs: number;
  n_vars: number;
  r2: number;
  r2_adj: number;
  f_statistic: number;
  f_pvalue: number;
  anova: AnovaResult;
  coefficients: {
    variable: string;
    coef: number;
    p_value: number;
  }[];
  normality: {
    shapiro_stat: number;
    shapiro_p: number;
    ks_stat: number;
    ks_p: number;
    jarque_bera_stat: number;
    jarque_bera_p: number;
    skewness: number;
    kurtosis: number;
  };
  breusch_pagan: {
    "Lagrange multiplier": number;
    "p-value": number;
    "f-value": number;
    "f p-value": number;
    LM_p: number; // por compatibilidad extra
    F_p: number;
  };
  white_test: {
    stat: number;
    p_value: number;
    f_stat: number;
    f_p_value: number;
    error?: string;
  };
  durbin_watson: number;
  vif: {
    variable: string;
    VIF: number;
  }[];
  cooks_distance: number[];
  conclusion: string;
  results_table: {
    id: number;
    Y_observado: number;
    Y_predicho: number;
    Residuo: number;
    Residuo_estandarizado: number;
    Leverage: number;
    Cooks_distance: number;
    Outlier: boolean;
  }[];
};
