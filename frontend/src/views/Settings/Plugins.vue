<script setup lang="ts">
// Plugins: what is installed, what each one adds, and what it asks its user for.
//
// A plugin is a manifest, so this page is a form over someone else's file: the
// left column lists what is installed, the right column shows what the selected
// one does and the settings its manifest declares. Values live on the server
// beside the manifest, which is why saving is a round trip.
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { PluginSchema, PluginSettingSchema } from "@/__generated__";
import PluginSlot from "@/components/shared/PluginSlot.vue";
import { useConfirm } from "@/composables/useConfirm";
import {
  RBtn,
  RCard,
  RChip,
  RDialog,
  RIcon,
  RSelect,
  RSwitch,
  RTextField,
} from "@/lib";
import storeAuth from "@/stores/auth";
import { usePluginStore } from "@/stores/plugins";

const { t } = useI18n();
const confirm = useConfirm();
const store = usePluginStore();

// Installing writes to the server's disk, so only a user who may administer it
// is offered the controls. The routes enforce the same scope.
const auth = storeAuth();
const mayManage = computed(() => auth.scopes.includes("users.write"));

const selectedId = ref<string>("");
const selected = computed<PluginSchema | null>(
  () => store.plugins.find((plugin) => plugin.id === selectedId.value) ?? null,
);

const draft = ref<Record<string, unknown>>({});
const saved = ref<Record<string, unknown>>({});
const problem = ref("");
const busy = ref(false);
const flash = ref("");

const hasSettingsActions = computed(() =>
  store.plugins.some((plugin) =>
    plugin.actions.some((action) => action.slot === "settings.page"),
  ),
);

const dirty = computed(
  () => JSON.stringify(draft.value) !== JSON.stringify(saved.value),
);

async function pick(pluginId: string): Promise<void> {
  selectedId.value = pluginId;
  problem.value = "";
  flash.value = "";
  const values = await store.settings(pluginId);
  draft.value = { ...(values ?? {}) };
  saved.value = { ...(values ?? {}) };
}

watch(
  () => store.plugins.length,
  () => {
    if (!selected.value && store.plugins.length)
      void pick(store.plugins[0]!.id);
  },
);

function fieldValue(setting: PluginSettingSchema): unknown {
  const value = draft.value[setting.key];
  return value === undefined || value === null ? setting.default : value;
}

function setField(setting: PluginSettingSchema, value: unknown): void {
  draft.value = { ...draft.value, [setting.key]: value };
}

function selectItems(setting: PluginSettingSchema) {
  return (setting.options ?? []).map((option) => ({
    title: option.label,
    value: option.value,
  }));
}

async function save(): Promise<void> {
  if (!selected.value) return;
  busy.value = true;
  problem.value = "";
  const result = await store.saveSettings(selected.value.id, draft.value);
  busy.value = false;
  if (!result.ok) {
    problem.value = result.message ?? "";
    return;
  }
  saved.value = { ...draft.value };
  flash.value = t("settings.plugins-saved");
  setTimeout(() => (flash.value = ""), 2500);
}

async function remove(pluginId: string, name: string): Promise<void> {
  const agreed = await confirm({
    title: t("settings.plugins-remove-title", { name }),
    body: t("settings.plugins-remove-body"),
    confirmText: t("settings.plugins-remove"),
    tone: "danger",
  });
  if (!agreed) return;
  await store.remove(pluginId);
  selectedId.value = "";
}

// Add plugin: the curated index, or a manifest of your own.
const adding = ref(false);
const tab = ref<"store" | "manual">("store");
const url = ref("");
const pasted = ref("");
const addProblem = ref("");
const addBusy = ref("");
const storeProblem = ref("");

function openAdd(): void {
  url.value = "";
  pasted.value = "";
  addProblem.value = "";
  adding.value = true;
  if (tab.value === "store") void openStore();
}

async function openStore(): Promise<void> {
  storeProblem.value = "";
  const failure = await store.loadStore();
  if (failure) storeProblem.value = failure;
}

