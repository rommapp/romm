<script setup lang="ts">
import { onMounted, ref, useSlots } from "vue";
import { useDisplay } from "vuetify";
import EmptyGame from "@/components/Gallery/EmptyGame.vue";
import EmptyPlatform from "@/components/Gallery/EmptyPlatform.vue";

// Props
withDefaults(
  defineProps<{
    modelValue: boolean;
    loadingCondition?: boolean;
    emptyStateCondition?: boolean;
    emptyStateType?: string | null;
    showRommIcon?: boolean;
    icon?: string | null;
  }>(),
  {
    loadingCondition: false,
    emptyStateCondition: false,
    emptyStateType: null,
    showRommIcon: false,
    icon: null,
  }
);
const emit = defineEmits(["update:modelValue", "close"]);
const { xs, mdAndDown, lgAndUp } = useDisplay();
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
    scroll-strategy="none"
    width="auto"
    no-click-animation
    persistent
  >
    <v-card
      :class="{
        desktop: lgAndUp,
        tablet: mdAndDown,
        mobile: xs,
      }"
      rounded="0"
    >
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10" xs="10" sm="11" md="11" lg="11">
            <v-icon v-if="icon" :icon="icon" class="ml-5" />
            <v-avatar v-if="showRommIcon" :rounded="0" :size="30" class="mx-4"
              ><v-img src="/assets/isotipo.svg"
            /></v-avatar>
            <slot name="header"></slot>
          </v-col>
          <v-col cols="2" xs="2" sm="1" md="1" lg="1">
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
        <v-toolbar density="compact" class="bg-primary">
          <slot name="toolbar"></slot>
        </v-toolbar>
        <v-divider />
      </template>

      <v-card-text class="pa-1 scroll">
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

<style scoped>
.desktop {
  width: 60vw;
  height: 90vh;
}

.tablet {
  width: 75vw;
  height: 775px;
}

.mobile {
  width: 85vw;
  height: 775px;
}
</style>
