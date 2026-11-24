<script setup lang="ts">
// One field of a plugin's settings form, rendered from the manifest.
//
// A field can be a list of entries (`groups`), and each entry is drawn by this
// same component, so a setup's CPU is the same kind of control as a top-level
// text box. Nothing here knows what a "setup" is: the manifest says which
// fields an entry holds, and this draws them.
import { onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { PluginOptionSchema, PluginSettingSchema } from "@/__generated__";
import { RBtn, RIcon, RSelect, RSwitch, RTextField } from "@/lib";
import pluginApi from "@/services/api/plugin";

const props = defineProps<{
  setting: PluginSettingSchema;
  modelValue: unknown;
  pluginId: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{ (e: "update:modelValue", value: unknown): void }>();

const { t } = useI18n();

/** One entry of a list field, as this component draws it. */
type Entry = Record<string, unknown>;

const entries = ref<Entry[]>([]);
const typed = ref("");

// `search` fields ask the plugin's source as the user types; the first page is
// asked for on mount so the control is not empty before any typing.
const options = ref<PluginOptionSchema[]>([]);
const note = ref("");
const loading = ref(false);
let asked = 0;
let timer: ReturnType<typeof setTimeout> | undefined;

const asEntries = (): Entry[] =>
  Array.isArray(props.modelValue) ? (props.modelValue as Entry[]) : [];

watch(
  () => props.setting.key,
  () => {
    entries.value = asEntries().map((entry) => ({ ...entry }));
  },
  { immediate: true },
);

watch(
  () => JSON.stringify(props.modelValue ?? null),
  () => {
    // The parent can replace the whole list (a different plugin, a reload), and
    // this copy has to follow it rather than keep writing over it.
    if (JSON.stringify(entries.value) !== JSON.stringify(asEntries())) {
      entries.value = asEntries().map((entry) => ({ ...entry }));
    }
  },
);

function setEntry(index: number, key: string, value: unknown): void {
  const next = entries.value.map((entry, at) =>
    at === index ? { ...entry, [key]: value } : entry,
  );
  entries.value = next;
  emit("update:modelValue", next);
}

function addEntry(): void {
  const empty: Entry = {};
  for (const field of props.setting.fields ?? []) {
    if (field.type === "number") empty[field.key] = undefined;
    else if (field.type === "boolean") empty[field.key] = false;
    else empty[field.key] = "";
  }
  entries.value = [...entries.value, empty];
  emit("update:modelValue", entries.value);
}

function removeEntry(index: number): void {
  entries.value = entries.value.filter((_, at) => at !== index);
  emit("update:modelValue", entries.value);
}

function selectItems(setting: PluginSettingSchema) {
  return (setting.options ?? []).map((option) => ({
    title: option.label,
    value: option.value,
  }));
}

function searchItems() {
  return options.value.map((option) => ({
    title: option.label,
    value: option.value,
  }));
}

async function ask(query: string): Promise<void> {
  const mine = ++asked;
  loading.value = true;
  try {
    const { data } = await pluginApi.getOptions(
      props.pluginId,
      props.setting.key,
      query,
    );
    if (mine !== asked) return;
    options.value = data.options ?? [];
    note.value = data.note ?? "";
  } catch {
    if (mine !== asked) return;
    options.value = [];
    note.value = t("settings.plugins-search-failed");
  } finally {
    if (mine === asked) loading.value = false;
  }
}

watch(
  () => [props.pluginId, props.setting.key],
  () => {
    if (props.setting.type === "search") void ask("");
  },
  { immediate: true },
);

watch(typed, (value) => {
  if (props.setting.type !== "search") return;
  // One request per pause, not one per keystroke.
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => void ask(value), 250);
});

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer);
});
</script>

<template>
  <RSwitch
    v-if="setting.type === 'boolean'"
    :model-value="Boolean(modelValue)"
    :label="setting.label"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event)"
  />

  <div v-else-if="setting.type === 'groups'" class="plugin-field__group">
    <div
      v-for="(entry, index) in entries"
      :key="index"
      class="plugin-field__entry"
    >
      <div class="plugin-field__entry-head">
        <span class="plugin-field__entry-name">
          {{ t("settings.plugins-setup-n", { n: index + 1 }) }}
        </span>
        <RBtn
          variant="bare"
          size="small"
          :disabled="disabled"
          @click="removeEntry(index)"
        >
          <RIcon icon="mdi-trash-can-outline" size="small" />
        </RBtn>
      </div>
      <PluginSettingField
        v-for="field in setting.fields ?? []"
        :key="field.key"
        :setting="field"
        :model-value="entry[field.key]"
        :plugin-id="pluginId"
        :disabled="disabled"
        @update:model-value="setEntry(index, field.key, $event)"
      />
    </div>
    <RBtn
      v-if="entries.length < (setting.max_items ?? 8)"
      variant="surface"
      size="small"
      :disabled="disabled"
      @click="addEntry"
    >
      <RIcon icon="mdi-plus" size="small" />
      {{ t("settings.plugins-add-setup") }}
    </RBtn>
  </div>

  <template v-else>
    <label class="plugin-field__label" :for="`plugin-setting-${setting.key}`">
      {{ setting.label }}
    </label>
    <RSelect
      v-if="setting.type === 'search'"
      :model-value="String(modelValue ?? '')"
      :items="searchItems()"
      searchable
      :loading="loading"
      :search-placeholder="t('settings.plugins-search')"
      :placeholder="setting.placeholder ?? setting.label"
      :disabled="disabled"
      @update:model-value="emit('update:modelValue', $event)"
      @update:search="typed = $event"
    />
    <RSelect
      v-else-if="setting.type === 'select'"
      :model-value="String(modelValue ?? '')"
      :items="selectItems(setting)"
      :disabled="disabled"
      @update:model-value="emit('update:modelValue', $event)"
    />
    <RTextField
      v-else
      :id="`plugin-setting-${setting.key}`"
      :model-value="String(modelValue ?? '')"
      :placeholder="setting.placeholder ?? setting.label"
      :type="
        setting.type === 'number'
          ? 'number'
          : setting.type === 'password'
            ? 'password'
            : 'text'
      "
      :disabled="disabled"
      @update:model-value="
        emit(
          'update:modelValue',
          setting.type === 'number' && $event !== '' ? Number($event) : $event,
        )
      "
    />
  </template>

  <p v-if="note" class="plugin-field__note">{{ note }}</p>
  <p v-if="setting.help" class="plugin-field__help">{{ setting.help }}</p>
</template>

<style scoped>
.plugin-field__label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 4px;
}

.plugin-field__help,
.plugin-field__note {
  margin: 4px 0 0;
  font-size: 11px;
  opacity: 0.7;
}

.plugin-field__note {
  color: var(--r-color-warning, inherit);
}

.plugin-field__group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.plugin-field__entry {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--r-color-border, rgba(255, 255, 255, 0.1));
  border-radius: 8px;
}

.plugin-field__entry-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.plugin-field__entry-name {
  font-size: 12px;
  font-weight: 600;
  opacity: 0.8;
}
</style>
