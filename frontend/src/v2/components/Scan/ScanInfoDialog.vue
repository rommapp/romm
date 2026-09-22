<script setup lang="ts">
// ScanInfoDialog — reference card for the Scan view. Two tabs (same
// underlined-pill pattern as GameDetails): "Scan types" explains what
// each scan does in long form (matching v1's reference card); "Metadata
// providers" lists every provider RomM can talk to with one-line setup
// notes. Pure static content — it's a lookup card, not a configurator.
//
// Why static descriptions instead of i18n: the v1 `scan-types-info`
// key shipped as one HTML blob with `<strong>` + `<br>` — hard to
// translate by section and harder to restyle. Embedding the text as
// typed arrays here keeps the layout flexible. If i18n becomes
// necessary, each row maps cleanly to a key.
import { RDialog, RIcon, RTabNav } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import MetadataProviderCard from "@/v2/components/shared/MetadataProviderCard/MetadataProviderCard.vue";
import {
  groupProviders,
  SETUP_GROUP_LABELS,
} from "@/v2/utils/metadataProviderGroups";
import { METADATA_PROVIDER_INFO } from "@/v2/utils/metadataProviderInfo";

defineProps<{
  modelValue: boolean;
}>();

defineEmits<{
  (e: "update:modelValue", value: boolean): void;
}>();

const { t } = useI18n();

type TabId = "types" | "providers";
const activeTab = ref<TabId>("types");

const tabs = computed(() => [
  {
    id: "types" as const,
    label: t("scan.scan-types", "Scan types"),
    icon: "mdi-magnify-scan",
  },
  {
    id: "providers" as const,
    label: t("scan.metadata-sources", "Metadata providers"),
    icon: "mdi-database-search",
  },
]);

const docsUrl = computed(() =>
  activeTab.value === "providers"
    ? "https://docs.romm.app/latest/Getting-Started/Metadata-Providers/"
    : "https://docs.romm.app/latest/Usage/LibraryManagement/#scan",
);

interface ScanTypeRow {
  id: string;
  title: string;
  // Long-form description — single paragraph or `\n\n`-separated. The
  // template splits on double-newline so each paragraph gets its own
  // `<p>` for spacing.
  desc: string;
}

const scanTypes = computed<ScanTypeRow[]>(() => [
  {
    id: "new_platforms",
    title: t("scan.new-platforms"),
    desc: t("scan.info-new-platforms-desc"),
  },
  {
    id: "quick",
    title: t("scan.quick-scan"),
    desc: t("scan.info-quick-scan-desc"),
  },
  {
    id: "unmatched",
    title: t("scan.unmatched-games"),
    desc: t("scan.info-unmatched-games-desc"),
  },
  {
    id: "update",
    title: t("scan.update-metadata"),
    desc: t("scan.info-update-metadata-desc"),
  },
  {
    id: "hashes",
    title: t("scan.hashes"),
    desc: t("scan.info-hashes-desc"),
  },
  {
    id: "title_ids",
    title: t("scan.title-ids"),
    desc: t("scan.info-title-ids-desc"),
  },
  {
    id: "complete",
    title: t("scan.complete-rescan"),
    desc: t("scan.info-complete-rescan-desc"),
  },
]);

// Static reference set: names, logos and `setup.*` locale keys come
// from the shared provider registry so the Setup Wizard's Step 3 and
// this dialog never drift.
const providerGroups = groupProviders(
  METADATA_PROVIDER_INFO,
  SETUP_GROUP_LABELS,
);

// Split a multi-line description on double-newline so each paragraph
// renders in its own `<p>`. Single newlines stay inline.
function paragraphs(text: string): string[] {
  return text
    .split("\n\n")
    .map((p) => p.trim())
    .filter(Boolean);
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-information-outline"
    width="640px"
    height="640px"
    scroll-content
    @update:model-value="(v) => $emit('update:modelValue', v)"
  >
    <template #header>
      {{ t("scan.info-dialog-title", "Scan reference") }}
    </template>

    <template #toolbar>
      <RTabNav
        v-model="activeTab"
        :items="tabs"
        variant="underlined"
        size="small"
      />
    </template>

    <template #content>
      <div v-if="activeTab === 'types'" class="r-v2-scan-info__list">
        <article
          v-for="st in scanTypes"
          :key="st.id"
          class="r-v2-scan-info__row"
        >
          <h4 class="r-v2-scan-info__row-name">{{ st.title }}</h4>
          <div class="r-v2-scan-info__row-desc">
            <p
              v-for="(para, i) in paragraphs(st.desc)"
              :key="i"
              class="r-v2-scan-info__para"
            >
              {{ para }}
            </p>
          </div>
        </article>
      </div>

      <div v-else class="r-v2-scan-info__list">
        <!-- Section labels and per-provider strings come from the same
             `setup.*` locale keys the Setup Wizard's Step 3 uses, so the
             two views stay in sync. -->
        <section
          v-for="group in providerGroups"
          :key="group.group"
          class="r-v2-scan-info__section"
          :data-group="group.group"
        >
          <header class="r-v2-scan-info__section-head">
            <span>{{ t(group.titleKey) }}</span>
            <p class="r-v2-scan-info__section-hint">
              {{ t(group.hintKey) }}
            </p>
          </header>
          <MetadataProviderCard
            v-for="p in group.providers"
            :key="p.key"
            layout="row"
            name-tag="h4"
            :data-provider="p.key"
            :name="p.name"
            :logo="p.logo"
            :setup-hint="t(p.setupKey)"
            :caveat="p.caveatKey ? t(p.caveatKey) : undefined"
          >
            <template #description>{{ t(p.descKey) }}</template>
          </MetadataProviderCard>
        </section>
      </div>
    </template>

    <template #footer>
      <a
        :href="docsUrl"
        target="_blank"
        rel="noopener"
        class="r-v2-scan-info__doc-link"
      >
        {{ t("scan.info-full-docs", "Read the full docs") }}
        <RIcon icon="mdi-open-in-new" size="12" />
      </a>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-scan-info__list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Section grouping inside the providers tab — header + rows. The
   header is intentionally lightweight: small caps, muted icon, and an
   inline hint that explains the section in one sentence. */
.r-v2-scan-info__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-v2-scan-info__section-head {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  column-gap: 8px;
  row-gap: 2px;
  color: var(--r-color-fg-secondary);
}

.r-v2-scan-info__section-head > span {
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.r-v2-scan-info__section-hint {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
}
.r-v2-scan-info__row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 14px;
  padding: 12px 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-v2-scan-info__row-name {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  align-self: flex-start;
  min-width: 0;
  /* Long titles wrap inside the 140px column. */
  overflow-wrap: anywhere;
}
.r-v2-scan-info__row-desc {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.r-v2-scan-info__para {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--r-color-fg-secondary);
}

.r-v2-scan-info__doc-link {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-brand-primary);
  text-decoration: none;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-scan-info__doc-link:hover {
  color: var(--r-color-fg);
  text-decoration: underline;
}

/* Mobile — the 140px column for names gets tight at small widths.
   Stack name + desc vertically on narrow viewports. */
html[data-bp~="sm-and-down"] .r-v2-scan-info__row {
  grid-template-columns: 1fr;
  gap: 8px;
}
</style>
