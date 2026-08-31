#!/usr/bin/env node
"use strict";
/**
 * Astaroth — lanzador local (solo lo que consume el ecommerce).
 *
 * Levanta únicamente los servicios ligeros que usa la plataforma
 * mercaldas-ecommerce en desarrollo local:
 *
 *   clustering (8010) — segmentación (kmeans / minibatch / gmm)
 *   xgboost    (8011) — propensión de compra
 *   uplift     (8012) — uplift modeling
 *
 * Los servicios pesados de PyTorch (transformer 8013, causal 8014)
 * NO se levantan aquí; usa `node dev.js` para el set completo.
 *
 * Uso:
 *   node dev-ecommerce.js            # DEV: servicios con --reload, en segundo plano
 *   node dev-ecommerce.js --prod     # PRODUCCIÓN: uvicorn sin --reload
 *   node dev-ecommerce.js --stop     # Detiene los servicios de este script
 *   node dev-ecommerce.js --help     # Esta ayuda
 *
 * Logs: logs/*.log (compartidos con dev.js).
 * Pids: logs/.pids-ecommerce.json (independiente de dev.js).
 */
const { run } = require("./dev-lib.js");

const SERVICES = [
  { name: "clustering", dir: "clustering-api", port: 8010, entry: "app.main:app" },
  { name: "xgboost", dir: "XGBoost-api", port: 8011, entry: "app.main:app" },
  { name: "uplift", dir: "uplift-api", port: 8012, entry: "app.main:app" },
];

run(SERVICES, "ecommerce", process.argv.slice(2));
