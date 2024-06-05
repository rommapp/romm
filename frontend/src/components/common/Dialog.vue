<script setup lang="ts">
import { onMounted, ref, useSlots } from "vue";
import EmptyGame from "@/components/Gallery/EmptyGame.vue";
import EmptyPlatform from "@/components/Gallery/EmptyPlatform.vue";
import RommIso from "@/components/common/RommIso.vue";

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
    width?: string;
    height?: string;
  }>(),
  {
    loadingCondition: false,
    emptyStateCondition: false,
    emptyStateType: null,
    expandContentOnEmptyState: false,
    scrollContent: false,
    showRommIcon: false,
    icon: null,
    width: "",
    height: "",
  }
);
const emit = defineEmits(["update:modelValue", "close"]);
const hasToolbarSlot = ref(false);
const hasFooterSlot = ref(false);

// Functions
function closeDialog() {
  emit("update:modelValue", false);
  emit("close");
}

onMounted(() => {
  const slots = useSlots();
  hasToolbarSlot.value = !!slots.toolbar;
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
    <v-card rounded="0" :height="height">
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10" sm="11">
            <v-icon v-if="icon" :icon="icon" class="ml-5" />
            <romm-iso :size="30" class="mx-4" v-if="showRommIcon" />
            <slot name="header"></slot>
          </v-col>
          <v-col cols="2" sm="1">
            <v-btn
              @click="closeDialog"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider />

      <template v-if="hasToolbarSlot">
        <v-toolbar density="compact" class="bg-terciary">
          <slot name="toolbar"></slot>
        </v-toolbar>
        <v-divider />
      </template>

      <v-card-text class="pa-1" :class="{ scroll: scrollContent }">
        <v-row
          v-if="loadingCondition"
          class="justify-center align-center fill-height"
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
          class="justify-center align-center fill-height"
          no-gutters
        >
          <empty-game v-if="emptyStateType == 'game'" />
          <empty-platform v-else-if="emptyStateType == 'platform'" />
          <slot v-else name="emptyState"></slot>
        </v-row>

        <slot name="content"></slot>
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
