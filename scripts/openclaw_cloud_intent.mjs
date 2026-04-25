import path from "node:path";
import process from "node:process";
import { randomUUID } from "node:crypto";
import { t as GatewayClient } from "../openclaw/dist/client-CmNBUjg-.js";
import { n as loadOrCreateDeviceIdentity } from "../openclaw/dist/device-identity-BgBPx0OC.js";

const WORKSPACE_ROOT = "E:\\aNB\\Ease-claw";
const STATE_DIR = process.env.OPENCLAW_CLOUD_STATE_DIR || path.join(WORKSPACE_ROOT, ".openclaw-cloud");
const IDENTITY_PATH = path.join(STATE_DIR, "identity", "device.json");
const GATEWAY_URL = process.env.OPENCLAW_CLOUD_URL || "ws://127.0.0.1:31879";
const SESSION_PREFIX = process.env.OPENCLAW_CLOUD_SESSION_PREFIX || "clawease-intent";
const MESSAGE = process.argv.slice(2).join(" ").trim();

if (!MESSAGE) {
  console.error("usage: node scripts/openclaw_cloud_intent.mjs <message>");
  process.exit(2);
}

const identity = loadOrCreateDeviceIdentity(IDENTITY_PATH);
const idempotencyKey = `clawease-${randomUUID()}`;
const sessionKey = `${SESSION_PREFIX}-${randomUUID()}`;
let settled = false;
let textBuffer = "";

function extractText(payload) {
  const message = payload?.message;
  const parts = Array.isArray(message?.content) ? message.content : [];
  return parts
    .filter((part) => part?.type === "text" && typeof part.text === "string")
    .map((part) => part.text)
    .join("")
    .trim();
}

const client = new GatewayClient({
  url: GATEWAY_URL,
  role: "operator",
  scopes: ["operator.read", "operator.write", "operator.talk.secrets", "operator.approvals"],
  clientName: "cli",
  clientDisplayName: "clawease-bootstrap-operator",
  mode: "cli",
  platform: "windows",
  deviceFamily: "desktop",
  deviceIdentity: identity,
  requestTimeoutMs: 10000,
  onHelloOk: async () => {
    try {
      await client.request(
        "chat.send",
        {
          sessionKey,
          message: MESSAGE,
          idempotencyKey,
        },
        { timeoutMs: null },
      );
    } catch (err) {
      console.error(String(err));
      await client.stopAndWait({ timeoutMs: 2000 }).catch(() => {});
      process.exit(1);
    }
  },
  onEvent: async (evt) => {
    if (evt?.event !== "chat") {
      return;
    }
    const payload = evt.payload || {};
    if (payload.runId !== idempotencyKey) {
      return;
    }
    const chunk = extractText(payload);
    if (chunk) {
      textBuffer += chunk;
    }
    if (payload.state === "final") {
      settled = true;
      const text = (extractText(payload) || textBuffer).trim();
      if (!text) {
        console.error(JSON.stringify(payload));
        process.exitCode = 1;
      } else {
        process.stdout.write(text);
      }
      await client.stopAndWait({ timeoutMs: 2000 }).catch(() => {});
      process.exit(process.exitCode ?? 0);
    }
    if (payload.state === "error") {
      settled = true;
      console.error(payload.errorMessage || JSON.stringify(payload));
      await client.stopAndWait({ timeoutMs: 2000 }).catch(() => {});
      process.exit(1);
    }
  },
  onConnectError: (err) => {
    console.error(String(err));
  },
});

client.start();
setTimeout(async () => {
  if (!settled) {
    console.error("cloud openclaw timeout");
  }
  await client.stopAndWait({ timeoutMs: 2000 }).catch(() => {});
  process.exit(2);
}, 45000);
