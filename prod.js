#!/usr/bin/env node
/**
 * prod.js — despliegue de PRODUCCIÓN de Astaroth (contenedor único en docker/).
 *
 * `node prod.js` sincroniza `docker/.env` desde `prod.config.json` (dominio,
 * TLS, puertos y variante de imagen — sin pisar secretos), valida que
 * ADMIN_KEY esté definida y construye/levanta el contenedor.
 *
 * Uso:
 *   node prod.js --init-config   → crea prod.config.json (plantilla)
 *   node prod.js --dns           → imprime los registros DNS/red a configurar
 *   node prod.js                 → sincroniza, construye y levanta
 *   node prod.js --no-build      → levanta sin reconstruir la imagen
 *   node prod.js --stop          → detiene el contenedor (down)
 *   node prod.js --logs          → logs en vivo
 *   node prod.js --status        → estado del contenedor
 *   node prod.js --config <ruta> → usa otro prod.config.json
 *   node prod.js --help
 */
const cp = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = __dirname;
const DOCKER_DIR = path.join(ROOT, "docker");
const COMPOSE_FILE = path.join(DOCKER_DIR, "docker-compose.yml");
const ENV_FILE = path.join(DOCKER_DIR, ".env");
const ENV_EXAMPLE = path.join(DOCKER_DIR, ".env.example");

const ARGS = process.argv.slice(2);
const has = (f) => ARGS.includes(f);
const CONFIG_IDX = ARGS.indexOf("--config");
const CONFIG_PATH =
  CONFIG_IDX >= 0 && ARGS[CONFIG_IDX + 1]
    ? path.resolve(ROOT, ARGS[CONFIG_IDX + 1])
    : path.join(ROOT, "prod.config.json");

const C = {
  ok: "\x1b[32m",
  err: "\x1b[31m",
  warn: "\x1b[33m",
  cyan: "\x1b[36m",
  dim: "\x1b[2m",
  reset: "\x1b[0m",
};
const rel = (p) => path.relative(ROOT, p) || ".";
const die = (msg) => {
  console.error(`\n${C.err}✘ ${msg}${C.reset}\n`);
  process.exit(1);
};

// ── Configuración ───────────────────────────────────────────
const CONFIG_TEMPLATE = {
  mode: "edge",
  baseDomain: "tudominio.com",
  publicIp: "<IP_PUBLICA_DEL_SERVIDOR>",
  dnsZone: "tudominio.com",
  acmeEmail: "admin@tudominio.com",
  tls: true,
  hosts: { ml: "ml.tudominio.com" },
  withPyTorch: false,
  publicHttpPort: 80,
  publicHttpsPort: 443,
  edgePorts: { http: "127.0.0.1:30380", https: "127.0.0.1:30381" },
};

function loadConfig() {
  if (!fs.existsSync(CONFIG_PATH)) {
    die(
      `No existe ${rel(CONFIG_PATH)}. Créalo con:  node prod.js --init-config\n` +
        `  (el del repositorio ya viene configurado para este servidor).`,
    );
  }
  let cfg;
  try {
    cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
  } catch (e) {
    die(`${rel(CONFIG_PATH)} no es JSON válido: ${e.message}`);
  }
  cfg.mode = cfg.mode === "direct" ? "direct" : "edge";
  cfg.hosts = cfg.hosts ?? {};
  cfg.edgePorts = cfg.edgePorts ?? CONFIG_TEMPLATE.edgePorts;
  if (!cfg.hosts.ml) die(`Falta "hosts.ml" en ${rel(CONFIG_PATH)}.`);
  if (!cfg.acmeEmail) die(`Falta "acmeEmail" en ${rel(CONFIG_PATH)}.`);
  return cfg;
}

const schemeOf = (cfg) => (cfg.tls ? "https" : "http");
const edgeMode = (cfg) => cfg.mode !== "direct";

// ── docker/.env ─────────────────────────────────────────────
/** Actualiza/agrega pares KEY=valor conservando el resto del archivo. */
function setEnvKeys(text, pairs) {
  let out = text;
  const added = [];
  for (const [key, value] of Object.entries(pairs)) {
    const re = new RegExp(`^${key}=.*$`, "m");
    if (re.test(out)) {
      out = out.replace(re, `${key}=${value}`);
    } else if (new RegExp(`^#\\s*${key}=`, "m").test(out)) {
      // clave comentada: se descomenta con el valor nuevo.
      out = out.replace(new RegExp(`^#\\s*${key}=.*$`, "m"), `${key}=${value}`);
    } else {
      added.push(`${key}=${value}`);
    }
  }
  if (added.length) {
    if (!out.endsWith("\n")) out += "\n";
    out += `\n# ── Sincronizado por prod.js desde prod.config.json ──\n${added.join("\n")}\n`;
  }
  return out;
}

function envValue(text, key) {
  const m = text.match(new RegExp(`^\\s*${key}=(.*)$`, "m"));
  return m ? m[1].trim() : "";
}

