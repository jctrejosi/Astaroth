#!/usr/bin/env node
/**
 * linear-regression Backend — launcher.
 *
 * Crea el entorno virtual (venv/) si no existe, instala las dependencias de
 * requirements.txt la primera vez y arranca el backend (Flask).
 *
 * Uso:
 *   node dev.js            → crea venv si falta, instala deps (1ª vez) y arranca
 *                            en desarrollo (Flask, http://0.0.0.0:5000)
 *   node dev.js --prod     → arranca con gunicorn (solo Linux/macOS)
 *   node dev.js --install  → reinstala requirements.txt aunque ya exista venv
 *   node dev.js --port 6000→ cambia el puerto (por defecto 5000)
 *   node dev.js --host 127.0.0.1 → cambia el host (por defecto 0.0.0.0)
 *   node dev.js --help     → esta ayuda
 *
 * El .env de la carpeta se carga automáticamente (main.py llama a load_dotenv()).
 */

const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = __dirname;
const VENV_DIR = path.join(ROOT, "venv");
const REQS_FILE = path.join(ROOT, "requirements.txt");

const IS_WIN = process.platform === "win32";

const PYTHON_BIN = IS_WIN
  ? path.join(VENV_DIR, "Scripts", "python.exe")
  : path.join(VENV_DIR, "bin", "python");
const PIP_BIN = IS_WIN
  ? path.join(VENV_DIR, "Scripts", "pip.exe")
  : path.join(VENV_DIR, "bin", "pip");
const GUNICORN_BIN = IS_WIN
  ? null
  : path.join(VENV_DIR, "bin", "gunicorn");

// ── Argumentos ──────────────────────────────────────────────

const args = process.argv.slice(2);
const HELP = args.includes("--help") || args.includes("-h");
const INSTALL = args.includes("--install") || args.includes("-i");
const PROD = args.includes("--prod") || args.includes("--production");

function readArg(flag) {
  const i = args.findIndex((a) => a === flag);
  return i >= 0 && args[i + 1] ? args[i + 1] : null;
}

const PORT = readArg("--port") || readArg("-p") || "5000";
const HOST = readArg("--host") || "0.0.0.0";

// ── Utilidades ──────────────────────────────────────────────

function log(msg) {
  console.log(`\x1b[36m[dev]\x1b[0m ${msg}`);
}

function ok(msg) {
  console.log(`\x1b[32m[dev]\x1b[0m ✓ ${msg}`);
}

function fail(msg) {
  console.error(`\x1b[31m[dev]\x1b[0m ✘ ${msg}`);
}

/** Encuentra un intérprete de Python disponible en el sistema. */
function findSystemPython() {
  const candidates = IS_WIN ? ["python", "py"] : ["python3", "python"];
  for (const c of candidates) {
    const r = spawnSync(c, ["--version"], { stdio: "ignore" });
    if (r.status === 0) return c;
  }
  return null;
}

function runSync(cmd, cmdArgs, opts = {}) {
  const r = spawnSync(cmd, cmdArgs, { stdio: "inherit", ...opts });
  if (r.error) {
    fail(`no se pudo ejecutar: ${cmd} (${r.error.message})`);
    return 1;
  }
  return r.status === null ? 1 : r.status;
}

// ── Entorno virtual ─────────────────────────────────────────

function venvReady() {
  return (
    fs.existsSync(PYTHON_BIN) &&
    fs.existsSync(PIP_BIN) &&
    fs.existsSync(REQS_FILE)
  );
}

function ensureVenv() {
  if (venvReady() && !INSTALL) {
    ok(`entorno virtual detectado (${path.basename(VENV_DIR)}/)`);
    return true;
  }

  const python = findSystemPython();
  if (!python) {
    fail("no se encontró Python en el PATH (probé: python3 / python).");
    return false;
  }

  if (!fs.existsSync(PYTHON_BIN)) {
    log(`creando entorno virtual con ${python}...`);
    if (runSync(python, ["-m", "venv", VENV_DIR]) !== 0) {
      fail("falló la creación del entorno virtual.");
      return false;
    }
    ok("entorno virtual creado.");
  }

  log("actualizando pip...");
  if (runSync(PYTHON_BIN, ["-m", "pip", "install", "--upgrade", "pip"]) !== 0) {
    fail("no se pudo actualizar pip.");
    return false;
  }

  log("instalando dependencias (requirements.txt)...");
  if (runSync(PIP_BIN, ["install", "-r", REQS_FILE]) !== 0) {
    fail("falló la instalación de dependencias.");
    return false;
  }
  ok("dependencias instaladas.");

  return true;
}

// ── Arranque ────────────────────────────────────────────────

function spawnServer(cmd, cmdArgs, env) {
  const child = spawn(cmd, cmdArgs, {
    cwd: ROOT,
    stdio: "inherit",
    env,
    shell: IS_WIN,
  });

  child.on("error", (err) => {
    fail(`no se pudo arrancar el servidor: ${err.message}`);
    process.exit(1);
  });

  child.on("exit", (code) => {
    process.exit(code ?? 0);
  });
}

function startServer() {
  const env = { ...process.env, HOST, PORT };

  if (PROD) {
    if (!GUNICORN_BIN || !fs.existsSync(GUNICORN_BIN)) {
      fail("gunicorn no está disponible (solo Linux/macOS). Usa: node dev.js");
      process.exit(1);
    }
    log(`arrancando gunicorn en http://${HOST}:${PORT}`);
    spawnServer(GUNICORN_BIN, ["-b", `${HOST}:${PORT}`, "main:app"], env);
    return;
  }

  env.DEBUG = "true";
  log(`arrancando Flask (dev) en http://${HOST}:${PORT}`);
  spawnServer(PYTHON_BIN, ["main.py"], env);
}

// ── Main ────────────────────────────────────────────────────

function main() {
  if (HELP) {
    console.log(
      "linear-regression Backend launcher\n" +
        "  node dev.js            → crea venv si falta, instala deps (1ª vez) y arranca (dev)\n" +
        "  node dev.js --prod     → arranca con gunicorn (solo Linux/macOS)\n" +
        "  node dev.js --install  → reinstala requirements.txt\n" +
        "  node dev.js --port 6000→ cambia el puerto (default 5000)\n" +
        "  node dev.js --host 127.0.0.1 → cambia el host (default 0.0.0.0)\n",
    );
    return;
  }

  if (!ensureVenv()) {
    process.exit(1);
  }

  startServer();
}

main();
