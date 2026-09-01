"use strict";
/**
 * dev-lib.js — lanzador compartido de servicios Astaroth.
 *
 * Lo usan:
 *   dev.js            → todos los servicios (5)
 *   dev-ecommerce.js  → solo los que consume el ecommerce (3 ligeros)
 *
 * Cada entrada define su lista de servicios y su propio archivo de pids
 * (logs/.pids-<id>.json), así --stop de un script no toca al otro.
 */
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");

const ROOT = __dirname;
const LOGS_DIR = path.join(ROOT, "logs");

const C = {
  clustering: "\x1b[36m",
  xgboost: "\x1b[32m",
  uplift: "\x1b[33m",
  transformer: "\x1b[95m",
  causal: "\x1b[91m",
  reset: "\x1b[0m",
};

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

  console.log(
    `${color}[${svc.name}]${C.reset} 📦 creando .venv e instalando dependencias...`,
  );
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

function stopAll(services, pidsFile) {
  let pids = {};
  try {
    pids = JSON.parse(fs.readFileSync(pidsFile, "utf8"));
  } catch {
    /* sin archivo de pids */
  }

  const entries = Object.entries(pids);
  if (!entries.length) console.log("No hay servicios registrados.");
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

  for (const svc of services) killPort(svc.port);

  try {
    fs.unlinkSync(pidsFile);
  } catch {
    /* noop */
  }
}

// ── Main compartido ─────────────────────────────────────────

async function run(services, id, argv) {
  const MODE = argv.includes("--prod") || argv.includes("--live") ? "prod" : "dev";
  const STOP = argv.includes("--stop");
  const HELP = argv.includes("--help");
  const PIDS_FILE = path.join(LOGS_DIR, `.pids-${id}.json`);

  const usage = () =>
    `Astaroth launcher [${id}]\n` +
    `  node ${id === "all" ? "dev.js" : "dev-ecommerce.js"}            → dev (--reload)\n` +
    `  node ${id === "all" ? "dev.js" : "dev-ecommerce.js"} --prod     → producción\n` +
    `  node ${id === "all" ? "dev.js" : "dev-ecommerce.js"} --stop     → detiene los servicios\n` +
    `  node ${id === "all" ? "dev.js" : "dev-ecommerce.js"} --help     → esta ayuda\n`;

  if (HELP) {
    console.log(usage());
    return;
  }
  if (STOP) return stopAll(services, PIDS_FILE);

  fs.mkdirSync(LOGS_DIR, { recursive: true });
  console.log(`🧪 Astaroth [${id}] — modo ${MODE.toUpperCase()}  (logs → logs/*.log)`);
  console.log("");

  // Instalar dependencias faltantes ANTES de arrancar: si un servicio falla
  // la instalación, se omite más abajo.
  const sinDeps = new Set();
  for (const svc of services) {
    if (!ensureDeps(svc)) sinDeps.add(svc.name);
  }
  console.log("");

  const pids = {};
  for (const svc of services) {
    if (sinDeps.has(svc.name)) continue; // falló la instalación de dependencias
    const pid = startService(svc, MODE);
    if (pid) pids[svc.name] = pid;
  }
  fs.writeFileSync(PIDS_FILE, JSON.stringify(pids, null, 2));

  for (const svc of services) {
    if (!pids[svc.name]) {
      console.log(`${C[svc.name] || ""}[${svc.name}]${C.reset} ⏭  dependencias fallidas — omitido`);
      continue;
    }
    console.log(`${C[svc.name] || ""}[${svc.name}]${C.reset} ⏳ esperando :${svc.port}...`);
    const up = await waitForPort(svc.port, 90000);
    if (up) console.log(`${C[svc.name] || ""}[${svc.name}]${C.reset} ✅ listo`);
    else console.warn(`${C[svc.name] || ""}[${svc.name}]${C.reset} ⚠️  no respondió en :${svc.port} — revisa logs/${svc.name}.log`);
  }

  printUrls(services);
  console.log("\n✅ Todo levantado. Esta terminal queda libre — puedes cerrarla.");
  console.log(`Comandos útiles:`);
  console.log(`  node ${id === "all" ? "dev.js" : "dev-ecommerce.js"} --stop   → detener los servicios`);
  process.exit(0);
}

module.exports = { run };
