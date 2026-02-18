import type {
  Body_request_password_reset_api_forgot_password_post as RequestPasswordResetInput,
  Body_reset_password_api_reset_password_post as ResetPasswordInput,
} from "@/__generated__";
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
  const payload: RequestPasswordResetInput = {
    username,
  };
  return api.post("/forgot-password", payload);
}

async function resetPassword(token: string, newPassword: string) {
  const payload: ResetPasswordInput = {
    token,
    new_password: newPassword,
  };
  return api.post("/reset-password", payload);
}

export default {
  login,
  logout,
  requestPasswordReset,
  resetPassword,
};
