#!/usr/bin/env node
"use strict";
/**
 * Astaroth — lanzador único de los servicios de ML (FastAPI).
 *
 * Un solo script con selección por parámetros (sin flags = todos):
 *
 *   node dev.js                        # los 5 servicios
 *   node dev.js --analytics            # solo lo que consume el ecommerce/analytics
 *                                      #   (clustering 8010 + xgboost 8011 + uplift 8012)
 *   node dev.js --clustering           # un servicio concreto (combinable)
 *   node dev.js --xgboost --uplift     # solo esos dos
 *   node dev.js --transformer --causal # los pesados (PyTorch)
 *   node dev.js --all                  # explícito: todos
 *
 * Modos:
 *   node dev.js --prod                 # producción (uvicorn sin --reload)
 *   node dev.js --stop [flags]         # detiene todos, o solo los seleccionados
 *   node dev.js --help
 *
 * Logs: logs/<servicio>.log · PIDs: logs/.pids.json.
 */
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");

const ROOT = __dirname;
const LOGS_DIR = path.join(ROOT, "logs");
const PIDS_FILE = path.join(LOGS_DIR, ".pids.json");
// Pids de los launchers anteriores (dev.js / dev-ecommerce.js): se limpian al
// detener para no dejar procesos huérfanos.
const LEGACY_PIDS_FILES = [
  path.join(LOGS_DIR, ".pids-all.json"),
  path.join(LOGS_DIR, ".pids-ecommerce.json"),
];

// ── Catálogo de servicios ───────────────────────────────────
// `group: "analytics"` = lo que consume la plataforma mercaldas-ecommerce
// (segmentación + propensión + uplift). El resto son los pesados (PyTorch).
const SERVICES = [
  { name: "clustering", dir: "clustering-api", port: 8010, entry: "app.main:app", group: "analytics" },
  { name: "xgboost", dir: "XGBoost-api", port: 8011, entry: "app.main:app", group: "analytics" },
  { name: "uplift", dir: "uplift-api", port: 8012, entry: "app.main:app", group: "analytics" },
  { name: "transformer", dir: "transformerApi", port: 8013, entry: "apis.main:app" },
  { name: "causal", dir: "causalTransformer-api", port: 8014, entry: "api.main:app" },
];

const SERVICE_NAMES = new Set(SERVICES.map((s) => s.name));
const GROUP_ALIASES = { analytics: "analytics" };

/**
 * Servicios elegidos por los flags. `null` ⇒ todos (sin flags de selección).
 *   --all / sin flags       → los 5
 *   --analytics             → grupo analytics (clustering + xgboost + uplift)
 *   --clustering --uplift   → servicios concretos (combinables)
 * Los flags de modo (--prod, --stop, --help, ...) y desconocidos se ignoran aquí.
 */
function selectServices(argv) {
  const flags = argv.filter((a) => a.startsWith("--")).map((a) => a.slice(2).toLowerCase());
  const chosen = new Set();
  let any = false;
  for (const f of flags) {
    if (f === "all") {
      SERVICES.forEach((s) => chosen.add(s.name));
      any = true;
    } else if (GROUP_ALIASES[f]) {
      SERVICES.filter((s) => s.group === GROUP_ALIASES[f]).forEach((s) => chosen.add(s.name));
      any = true;
    } else if (SERVICE_NAMES.has(f)) {
      chosen.add(f);
      any = true;
    }
  }
  return any ? SERVICES.filter((s) => chosen.has(s.name)) : null;
}

const VALID_FLAGS = new Set([
  "--prod",
  "--live",
  "--stop",
  "--help",
  "--all",
  "--analytics",
  ...SERVICES.map((s) => `--${s.name}`),
]);

/** Flags `--x` no reconocidos. Si hay alguno, el launcher no ejecuta nada. */
function unknownFlags(argv) {
  return argv.filter((a) => a.startsWith("--") && !VALID_FLAGS.has(a.toLowerCase()));
}

// ── Utilidades de red ───────────────────────────────────────

function waitForPort(port, timeoutMs = 90000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve) => {
    const attempt = () => {
      const sock = net.connect({ host: "127.0.0.1", port });
      const done = (ok) => {
        try {
          sock.destroy();
        } catch {
          /* noop */
        }
        resolve(ok);
      };
      sock.once("connect", () => done(true));
      sock.once("error", () => {
        try {
          sock.destroy();
        } catch {
          /* noop */
        }
        if (Date.now() > deadline) done(false);
        else setTimeout(attempt, 1000);
      });
    };
    attempt();
  });
}