function syncEnvFile(cfg) {
  if (!fs.existsSync(ENV_FILE)) {
    if (!fs.existsSync(ENV_EXAMPLE)) die(`Falta ${rel(ENV_EXAMPLE)} (no puedo crear docker/.env).`);
    fs.copyFileSync(ENV_EXAMPLE, ENV_FILE);
    console.log(`✅ Creado ${rel(ENV_FILE)} a partir del ejemplo.`);
  }
  const text = fs.readFileSync(ENV_FILE, "utf8");

  const edge = edgeMode(cfg);
  const containerTls = !edge && cfg.tls !== false;
  const pairs = {
    HOST_ML: cfg.hosts.ml,
    ACME_EMAIL: cfg.acmeEmail,
    // Modo edge: el TLS lo termina el edge compartido; el contenedor sirve
    // HTTP en loopback (por eso ALLOW_INSECURE=true, aceptado explícitamente).
    TLS: containerTls ? "true" : "false",
    ALLOW_INSECURE: containerTls ? "false" : "true",
    PUBLIC_HTTP_PORT: edge ? cfg.edgePorts.http : String(cfg.publicHttpPort),
    PUBLIC_HTTPS_PORT: edge ? cfg.edgePorts.https : String(cfg.publicHttpsPort),
    BUILD_TARGET: cfg.withPyTorch ? "full" : "lite",
    ASTROTH_FULL: cfg.withPyTorch ? "1" : "0",
  };

  fs.writeFileSync(ENV_FILE, setEnvKeys(text, pairs));
  try {
    fs.chmodSync(ENV_FILE, 0o600);
  } catch {
    /* Windows */
  }
  console.log(`✅ ${rel(ENV_FILE)} sincronizado (dominio, TLS, puertos y variante).`);

  // Fail-closed del contenedor: avisamos aquí, no en los logs de Docker.
  const adminKey = envValue(fs.readFileSync(ENV_FILE, "utf8"), "ADMIN_KEY");
  if (!adminKey || adminKey === "change-me") {
    console.error(`\n${C.err}✘ docker/.env sin ADMIN_KEY (el contenedor NO arrancaría):${C.reset}`);
    console.error(`   • Generala con:  node scripts-agent/set-prod-secrets.mjs`);
    console.error(`   • Debe ser IDÉNTICA al CLUSTERING_API_KEY del CRM.`);
    process.exit(1);
  }
}

// ── DNS / red ───────────────────────────────────────────────
function printDns(cfg) {
  const edge = edgeMode(cfg);
  const ip = cfg.publicIp || "<IP_PUBLICA_DEL_SERVIDOR>";
  const W = 66;
  const bar = "━".repeat(W);
  const line = (s = "") => console.log(`  ${s}`);
  const name = cfg.hosts.ml;
  const zone = name.split(".").slice(1).join(".");

  console.log(`\n${bar}`);
  console.log(`  DNS y red a configurar (Astaroth)`);
  console.log(bar);
  line(`Dominio   : ${name}`);
  line(`IP pública: ${ip}`);
  line(`Modo      : ${edge ? "edge (el edge compartido publica 80/443 y hace TLS)" : "directo (este contenedor publica 80/443 y hace TLS)"}`);
  console.log(bar);

  if (edge) {
    line(`${C.cyan}1) DNS (GoDaddy → zona ${cfg.dnsZone}) — SOLO si expones el API ML:${C.reset}`);
    line(`   Tipo: A   TTL: 600   Valor: ${ip}`);
    line(`   ─────────────────────────────────────────────`);
    line(`   Nombre: ${name.slice(0, -(zone.length + 1))}   →   ${name}`);
    line();
    line(`${C.dim}   El CRM NO necesita este registro: consume Astaroth por la red`);
    line(`   interna del servidor (mercaldas_astaroth_app:8080).${C.reset}`);
  } else {
    line(`${C.cyan}1) DNS (GoDaddy → zona ${cfg.dnsZone}) — obligatorio:${C.reset}`);
    line(`   Tipo: A   TTL: 600   Valor: ${ip}`);
    line(`   ─────────────────────────────────────────────`);
    line(`   Nombre: ${name.slice(0, -(zone.length + 1))}   →   ${name}`);
    line();
    line(`${C.dim}   Let's Encrypt valida por HTTP-01 en el puerto 80: el certificado`);
    line(`   no se emitirá hasta que el DNS apunte aquí (Caddy reintenta solo).${C.reset}`);
  }

  console.log(bar);
  line(`${C.cyan}2) Firewall:${C.reset}`);
  if (edge) {
    line(`   Abre SOLO 80 y 443 (los publica el edge en ecommerce/docker/edge/).`);
    line(`   Astaroth publica ${cfg.edgePorts.http}/${cfg.edgePorts.https} en loopback: no abras nada más.`);
  } else {
    line(`   Abre SOLO TCP 80 y 443 en el proveedor del VPS y en Windows.`);
    line(`   Comprueba que IIS/HTTP.sys no los estén ocupando.`);
  }

  console.log(bar);
  line(`${C.cyan}3) Para EXPONERLO públicamente (opcional):${C.reset}`);
  if (edge) {
    line(`   • Descomenta el bloque \`${name}\` en:`);
    line(`     ecommerce/docker/edge/Caddyfile`);
    line(`   • cd ecommerce/docker/edge && docker compose up -d`);
  } else {
    line(`   Ya queda expuesto por este contenedor (TLS incluido).`);
  }
  line(`${C.warn}   ⚠️  Superficie sensible: revisa docs/SECURITY.md antes de exponer.${C.reset}`);

  console.log(bar);
  line(`${C.cyan}4) Base analytics (opcional; /fit-from-db y /assign-from-db):${C.reset}`);
  line(`   docker network connect crm_internal mercaldas_astaroth_app`);
  line(`${C.dim}   (requiere el CRM levantado; sin esto, el resto funciona igual)${C.reset}`);

  console.log(bar);
  line(`${C.cyan}5) Consumo interno (ya configurado en el CRM):${C.reset}`);
  line(`   CLUSTERING_API_URL=http://mercaldas_astaroth_app:8080/clustering`);
  line(`   XGBOOST_API_URL   =http://mercaldas_astaroth_app:8080/xgboost`);
  line(`   UPLIFT_API_URL    =http://mercaldas_astaroth_app:8080/uplift`);
  console.log(`${bar}\n`);
}

