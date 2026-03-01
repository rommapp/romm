import type { AxiosResponse } from "axios";
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
  return api.post("/logout", {});
}

async function requestPasswordReset(username: string) {
  return api.post<void, AxiosResponse<void>, RequestPasswordResetInput>(
    "/forgot-password",
    { username },
  );
}

async function resetPassword(token: string, newPassword: string) {
  return api.post<void, AxiosResponse<void>, ResetPasswordInput>(
    "/reset-password",
    {
      token,
      new_password: newPassword,
    },
  );
}

export default {
  login,
  logout,
  requestPasswordReset,
  resetPassword,
};
