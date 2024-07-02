<script setup lang="ts">
import { useTheme } from "vuetify";

withDefaults(defineProps<{ src?: string | null; size?: number }>(), { size: 45 });
const theme = useTheme();
</script>

<template>
  <v-avatar :rounded="0" :size="size">
    <v-img
      :src="
        src ?? `/assets/default/cover/big_${theme.global.name.value}_empty.png`
      "
    >
      <template #error>
        <v-img
          :src="`assets/default/cover/big_${theme.global.name.value}_empty.png`"
        >
        </v-img>
      </template>
    </v-img>
  </v-avatar>
</template>
