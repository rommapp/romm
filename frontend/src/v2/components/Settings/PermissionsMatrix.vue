<script setup lang="ts">
// PermissionsMatrix — entity (rows) x action (columns) grid of tri-state
// checkboxes for the group editor. Each cell cycles none -> full -> own ->
// none: "none" is no grant, "full" is library-wide (primary), "own" limits
// the grant to the user's own items (accent, own_only). The model is the list
// of granted (entity, action) pairs; cycling rewrites the touched cell only.
import { RCheckbox, type RCheckboxState, RTooltip } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { GrantSchemaIO, PermAction, PermEntity } from "@/__generated__";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: GrantSchemaIO[];
  entities: PermEntity[];
  actions: PermAction[];
  readonly?: boolean;
}>();

const emit = defineEmits<{ "update:modelValue": [GrantSchemaIO[]] }>();

const { t } = useI18n();

type CellState = "none" | "full" | "own";

const gridStyle = computed(() => ({
  gridTemplateColumns: `minmax(110px, 1.4fr) repeat(${props.actions.length}, minmax(60px, 1fr))`,
}));

function grantOf(
  entity: PermEntity,
  action: PermAction,
): GrantSchemaIO | undefined {
  return props.modelValue.find(
    (g) => g.entity === entity && g.action === action,
  );
}

function stateOf(entity: PermEntity, action: PermAction): CellState {
  const g = grantOf(entity, action);
  if (!g) return "none";
  return g.own_only ? "own" : "full";
}

// Cycle: none (empty) -> full (primary check) -> own (accent person).
const PERM_STATES: RCheckboxState[] = [
  { value: "none" },
  { value: "full", color: "primary" },
  { value: "own", color: "accent", icon: "mdi-account" },
];

function onState(entity: PermEntity, action: PermAction, value: string) {
  if (props.readonly) return;
  const without = props.modelValue.filter(
    (g) => !(g.entity === entity && g.action === action),
  );
  if (value === "none") {
    emit("update:modelValue", without);
  } else {
    emit("update:modelValue", [
      ...without,
      { entity, action, own_only: value === "own" },
    ]);
  }
}

function stateLabel(state: CellState): string {
  return t(`settings.grant-${state}`);
}

// Extra explanation shown under the state label in the tooltip; only "own"
// needs spelling out (the others are self-evident from their label).
function stateHint(state: CellState): string {
  return state === "own" ? t("settings.perm-own-only-hint") : "";
}

const entityLabel = (e: PermEntity) => t(`settings.perm-entity.${e}`);
const actionLabel = (a: PermAction) => t(`settings.perm-action.${a}`);

// Per-column select-all: granted = any non-"none" state for the action.
function columnAllGranted(a: PermAction): boolean {
  return (
    props.entities.length > 0 &&
    props.entities.every((e) => stateOf(e, a) !== "none")
  );
}
function columnSomeGranted(a: PermAction): boolean {
  return props.entities.some((e) => stateOf(e, a) !== "none");
}
function toggleColumn(a: PermAction, value: boolean) {
  if (props.readonly) return;
  const without = props.modelValue.filter((g) => g.action !== a);
  if (value) {
    emit("update:modelValue", [
      ...without,
      ...props.entities.map((e) => ({ entity: e, action: a, own_only: false })),
    ]);
  } else {
    emit("update:modelValue", without);
  }
}
</script>

<template>
  <div class="r-v2-perm-matrix">
    <div class="r-v2-perm-matrix__head" :style="gridStyle">
      <span class="r-v2-perm-matrix__corner">
        {{ t("settings.perm-entity-label") }}
      </span>
      <div v-for="a in actions" :key="a" class="r-v2-perm-matrix__col">
        <span class="r-v2-perm-matrix__col-label" :title="actionLabel(a)">
          {{ actionLabel(a) }}
        </span>
        <RCheckbox
          bare
          size="sm"
          color="primary"
          :model-value="columnAllGranted(a)"
          :indeterminate="columnSomeGranted(a) && !columnAllGranted(a)"
          :disabled="readonly"
          :aria-label="`${t('rom.select-all')} ${actionLabel(a)}`"
          @update:model-value="(v) => toggleColumn(a, v)"
        />
      </div>
    </div>

    <div
      v-for="e in entities"
      :key="e"
      class="r-v2-perm-matrix__row"
      :style="gridStyle"
    >
      <span class="r-v2-perm-matrix__entity">{{ entityLabel(e) }}</span>
      <div v-for="a in actions" :key="a" class="r-v2-perm-matrix__cell">
        <RTooltip
          activator="parent"
          location="top"
          :text="stateLabel(stateOf(e, a))"
          :hint="stateHint(stateOf(e, a))"
        />
        <RCheckbox
          bare
          size="sm"
          :states="PERM_STATES"
          :state-value="stateOf(e, a)"
          :disabled="readonly"
          :aria-label="`${entityLabel(e)} ${actionLabel(a)} ${stateLabel(stateOf(e, a))}`"
          @update:state-value="(v) => onState(e, a, v)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-v2-perm-matrix {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--r-color-border);
  border-radius: 10px;
  overflow: hidden;
}

.r-v2-perm-matrix__head,
.r-v2-perm-matrix__row {
  display: grid;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
}

.r-v2-perm-matrix__head {
  background: var(--r-color-surface);
  border-bottom: 1px solid var(--r-color-border);
}

.r-v2-perm-matrix__row:not(:last-child) {
  border-bottom: 1px solid var(--r-color-border);
}

.r-v2-perm-matrix__corner,
.r-v2-perm-matrix__col-label {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--r-color-fg-secondary);
}

.r-v2-perm-matrix__col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  text-align: center;
}

.r-v2-perm-matrix__entity {
  font-weight: var(--r-font-weight-semibold);
  text-transform: capitalize;
}

.r-v2-perm-matrix__cell {
  display: flex;
  justify-content: center;
}
</style>