function sleepSync(ms) {
  const sab = new SharedArrayBuffer(4);
  Atomics.wait(new Int32Array(sab), 0, 0, ms);
}

function killPort(port) {
  if (process.platform === "win32") {
    try {
      const out = spawnSync("netstat", ["-ano"], { encoding: "utf8" }).stdout;
      const pids = new Set();
      out.split("\n").forEach((line) => {
        const m = line.trim().match(new RegExp(`:${port}\\s+.*?LISTENING\\s+(\\d+)\\s*$`));
        if (m) pids.add(m[1]);
      });
      pids.forEach((pid) => {
        try {
          spawnSync("taskkill", ["/PID", pid, "/T", "/F"], { stdio: "ignore" });
        } catch {
          /* ya terminó */
        }
      });
      if (pids.size) console.log(`  ✓ puerto ${port} liberado (PID ${[...pids].join(", ")})`);
    } catch {
      /* sin procesos */
    }
  } else {
    const r = spawnSync("fuser", ["-k", `${port}/tcp`], {
      stdio: ["ignore", "pipe", "ignore"],
      encoding: "utf8",
    });
    const out = (r.stdout || "").toString().trim();
    if (out) console.log(`  ✓ puerto ${port} liberado (PID ${out})`);
  }
}

// ── Logs ────────────────────────────────────────────────────

function openLog(name, mode) {
  fs.mkdirSync(LOGS_DIR, { recursive: true });
  const logPath = path.join(LOGS_DIR, `${name}.log`);
  const fd = fs.openSync(logPath, "a");
  fs.writeSync(fd, `\n===== [${name}] ${new Date().toISOString()} modo=${mode} =====\n`);
  return { fd, logPath };
}

// ── Dependencias ────────────────────────────────────────────

/**
 * Crea el .venv e instala requirements.txt si el venv del servicio no existe.
 * Devuelve true si las dependencias quedaron listas (ya estaban o se instalaron).
 */
function ensureDeps(svc) {
  const color = C[svc.name] || "";
  const cwd = path.join(ROOT, svc.dir);
  if (fs.existsSync(path.join(cwd, ".venv", "bin", "python"))) return true;

  console.log(`${color}[${svc.name}]${C.reset} 📦 creando .venv e instalando dependencias...`);
  const steps = [
    ["python3", "-m", "venv", ".venv"],
    [".venv", "bin", "pip", "install", "-r", "requirements.txt"],
  ];
  for (const step of steps) {
    const r = spawnSync(step[0], step.slice(1), { cwd, stdio: "inherit" });
    if (r.status !== 0) {
      console.error(
        `${color}[${svc.name}]${C.reset} ✘ falló la instalación: ${step.join(" ")} — se omite este servicio`,
      );
      return false;
    }
  }
  console.log(`${color}[${svc.name}]${C.reset} ✅ dependencias listas`);
  return true;
}

// ── Arranque de servicios ───────────────────────────────────

function resolveCmd(svc, mode) {
  const py = path.join(ROOT, svc.dir, ".venv", "bin", "python");
  if (!fs.existsSync(py)) {
    console.warn(
      `${C[svc.name] || ""}[${svc.name}]${C.reset} ⚠️  ${svc.dir}/.venv no existe — crealo con: ` +
        `cd ${svc.dir} && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`,
    );
    return null;
  }
  const args = [
    py, "-m", "uvicorn", svc.entry,
    "--host", "127.0.0.1", "--port", String(svc.port),
  ];
  if (mode === "dev") args.push("--reload");
  return args;
}

function startService(svc, mode) {
  const color = C[svc.name] || "";
  console.log(`${color}[${svc.name}]${C.reset} ▶ http://localhost:${svc.port}  (log: logs/${svc.name}.log)`);

  const cmd = resolveCmd(svc, mode);
  if (!cmd) return null;

  killPort(svc.port);
  sleepSync(800);

  const { fd } = openLog(svc.name, mode);
  const child = spawn(cmd[0], cmd.slice(1), {
    cwd: path.join(ROOT, svc.dir),
    stdio: ["ignore", fd, fd],
    detached: true,
    shell: process.platform === "win32",
  });

  child.on("error", (err) => {
    console.error(`${color}[${svc.name}]${C.reset} ✘ no se pudo arrancar: ${err.message}`);
  });
  child.unref();
  fs.closeSync(fd);
  return child.pid;
}

