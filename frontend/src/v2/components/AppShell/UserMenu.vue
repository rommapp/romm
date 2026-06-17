<script setup lang="ts">
// UserMenu — the avatar pill in the navbar that opens the v2 quick
// navigator. The dropdown mirrors the SettingsSidebar's information
// architecture so the user has the same mental model in both places:
//
//   • Account  — Profile, User interface
//   • Library  — Library management, Metadata sources, Client API tokens
//   • System   — Administration, Server stats
//   • Tools    — Controller debug
//   • Actions  — Scan, Upload, Patcher (librarian actions, not settings)
//   • About / Changelog — kept as dialogs (no dedicated views)
//   • Log out
//
// Items inherit the same scope/role gates as their target views so
// unauthorised users don't see options they can't open.
import {
  RAvatar,
  RBtn,
  RChip,
  RDivider,
  RIcon,
  RMenu,
  RMenuItem,
} from "@v2/lib";
import type { Emitter } from "mitt";
import { getActivePinia, storeToRefs, type StateTree } from "pinia";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import { refetchCSRFToken } from "@/services/api";
import identityApi from "@/services/api/identity";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import { useCan } from "@/v2/composables/useCan";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const router = useRouter();
const authStore = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const { user, scopes } = storeToRefs(authStore);

const open = ref(false);

const avatarSrc = computed(() =>
  userAvatarUrl(user.value?.avatar_path, user.value?.updated_at),
);

const isAdmin = useCan("app.admin");

const canSeeProfile = computed(
  () => !!user.value?.id && scopes.value.includes("me.write"),
);
const canScan = computed(() => scopes.value.includes("platforms.write"));
const canUpload = computed(() => scopes.value.includes("roms.write"));
// Patcher is always reachable (matches v1) — pure client-side worker.
const canSeeLibraryMgmt = computed(() =>
  scopes.value.includes("platforms.write"),
);
const canSeeMetadata = computed(() => scopes.value.includes("me.write"));
const canSeeApiTokens = computed(() => scopes.value.includes("me.write"));
const canSeeAdmin = computed(() => scopes.value.includes("users.write"));

// The System group can be empty for restricted scopes — gate the whole
// region so a lone group label doesn't dangle. The Library group always
// contains at least the Patcher, so it never needs gating.
const showSystemGroup = computed(() => canSeeAdmin.value || isAdmin.value);

function showAbout() {
  open.value = false;
  emitter?.emit("showAboutDialog", null);
}

function showChangelog() {
  open.value = false;
  emitter?.emit("showChangelogDialog", null);
}

async function onLogout() {
  open.value = false;
  try {
    const { data } = await identityApi.logout();
    const oidcLogoutUrl = (data as { oidc_logout_url?: string })
      ?.oidc_logout_url;
    if (oidcLogoutUrl) {
      window.location.href = oidcLogoutUrl;
      return;
    }
    await refetchCSRFToken();
    snackbar.success("Logged out", { icon: "mdi-check-bold" });
    await router.push({ name: ROUTES.LOGIN });
    const pinia = getActivePinia() as
      | { _s?: Map<string, { reset?: () => void } & StateTree> }
      | undefined;
    pinia?._s?.forEach((store) => {
      store.reset?.();
    });
  } catch (error) {
    snackbar.error("Could not log out. Please try again.", {
      icon: "mdi-close-circle",
    });
    console.error("Logout error:", error);
  }
}
</script>