function installed(pluginId: string): boolean {
  return store.plugins.some((plugin) => plugin.id === pluginId);
}

async function addFromStore(pluginId: string): Promise<void> {
  addBusy.value = pluginId;
  addProblem.value = "";
  const result = await store.installFromStore(pluginId);
  addBusy.value = "";
  if (!result.ok) {
    addProblem.value = result.message ?? "";
    return;
  }
  adding.value = false;
  await pick(pluginId);
}

async function addManual(): Promise<void> {
  addProblem.value = "";
  let source: { url?: string; manifest?: object } = {};
  if (pasted.value.trim()) {
    try {
      source = { manifest: JSON.parse(pasted.value) };
    } catch {
      addProblem.value = t("settings.plugins-add-bad-json");
      return;
    }
  } else if (url.value.trim()) {
    source = { url: url.value.trim() };
  } else {
    addProblem.value = t("settings.plugins-add-empty");
    return;
  }
  busy.value = true;
  const result = await store.install(source);
  busy.value = false;
  if (!result.ok) {
    addProblem.value = result.message ?? "";
    return;
  }
  adding.value = false;
  const ids = store.plugins.map((plugin) => plugin.id);
  const newest = ids[ids.length - 1];
  if (newest) await pick(newest);
}

onMounted(async () => {
  await store.load();
  if (store.plugins.length) await pick(store.plugins[0]!.id);
});
</script>

