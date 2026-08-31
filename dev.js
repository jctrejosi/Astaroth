#!/usr/bin/env node
/**
 * Astaroth — lanzador de servicios de ML.
 *
 * Uso:
 *   node dev.js            # DEV: levanta clustering-api (8010), xgboost-api (8011)
 *                          #   y uplift-api (8012) con --reload, en segundo plano.
 *   node dev.js --prod     # PRODUCCIÓN: uvicorn sin --reload.
 *   node dev.js --stop     # Detiene los servicios levantados por dev.js.
 *   node dev.js --help     # Esta ayuda.
 *
 * Logs: logs/*.log (un archivo por servicio).
 */
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");

const ROOT = __dirname;
const LOGS_DIR = path.join(ROOT, "logs");
const PIDS_FILE = path.join(LOGS_DIR, ".pids.json");

const ARGS = process.argv.slice(2);
const MODE = ARGS.includes("--prod") || ARGS.includes("--live") ? "prod" : "dev";
const STOP = ARGS.includes("--stop");
const HELP = ARGS.includes("--help");

const SERVICES = [
  { name: "clustering", dir: "clustering-api", port: 8010, entry: "app.main:app" },
  { name: "xgboost", dir: "XGBoost-api", port: 8011, entry: "app.main:app" },
  { name: "uplift", dir: "uplift-api", port: 8012, entry: "app.main:app" },
  { name: "transformer", dir: "transformerApi", port: 8013, entry: "apis.main:app" },
  { name: "causal", dir: "causalTransformer-api", port: 8014, entry: "api.main:app" },
];

const C = {
  clustering: "\x1b[36m",
  xgboost: "\x1b[32m",
  uplift: "\x1b[33m",
  transformer: "\x1b[95m",
  causal: "\x1b[91m",
  reset: "\x1b[0m",
};

// ── Utilidades de red ───────────────────────────────────────

function waitForPort(port, timeoutMs = 60000) {
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
      if (pids.size)
        console.log(`  ✓ puerto ${port} liberado (PID ${[...pids].join(", ")})`);
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

function openLog(name) {
  fs.mkdirSync(LOGS_DIR, { recursive: true });
  const logPath = path.join(LOGS_DIR, `${name}.log`);
  const fd = fs.openSync(logPath, "a");
  fs.writeSync(fd, `\n===== [${name}] ${new Date().toISOString()} modo=${MODE} =====\n`);
  return { fd, logPath };
}

// ── Arranque de servicios ───────────────────────────────────

function resolveCmd(svc) {
  const py = path.join(ROOT, svc.dir, ".venv", "bin", "python");
  if (!fs.existsSync(py)) {
    console.warn(
      `${C[svc.name]}[${svc.name}]${C.reset} ⚠️  ${svc.dir}/.venv no existe — crealo con: ` +
        `cd ${svc.dir} && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`,
    );
    return null;
  }
  const args = [
    py, "-m", "uvicorn", svc.entry,
    "--host", "127.0.0.1", "--port", String(svc.port),
  ];
  if (MODE === "dev") args.push("--reload");
  return args;
}

function startService(svc) {
  const color = C[svc.name] || "";
  console.log(`${color}[${svc.name}]${C.reset} ▶ http://localhost:${svc.port}  (log: logs/${svc.name}.log)`);

  const cmd = resolveCmd(svc);
  if (!cmd) return null;

  killPort(svc.port);
  sleepSync(800);

  const { fd } = openLog(svc.name);
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

function printUrls() {
  console.log("\n━━━━━━━━━━━━━ Astaroth — URLs ━━━━━━━━━━━━━");
  for (const svc of SERVICES) {
    console.log(`  ${svc.name.toUpperCase().padEnd(11)} → http://localhost:${svc.port}`);
  }
  console.log("  Docs        → http://localhost:{puerto}/docs");
  console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log("Logs: logs/*.log");
}

// ── Detención ───────────────────────────────────────────────

function stopAll() {
  let pids = {};
  try {
    pids = JSON.parse(fs.readFileSync(PIDS_FILE, "utf8"));
  } catch {
    /* sin archivo de pids */
  }

  const entries = Object.entries(pids);
  if (!entries.length) console.log("No hay servicios registrados (logs/.pids.json).");
  for (const [name, pid] of entries) {
    try {
      if (process.platform === "win32") {
        spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"]);
      } else {
        process.kill(-pid, "SIGTERM");
      }
      console.log(`⏹  ${name} (pid ${pid})`);
    } catch {
      try {
        process.kill(pid, "SIGTERM");
        console.log(`⏹  ${name} (pid ${pid})`);
      } catch {
        console.log(`  ${name} ya no estaba corriendo`);
      }
    }
  }

  for (const svc of SERVICES) killPort(svc.port);

  try {
    fs.unlinkSync(PIDS_FILE);
  } catch {
    /* noop */
  }
}

// ── Main ────────────────────────────────────────────────────

async function main() {
  if (HELP) {
    console.log(
      "Astaroth launcher\n" +
        "  node dev.js            → dev (servicios con --reload, terminal libre)\n" +
        "  node dev.js --prod     → producción (uvicorn sin --reload)\n" +
        "  node dev.js --stop     → detiene los servicios\n" +
        "  node dev.js --help     → esta ayuda\n",
    );
    return;
  }
  if (STOP) return stopAll();

  fs.mkdirSync(LOGS_DIR, { recursive: true });
  console.log(`🧪 Astaroth — modo ${MODE.toUpperCase()}  (logs → logs/*.log)`);
  console.log("");

  const pids = {};
  for (const svc of SERVICES) {
    const pid = startService(svc);
    if (pid) pids[svc.name] = pid;
  }
  fs.writeFileSync(PIDS_FILE, JSON.stringify(pids, null, 2));

  for (const svc of SERVICES) {
    if (!pids[svc.name]) {
      console.log(`${C[svc.name]}[${svc.name}]${C.reset} ⏭  sin venv — omitido`);
      continue;
    }
    console.log(`${C[svc.name]}[${svc.name}]${C.reset} ⏳ esperando :${svc.port}...`);
    const up = await waitForPort(svc.port, 90000);
    if (up) console.log(`${C[svc.name]}[${svc.name}]${C.reset} ✅ listo`);
    else console.warn(`${C[svc.name]}[${svc.name}]${C.reset} ⚠️  no respondió en :${svc.port} — revisa logs/${svc.name}.log`);
  }

  printUrls();
  console.log("\n✅ Todo levantado. Esta terminal queda libre — puedes cerrarla.");
  console.log("Comandos útiles:");
  console.log(`  node dev.js --stop   → detener los servicios`);
  console.log(`  node dev.js --help   → ayuda`);
  process.exit(0);
}

main();
