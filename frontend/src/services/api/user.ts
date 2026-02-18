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
}) {
  const payload: AddUserInput = { username, password, email, role };
  return api.post<UserSchema>("/users", payload);
}

async function createInviteLink({ role }: { role: string }) {
  return api.post<InviteLinkSchema>(
    "/users/invite-link",
    {},
    { params: { role } },
  );
}

async function registerUser(
  username: string,
  email: string,
  password: string,
  token: string,
) {
  const payload: RegisterUserInput = { username, email, password, token };
  return api.post<UserSchema>("/users/register", payload);
}

async function fetchUsers() {
  return api.get<UserSchema[]>("/users");
}

async function fetchUser(user: Pick<UserSchema, "id">) {
  return api.get<UserSchema>(`/users/${user.id}`);
}

async function fetchCurrentUser() {
  return api.get<UserSchema | null>("/users/me");
}

async function updateUser({
  id,
  avatar,
  ...attrs
}: Partial<UserSchema> & {
  avatar?: File;
  password?: string;
}) {
  const uiSettings =
    typeof attrs.ui_settings === "string"
      ? attrs.ui_settings
      : attrs.ui_settings
        ? JSON.stringify(attrs.ui_settings)
        : attrs.ui_settings;

  return api.put<UserSchema>(
    `/users/${id}`,
    {
      avatar: avatar || null,
      username: attrs.username,
      password: attrs.password,
      email: attrs.email,
      enabled: attrs.enabled,
      role: attrs.role,
      ra_username: attrs.ra_username,
      ui_settings: uiSettings,
    },
    {
      headers: {
        "Content-Type": avatar
          ? "multipart/form-data"
          : "application/x-www-form-urlencoded",
      },
    },
  );
}

async function deleteUser(user: UserSchema) {
  return api.delete(`/users/${user.id}`);
}

async function refreshRetroAchievements({
  id,
  incremental = false,
}: {
  id: number;
  incremental?: boolean;
}) {
  const payload: RefreshRetroAchievementsInput = { incremental };
  return api.post<void>(`/users/${id}/ra/refresh`, payload);
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
