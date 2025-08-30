import api from "@/services/api";

export const identityApi = api;

async function login(username: string, password: string) {
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

async function logout() {
  return api.post("/logout");
}

async function requestPasswordReset(username: string) {
  return api.post("/forgot-password", { username });
}

async function resetPassword(token: string, newPassword: string) {
  return api.post("/reset-password", { token, new_password: newPassword });
}

export default {
  login,
  logout,
  requestPasswordReset,
  resetPassword,
};
