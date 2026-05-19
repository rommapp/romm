<script setup lang="ts">
// SaveDataTab — Saves + States, each its own subtab with badge counts.
// URL-persistent via `?subtab=`. Per-row UI is intentionally lean for
// now — filename, size, timestamp, emulator. Action buttons (download,
// delete, set as main, screenshot preview) come in a follow-up pass.
import { REmptyState, RIcon, RTabNav, type RTabNavItem } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type {
  DetailedRomSchema,
  SaveSchema,
  StateSchema,
} from "@/__generated__";
import { formatBytes } from "@/utils";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRomSchema }>();

const validSubtabs = ["saves", "states"] as const;
type Subtab = (typeof validSubtabs)[number];

const route = useRoute();
const router = useRouter();

const subTab = ref<Subtab>(
  validSubtabs.includes(route.query.subtab as Subtab)
    ? (route.query.subtab as Subtab)
    : "saves",
);

watch(subTab, (value) => {
  if (route.query.subtab !== value) {
    router.replace({
      path: route.path,
      query: { ...route.query, subtab: value },
    });
  }
});
watch(
  () => route.query.subtab,
  (value) => {
    if (typeof value === "string" && validSubtabs.includes(value as Subtab)) {
      subTab.value = value as Subtab;
    }
  },
);
// When the user navigates away from this tab, drop the subtab param
// so it doesn't leak onto sibling tabs.
watch(
  () => route.query.tab,
  (value) => {
    if (value !== "save-data" && route.query.subtab) {
      const rest = { ...route.query };
      delete rest.subtab;
      router.replace({ path: route.path, query: rest });
    }
  },
);

const saves = computed<SaveSchema[]>(() => props.rom.user_saves ?? []);
const states = computed<StateSchema[]>(() => props.rom.user_states ?? []);

const subtabItems = computed<RTabNavItem[]>(() => [
  {
    id: "saves",
    label: "Saves",
    icon: "mdi-content-save-outline",
    badge: saves.value.length,
  },
  {
    id: "states",
    label: "States",
    icon: "mdi-camera-outline",
    badge: states.value.length,
  },
]);

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}
</script>

<template>
  <div class="save-data">
    <RTabNav
      v-model="subTab"
      :items="subtabItems"
      variant="pill"
      orientation="vertical"
      size="small"
      class="save-data__nav"
    />

    <div class="save-data__content">
      <section v-if="subTab === 'saves'" class="save-data__panel">
        <REmptyState
          v-if="saves.length === 0"
          icon="mdi-content-save-outline"
          title="No saves yet"
          hint="Saves uploaded for this ROM will appear here."
        />
        <ul v-else class="save-data__list">
          <li v-for="s in saves" :key="s.id" class="save-data__row">
            <RIcon icon="mdi-content-save-outline" size="18" />
            <div class="save-data__row-main">
              <div class="save-data__row-name">{{ s.file_name }}</div>
              <div class="save-data__row-meta">
                <span>{{ formatBytes(s.file_size_bytes) }}</span>
                <span class="save-data__sep">·</span>
                <span>{{ fmtDate(s.updated_at) }}</span>
                <template v-if="s.emulator">
                  <span class="save-data__sep">·</span>
                  <span>{{ s.emulator }}</span>
                </template>
              </div>
            </div>
          </li>
        </ul>
      </section>

      <section v-if="subTab === 'states'" class="save-data__panel">
        <REmptyState
          v-if="states.length === 0"
          icon="mdi-camera-outline"
          title="No states yet"
          hint="Save states uploaded for this ROM will appear here."
        />
        <ul v-else class="save-data__list">
          <li v-for="s in states" :key="s.id" class="save-data__row">
            <RIcon icon="mdi-camera-outline" size="18" />
            <div class="save-data__row-main">
              <div class="save-data__row-name">{{ s.file_name }}</div>
              <div class="save-data__row-meta">
                <span>{{ formatBytes(s.file_size_bytes) }}</span>
                <span class="save-data__sep">·</span>
                <span>{{ fmtDate(s.updated_at) }}</span>
                <template v-if="s.emulator">
                  <span class="save-data__sep">·</span>
                  <span>{{ s.emulator }}</span>
                </template>
              </div>
            </div>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
.save-data {
  display: flex;
  align-items: stretch;
  gap: 24px;
}

.save-data__nav {
  width: 180px;
  flex-shrink: 0;
}

.save-data__content {
  flex: 1;
  min-width: 0;
}

.save-data__panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

html[data-bp~="xs"] .save-data {
  flex-direction: column;
  gap: 14px;
}
html[data-bp~="xs"] .save-data__nav {
  width: auto;
}

.save-data__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.save-data__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg);
}
.save-data__row > .mdi {
  color: var(--r-color-fg-muted);
}

.save-data__row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.save-data__row-name {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.save-data__row-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
  flex-wrap: wrap;
}
.save-data__sep {
  opacity: 0.5;
}
</style>
