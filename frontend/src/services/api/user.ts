import type {
  MessageResponse,
  UserSchema,
  InviteLinkSchema,
} from "@/__generated__";
import api from "@/services/api/index";
import type { User } from "@/stores/users";

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
  return api.post(
    "/users",
    {},
    { params: { username, password, email, role } },
  );
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
): Promise<{ data: MessageResponse }> {
  return api.post("/users/register", { username, email, password, token });
}

async function fetchUsers(): Promise<{ data: UserSchema[] }> {
  return api.get("/users");
}

async function fetchUser(user: User): Promise<{ data: UserSchema }> {
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
  return api.put(
    `/users/${id}`,
    {
      avatar: avatar || null,
    },
    {
      headers: {
        "Content-Type": avatar ? "multipart/form-data" : "application/json",
      },
      params: {
        username: attrs.username,
        password: attrs.password,
        email: attrs.email,
        enabled: attrs.enabled,
        role: attrs.role,
        ra_username: attrs.ra_username,
      },
    },
  );
}

async function deleteUser(user: User): Promise<{ data: MessageResponse }> {
  return api.delete(`/users/${user.id}`);
}

async function refreshRetroAchievements({
  id,
}: {
  id: number;
}): Promise<{ data: MessageResponse }> {
  return api.post(`/users/${id}/ra/refresh`);
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
