<script setup lang="ts">
// OverridesMatrix — per-user permission overrides on top of the user's
// group. Each (entity, action) cell is a multi-state checkbox cycling
// inherit (defer to group) -> grant (force-allow, primary) -> grant-own
// (force-allow own items, accent) -> revoke (force-deny, danger). The
// model is the list of explicit overrides (absence of a cell = inherit).
import { RCheckbox, type RCheckboxState, RTooltip } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { OverrideSchemaIO, PermAction, PermEntity } from "@/__generated__";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: OverrideSchemaIO[];
  entities: PermEntity[];
  actions: PermAction[];
}>();

const emit = defineEmits<{ "update:modelValue": [OverrideSchemaIO[]] }>();

const { t } = useI18n();

type CellState = "inherit" | "grant" | "grant_own" | "revoke";

const gridStyle = computed(() => ({
  gridTemplateColumns: `minmax(110px, 1.4fr) repeat(${props.actions.length}, minmax(60px, 1fr))`,
}));

function stateOf(entity: PermEntity, action: PermAction): CellState {
  const o = props.modelValue.find(
    (x) => x.entity === entity && x.action === action,
  );
  if (!o) return "inherit";
  if (!o.granted) return "revoke";
  return o.own_only ? "grant_own" : "grant";
}

// Cycle: inherit (empty) -> grant (primary check) -> grant-own (accent
// person) -> revoke (danger cross).
const OVR_STATES: RCheckboxState[] = [
  { value: "inherit" },
  { value: "grant", color: "primary" },
  { value: "grant_own", color: "accent", icon: "mdi-account" },
  { value: "revoke", color: "danger", icon: "mdi-close" },
];

function onState(entity: PermEntity, action: PermAction, value: string) {
  const without = props.modelValue.filter(
    (x) => !(x.entity === entity && x.action === action),
  );
  if (value === "inherit") {
    emit("update:modelValue", without);
    return;
  }
  emit("update:modelValue", [
    ...without,
    {
      entity,
      action,
      granted: value !== "revoke",
      own_only: value === "grant_own",
    },
  ]);
}

function stateLabel(state: CellState): string {
  return t(`settings.override-${state.replace("_", "-")}`);
}

// Only "grant-own" needs spelling out beyond its label.
function stateHint(state: CellState): string {
  return state === "grant_own" ? t("settings.perm-own-only-hint") : "";
}

const entityLabel = (e: PermEntity) => t(`settings.perm-entity.${e}`);
const actionLabel = (a: PermAction) => t(`settings.perm-action.${a}`);

// Per-column select-all: "set" = any non-"inherit" override for the action.
// Selecting all applies a plain grant; clearing returns the column to inherit.
function columnAllSet(a: PermAction): boolean {
  return (
    props.entities.length > 0 &&
    props.entities.every((e) => stateOf(e, a) !== "inherit")
  );
}
function columnSomeSet(a: PermAction): boolean {
  return props.entities.some((e) => stateOf(e, a) !== "inherit");
}
function toggleColumn(a: PermAction, value: boolean) {
  const without = props.modelValue.filter((x) => x.action !== a);
  if (value) {
    emit("update:modelValue", [
      ...without,
      ...props.entities.map((e) => ({
        entity: e,
        action: a,
        granted: true,
        own_only: false,
      })),
    ]);
  } else {
    emit("update:modelValue", without);
  }
}
</script>

<template>
  <div class="r-v2-ovr-matrix">
    <div class="r-v2-ovr-matrix__head" :style="gridStyle">
      <span class="r-v2-ovr-matrix__corner">
        {{ t("settings.perm-entity-label") }}
      </span>
      <div v-for="a in actions" :key="a" class="r-v2-ovr-matrix__col">
        <span class="r-v2-ovr-matrix__col-label">{{ actionLabel(a) }}</span>
        <RCheckbox
          bare
          size="sm"
          color="primary"
          :model-value="columnAllSet(a)"
          :indeterminate="columnSomeSet(a) && !columnAllSet(a)"
          :aria-label="`${t('rom.select-all')} ${actionLabel(a)}`"
          @update:model-value="(v) => toggleColumn(a, v)"
        />
      </div>
    </div>

    <div
      v-for="e in entities"
      :key="e"
      class="r-v2-ovr-matrix__row"
      :style="gridStyle"
    >
      <span class="r-v2-ovr-matrix__entity">{{ entityLabel(e) }}</span>
      <div v-for="a in actions" :key="a" class="r-v2-ovr-matrix__cell">
        <RTooltip
          activator="parent"
          location="top"
          :text="stateLabel(stateOf(e, a))"
          :hint="stateHint(stateOf(e, a))"
        />
        <RCheckbox
          bare
          size="sm"
          :states="OVR_STATES"
          :state-value="stateOf(e, a)"
          :aria-label="`${entityLabel(e)} ${actionLabel(a)} ${stateLabel(stateOf(e, a))}`"
          @update:state-value="(v) => onState(e, a, v)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-v2-ovr-matrix {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--r-color-border);
  border-radius: 10px;
  overflow: hidden;
}
.r-v2-ovr-matrix__head,
.r-v2-ovr-matrix__row {
  display: grid;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
}
.r-v2-ovr-matrix__head {
  background: var(--r-color-surface);
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-ovr-matrix__row:not(:last-child) {
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-ovr-matrix__corner,
.r-v2-ovr-matrix__col-label {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--r-color-fg-secondary);
}
.r-v2-ovr-matrix__col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  text-align: center;
}
.r-v2-ovr-matrix__entity {
  font-weight: var(--r-font-weight-semibold);
  text-transform: capitalize;
}
.r-v2-ovr-matrix__cell {
  display: flex;
  justify-content: center;
}
</style>
