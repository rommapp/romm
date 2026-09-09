<script setup lang="ts">
// LauncherDevicesSection: the desktop companions paired with this account
// and where each one's Steam queue stands. Lives under the token table
// because a companion is paired through a client token.
import { RBtn, RTable, type RTableColumn } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { DeviceSchema } from "@/__generated__";
import { launcherDeviceName, useShortcutsStore } from "@/stores/shortcuts";
import { formatTimestamp } from "@/utils";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t, locale } = useI18n();
const store = useShortcutsStore();
const confirm = useConfirm();
const snackbar = useSnackbar();

const removing = ref<string | null>(null);

const columns = computed<RTableColumn[]>(() => [
  {
    key: "name",
    label: t("common.name"),
    width: "minmax(0, 1.5fr)",
    skeletonWidth: 140,
  },
  {
    key: "last_seen",
    label: t("settings.launcher-last-seen"),
    width: "minmax(0, 1fr)",
    skeletonWidth: 110,
  },
  {
    key: "platforms",
    label: t("settings.launcher-platforms"),
    width: "minmax(0, 1fr)",
    align: "end",
    skeletonWidth: 40,
  },
  {
    key: "shortcuts",
    label: t("settings.launcher-shortcuts"),
    width: "minmax(0, 1fr)",
    align: "end",
    skeletonWidth: 40,
  },
  {
    key: "pending",
    label: t("settings.launcher-pending"),
    width: "minmax(0, 1fr)",
    align: "end",
    skeletonWidth: 40,
  },
  {
    key: "actions",
    label: "",
    width: "200px",
    align: "end",
    skeletonWidth: 0,
  },
]);

// The hostname only earns a second line when the user named the device
// something else.
function showHostname(device: DeviceSchema): boolean {
  return Boolean(device.hostname) && device.hostname !== device.name;
}

function playablePlatforms(device: DeviceSchema): number {
  return Object.values(device.launch_capabilities ?? {}).filter(Boolean).length;
}

function addedCount(device: DeviceSchema): number {
  return store.shortcutsForDevice(device.id).filter((s) => s.status === "added")
    .length;
}

function pendingCount(device: DeviceSchema): number {
  return store.shortcutsForDevice(device.id).filter((s) => s.status !== "added")
    .length;
}

async function removeAll(device: DeviceSchema) {
  const rows = store
    .shortcutsForDevice(device.id)
    .filter((s) => s.status !== "pending_remove");
  if (rows.length === 0) return;
  const ok = await confirm({
    title: t("settings.launcher-remove-all"),
    body: t("settings.launcher-remove-all-confirm", {
      device: launcherDeviceName(device),
      count: rows.length,
    }),
    confirmText: t("settings.launcher-remove-all"),
    tone: "danger",
  });
  if (!ok) return;
  removing.value = device.id;
  try {
    for (const row of rows) await store.remove(row);
    snackbar.success(
      t("settings.launcher-removed-all", { count: rows.length }),
      { icon: "mdi-check-bold" },
    );
  } catch {
    snackbar.error(t("settings.launcher-remove-all-failed"), {
      icon: "mdi-alert-circle-outline",
    });
  } finally {
    removing.value = null;
  }
}

onMounted(() => {
  void store.ensureLoaded();
});
</script>

<template>
  <section class="r-v2-launchers">
    <h3 class="r-v2-launchers__title">
      {{ t("settings.launchers") }}
    </h3>
    <p class="r-v2-launchers__help">
      {{ t("settings.launchers-help") }}
    </p>
    <RTable
      :columns="columns"
      :items="store.launcherDevices"
      :item-key="(r) => (r as DeviceSchema).id"
      :loading="!store.loaded && store.canRead"
      empty-icon="mdi-steam"
      :empty-message="t('settings.launchers-none')"
    >
      <template #cell.name="{ row }">
        <div class="r-v2-launchers__name-cell">
          <span class="r-v2-launchers__name">
            {{ launcherDeviceName(row as DeviceSchema) }}
          </span>
          <span
            v-if="showHostname(row as DeviceSchema)"
            class="r-v2-launchers__meta"
          >
            {{ (row as DeviceSchema).hostname }}
          </span>
        </div>
      </template>
      <template #cell.last_seen="{ row }">
        <span class="r-v2-launchers__meta">
          {{
            (row as DeviceSchema).last_seen
              ? formatTimestamp((row as DeviceSchema).last_seen!, locale)
              : "-"
          }}
        </span>
      </template>
      <template #cell.platforms="{ row }">
        {{ playablePlatforms(row as DeviceSchema) }}
      </template>
      <template #cell.shortcuts="{ row }">
        {{ addedCount(row as DeviceSchema) }}
      </template>
      <template #cell.pending="{ row }">
        {{ pendingCount(row as DeviceSchema) }}
      </template>
      <template #cell.actions="{ row }">
        <RBtn
          variant="text"
          size="small"
          color="danger"
          prepend-icon="mdi-steam"
          :disabled="
            store.shortcutsForDevice((row as DeviceSchema).id).length === 0
          "
          :loading="removing === (row as DeviceSchema).id"
          @click="removeAll(row as DeviceSchema)"
        >
          {{ t("settings.launcher-remove-all") }}
        </RBtn>
      </template>
    </RTable>
  </section>
</template>

<style scoped>
.r-v2-launchers {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.r-v2-launchers__title {
  margin: 0;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-launchers__help {
  margin: 0;
  font-size: var(--r-font-size-md);
  color: var(--r-color-fg-muted);
}
.r-v2-launchers__name-cell {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.r-v2-launchers__name {
  font-weight: var(--r-font-weight-semibold);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-launchers__meta {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}
</style>
