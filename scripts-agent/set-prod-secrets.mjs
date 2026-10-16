#!/usr/bin/env node
/**
 * Rellena los secretos de DESPLIEGUE que el proyecto puede generar solo, en
 * `docker/.env` de Astaroth:
 *
 *   - ADMIN_KEY → aleatorio de 64 hex si está vacío/placeholder o es débil.
 *                 Protege /admin/*, /fit*, /assign*… (header X-Admin-Key).
 *
 * ⚠️ ADMIN_KEY es COMPARTIDA con el CRM: su backend la envía como
 *    CLUSTERING_API_KEY en las llamadas a clustering-api. Si la regeneras,
 *    copia el mismo valor al `CLUSTERING_API_KEY` del CRM (docker/.env) y
 *    reinicia ambos contenedores.
 *
 * Uso (desde la raíz del repo):
 *   node scripts-agent/set-prod-secrets.mjs
 *
 * Es idempotente: si ya hay un valor válido, lo conserva.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const ENV_PATH = path.resolve("docker/.env");
if (!fs.existsSync(ENV_PATH)) {
  console.error(`✘ No existe ${ENV_PATH} — créalo antes:  cp docker/.env.example docker/.env`);
  process.exit(1);
}

let txt = fs.readFileSync(ENV_PATH, "utf8");

const PLACEHOLDER =
  /^(|change-?me|cambia(-esto)?|tu[_-]|your[_-]|example|placeholder|xxx+|secreto?|secret|test|demo|admin|password|<.*>)$/i;
const cur = (k) => (txt.match(new RegExp(`^${k}=(.*)$`, "m")) || [])[1]?.trim() ?? "";
const isWeak = (v) => PLACEHOLDER.test(v) || (v.length > 0 && v.length < 32);

const now = cur("ADMIN_KEY");
let generated = "";
if (isWeak(now)) {
  generated = crypto.randomBytes(32).toString("hex");
  const re = /^ADMIN_KEY=.*$/m;
  txt = re.test(txt) ? txt.replace(re, `ADMIN_KEY=${generated}`) : txt.trimEnd() + `\nADMIN_KEY=${generated}\n`;
} else {
  generated = now;
}

fs.writeFileSync(ENV_PATH, txt);

console.log(`✔ docker/.env actualizado:`);
console.log(
  isWeak(now)
    ? `  ADMIN_KEY       : generado`
    : `  ADMIN_KEY       : se conserva el existente (${now.length} chars)`,
);
console.log(`\n  🔑 ADMIN_KEY (X-Admin-Key, compartida con el CRM):`);
console.log(`       ${generated}`);
console.log(
  `     Copia EXACTAMENTE este valor al CLUSTERING_API_KEY del CRM (crm/docker/.env)\n` +
    `     si difieren, y reinicia los dos contenedores.`,
);
