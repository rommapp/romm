<script lang="ts" setup>
withDefaults(
  defineProps<{
    text: string;
    size?: number;
    chip?: boolean;
    chipLabel?: boolean;
    chipSize?: "x-small" | "small" | "default" | "large";
    chipDensity?: "compact" | "comfortable";
  }>(),
  {
    size: 20,
    text: "",
    chip: false,
    chipLabel: false,
    chipSize: "default",
    chipDensity: "comfortable",
  },
);
</script>
<template>
  <v-chip
    v-if="chip"
    class="translucent-dark"
    :density="chipDensity"
    color="secondary"
    :label="chipLabel"
    :size="chipSize"
  >
    <v-tooltip
      location="top"
      class="tooltip"
      transition="fade-transition"
      :text="text"
      open-delay="500"
      activator="parent"
    />
    <v-icon>mdi-folder-question</v-icon>
  </v-chip>
  <span v-else>
    <v-tooltip
      location="top"
      class="tooltip"
      transition="fade-transition"
      :text="text"
      open-delay="500"
      activator="parent"
    />
    <v-icon color="secondary" :size="size">mdi-folder-question</v-icon>
  </span>
</template>
<style scoped>
.v-icon {
  opacity: 1 !important;
}
</style>
