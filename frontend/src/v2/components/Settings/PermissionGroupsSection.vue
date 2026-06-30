<script setup lang="ts">
// PermissionGroupsSection — v2 admin table of permission groups. Mirrors
// UsersSection's layout (table + bottom action button). Reads the shared
// permissionGroups store; create/edit go through GroupFormDialog (which
// refetches the store), delete removes from the store via useConfirm.
import {
  RBtn,
  RIcon,
  RTable,
  RTag,
  RTextField,
  RTooltip,
  type RTableColumn,
  type RTableSortPayload,
} from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { PermissionGroupSchema } from "@/__generated__";
import permissionsApi from "@/services/api/permissions";
import storePermissionGroups from "@/stores/permissionGroups";
import type { Events } from "@/types/emitter";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { groupColor } from "@/v2/utils/groupColor";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const confirm = useConfirm();
const groupsStore = storePermissionGroups();

const search = ref("");

const sortKey = ref<"name" | "member_count">("name");
const sortDir = ref<"asc" | "desc">("asc");

const sorted = computed(() => {
  const list = [...groupsStore.groups];
  const asc = sortDir.value === "asc";
  list.sort((a, b) => {
    if (sortKey.value === "member_count") {
      return asc
        ? a.member_count - b.member_count
        : b.member_count - a.member_count;
    }
    return asc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
  });
  return list;
});

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return sorted.value;
  return sorted.value.filter(
    (g) =>
      g.name.toLowerCase().includes(q) ||
      g.description.toLowerCase().includes(q),
  );
});

const columns = computed<RTableColumn[]>(() => [
  {
    key: "name",
    label: t("common.name"),
    sortable: true,
    width: "minmax(0, 1.4fr)",
    skeletonWidth: 160,
  },
  {
    key: "description",
    label: t("settings.description"),
    width: "minmax(0, 2fr)",
    skeletonWidth: 220,
  },
  {
    key: "member_count",
    label: t("settings.group-members"),
    sortable: true,
    width: "minmax(0, 0.8fr)",
    align: "center",
    skeletonWidth: 60,
  },
  {
    key: "actions",
    label: "",
    width: "96px",
    align: "end",
    skeletonWidth: 0,
  },
]);

function onSort({ key, dir }: RTableSortPayload) {
  if (key !== "name" && key !== "member_count") return;
  sortKey.value = key;
  sortDir.value = dir;
}

async function fetchGroups() {
  try {
    await groupsStore.fetch();
  } catch (err) {
    console.error("Failed to load permission groups", err);
  }
}

async function deleteGroup(group: PermissionGroupSchema) {
  const ok = await confirm({
    title: t("common.confirm-deletion"),
    body: t("settings.group-delete-confirm", { name: group.name }),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await permissionsApi.deleteGroup(group.id);
    snackbar.success(t("settings.group-removed", { name: group.name }), {
      icon: "mdi-check-bold",
    });
    groupsStore.remove(group.id);
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      t("settings.group-delete-failed", {
        detail:
          e?.response?.data?.detail || e?.response?.statusText || e?.message,
      }),
      { icon: "mdi-close-circle" },
    );
  }
}

onMounted(fetchGroups);
</script>

<template>
  <div class="r-v2-groups">
    <RTextField
      v-model="search"
      prefix-label="inline"
      :placeholder="t('common.search')"
      hide-details
      density="compact"
      :aria-label="t('settings.search-groups')"
    >
      <template #prefix-label>
        <RIcon icon="mdi-magnify" size="15" />
      </template>
    </RTextField>

    <RTable
      :columns="columns"
      :items="filtered"
      :item-key="(r) => (r as PermissionGroupSchema).id"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      :loading="groupsStore.loading"
      empty-icon="mdi-shield-off-outline"
      :empty-message="t('settings.groups-empty')"
      @update:sort="onSort"
    >
      <template #cell.name="{ row }">
        <div class="r-v2-groups__name">
          <span
            class="r-v2-groups__dot"
            :style="{
              background: groupColor((row as PermissionGroupSchema).color),
            }"
          />
          <span>{{ (row as PermissionGroupSchema).name }}</span>
          <RTag
            v-if="(row as PermissionGroupSchema).is_default"
            tone="brand"
            :text="t('settings.group-default-tag')"
            size="x-small"
          />
          <RTag
            v-if="(row as PermissionGroupSchema).is_system"
            tone="info"
            :text="t('settings.group-system-tag')"
            size="x-small"
          />
        </div>
      </template>
      <template #cell.description="{ row }">
        <span class="r-v2-groups__desc">
          {{ (row as PermissionGroupSchema).description || "—" }}
        </span>
      </template>
      <template #cell.member_count="{ row }">
        {{ (row as PermissionGroupSchema).member_count }}
      </template>
      <template #cell.actions="{ row }">
        <div class="r-v2-groups__actions">
          <RTooltip>
            <template #activator="{ props: tipProps }">
              <RBtn
                v-bind="tipProps"
                variant="text"
                size="small"
                icon="mdi-pencil"
                :aria-label="t('settings.edit-group')"
                @click="
                  emitter?.emit(
                    'showGroupFormDialog',
                    row as PermissionGroupSchema,
                  )
                "
              />
            </template>
            <span>{{ t("settings.edit-group") }}</span>
          </RTooltip>
          <RTooltip>
            <template #activator="{ props: tipProps }">
              <RBtn
                v-bind="tipProps"
                variant="text"
                size="small"
                color="danger"
                icon="mdi-trash-can-outline"
                :disabled="(row as PermissionGroupSchema).is_default"
                :aria-label="t('common.delete')"
                @click="deleteGroup(row as PermissionGroupSchema)"
              />
            </template>
            <span>{{ t("common.delete") }}</span>
          </RTooltip>
        </div>
      </template>
    </RTable>

    <div class="r-v2-groups__footer">
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-plus"
        @click="emitter?.emit('showGroupFormDialog', null)"
      >
        {{ t("settings.new-group") }}
      </RBtn>
    </div>
  </div>
</template>

<style scoped>
.r-v2-groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
/* A touch more breathing room before the colour dot (and matching header). */
.r-v2-groups :deep(.r-table__header-cell:first-child),
.r-v2-groups :deep(.r-table__cell:first-child) {
  padding-inline-start: 6px;
}
.r-v2-groups__name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: var(--r-font-weight-semibold);
  min-width: 0;
}
.r-v2-groups__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.r-v2-groups__desc {
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-groups__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.r-v2-groups__footer {
  display: flex;
  gap: 10px;
}
</style>