<template>
  <RMenu
    v-model="open"
    location="bottom end"
    :offset="8"
    width="260px"
    max-height="calc(100dvh - var(--r-nav-h) - 24px)"
  >
    <template #activator="{ props: menuProps }">
      <RBtn
        v-bind="menuProps"
        variant="text"
        class="r-v2-user"
        data-user-menu-trigger
        :aria-label="`Account menu for ${user?.username ?? 'Guest'}`"
      >
        <RAvatar :image="avatarSrc" size="30" />
        <span class="r-v2-user__name">
          {{ user?.username ?? "Guest" }}
        </span>
        <RIcon
          icon="mdi-chevron-down"
          size="16"
          class="r-v2-user__chevron r-chevron-toggle"
        />
      </RBtn>
    </template>

    <!-- User header — inlined; the layout is feature-specific so it
         lives at the call site, not in the lib. -->
    <div class="r-v2-user-menu__header">
      <RAvatar :image="avatarSrc" size="30" />
      <div class="r-v2-user-menu__header-text">
        <div class="r-v2-user-menu__header-title">
          {{ user?.username ?? "Guest" }}
        </div>
        <div v-if="user?.role" class="r-v2-user-menu__header-sub">
          {{ user.role }}
        </div>
      </div>
    </div>

    <RDivider />

    <!-- Account -->
    <div class="r-v2-user-menu__group">
      <div class="r-v2-user-menu__group-label">
        {{ t("settings.group-account") }}
      </div>
      <RMenuItem
        v-if="canSeeProfile"
        :to="{ name: ROUTES.USER_PROFILE, params: { user: user?.id } }"
        icon="mdi-account-outline"
        :label="t('common.profile')"
        @click="open = false"
      />
      <RMenuItem
        :to="{ name: ROUTES.USER_INTERFACE }"
        icon="mdi-palette-outline"
        :label="t('common.user-interface')"
        @click="open = false"
      />
    </div>

    <!-- Library -->
    <div class="r-v2-user-menu__group">
      <div class="r-v2-user-menu__group-label">
        {{ t("settings.group-library") }}
      </div>
      <RMenuItem
        :to="{ name: ROUTES.SCAN }"
        icon="mdi-radar"
        :label="t('scan.scan')"
        :disabled="!canScan"
        @click="open = false"
      />
      <RMenuItem
        :to="{ name: ROUTES.UPLOAD }"
        icon="mdi-cloud-upload-outline"
        :label="t('common.upload-roms')"
        :disabled="!canUpload"
        @click="open = false"
      />
      <RMenuItem
        :to="{ name: ROUTES.PATCHER }"
        icon="mdi-file-cog-outline"
        :label="t('common.patcher')"
        @click="open = false"
      />
      <RMenuItem
        v-if="canSeeLibraryMgmt"
        :to="{ name: ROUTES.LIBRARY_MANAGEMENT }"
        icon="mdi-table-cog"
        :label="t('common.library-management')"
        @click="open = false"
      />
      <RMenuItem
        v-if="canSeeMetadata"
        :to="{ name: ROUTES.METADATA_SOURCES }"
        icon="mdi-database-cog-outline"
        :label="t('scan.metadata-sources')"
        @click="open = false"
      />
      <RMenuItem
        v-if="canSeeApiTokens"
        :to="{ name: ROUTES.CLIENT_API_TOKENS }"
        icon="mdi-key-variant"
        :label="t('settings.client-api-tokens')"
        @click="open = false"
      />
    </div>

    <!-- System -->
    <div v-if="showSystemGroup" class="r-v2-user-menu__group">
      <div class="r-v2-user-menu__group-label">
        {{ t("settings.group-system") }}
      </div>
      <RMenuItem
        v-if="canSeeAdmin"
        :to="{ name: ROUTES.ADMINISTRATION }"
        icon="mdi-shield-account-outline"
        :label="t('common.administration')"
        @click="open = false"
      />
      <RMenuItem
        v-if="isAdmin"
        :to="{ name: ROUTES.SERVER_STATS }"
        icon="mdi-server"
        :label="t('common.server-stats')"
        @click="open = false"
      />
    </div>

    <!-- Tools -->
    <div class="r-v2-user-menu__group">
      <div class="r-v2-user-menu__group-label">
        {{ t("settings.group-tools") }}
      </div>
      <RMenuItem
        :to="{ name: ROUTES.CONTROLLER_DEBUG }"
        icon="mdi-controller"
        :label="t('settings.controller-debug')"
        @click="open = false"
      >
        <template #append>
          <RChip size="x-small" color="primary">
            {{ t("common.beta") }}
          </RChip>
        </template>
      </RMenuItem>
    </div>

    <RDivider />

    <!-- About is admin-only in v1; keep that gate. About + Changelog
           remain dialogs (no dedicated views) — see CLAUDE.md. -->
    <RMenuItem
      v-if="isAdmin"
      icon="mdi-help-circle-outline"
      :label="t('common.about')"
      @click="showAbout"
    />
    <RMenuItem
      icon="mdi-clock-outline"
      :label="t('common.changelog')"
      @click="showChangelog"
    />

    <RDivider />

    <RMenuItem
      icon="mdi-logout"
      variant="danger"
      :label="t('common.logout')"
      @click="onLogout"
    />
  </RMenu>
</template>

<style scoped>
.r-v2-user {
  background: var(--r-color-surface) !important;
  border: 1px solid var(--r-color-border-strong) !important;
  border-radius: var(--r-radius-pill) !important;
  padding: 3px 12px 3px 3px !important;
  color: var(--r-color-fg) !important;
  height: auto !important;
  min-width: 0 !important;
  opacity: 1;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-user:hover {
  background: var(--r-color-surface-hover) !important;
}

.r-v2-user__chevron {
  color: var(--r-color-fg-muted);
}

.r-v2-user__name {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
}

/* Group section inside the dropdown — small uppercase label above each
   cluster so the IA mirrors SettingsSidebar exactly. The label is omitted
   for the trailing Actions/About/Logout regions where dividers already
   communicate the boundary. */
.r-v2-user-menu__group {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 4px 0 6px;
}

.r-v2-user-menu__group-label {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 10px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-muted);
  padding: 4px 12px 2px;
}

/* Inlined header — was RMenuHeader before. Identity card at the top
   of the dropdown: avatar + username + role pill. */
.r-v2-user-menu__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px 12px;
  min-width: 0;
}
.r-v2-user-menu__header-text {
  min-width: 0;
}
.r-v2-user-menu__header-title {
  font-size: 13px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-v2-user-menu__header-sub {
  font-size: 10.5px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: capitalize;
  color: var(--r-color-fg-muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
