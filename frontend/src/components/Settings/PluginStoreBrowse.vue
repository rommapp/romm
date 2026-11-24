<script setup lang="ts">
// The store, as something to look through rather than a list to scroll past.
//
// An entry carries what a reader needs to decide: what it does, who wrote it,
// and the words its author thinks describe it. The index is a repository's own
// file, so this shows what the index says and nothing more.
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { StorePluginSchema } from "@/__generated__";
import { RBtn, RChip, RDialog, RIcon, RTextField } from "@/lib";

const props = defineProps<{
  open: boolean;
  entries: StorePluginSchema[];
  installedIds: string[];
  busyId: string;
  problem: string;
}>();

const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
  (e: "install", pluginId: string): void;
  (e: "refresh"): void;
}>();

const { t } = useI18n();

const query = ref("");
const tag = ref("");

/** Every tag the index uses, once, in the order the entries mention them. */
const tags = computed(() => {
  const seen: string[] = [];
  for (const entry of props.entries) {
    for (const name of entry.tags ?? []) {
      if (!seen.includes(name)) seen.push(name);
    }
  }
  return seen;
});

const shown = computed(() => {
  const needle = query.value.trim().toLowerCase();
  return props.entries.filter((entry) => {
    if (tag.value && !(entry.tags ?? []).includes(tag.value)) return false;
    if (!needle) return true;
    const haystack = [entry.name, entry.description ?? "", entry.author ?? ""]
      .concat(entry.tags ?? [])
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
});

function isInstalled(pluginId: string): boolean {
  return props.installedIds.includes(pluginId);
}

/** The homepage, when it is a web address. The catalogue is a remote file, so
 *  a link from it is held to the schemes a browser may follow. */
function webLink(url: string | null | undefined): string | null {
  if (!url) return null;
  const lower = url.trim().toLowerCase();
  return lower.startsWith("http://") || lower.startsWith("https://")
    ? url.trim()
    : null;
}

function close(): void {
  emit("update:open", false);
}
</script>

<template>
  <RDialog
    :model-value="open"
    icon="mdi-storefront-outline"
    width="860"
    scroll-content
    cancelable
    @update:model-value="emit('update:open', $event)"
  >
    <template #header>
      <span>{{ t("settings.plugins-store-title") }}</span>
    </template>

    <template #content>
      <div class="store">
        <div class="store__bar">
          <RTextField
            v-model="query"
            :placeholder="t('settings.plugins-store-search')"
            prepend-inner-icon="mdi-magnify"
            density="compact"
            hide-details
          />
          <span class="store__count">
            {{ t("settings.plugins-store-count", { count: shown.length }) }}
          </span>
        </div>

        <div v-if="tags.length" class="store__tags">
          <button
            class="store__tag"
            :class="{ 'is-on': tag === '' }"
            type="button"
            @click="tag = ''"
          >
            {{ t("settings.plugins-store-all") }}
          </button>
          <button
            v-for="name in tags"
            :key="name"
            class="store__tag"
            :class="{ 'is-on': tag === name }"
            type="button"
            @click="tag = tag === name ? '' : name"
          >
            {{ name }}
          </button>
        </div>

        <p v-if="problem" class="store__problem">
          {{ problem }}
          <RBtn variant="text" size="small" @click="emit('refresh')">
            {{ t("settings.plugins-store-retry") }}
          </RBtn>
        </p>

        <p v-else-if="!entries.length" class="store__empty">
          {{ t("settings.plugins-store-empty") }}
        </p>

        <p v-else-if="!shown.length" class="store__empty">
          {{ t("settings.plugins-store-nothing") }}
        </p>

        <ul v-else class="store__grid">
          <li v-for="entry in shown" :key="entry.id" class="card">
            <div class="card__head">
              <span class="card__name">{{ entry.name }}</span>
              <RChip size="x-small" variant="text">{{ entry.version }}</RChip>
            </div>
            <p class="card__desc">{{ entry.description }}</p>
            <p v-if="entry.author" class="card__author">
              {{ t("settings.plugins-author", { author: entry.author }) }}
            </p>
            <div v-if="entry.tags?.length" class="card__tags">
              <span v-for="name in entry.tags" :key="name" class="card__tag">
                {{ name }}
              </span>
            </div>
            <div class="card__foot">
              <a
                v-if="webLink(entry.homepage)"
                class="card__link"
                :href="webLink(entry.homepage)!"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ t("settings.plugins-store-homepage") }}
                <RIcon icon="mdi-open-in-new" size="x-small" />
              </a>
              <span v-else />
              <RBtn
                v-if="!isInstalled(entry.id)"
                variant="flat"
                color="primary"
                size="small"
                :disabled="busyId === entry.id"
                @click="emit('install', entry.id)"
              >
                {{ t("settings.plugins-install") }}
              </RBtn>
              <RChip v-else size="x-small" variant="text">
                {{ t("settings.plugins-installed") }}
              </RChip>
            </div>
          </li>
        </ul>
      </div>
    </template>

    <template #footer>
      <RBtn variant="text" @click="close">
        {{ t("common.close") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.store {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 260px;
}

.store__bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.store__bar > :first-child {
  flex: 1;
}

.store__count {
  font-size: 12px;
  opacity: 0.6;
  white-space: nowrap;
}

.store__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.store__tag {
  padding: 3px 10px;
  border: 1px solid var(--r-color-border, rgba(255, 255, 255, 0.16));
  border-radius: 999px;
  background: transparent;
  color: inherit;
  font-size: 12px;
  cursor: pointer;
  opacity: 0.72;
}

.store__tag.is-on {
  border-color: var(--r-color-primary, #7c5cff);
  opacity: 1;
}

.store__problem,
.store__empty {
  margin: 0;
  font-size: 13px;
  opacity: 0.72;
}

.store__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  border: 1px solid var(--r-color-border, rgba(255, 255, 255, 0.12));
  border-radius: 10px;
}

.card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card__name {
  font-weight: 600;
}

.card__desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.45;
  opacity: 0.78;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card__author {
  margin: 0;
  font-size: 12px;
  opacity: 0.55;
}

.card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.card__tag {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  opacity: 0.75;
}

.card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  padding-top: 6px;
}

.card__link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  color: inherit;
  opacity: 0.62;
  text-decoration: none;
}

.card__link:hover {
  opacity: 1;
}
</style>