// ── docker ──────────────────────────────────────────────────
function compose(args, opts = {}) {
  return cp.spawnSync(
    "docker",
    ["compose", "-f", COMPOSE_FILE, ...args],
    { cwd: ROOT, stdio: "inherit", windowsHide: true, ...opts },
  );
}

function checkDocker() {
  const r = cp.spawnSync("docker", ["--version"], { stdio: "ignore", windowsHide: true });
  if (r.status !== 0) die(`Docker no está disponible en el PATH (¿Docker Desktop / WSL2 arrancado?).`);
}

function printHelp() {
  console.log(`
Astaroth — despliegue de producción (contenedor único)

  node prod.js                 sincroniza docker/.env, construye y levanta
  node prod.js --no-build      levanta sin reconstruir la imagen
  node prod.js --dns           imprime los registros DNS/red a configurar
  node prod.js --status        estado del contenedor
  node prod.js --logs          logs en vivo
  node prod.js --stop          detiene el contenedor
  node prod.js --init-config   crea prod.config.json (plantilla)
  node prod.js --config <ruta> usa otro prod.config.json
  node prod.js --help

Dominio/TLS/puertos/variante : prod.config.json (mode: edge|direct)
Secretos (ADMIN_KEY)         : docker/.env  → node scripts-agent/set-prod-secrets.mjs
`);
}

function main() {
  if (has("--help")) return printHelp();

  if (has("--init-config")) {
    if (fs.existsSync(CONFIG_PATH)) die(`Ya existe ${rel(CONFIG_PATH)}.`);
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(CONFIG_TEMPLATE, null, 2) + "\n");
    console.log(`✅ Creado ${rel(CONFIG_PATH)} — edita dominios/IP y ejecuta:  node prod.js --dns`);
    return;
  }

  const cfg = loadConfig();

  if (has("--dns")) return printDns(cfg);

  checkDocker();

  if (has("--stop")) return run(compose(["down"]), "down");
  if (has("--logs")) return run(compose(["logs", "-f", "app"]), "logs");
  if (has("--status")) return run(compose(["ps"]), "ps");

  // Despliegue completo.
  syncEnvFile(cfg);

  if (!has("--no-build")) {
    console.log(`\n==> construyendo imagen (target=${cfg.withPyTorch ? "full" : "lite"})…`);
    const b = compose(["build"]);
    if (b.status !== 0) die(`Falló la construcción de la imagen.`);
  }

  console.log(`\n==> levantando contenedor…`);
  const u = compose(["up", "-d"]);
  if (u.status !== 0) die(`Falló docker compose up.`);

  compose(["ps"]);
  const donde = edgeMode(cfg)
    ? `${cfg.edgePorts.http}/${cfg.edgePorts.https} en loopback (lo alcanza el edge por shared_edge)`
    : `${cfg.publicHttpPort}/${cfg.publicHttpsPort} público (TLS propio para ${cfg.hosts.ml})`;
  console.log(`
${C.ok}✅ Astaroth desplegado.${C.reset}

  • Publicado en : ${donde}
  • Logs        : node prod.js --logs
  • DNS/red     : node prod.js --dns
  • Recuerda    : ADMIN_KEY debe coincidir con el CLUSTERING_API_KEY del CRM.

${C.warn}Si es la primera vez, ejecuta también:  node prod.js --dns${C.reset}
`);
}

function run(res, what) {
  if (res.status !== 0) die(`Falló docker compose ${what}.`);
}

main();
