import { ref } from "vue";
import api from "@/services/api";
import type {
  AchievementGameSchema as AchievementGame,
  AchievementTypeCountsSchema as AchievementTypeCounts,
  Body_add_user_api_users_post as AddUserInput,
  Body_create_user_from_invite_api_users_register_post as RegisterUserInput,
  Body_refresh_retro_achievements_api_users__id__ra_refresh_post as RefreshRetroAchievementsInput,
  CatalogAchievementSchema as CatalogAchievement,
  EarnedAchievementsSchema as EarnedAchievementsResponse,
  InviteLinkSchema,
  UserSchema,
} from "@/__generated__";

export type {
  AchievementGame,
  AchievementTypeCounts,
  CatalogAchievement,
  EarnedAchievementsResponse,
};

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

async function createInviteLink({
  role,
  expiration,
}: {
  role: string;
  expiration?: number;
}) {
  const params: Record<string, string | number> = { role };
  if (expiration !== undefined) {
    params.expiration = expiration;
  }
  return api.post<InviteLinkSchema>("/users/invite-link", {}, { params });
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
  current_password?: string | undefined;
}) {
  return api.put<UserSchema>(
    `/users/${id}`,
    {
      avatar: avatar || null,
      username: attrs.username,
      password: attrs.password,
      current_password: attrs.current_password,
      email: attrs.email,
      enabled: attrs.enabled,
      role: attrs.role,
      ra_username: attrs.ra_username,
      ui_settings: attrs.ui_settings,
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

async function fetchEarnedAchievements() {
  return api.get<EarnedAchievementsResponse>("/users/me/earned-achievements");
}

const earnedAchievementsLoading = ref(true);
const earnedAchievementsRefreshing = ref(false);
const earnedAchievementsFailed = ref(false);
const earnedAchievementsPayload = ref<EarnedAchievementsResponse | null>(null);
let earnedAchievementsFetchedAt = 0;
let earnedAchievementsInFlight: Promise<void> | null = null;
let earnedAchievementsGeneration = 0;

export function resetEarnedAchievements(): void {
  earnedAchievementsGeneration += 1;
  earnedAchievementsLoading.value = false;
  earnedAchievementsRefreshing.value = false;
  earnedAchievementsFailed.value = false;
  earnedAchievementsPayload.value = null;
  earnedAchievementsFetchedAt = 0;
  earnedAchievementsInFlight = null;
}

export function useEarnedAchievementsState() {
  return {
    loading: earnedAchievementsLoading,
    refreshing: earnedAchievementsRefreshing,
    failed: earnedAchievementsFailed,
    payload: earnedAchievementsPayload,
    load: loadEarnedAchievements,
  };
}

export async function loadEarnedAchievements(silent = false): Promise<void> {
  const generation = earnedAchievementsGeneration;
  if (earnedAchievementsInFlight) return earnedAchievementsInFlight;
  if (silent && Date.now() - earnedAchievementsFetchedAt < 1500) return;
  const keepContent = silent && earnedAchievementsPayload.value !== null;
  earnedAchievementsRefreshing.value = true;
  earnedAchievementsFetchedAt = Date.now();
  if (!keepContent) {
    earnedAchievementsLoading.value = true;
    earnedAchievementsFailed.value = false;
  }
  earnedAchievementsInFlight = (async () => {
    try {
      const { data } = await fetchEarnedAchievements();
      if (generation !== earnedAchievementsGeneration) return;
      earnedAchievementsPayload.value = data;
      earnedAchievementsFailed.value = false;
    } catch {
      if (generation !== earnedAchievementsGeneration) return;
      if (!keepContent || earnedAchievementsPayload.value == null) {
        earnedAchievementsFailed.value = true;
        earnedAchievementsPayload.value = null;
      }
    } finally {
      if (generation !== earnedAchievementsGeneration) return;
      earnedAchievementsLoading.value = false;
      earnedAchievementsRefreshing.value = false;
      earnedAchievementsInFlight = null;
    }
  })();
  return earnedAchievementsInFlight;
}

export async function prefetchEarnedAchievements(): Promise<void> {
  if (earnedAchievementsPayload.value !== null) {
    void loadEarnedAchievements(true);
    return;
  }
  await loadEarnedAchievements(false);
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
  fetchEarnedAchievements,
  prefetchEarnedAchievements,
  updateUser,
  deleteUser,
  refreshRetroAchievements,
};