function printUrls(services) {
  console.log("\n━━━━━━━━━━━━━ Astaroth — URLs ━━━━━━━━━━━━━");
  for (const svc of services) {
    console.log(`  ${svc.name.toUpperCase().padEnd(11)} → http://localhost:${svc.port}`);
  }
  console.log("  Docs        → http://localhost:{puerto}/docs");
  console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log("Logs: logs/*.log");
}

// ── Detención ───────────────────────────────────────────────

function killPid(pid) {
  try {
    if (process.platform === "win32") {
      spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"]);
    } else {
      process.kill(-pid, "SIGTERM");
    }
    return true;
  } catch {
    try {
      process.kill(pid, "SIGTERM");
      return true;
    } catch {
      return false;
    }
  }
}

/** Detiene `targets` (pids registrados + puertos). Si es todo el catálogo, limpia el archivo de pids. */
function stopAll(targets) {
  const names = new Set(targets.map((s) => s.name));
  const stopEverything = names.size === SERVICES.length;

  const pids = {};
  for (const f of [PIDS_FILE, ...LEGACY_PIDS_FILES]) {
    try {
      Object.assign(pids, JSON.parse(fs.readFileSync(f, "utf8")));
    } catch {
      /* sin archivo */
    }
  }

  const remaining = {};
  let stopped = 0;
  for (const [name, pid] of Object.entries(pids)) {
    if (!stopEverything && !names.has(name)) {
      remaining[name] = pid; // no seleccionado: sigue corriendo
      continue;
    }
    if (killPid(pid)) {
      console.log(`⏹  ${name} (pid ${pid})`);
      stopped += 1;
    } else {
      console.log(`   ${name} ya no estaba corriendo (pid ${pid})`);
    }
  }

  // Red de seguridad: liberar los puertos de los servicios seleccionados aunque
  // el proceso no hubiera quedado registrado.
  for (const svc of targets) killPort(svc.port);

  fs.mkdirSync(LOGS_DIR, { recursive: true });
  if (Object.keys(remaining).length) {
    fs.writeFileSync(PIDS_FILE, JSON.stringify(remaining, null, 2));
  } else {
    try {
      fs.unlinkSync(PIDS_FILE);
    } catch {
      /* noop */
    }
  }
  for (const f of LEGACY_PIDS_FILES) {
    try {
      fs.unlinkSync(f);
    } catch {
      /* noop */
    }
  }

  if (!stopped) console.log("No había servicios registrados para detener.");
}

// ── Ayuda ───────────────────────────────────────────────────

function printHelp() {
  const out = [];
  out.push("Astaroth — lanzador de servicios de ML");
  out.push("");
  out.push("USO");
  out.push("  node dev.js [flags]");
  out.push("");
  out.push("SELECCIÓN (sin flags levanta los 5)");
  out.push("  --analytics        solo lo del ecommerce/analytics: clustering + xgboost + uplift");
  out.push("  --clustering       solo clustering-api        :8010");
  out.push("  --xgboost          solo XGBoost-api           :8011");
  out.push("  --uplift           solo uplift-api            :8012");
  out.push("  --transformer      solo transformerApi        :8013  (PyTorch, pesado)");
  out.push("  --causal           solo causalTransformer-api :8014  (PyTorch, pesado)");
  out.push("  --all              los 5 (explícito)");
  out.push("");
  out.push("MODOS");
  out.push("  --prod / --live    producción (uvicorn sin --reload)");
  out.push("  --stop [flags]     detiene los servicios (todos, o solo los seleccionados)");
  out.push("  --help             esta ayuda");
  out.push("");
  out.push("EJEMPLOS");
  out.push("  node dev.js                       → los 5 servicios");
  out.push("  node dev.js --analytics           → clustering + xgboost + uplift (analytics)");
  out.push("  node dev.js --xgboost --uplift    → solo esos dos");
  out.push("  node dev.js --stop --analytics    → detiene solo el set de analytics");
  out.push("");
  out.push("Logs: logs/<servicio>.log · PIDs: logs/.pids.json");
  out.push("Un flag desconocido no ejecuta nada (aborta; usa --help para ver las opciones).");
  console.log(out.join("\n"));
}

