<script setup lang="ts">
// GroupFormDialog — create/edit a permission group. Emitter-driven
// (`showGroupFormDialog` with the group to edit, or null to create), mounted
// alongside the groups table in Administration. On save it refetches the
// shared permissionGroups store so every consumer (table, user dialogs)
// reflects the change immediately.
import { RBtn, RIcon, RSwitch, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { GrantSchemaIO, PermAction, PermEntity } from "@/__generated__";
import permissionsApi from "@/services/api/permissions";
import platformApi from "@/services/api/platform";
import storePermissionGroups from "@/stores/permissionGroups";
import type { Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";
import { GROUP_COLOR_PALETTE } from "@/v2/utils/groupColor";
import HiddenGamesPicker from "./HiddenGamesPicker.vue";
import HiddenPlatformsPicker from "./HiddenPlatformsPicker.vue";
import PermissionsMatrix from "./PermissionsMatrix.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const groupsStore = storePermissionGroups();

const show = ref(false);
const submitting = ref(false);
const editingId = ref<number | null>(null);
const isSystem = ref(false);

const name = ref("");
const description = ref("");
const isDefault = ref(false);
const color = ref<string>(GROUP_COLOR_PALETTE[0]);
const palette = GROUP_COLOR_PALETTE;
const grants = ref<GrantSchemaIO[]>([]);

// Group-level hidden entities (members inherit these; per-user overrides on
// top still apply). Diffed against the originals on save.
const platforms = ref<Platform[]>([]);
const hiddenPlatformIds = ref<number[]>([]);
const originalHiddenPlatformIds = ref<number[]>([]);
const hiddenRomIds = ref<number[]>([]);
const originalHiddenRomIds = ref<number[]>([]);

const sortedPlatforms = computed(() =>
  [...platforms.value].sort((a, b) =>
    a.display_name.localeCompare(b.display_name),
  ),
);

const entities = ref<PermEntity[]>([]);
const actions = ref<PermAction[]>([]);

async function ensureCatalog() {
  if (entities.value.length) return;
  try {
    const { data } = await permissionsApi.fetchCatalog();
    entities.value = data.entities;
    actions.value = data.actions;
  } catch (err) {
    console.error("Failed to load permission catalog", err);
  }
}

async function ensurePlatforms() {
  if (platforms.value.length) return;
  try {
    const { data } = await platformApi.getPlatforms();
    platforms.value = data;
  } catch (err) {
    console.error("Failed to load platforms", err);
  }
}

function diffHidden(
  entity: PermEntity,
  current: number[],
  original: number[],
  groupId: number,
): Promise<unknown>[] {
  const added = current.filter((id) => !original.includes(id));
  const removed = original.filter((id) => !current.includes(id));
  return [
    ...added.map((id) =>
      permissionsApi.addHiddenEntity({
        entity,
        entity_id: id,
        group_id: groupId,
      }),
    ),
    ...removed.map((id) =>
      permissionsApi.removeHiddenEntity({
        entity,
        entity_id: id,
        group_id: groupId,
      }),
    ),
  ];
}

emitter?.on("showGroupFormDialog", async (group) => {
  editingId.value = group?.id ?? null;
  isSystem.value = group?.is_system ?? false;
  name.value = group?.name ?? "";
  description.value = group?.description ?? "";
  isDefault.value = group?.is_default ?? false;
  color.value = group?.color ?? GROUP_COLOR_PALETTE[0];
  grants.value = group ? group.grants.map((g) => ({ ...g })) : [];

  const hidden = group?.hidden ?? [];
  const hiddenPlatforms = hidden
    .filter((h) => h.entity === "platforms")
    .map((h) => h.entity_id);
  const hiddenRoms = hidden
    .filter((h) => h.entity === "roms")
    .map((h) => h.entity_id);
  hiddenPlatformIds.value = [...hiddenPlatforms];
  originalHiddenPlatformIds.value = [...hiddenPlatforms];
  hiddenRomIds.value = [...hiddenRoms];
  originalHiddenRomIds.value = [...hiddenRoms];

  await Promise.all([ensureCatalog(), ensurePlatforms()]);
  show.value = true;
});

async function save() {
  if (!name.value.trim()) return;
  submitting.value = true;
  const body = {
    name: name.value.trim(),
    description: description.value,
    is_default: isDefault.value,
    color: color.value,
    grants: grants.value,
  };
  try {
    const { data: saved } =
      editingId.value !== null
        ? await permissionsApi.updateGroup(editingId.value, body)
        : await permissionsApi.createGroup(body);
    // Apply hidden-entity diffs against the (now-known) group id.
    await Promise.all([
      ...diffHidden(
        "platforms",
        hiddenPlatformIds.value,
        originalHiddenPlatformIds.value,
        saved.id,
      ),
      ...diffHidden(
        "roms",
        hiddenRomIds.value,
        originalHiddenRomIds.value,
        saved.id,
      ),
    ]);
    snackbar.success(t("settings.group-saved", { name: body.name }), {
      icon: "mdi-check-bold",
    });
    // Refetch (not upsert): toggling `is_default` reassigns it server-side,
    // so the previous default's flag must be refreshed too.
    await groupsStore.fetch();
    show.value = false;
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      t("settings.group-save-failed", {
        detail:
          e?.response?.data?.detail || e?.response?.statusText || e?.message,
      }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-shield-lock-outline"
    :width="720"
    scroll-content
  >
    <template #header>
      <span class="r-v2-group-dialog__title">
        {{
          editingId !== null
            ? t("settings.edit-group")
            : t("settings.new-group")
        }}
      </span>
    </template>
    <template #content>
      <div class="r-v2-group-dialog__form">
        <p v-if="isSystem" class="r-v2-group-dialog__sys-warn">
          <RIcon icon="mdi-alert-outline" size="14" />
          {{ t("settings.group-system-warning") }}
        </p>

        <RTextField v-model="name" prefix-label="stacked" required clearable>
          <template #prefix-label>
            <RIcon icon="mdi-label-outline" size="14" />
            {{ t("common.name") }}
          </template>
        </RTextField>

        <RTextField
          v-model="description"
          prefix-label="stacked"
          multiline
          :rows="2"
        >
          <template #prefix-label>
            <RIcon icon="mdi-text" size="14" />
            {{ t("settings.description") }}
          </template>
        </RTextField>

        <div class="r-v2-group-dialog__default">
          <RSwitch
            v-model="isDefault"
            :label="t('settings.group-is-default')"
          />
          <span class="r-v2-group-dialog__default-hint">
            {{ t("settings.group-is-default-hint") }}
          </span>
        </div>

        <div class="r-v2-group-dialog__color">
          <span class="r-v2-group-dialog__color-label">
            {{ t("settings.group-color") }}
          </span>
          <div class="r-v2-group-dialog__swatches">
            <RBtn
              v-for="swatch in palette"
              :key="swatch"
              variant="text"
              class="r-v2-group-dialog__swatch"
              :class="{
                'r-v2-group-dialog__swatch--active': color === swatch,
              }"
              :style="{ '--swatch': swatch }"
              :aria-label="swatch"
              :aria-pressed="color === swatch"
              @click="color = swatch"
            >
              <RIcon
                v-if="color === swatch"
                icon="mdi-check"
                size="14"
                class="r-v2-group-dialog__swatch-check"
              />
            </RBtn>
          </div>
        </div>

        <div class="r-v2-group-dialog__matrix">
          <span class="r-v2-group-dialog__matrix-label">
            {{ t("settings.group-grants") }}
          </span>
          <PermissionsMatrix
            v-model="grants"
            :entities="entities"
            :actions="actions"
          />
        </div>

        <div class="r-v2-group-dialog__matrix">
          <span class="r-v2-group-dialog__matrix-label">
            {{ t("settings.hidden-platforms") }}
          </span>
          <HiddenPlatformsPicker
            v-model="hiddenPlatformIds"
            :platforms="sortedPlatforms"
          />
        </div>

        <div class="r-v2-group-dialog__matrix">
          <span class="r-v2-group-dialog__matrix-label">
            {{ t("settings.hidden-games") }}
          </span>
          <HiddenGamesPicker v-model="hiddenRomIds" />
        </div>
      </div>
    </template>
    <template #footer>
      <RBtn variant="text" @click="show = false">{{ t("common.cancel") }}</RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="flat"
        color="primary"
        :loading="submitting"
        :disabled="!name.trim()"
        @click="save"
      >
        {{ t("common.apply") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-group-dialog__title {
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-group-dialog__form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.r-v2-group-dialog__sys-warn {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 12px;
  color: var(--r-color-warning, var(--r-color-fg-muted));
}
.r-v2-group-dialog__default {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.r-v2-group-dialog__default-hint {
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
.r-v2-group-dialog__color {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.r-v2-group-dialog__color-label {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-secondary);
}
.r-v2-group-dialog__swatches {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.r-v2-group-dialog__swatch {
  width: 26px;
  height: 26px;
  min-width: 26px;
  padding: 0;
  border-radius: 50%;
  border: 2px solid transparent;
  background: var(--swatch) !important;
  transition: transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-group-dialog__swatch:hover {
  transform: scale(1.12);
}
.r-v2-group-dialog__swatch--active {
  border-color: var(--r-color-fg);
}
.r-v2-group-dialog__swatch-check {
  color: var(--r-color-overlay-fg);
}
.r-v2-group-dialog__matrix {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.r-v2-group-dialog__matrix-label {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-secondary);
}
</style>
