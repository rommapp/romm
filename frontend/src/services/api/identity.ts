import type { AuthenticationResponse } from "@/__generated__";
import api from "@/services/api/index";

export const identityApi = api;

async function login(
  username: string,
  password: string,
): Promise<{ data: AuthenticationResponse }> {
  return api.post(
    "/login",
    {},
    {
      auth: {
        username: username,
        password: password,
      },
    },
  );
}

async function logout(): Promise<{ data: AuthenticationResponse }> {
  return api.post("/logout");
}

async function requestPasswordReset(username: string): Promise<{ data: null }> {
  return api.post("/forgot-password", { username });
}

async function resetPassword(
  token: string,
  newPassword: string,
): Promise<{ data: null }> {
  return api.post("/reset-password", { token, new_password: newPassword });
}

export default {
  login,
  logout,
  requestPasswordReset,
  resetPassword,
};