<template>
  <section class="plugins-page">
    <header class="plugins-page__header">
      <div>
        <h2 class="r-letter-heading">{{ t("settings.plugins") }}</h2>
        <p class="plugins-page__hint">{{ t("settings.plugins-hint") }}</p>
      </div>
      <RBtn
        v-if="mayManage"
        prepend-icon="mdi-plus"
        variant="outlined"
        @click="openAdd"
      >
        {{ t("settings.plugins-add") }}
      </RBtn>
    </header>

    <RCard v-if="hasSettingsActions" class="plugins-detail">
      <PluginSlot slot="settings.page" labelled />
    </RCard>

    <p v-if="store.plugins.length === 0" class="plugins-page__empty">
      {{ t("settings.plugins-empty") }}
    </p>

    <div v-else class="plugins-grid">
      <!-- What is installed -->
      <RCard class="plugins-list">
        <button
          v-for="plugin in store.plugins"
          :key="plugin.id"
          type="button"
          class="plugins-list__row"
          :class="{ 'plugins-list__row--on': plugin.id === selectedId }"
          @click="pick(plugin.id)"
        >
          <RIcon icon="mdi-puzzle-outline" />
          <span class="plugins-list__name">{{ plugin.name }}</span>
          <RChip size="x-small" variant="text">{{ plugin.version }}</RChip>
        </button>
      </RCard>

      <!-- What the selected one is, does, and asks for -->
      <RCard v-if="selected" class="plugins-detail">
        <div class="plugins-detail__head">
          <h3 class="plugins-detail__name">{{ selected.name }}</h3>
          <RChip size="x-small" variant="text">{{ selected.version }}</RChip>
          <a
            v-if="selected.homepage"
            class="plugins-detail__link"
            :href="selected.homepage"
            target="_blank"
            rel="noopener noreferrer"
            >{{ t("settings.plugins-homepage") }}</a
          >
          <RBtn
            v-if="mayManage"
            prepend-icon="mdi-delete-outline"
            variant="text"
            size="small"
            @click="remove(selected.id, selected.name)"
          >
            {{ t("settings.plugins-remove") }}
          </RBtn>
        </div>

        <p v-if="selected.description" class="plugins-detail__desc">
          {{ selected.description }}
        </p>
        <p v-if="selected.author" class="plugins-detail__meta">
          {{ t("settings.plugins-author", { author: selected.author }) }}
        </p>

        <h4 class="plugins-detail__section">
          {{ t("settings.plugins-actions") }}
        </h4>
        <ul class="plugins-detail__actions">
          <li v-for="action in selected.actions" :key="action.id">
            <RIcon :icon="action.icon ?? 'mdi-puzzle-outline'" size="small" />
            <span>{{ action.label }}</span>
            <code class="plugins-detail__slot">{{ action.slot }}</code>
            <code v-if="action.platforms?.length" class="plugins-detail__slot">
              {{ action.platforms.join(", ") }}
            </code>
          </li>
        </ul>

        <template v-if="selected.settings.length">
          <h4 class="plugins-detail__section">
            {{ t("settings.plugins-settings") }}
          </h4>
          <div class="plugins-form">
            <div
              v-for="setting in selected.settings"
              :key="setting.key"
              class="plugins-form__field"
            >
              <RSwitch
                v-if="setting.type === 'boolean'"
                :model-value="Boolean(fieldValue(setting))"
                :label="setting.label"
                @update:model-value="setField(setting, $event)"
              />
              <label
                v-else
                class="plugins-form__label"
                :for="`plugin-setting-${setting.key}`"
                >{{ setting.label }}</label
              >
              <RSelect
                v-if="setting.type === 'select'"
                :model-value="String(fieldValue(setting) ?? '')"
                :items="selectItems(setting)"
                @update:model-value="setField(setting, $event)"
              />
              <RTextField
                v-else-if="setting.type !== 'boolean'"
                :id="`plugin-setting-${setting.key}`"
                :model-value="String(fieldValue(setting) ?? '')"
                :placeholder="setting.placeholder ?? setting.label"
                :type="setting.type === 'number' ? 'number' : 'text'"
                @update:model-value="setField(setting, $event)"
              />
              <p v-if="setting.help" class="plugins-form__help">
                {{ setting.help }}
              </p>
            </div>
            <div class="plugins-form__actions">
              <p v-if="problem" class="plugins-form__problem">{{ problem }}</p>
              <p v-else-if="flash" class="plugins-form__flash">{{ flash }}</p>
              <RBtn
                v-if="mayManage"
                variant="flat"
                color="primary"
                :disabled="busy || !dirty"
                @click="save"
              >
                {{ t("settings.plugins-save") }}
              </RBtn>
            </div>
          </div>
        </template>
        <p v-else class="plugins-detail__desc">
          {{ t("settings.plugins-no-settings") }}
        </p>
      </RCard>
    </div>

    <RDialog v-model="adding" icon="mdi-plus" width="620" cancelable>
      <template #header>
        <span>{{ t("settings.plugins-add") }}</span>
      </template>
      <template #content>
        <div class="plugins-add">
          <div class="plugins-add__tabs">
            <RBtn
              :variant="tab === 'store' ? 'flat' : 'text'"
              size="small"
              prepend-icon="mdi-storefront-outline"
              @click="
                tab = 'store';
                openStore();
              "
            >
              {{ t("settings.plugins-add-store") }}
            </RBtn>
            <RBtn
              :variant="tab === 'manual' ? 'flat' : 'text'"
              size="small"
              prepend-icon="mdi-link"
              @click="tab = 'manual'"
            >
              {{ t("settings.plugins-add-manual") }}
            </RBtn>
          </div>

          <template v-if="tab === 'store'">
            <p class="plugins-page__hint">
              {{ t("settings.plugins-add-store-hint") }}
            </p>
            <p v-if="storeProblem" class="plugins-form__problem">
              {{ storeProblem }}
            </p>
            <p v-else-if="!store.store.length" class="plugins-page__hint">
              {{ t("settings.plugins-store-empty") }}
            </p>
            <ul class="plugins-store">
              <li
                v-for="entry in store.store"
                :key="entry.id"
                class="plugins-store__row"
              >
                <div>
                  <b>{{ entry.name }}</b>
                  <RChip size="x-small" variant="text">{{
                    entry.version
                  }}</RChip>
                  <p class="plugins-store__desc">{{ entry.description }}</p>
                  <p v-if="entry.author" class="plugins-store__desc">
                    {{ t("settings.plugins-author", { author: entry.author }) }}
                  </p>
                </div>
                <RBtn
                  v-if="!installed(entry.id)"
                  variant="flat"
                  color="primary"
                  size="small"
                  :disabled="addBusy === entry.id"
                  @click="addFromStore(entry.id)"
                >
                  {{ t("settings.plugins-install") }}
                </RBtn>
                <RChip v-else size="x-small" variant="text">
                  {{ t("settings.plugins-installed") }}
                </RChip>
              </li>
            </ul>
          </template>

          <template v-else>
            <p class="plugins-page__hint">
              {{ t("settings.plugins-add-hint") }}
            </p>
            <RTextField
              v-model="url"
              :label="t('settings.plugins-add-url')"
              placeholder="https://example.com/plugin.json"
              prepend-inner-icon="mdi-link"
              :disabled="busy"
            />
            <label class="plugins-add__label">
              {{ t("settings.plugins-add-manifest") }}
              <textarea
                v-model="pasted"
                class="plugins-add__paste"
                rows="8"
                spellcheck="false"
                :placeholder="{
                  id: 'my-plugin',
                  name: 'My plugin',
                  actions: [],
                }"
                :disabled="busy"
              />
            </label>
            <p v-if="addProblem" class="plugins-form__problem">
              {{ addProblem }}
            </p>
            <div class="plugins-add__actions">
              <RBtn
                variant="flat"
                color="primary"
                :disabled="busy"
                @click="addManual"
              >
                {{ t("settings.plugins-add") }}
              </RBtn>
            </div>
          </template>
        </div>
      </template>
    </RDialog>
  </section>
