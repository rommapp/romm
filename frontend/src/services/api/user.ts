import type { MessageResponse, UserSchema } from "@/__generated__";
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
}: UserSchema & {
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
      },
    },
  );
}

async function deleteUser(user: User): Promise<{ data: MessageResponse }> {
  return api.delete(`/users/${user.id}`);
}

export default {
  createUser,
  fetchUsers,
  fetchUser,
  fetchCurrentUser,
  updateUser,
  deleteUser,
};
