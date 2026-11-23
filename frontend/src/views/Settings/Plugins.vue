<script setup lang="ts">
// Plugins: what is installed on the server's plugin shelf, and what each one
// adds. A plugin is a manifest, so both installing and removing are the same
// kind of act: writing or deleting one small file the server already knows how
// to read. There is no package to fetch and nothing to run.
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import PluginSlot from "@/components/shared/PluginSlot.vue";
import { useConfirm } from "@/composables/useConfirm";
import { RBtn, RCard, RChip, RDialog, RIcon, RTextField } from "@/lib";
import storeAuth from "@/stores/auth";
import { usePluginStore } from "@/stores/plugins";

const { t } = useI18n();
const confirm = useConfirm();
const store = usePluginStore();

// Installing writes to the server's disk, so only a user who may administer it
// is offered the controls. The routes enforce the same scope.
const auth = storeAuth();
const mayManage = computed(() => auth.scopes.includes("users.write"));

const hasSettingsActions = computed(() =>
  store.plugins.some((plugin) =>
    plugin.actions.some((action) => action.slot === "settings.page"),
  ),
);

const adding = ref(false);
const url = ref("");
const pasted = ref("");
const problem = ref("");
const busy = ref(false);

function openAdd(): void {
  url.value = "";
  pasted.value = "";
  problem.value = "";
  adding.value = true;
}

async function add(): Promise<void> {
  problem.value = "";

  let source: { url?: string; manifest?: object } = {};
  if (pasted.value.trim()) {
    try {
      source = { manifest: JSON.parse(pasted.value) };
    } catch {
      problem.value = t("settings.plugins-add-bad-json");
      return;
    }
  } else if (url.value.trim()) {
    source = { url: url.value.trim() };
  } else {
    problem.value = t("settings.plugins-add-empty");
    return;
  }

  busy.value = true;
  const result = await store.install(source);
  busy.value = false;
  if (!result.ok) {
    problem.value = result.message ?? "";
    return;
  }
  adding.value = false;
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
}

onMounted(() => void store.load());
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

    <p v-if="store.plugins.length === 0" class="plugins-page__empty">
      {{ t("settings.plugins-empty") }}
    </p>

    <RCard v-if="hasSettingsActions" class="plugins-card">
      <PluginSlot slot="settings.page" labelled />
    </RCard>

    <RCard
      v-for="plugin in store.plugins"
      :key="plugin.id"
      class="plugins-card"
    >
      <div class="plugins-card__head">
        <RIcon icon="mdi-puzzle-outline" />
        <span class="plugins-card__name">{{ plugin.name }}</span>
        <RChip size="x-small" variant="text">{{ plugin.version }}</RChip>
        <a
          v-if="plugin.homepage"
          class="plugins-card__link"
          :href="plugin.homepage"
          target="_blank"
          rel="noopener noreferrer"
          >{{ t("settings.plugins-homepage") }}</a
        >
        <RBtn
          v-if="mayManage"
          class="plugins-card__remove"
          prepend-icon="mdi-delete-outline"
          variant="text"
          size="small"
          @click="remove(plugin.id, plugin.name)"
        >
          {{ t("settings.plugins-remove") }}
        </RBtn>
      </div>
      <p v-if="plugin.description" class="plugins-card__desc">
        {{ plugin.description }}
      </p>
      <ul class="plugins-card__actions">
        <li v-for="action in plugin.actions" :key="action.id">
          <RIcon :icon="action.icon ?? 'mdi-puzzle-outline'" size="small" />
          <span>{{ action.label }}</span>
          <code v-if="action.platforms?.length" class="plugins-card__platforms">
            {{ action.platforms.join(", ") }}
          </code>
        </li>
      </ul>
    </RCard>

    <RDialog v-model="adding" icon="mdi-plus" width="560" cancelable>
      <template #header>
        <span>{{ t("settings.plugins-add") }}</span>
      </template>
      <template #content>
        <div class="plugins-add">
          <p class="plugins-page__hint">{{ t("settings.plugins-add-hint") }}</p>
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
              :placeholder="{ id: 'my-plugin', name: 'My plugin', actions: [] }"
              :disabled="busy"
            />
          </label>
          <p v-if="problem" class="plugins-add__problem">{{ problem }}</p>
        </div>
      </template>
      <template #footer>
        <!-- The dialog draws its own cancel; this footer only adds the button
             that commits the form. -->
        <RBtn variant="flat" color="primary" :disabled="busy" @click="add">
          {{ t("settings.plugins-add") }}
        </RBtn>
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
.plugins-card__desc {
  color: var(--muted-foreground);
}

.plugins-card {
  padding: 16px;
}

.plugins-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.plugins-card__name {
  font-weight: 600;
}

.plugins-card__link {
  margin-inline-start: auto;
}

.plugins-card__remove {
  margin-inline-start: auto;
}

.plugins-card__actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.plugins-card__actions li {
  display: flex;
  align-items: center;
  gap: 8px;
}

.plugins-card__platforms {
  color: var(--muted-foreground);
}

.plugins-add {
  display: flex;
  flex-direction: column;
  gap: 12px;
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

.plugins-add__problem {
  color: var(--r-color-danger, #e5484d);
}
</style>
