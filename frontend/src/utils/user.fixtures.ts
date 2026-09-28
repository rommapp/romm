import type { UserSchema } from "@/__generated__";

const WRITTEN_AT = "2026-09-16T12:00:00Z";

export function userFixture(overrides: Partial<UserSchema> = {}): UserSchema {
  return {
    id: 1,
    username: "admin",
    email: null,
    enabled: true,
    role: "admin",
    oauth_scopes: [],
    avatar_path: "",
    last_login: null,
    last_active: null,
    created_at: WRITTEN_AT,
    updated_at: WRITTEN_AT,
    ...overrides,
  };
}
