<script setup lang="ts">
import EmptyFirmware from "@/components/common/EmptyStates/EmptyFirmware.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import EmptyPlatform from "@/components/common/EmptyStates/EmptyPlatform.vue";
import RIsotipo from "@/components/common/RIsotipo.vue";
import { onMounted, ref, useSlots } from "vue";

// Props
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
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
    :model-value="modelValue"
    :scrim="true"
    :width="width"
    scroll-strategy="block"
    no-click-animation
    persistent
  >
    <v-card rounded="0" :min-height="height" :max-height="height">
      <v-toolbar density="compact" class="bg-terciary">
        <v-icon v-if="icon" :icon="icon" class="ml-5" />
        <r-isotipo :size="30" class="mx-4" v-if="showRommIcon" />
        <slot name="header"></slot>
        <template #append>
          <v-btn
            @click="closeDialog"
            rounded="0"
            variant="text"
            icon="mdi-close"
          />
        </template>
      </v-toolbar>

      <v-divider />

      <v-toolbar v-if="hasToolbarSlot" density="compact" class="bg-terciary">
        <slot name="toolbar"></slot>
      </v-toolbar>
      <v-divider />

      <v-card-text v-if="hasPrependSlot" class="pa-1">
        <slot name="prepend"></slot>
      </v-card-text>

      <v-card-text
        id="r-dialog-content"
        class="pa-1 d-flex flex-column"
        :class="{ scroll: scrollContent }"
      >
        <v-row
          v-if="loadingCondition"
          class="justify-center align-center flex-grow-1"
          no-gutters
        >
          <v-progress-circular
            :width="2"
            :size="40"
            color="romm-accent-1"
            indeterminate
          />
        </v-row>

        <v-row
          v-if="!loadingCondition && emptyStateCondition"
          class="justify-center align-center flex-grow-1"
          no-gutters
        >
          <empty-game v-if="emptyStateType == 'game'" />
          <empty-platform v-else-if="emptyStateType == 'platform'" />
          <empty-firmware v-else-if="emptyStateType == 'firmware'" />
          <slot v-else name="emptyState"></slot>
        </v-row>

        <slot
          v-if="!loadingCondition && !emptyStateCondition"
          name="content"
        ></slot>
      </v-card-text>
      <v-card-text v-if="hasAppendSlot" class="pa-1">
        <slot name="append"></slot>
      </v-card-text>

      <template v-if="hasFooterSlot">
        <v-divider />
        <v-toolbar class="bg-terciary" density="compact">
          <slot name="footer"></slot>
        </v-toolbar>
      </template>
    </v-card>
  </v-dialog>
</template>
