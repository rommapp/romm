<script setup lang="ts">
import { onMounted, ref, useSlots } from "vue";
import { useTheme } from "vuetify";
import EmptyFirmware from "@/components/common/EmptyStates/EmptyFirmware.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import EmptyPlatform from "@/components/common/EmptyStates/EmptyPlatform.vue";
import RIsotipo from "@/components/common/RIsotipo.vue";

withDefaults(
  defineProps<{
    modelValue: boolean;
    loadingCondition?: boolean;
    emptyStateCondition?: boolean;
    emptyStateType?: string | null;
    expandContentOnEmptyState?: boolean;
    scrollContent?: boolean;
    showRommIcon?: boolean;
    icon?: string | null;
    width?: number | string;
    height?: number | string;
  }>(),
  {
    loadingCondition: false,
    emptyStateCondition: false,
    emptyStateType: null,
    expandContentOnEmptyState: false,
    scrollContent: false,
    showRommIcon: false,
    icon: null,
    width: "auto",
    height: "auto",
  },
);
const emit = defineEmits(["update:modelValue", "close"]);
const hasToolbarSlot = ref(false);
const hasPrependSlot = ref(false);
const hasAppendSlot = ref(false);
const hasFooterSlot = ref(false);
const theme = useTheme();

function closeDialog() {
  emit("update:modelValue", false);
  emit("close");
}

onMounted(() => {
  const slots = useSlots();
  hasToolbarSlot.value = !!slots.toolbar;
  hasPrependSlot.value = !!slots.prepend;
  hasAppendSlot.value = !!slots.append;
  hasFooterSlot.value = !!slots.footer;
});
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    :width="width"
    scroll-strategy="block"
    no-click-animation
    persistent
    z-index="9999"
    :scrim="theme.name.value == 'dark' ? 'black' : 'white'"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
  >
    <v-card :min-height="height" :max-height="height">
      <v-toolbar density="compact" class="bg-toplayer">
        <v-icon v-if="icon" :icon="icon" class="ml-5" />
        <RIsotipo v-if="showRommIcon" :size="30" class="mx-4" />
        <slot name="header" />
        <template #append>
          <v-btn
            size="small"
            variant="text"
            class="rounded"
            icon="mdi-close"
            @click="closeDialog"
          />
        </template>
      </v-toolbar>

      <v-divider />

      <v-toolbar v-if="hasToolbarSlot" density="compact" class="bg-toplayer">
        <slot name="toolbar" />
      </v-toolbar>
      <v-divider />

      <v-card-text v-if="hasPrependSlot" class="pa-0">
        <slot name="prepend" />
      </v-card-text>

      <v-card-text
        id="r-dialog-content"
        class="pa-0 d-flex flex-column"
        :class="{ scroll: scrollContent }"
      >
        <v-row
          v-if="loadingCondition"
          class="justify-center align-center flex-grow-1 my-4"
          no-gutters
        >
          <v-progress-circular
            :width="2"
            :size="40"
            color="primary"
            indeterminate
          />
        </v-row>

        <v-row
          v-if="!loadingCondition && emptyStateCondition"
          class="justify-center align-center flex-grow-1 my-4"
          no-gutters
        >
          <EmptyGame v-if="emptyStateType == 'game'" />
          <EmptyPlatform v-else-if="emptyStateType == 'platform'" />
          <EmptyFirmware v-else-if="emptyStateType == 'firmware'" />
          <slot v-else name="empty-state" />
        </v-row>

        <slot v-if="!loadingCondition && !emptyStateCondition" name="content" />
      </v-card-text>
      <v-card-text v-if="hasAppendSlot" class="pa-0">
        <slot name="append" />
      </v-card-text>

      <template v-if="hasFooterSlot">
        <v-divider />
        <v-toolbar class="bg-toplayer" density="compact">
          <slot name="footer" />
        </v-toolbar>
      </template>
    </v-card>
  </v-dialog>
</template>
