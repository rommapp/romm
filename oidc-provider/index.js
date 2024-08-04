import { config } from "dotenv";
import { resolve } from "path";
import { Provider } from "oidc-provider";
import express from "express";

import SQLiteAdapter from "./sqlite_adapter.js";

config({ path: resolve("../.env") });

const DEFAULT_SCOPES_MAP = {
  "me.read": "View your profile",
  "me.write": "Modify your profile",
  "roms.read": "View ROMs",
  "platforms.read": "View platforms",
  "assets.read": "View assets",
  "assets.write": "Modify assets",
  "firmware.read": "View firmware",
  "roms.user.read": "View user-rom properties",
  "roms.user.write": "Modify user-rom properties",
  "collections.read": "View collections",
  "collections.write": "Modify collections",
};

const WRITE_SCOPES_MAP = {
  "roms.write": "Modify ROMs",
  "platforms.write": "Modify platforms",
  "firmware.write": "Modify firmware",
};

const FULL_SCOPES_MAP = {
  "users.read": "View users",
  "users.write": "Modify users",
  "tasks.run": "Run tasks",
};

const ALL_SCOPES = [
  "openid",
  "profile",
  "email",
  ...Object.keys(DEFAULT_SCOPES_MAP),
  ...Object.keys(WRITE_SCOPES_MAP),
  ...Object.keys(FULL_SCOPES_MAP),
];

const app = express();
const clients = [
  {
    client_id: process.env.OAUTH_CLIENT_ID,
    client_secret: process.env.OAUTH_CLIENT_SECRET,
    grant_types: ["authorization_code"],
    redirect_uris: [process.env.OAUTH_REDIRECT_URI],
    response_types: ["code"],
    scope: ALL_SCOPES.join(" "),
  },
];

const oidc = new Provider("http://localhost:4000", {
  clients,
  features: {
    introspection: { enabled: true },
    revocation: { enabled: true },
    devInteractions: { enabled: true },
  },
  pkce: { methods: ["S256"], required: () => false },
  formats: {
    AccessToken: "jwt",
  },
  jwks: {
    keys: [
      {
        kty: "RSA",
        kid: "test-key",
        use: "sig",
        e: "AQAB",
        n: "test-key-n",
        d: "test-key-d",
        p: "test-key-p",
        q: "test-key-q",
        dp: "test-key-dp",
        dq: "test-key-dq",
        qi: "test-key-qi",
      },
    ],
  },
  cookies: {
    keys: [process.env.SIGNING_COOKIE_A, process.env.SIGNING_COOKIE_B],
  },
  scopes: ALL_SCOPES,
  adapter: SQLiteAdapter,
});

app.use("/oidc", oidc.callback());

app.listen(4000, () => {
  console.log("OIDC provider listening on http://localhost:4000");
});
