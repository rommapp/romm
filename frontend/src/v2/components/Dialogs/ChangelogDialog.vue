<script setup lang="ts">
// v2 ChangelogDialog — emitter-driven. Fetches the latest releases from
// the public GitHub API on first open and reuses the cached payload on
// subsequent opens within the same session. Each release renders as a
// glass-panel block (tag + date) with the release body rendered through
// MdPreview, the same markdown surface NotesTab uses.
import { RBtn, RDialog, REmptyState, RIcon, RSpinner } from "@v2/lib";
import { MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { Events } from "@/types/emitter";
import { useThemeMode } from "@/v2/composables/useThemeMode";

defineOptions({ inheritAttrs: false });

type Release = {
  tag_name: string;
  name: string | null;
  html_url: string;
  published_at: string;
  body: string;
  prerelease: boolean;
  draft: boolean;
};

const RELEASES_URL =
  "https://api.github.com/repos/rommapp/romm/releases?per_page=10";
const RELEASES_PAGE_URL = "https://github.com/rommapp/romm/releases";

const { t, locale } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const { isLight: isLightTheme } = useThemeMode();

const show = ref(false);
const loading = ref(false);
const error = ref(false);
// Module-level cache would share across instances, but the dialog is
// mounted once in GlobalDialogs, so an instance ref is enough and keeps
// teardown trivial.
const releases = ref<Release[]>([]);

const mdTheme = computed<"light" | "dark">(() =>
  isLightTheme.value ? "light" : "dark",
);

const dateFormatter = computed(
  () =>
    new Intl.DateTimeFormat(locale.value.replace("_", "-"), {
      year: "numeric",
      month: "short",
      day: "numeric",
    }),
);

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return dateFormatter.value.format(d);
}

async function fetchReleases() {
  loading.value = true;
  error.value = false;
  try {
    const res = await fetch(RELEASES_URL, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!res.ok) throw new Error(`GitHub ${res.status}`);
    const data: Release[] = await res.json();
    releases.value = data.filter((r) => !r.draft && !r.prerelease);
  } catch (e) {
    console.error("Changelog fetch failed", e);
    error.value = true;
  } finally {
    loading.value = false;
  }
}

const openHandler = () => {
  show.value = true;
  // Refetch only when we have nothing yet (or a previous attempt
  // errored). Keeps the dialog snappy on subsequent opens.
  if (releases.value.length === 0 && !loading.value) fetchReleases();
};
emitter?.on("showChangelogDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showChangelogDialog", openHandler));

function closeDialog() {
  show.value = false;
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-clock-outline"
    width="min(720px, max(50vw, 480px))"
    height="80vh"
    scroll-content
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("common.changelog") }}</span>
    </template>

    <template #content>
      <div
        class="r-v2-changelog"
        :class="{
          'r-v2-changelog--center': loading || error || releases.length === 0,
        }"
      >
        <div v-if="loading" class="r-v2-changelog__state">
          <RSpinner :size="28" />
          <span class="r-v2-changelog__state-label">
            {{ t("common.changelog-loading") }}
          </span>
        </div>

        <REmptyState
          v-else-if="error"
          icon="mdi-alert-circle-outline"
          :title="t('common.changelog-error-title')"
          :hint="t('common.changelog-error-hint')"
        >
          <template #actions>
            <RBtn variant="flat" color="primary" @click="fetchReleases">
              {{ t("common.try-again") }}
            </RBtn>
          </template>
        </REmptyState>

        <REmptyState
          v-else-if="releases.length === 0"
          icon="mdi-tray-remove"
          :title="t('common.changelog-empty-title')"
          :hint="t('common.changelog-empty-hint')"
        />

        <article
          v-for="r in releases"
          v-else
          :key="r.tag_name"
          class="r-v2-changelog__release"
        >
          <header class="r-v2-changelog__release-head">
            <a
              :href="r.html_url"
              target="_blank"
              rel="noopener noreferrer"
              class="r-v2-changelog__tag"
            >
              {{ r.tag_name }}
            </a>
            <span class="r-v2-changelog__date">{{
              fmtDate(r.published_at)
            }}</span>
          </header>
          <MdPreview
            no-highlight
            no-katex
            no-mermaid
            :model-value="r.body || ''"
            :theme="mdTheme"
            language="en-US"
            preview-theme="vuepress"
            code-theme="github"
            class="r-v2-changelog__body"
          />
        </article>
      </div>
    </template>

    <template #footer>
      <a
        :href="RELEASES_PAGE_URL"
        target="_blank"
        rel="noopener noreferrer"
        class="r-v2-changelog__view-all"
      >
        <RIcon icon="mdi-github" size="16" />
        <span>{{ t("common.changelog-view-all") }}</span>
        <RIcon icon="mdi-open-in-new" size="12" />
      </a>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-changelog {
  display: flex;
  flex-direction: column;
  gap: 36px;
  min-width: 0;
  min-height: 0;
  /* Extra breathing room under the last release so it doesn't touch
     the footer border once scrolled to the end. */
  padding-bottom: 12px;
}
.r-v2-changelog--center {
  flex: 1;
  align-items: center;
  justify-content: center;
}

.r-v2-changelog__state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--r-color-fg-muted);
}
.r-v2-changelog__state-label {
  font-size: var(--r-font-size-sm);
}

.r-v2-changelog__release {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.r-v2-changelog__release-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.r-v2-changelog__tag {
  font-size: 12px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
  border: 1px solid
    color-mix(in srgb, var(--r-color-brand-primary) 25%, transparent);
  border-radius: 6px;
  padding: 2px 8px;
  text-decoration: none;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-changelog__tag:hover {
  background: color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 45%,
    transparent
  );
}

.r-v2-changelog__date {
  font-size: 11px;
  color: var(--r-color-fg-muted);
}

.r-v2-changelog__body {
  border-radius: var(--r-radius-lg);
  background: color-mix(in srgb, black 22%, transparent);
  padding: 6px 16px;
  min-width: 0;
  overflow: hidden;
}
/* md-editor surface tweaks — the preview ships its own white card; we
   strip it and let the tinted body wrapper provide the surface. Same
   approach NotesTab uses. */
.r-v2-changelog__body :deep(.md-editor),
.r-v2-changelog__body :deep(.md-editor-preview-wrapper) {
  background: transparent;
  color: var(--r-color-fg);
  padding: 0;
}
.r-v2-changelog__body :deep(.md-editor-preview) {
  background: transparent !important;
  color: var(--r-color-fg);
  font-family: inherit;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.55;
  padding: 0;
}
.r-v2-changelog__body :deep(.md-editor-preview pre) {
  white-space: pre-wrap;
  word-break: break-word;
  max-width: 100%;
}
.r-v2-changelog__body :deep(.md-editor-preview img) {
  max-width: 100%;
  height: auto;
}
.r-v2-changelog__body :deep(.md-editor-preview blockquote) {
  border-left-color: var(--r-color-border-strong);
}
.r-v2-changelog__body :deep(.md-editor-preview code),
.r-v2-changelog__body :deep(.md-editor-preview pre) {
  background: color-mix(in srgb, black 30%, transparent) !important;
  color: var(--r-color-fg) !important;
}
.r-v2-changelog__body :deep(.md-editor-preview a) {
  color: var(--r-color-brand-primary);
}

.r-v2-changelog__view-all {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--r-color-fg-secondary);
  text-decoration: none;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-medium);
  padding: 4px 8px;
  border-radius: var(--r-radius-md);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-changelog__view-all:hover {
  color: var(--r-color-brand-primary);
}
</style>
