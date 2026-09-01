#!/usr/bin/env node
"use strict";
/**
 * Astaroth — lanzador de todos los servicios de ML.
 *
 * Uso:
 *   node dev.js            # DEV: instala dependencias (crea .venv si falta), levanta
 *                          #   los 5 servicios con --reload, en segundo plano
 *   node dev.js --prod     # PRODUCCIÓN: uvicorn sin --reload
 *   node dev.js --stop     # Detiene los servicios levantados por dev.js
 *   node dev.js --help     # Esta ayuda
 *
 * Logs: logs/*.log (un archivo por servicio).
 * Pids: logs/.pids.json.
 *
 * Para solo los 3 servicios que consume el ecommerce (sin PyTorch),
 * usa `node dev-ecommerce.js`.
 */
const { run } = require("./dev-lib.js");

const SERVICES = [
  { name: "clustering", dir: "clustering-api", port: 8010, entry: "app.main:app" },
  { name: "xgboost", dir: "XGBoost-api", port: 8011, entry: "app.main:app" },
  { name: "uplift", dir: "uplift-api", port: 8012, entry: "app.main:app" },
  { name: "transformer", dir: "transformerApi", port: 8013, entry: "apis.main:app" },
  { name: "causal", dir: "causalTransformer-api", port: 8014, entry: "api.main:app" },
];

run(SERVICES, "all", process.argv.slice(2));
