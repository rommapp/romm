import type { MessageResponse, UserSchema } from "@/__generated__";
import api from "@/services/api/index";
import type { User } from "@/stores/users";

export const userApi = api;

async function createUser({
  username,
  password,
  role,
}: {
  username: string;
  password: string;
  role: string;
}): Promise<{ data: UserSchema }> {
  return api.post("/users", {}, { params: { username, password, role } });
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
}: {
  id: number;
  avatar?: File[];
}): Promise<{ data: UserSchema }> {
  return api.put(
    `/users/${id}`,
    {
      avatar: avatar ? avatar[0] : null,
    },
    {
      headers: {
        "Content-Type": avatar ? "multipart/form-data" : "application/json",
      },
      params: attrs,
    }
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