/** Resumen final tras levantar: todas las formas de invocar el lanzador. */
function printCommands() {
  const rows = [
    ["node dev.js", "los 5 servicios"],
    ["node dev.js --analytics", "clustering + xgboost + uplift (lo que usa el ecommerce)"],
    ...SERVICES.map((svc) => [
      `node dev.js --${svc.name}`,
      `solo ${svc.dir} :${svc.port}${svc.group ? "" : " — PyTorch, pesado"}`,
    ]),
    ["node dev.js --all", "los 5 (explícito)"],
    ["node dev.js --prod", "producción (uvicorn sin --reload)"],
    ["node dev.js --stop [flags]", "detiene (todos, o solo los seleccionados)"],
    ["node dev.js --help", "esta ayuda"],
  ];
  const w = Math.max(...rows.map((r) => r[0].length));
  console.log("Comandos útiles:");
  for (const [cmd, desc] of rows) console.log(`  ${cmd.padEnd(w)}  → ${desc}`);
}

const C = {
  clustering: "\x1b[36m",
  xgboost: "\x1b[32m",
  uplift: "\x1b[33m",
  transformer: "\x1b[95m",
  causal: "\x1b[91m",
  reset: "\x1b[0m",
};

// ── Main ────────────────────────────────────────────────────

async function main() {
  const argv = process.argv.slice(2);
  const MODE = argv.includes("--prod") || argv.includes("--live") ? "prod" : "dev";
  const STOP = argv.includes("--stop");
  const HELP = argv.includes("--help");

  const selected = selectServices(argv); // null ⇒ todos
  const services = selected ?? SERVICES;
  const label = selected ? selected.map((s) => s.name).join(" + ") : "todos";

  if (HELP) return printHelp();

  // Flag desconocido ⇒ no se ejecuta nada (antes se interpretaba como "todos").
  const unknown = unknownFlags(argv);
  if (unknown.length) {
    console.error(`✘ Flag(s) desconocido(s): ${unknown.join(", ")} — no se levanta nada.`);
    console.error("  Usa `node dev.js --help` para ver las opciones.");
    process.exit(1);
  }

  if (STOP) return stopAll(services);

  fs.mkdirSync(LOGS_DIR, { recursive: true });
  console.log(`🧪 Astaroth — modo ${MODE.toUpperCase()} · servicios: ${label}  (logs → logs/*.log)`);
  console.log("");

  // Instalar dependencias faltantes ANTES de arrancar: si un servicio falla la
  // instalación, se omite más abajo.
  const sinDeps = new Set();
  for (const svc of services) {
    if (!ensureDeps(svc)) sinDeps.add(svc.name);
  }
  console.log("");

  const started = {};
  for (const svc of services) {
    if (sinDeps.has(svc.name)) continue; // falló la instalación de dependencias
    const pid = startService(svc, MODE);
    if (pid) started[svc.name] = pid;
  }
  // Conservar los pids de servicios no seleccionados que sigan corriendo.
  let existing = {};
  try {
    existing = JSON.parse(fs.readFileSync(PIDS_FILE, "utf8"));
  } catch {
    /* sin archivo */
  }
  fs.writeFileSync(PIDS_FILE, JSON.stringify({ ...existing, ...started }, null, 2));

  for (const svc of services) {
    if (!started[svc.name]) {
      console.log(`${C[svc.name] || ""}[${svc.name}]${C.reset} ⏭  dependencias fallidas — omitido`);
      continue;
    }
    console.log(`${C[svc.name] || ""}[${svc.name}]${C.reset} ⏳ esperando :${svc.port}...`);
    const up = await waitForPort(svc.port, 90000);
    if (up) console.log(`${C[svc.name] || ""}[${svc.name}]${C.reset} ✅ listo`);
    else
      console.warn(
        `${C[svc.name] || ""}[${svc.name}]${C.reset} ⚠️  no respondió en :${svc.port} — revisa logs/${svc.name}.log`,
      );
  }

  printUrls(services);
  console.log("\n✅ Listo. Esta terminal queda libre — puedes cerrarla.");
  printCommands();
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
