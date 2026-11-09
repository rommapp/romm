import { ref } from "vue";
import type {
  Body_add_user_api_users_post as AddUserInput,
  Body_create_user_from_invite_api_users_register_post as RegisterUserInput,
  Body_refresh_retro_achievements_api_users__id__ra_refresh_post as RefreshRetroAchievementsInput,
  InviteLinkSchema,
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

export type AchievementTypeCounts = {
  progression: number;
  missable: number;
  win_condition: number;
  other: number;
};

export type CatalogAchievement = {
  id: string;
  title: string | null;
  description: string | null;
  points: number | null;
  badge_url: string | null;
  badge_path: string | null;
  badge_url_lock: string | null;
  badge_path_lock: string | null;
  type: string | null;
  display_order: number | null;
  earned: boolean;
  earned_at: string | null;
};

export type AchievementGame = {
  rom_id: number;
  name: string;
  platform_name: string | null;
  platform_slug: string | null;
  platform_fs_slug: string | null;
  cover_url: string | null;
  path_cover_large: string | null;
  path_cover_small: string | null;
  url_cover: string | null;
  title_url: string | null;
  ingame_url: string | null;
  box_art_url: string | null;
  earned: number;
  total: number;
  points_earned: number;
  points_total: number;
  earned_by_type: AchievementTypeCounts;
  achievements: CatalogAchievement[];
};

export type EarnedAchievementsResponse = {
  linked: boolean;
  synced: boolean;
  earned: number;
  total: number;
  points_earned: number;
  points_total: number;
  earned_by_type: AchievementTypeCounts;
  games: AchievementGame[];
};

async function fetchEarnedAchievements() {
  return api.get<EarnedAchievementsResponse>("/users/me/earned-achievements");
}

const earnedAchievementsLoading = ref(true);
const earnedAchievementsRefreshing = ref(false);
const earnedAchievementsFailed = ref(false);
const earnedAchievementsPayload = ref<EarnedAchievementsResponse | null>(null);
let earnedAchievementsFetchedAt = 0;
let earnedAchievementsInFlight: Promise<void> | null = null;

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
      earnedAchievementsPayload.value = (await fetchEarnedAchievements()).data;
      earnedAchievementsFailed.value = false;
    } catch {
      if (!keepContent || earnedAchievementsPayload.value == null) {
        earnedAchievementsFailed.value = true;
        earnedAchievementsPayload.value = null;
      }
    } finally {
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
