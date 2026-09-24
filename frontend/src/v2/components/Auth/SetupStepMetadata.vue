<script setup lang="ts">
// SetupStepMetadata: Step 3 of the setup wizard. Informational only.
//
// Sections come from the shared provider taxonomy; each provider is
// rendered with the shared MetadataProviderCard (row layout) from the
// shared provider registry.
//
// For each source we surface two pieces of state separately:
//   * `disabled`  (admin flag from heartbeat) whether the provider is
//                 enabled server-side, i.e. has any API key configured
//   * probe state (runtime probe via /heartbeat/metadata) whether the
//                 configured key actually works
// The combined status pill maps these to one of: disabled, missing /
// invalid key, checking, available.
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeHeartbeat from "@/stores/heartbeat";
import MetadataProviderCard from "@/v2/components/shared/MetadataProviderCard/MetadataProviderCard.vue";
import type { ProviderCardStatus } from "@/v2/components/shared/MetadataProviderCard/types";
import {
  groupProviders,
  SETUP_GROUP_LABELS,
} from "@/v2/utils/metadataProviderGroups";
import {
  METADATA_PROVIDER_INFO,
  type MetadataProviderInfo,
} from "@/v2/utils/metadataProviderInfo";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const heartbeat = storeHeartbeat();

type ProbeState = "pending" | "ok" | "ko";

interface Source extends MetadataProviderInfo {
  disabled: boolean;
}

const probeStatus = ref<Record<string, ProbeState>>({});

const sources = computed<Source[]>(() =>
  METADATA_PROVIDER_INFO.map((info) => ({
    ...info,
    disabled: !heartbeat.value.METADATA_SOURCES?.[info.enabledFlag],
  })),
);

const groups = computed(() =>
  groupProviders(sources.value, SETUP_GROUP_LABELS),
);

function statusOf(source: Source): ProviderCardStatus {
  if (source.disabled) {
    // Flag-only providers have no key to be "missing"
    return {
      label: source.requiresKey
        ? t("setup.metadata-status-key-missing")
        : t("setup.metadata-status-disabled"),
      icon: source.requiresKey
        ? "mdi-key-alert-outline"
        : "mdi-power-plug-off-outline",
      tone: "warning",
    };
  }
  const probe = probeStatus.value[source.key] ?? "pending";
  if (probe === "ok") {
    return {
      label: t("setup.metadata-status-available"),
      icon: "mdi-check-circle-outline",
      tone: "success",
    };
  }
  if (probe === "ko") {
    // For flag-only providers a failed probe means the
    // service is unreachable, not that an API key is invalid.
    return {
      label: source.requiresKey
        ? t("setup.metadata-status-key-invalid")
        : t("setup.metadata-status-unreachable"),
      icon: "mdi-alert-circle-outline",
      tone: "danger",
    };
  }
  return {
    label: t("setup.metadata-status-checking"),
    icon: "mdi-progress-helper",
    tone: "neutral",
  };
}

function itemDataState(source: Source): "available" | "checking" | "missing" {
  if (source.disabled) return "missing";
  const probe = probeStatus.value[source.key];
  if (probe === "ok") return "available";
  return "checking";
}

async function probeAll() {
  await Promise.all(
    sources.value
      .filter((source) => !source.disabled)
      .map(async (source) => {
        probeStatus.value[source.key] = "pending";
        const ok = await heartbeat.fetchMetadataHeartbeat(source.key);
        probeStatus.value[source.key] = ok ? "ok" : "ko";
      }),
  );
}

onMounted(() => {
  void probeAll();
});
</script>

<template>
  <section class="r-setup-metadata">
    <p class="r-setup-metadata__lead">
      {{ t("setup.metadata-sources-intro") }}
    </p>

    <div class="r-setup-metadata__scroll">
      <div
        v-for="group in groups"
        :key="group.group"
        class="r-setup-metadata__group"
        :data-group="group.group"
      >
        <header class="r-setup-metadata__group-head">
          <div class="r-setup-metadata__group-title">
            <span>{{ t(group.titleKey) }}</span>
          </div>
          <p class="r-setup-metadata__group-hint">
            {{ t(group.hintKey) }}
          </p>
        </header>

        <ul class="r-setup-metadata__items">
          <li v-for="source in group.providers" :key="source.key">
            <MetadataProviderCard
              layout="row"
              class="r-setup-metadata__item"
              :data-provider="source.key"
              :data-state="itemDataState(source)"
              :name="source.name"
              :logo="source.logo"
              :status="statusOf(source)"
              :setup-hint="t(source.setupKey)"
              :caveat="source.caveatKey ? t(source.caveatKey) : undefined"
              :dimmed="source.disabled"
            >
              <template #description>{{ t(source.descKey) }}</template>
            </MetadataProviderCard>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.r-setup-metadata {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
}

.r-setup-metadata__lead {
  margin: 0 auto;
  max-width: 900px;
  text-align: center;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
  line-height: var(--r-line-height-normal);
}

.r-setup-metadata__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-5);
  padding-right: var(--r-space-1);
}

/* ── Group chrome ────────────────────────────────────────────────── */
.r-setup-metadata__group {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-setup-metadata__group-head {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
}

.r-setup-metadata__group-title {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-secondary);
}

.r-setup-metadata__group-hint {
  margin: 0;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}

/* ── Items ───────────────────────────────────────────────────────── */
.r-setup-metadata__items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr));
  gap: var(--r-space-2);
}

/* The card fills its list cell so rows stay equal-height. */
.r-setup-metadata__item {
  height: 100%;
}

/* Wizard-only state tint on top of the shared card chrome. */
.r-setup-metadata__item[data-state="available"] {
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-success) 30%,
    transparent
  );
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 6%,
    transparent
  );
}
</style>
