<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

const emitter = inject<Emitter<Events>>("emitter");
</script>
<template>
  <v-btn icon variant="flat" rounded="0" :to="{ name: 'search' }"
    ><v-icon :color="$route.name == 'search' ? 'romm-accent-1' : ''"
      >mdi-magnify</v-icon
    ></v-btn
  >
</template>
