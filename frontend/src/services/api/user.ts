import type {
  Body_add_user_api_users_post as AddUserInput,
  Body_create_user_from_invite_api_users_register_post as RegisterUserInput,
  Body_refresh_retro_achievements_api_users__id__ra_refresh_post as RefreshRetroAchievementsInput,
  InviteLinkSchema,
  UserForm,
  UserSchema,
} from "@/__generated__";
import api from "@/services/api";

export const userApi = api;

async function createUser({
  username,
  password,
  email,
  role,
}: {
  username: string;
  password: string;
  email: string;
  role: string;
}): Promise<{ data: UserSchema }> {
  const payload: AddUserInput = {
    username,
    password,
    email,
    role,
  };
  return api.post("/users", payload);
}

async function createInviteLink({
  role,
}: {
  role: string;
}): Promise<{ data: InviteLinkSchema }> {
  return api.post("/users/invite-link", {}, { params: { role } });
}

async function registerUser(
  username: string,
  email: string,
  password: string,
  token: string,
): Promise<{ data: UserSchema }> {
  const payload: RegisterUserInput = {
    username,
    email,
    password,
    token,
  };
  return api.post("/users/register", payload);
}

async function fetchUsers(): Promise<{ data: UserSchema[] }> {
  return api.get("/users");
}

async function fetchUser(
  user: Pick<UserSchema, "id">,
): Promise<{ data: UserSchema }> {
  return api.get(`/users/${user.id}`);
}

async function fetchCurrentUser(): Promise<{ data: UserSchema | null }> {
  return api.get("/users/me");
}

async function updateUser({
  id,
  avatar,
  ...attrs
}: Partial<UserSchema> & {
  avatar?: File;
  password?: string;
}): Promise<{ data: UserSchema }> {
  const uiSettings =
    typeof attrs.ui_settings === "string"
      ? attrs.ui_settings
      : attrs.ui_settings
        ? JSON.stringify(attrs.ui_settings)
        : attrs.ui_settings;

  const payload: UserForm = {
    avatar: avatar || null,
    username: attrs.username,
    password: attrs.password,
    email: attrs.email,
    enabled: attrs.enabled,
    role: attrs.role,
    ra_username: attrs.ra_username,
    ui_settings: uiSettings,
  };
  return api.put(`/users/${id}`, payload, {
    headers: {
      "Content-Type": avatar
        ? "multipart/form-data"
        : "application/x-www-form-urlencoded",
    },
  });
}

async function deleteUser(user: Pick<UserSchema, "id">) {
  return api.delete(`/users/${user.id}`);
}

async function refreshRetroAchievements({
  id,
  incremental = false,
}: {
  id: number;
  incremental?: boolean;
}) {
  const payload: RefreshRetroAchievementsInput = {
    incremental,
  };
  return api.post(`/users/${id}/ra/refresh`, payload);
}

export default {
  createUser,
  createInviteLink,
  registerUser,
  fetchUsers,
  fetchUser,
  fetchCurrentUser,
  updateUser,
  deleteUser,
  refreshRetroAchievements,
};