</template>

<style scoped>
.plugins-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.plugins-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.plugins-page__hint,
.plugins-page__empty,
.plugins-detail__desc,
.plugins-detail__meta,
.plugins-store__desc,
.plugins-form__help {
  color: var(--muted-foreground);
}

.plugins-grid {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

@media (width < 900px) {
  .plugins-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

.plugins-list {
  display: flex;
  flex-direction: column;
  padding: 8px;
  gap: 2px;
}

.plugins-list__row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 0;
  border-radius: 8px;
  background: none;
  color: inherit;
  cursor: pointer;
  text-align: start;
}

.plugins-list__row:hover {
  background: var(--accent);
}

.plugins-list__row--on {
  background: var(--accent);
  font-weight: 600;
}

.plugins-list__name {
  flex: 1 1 auto;
}

.plugins-detail {
  padding: 16px;
}

.plugins-detail__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.plugins-detail__name {
  margin: 0;
  font-size: 1.05rem;
}

.plugins-detail__link {
  margin-inline-start: auto;
}

.plugins-detail__section {
  margin: 18px 0 8px;
  font-size: 0.85rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted-foreground);
}

.plugins-detail__actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.plugins-detail__actions li {
  display: flex;
  align-items: center;
  gap: 8px;
}

.plugins-detail__slot {
  color: var(--muted-foreground);
}

.plugins-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 520px;
}

.plugins-form__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.plugins-form__label {
  font-size: 0.82rem;
  font-weight: 600;
}

.plugins-form__help {
  margin: 0;
  font-size: 0.8rem;
}

.plugins-form__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
}

.plugins-form__problem {
  color: var(--r-color-danger, #e5484d);
  margin: 0;
}

.plugins-form__flash {
  color: var(--r-color-ok, #59d18c);
  margin: 0;
}

.plugins-add {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plugins-add__tabs {
  display: flex;
  gap: 8px;
}

.plugins-add__label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--muted-foreground);
}

.plugins-add__paste {
  min-height: 120px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--card);
  color: var(--foreground);
  font-family: monospace;
  font-size: 13px;
  resize: vertical;
}

.plugins-add__actions {
  display: flex;
  justify-content: flex-end;
}

.plugins-store {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 380px;
  overflow-y: auto;
}

.plugins-store__row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.plugins-store__desc {
  margin: 2px 0 0;
  font-size: 0.85rem;
}
</style>
