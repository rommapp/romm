<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

const emitter = inject<Emitter<Events>>("emitter");
</script>
<template>
  <v-btn icon variant="flat" :to="{ name: 'search' }"
    ><v-icon :color="$route.name == 'search' ? 'primary' : ''"
      >mdi-magnify</v-icon
    ></v-btn
  >
</template>
