<script setup lang="ts">
// Plugins: what is installed on the server's plugin shelf, and what each one
// adds to a game. Read-only: the shelf is files on the server, so the page
// shows what was found and where to put more, and the manifests themselves own
// the labels an action carries.
import { computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import PluginSlot from "@/components/shared/PluginSlot.vue";
import { RCard, RChip, RIcon } from "@/lib";
import { usePluginStore } from "@/stores/plugins";

const { t } = useI18n();
const store = usePluginStore();
const hasSettingsActions = computed(() =>
  store.plugins.some((plugin) =>
    plugin.actions.some((action) => action.slot === "settings.page"),
  ),
);

onMounted(() => void store.load());
</script>

<template>
  <section class="plugins-page">
    <header class="plugins-page__header">
      <h2 class="r-letter-heading">{{ t("settings.plugins") }}</h2>
      <p class="plugins-page__hint">{{ t("settings.plugins-hint") }}</p>
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
  </section>
</template>

<style scoped>
.plugins-page {
  display: flex;
  flex-direction: column;
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
</style>
