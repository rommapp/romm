import type { MessageResponse } from "@/__generated__";
import api from "@/services/api/index";

export const identityApi = api;

async function login(
  username: string,
  password: string,
): Promise<{ data: MessageResponse }> {
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

async function logout(): Promise<{ data: MessageResponse }> {
  return api.post("/logout");
}

export default {
  login,
  logout,
};
