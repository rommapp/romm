<script setup lang="ts">
// LockableField (v2): wraps a single edit-ROM field with a lock toggle.
//
// A locked field is frozen permanently: neither manual edits nor a
// partial/complete rescan can change its value (the backend enforces this
// via the rom's `metadata_locks`). The toggle sits in the field's top-right
// corner (clear of the stacked label on the left and the input row below),
// and the host is expected to disable the wrapped control while locked.
//
// Feature composite, living under `components/EditRom/` next to the
// sections that use it.
import { RBtn } from "@v2/lib";
import { useI18n } from "vue-i18n";

defineProps<{ locked: boolean }>();

const emit = defineEmits<{ toggle: [] }>();

const { t } = useI18n();
</script>

<template>
  <div class="r-v2-lockable" :class="{ 'r-v2-lockable--locked': locked }">
    <slot />
    <RBtn
      class="r-v2-lockable__toggle"
      :icon="locked ? 'mdi-lock' : 'mdi-lock-open-variant'"
      variant="text"
      density="compact"
      :color="locked ? 'primary' : undefined"
      :tooltip="locked ? t('rom.unlock-field') : t('rom.lock-field')"
      :aria-pressed="locked"
      @click="emit('toggle')"
    />
  </div>
</template>

<style scoped>
.r-v2-lockable {
  position: relative;
  min-width: 0;
}

/* Anchored to the top-right so it pairs with the stacked field label on the
   left without overlapping the input row or its clearable adornment. */
.r-v2-lockable__toggle {
  position: absolute;
  top: -4px;
  right: -4px;
  z-index: 1;
}

/* A locked field reads as muted so the frozen state is obvious at a glance. */
.r-v2-lockable--locked {
  opacity: 0.75;
}
</style>
