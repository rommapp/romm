<script setup lang="ts">
import PlatformIcon from "@/components/Platform/Icon.vue";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const emit = defineEmits(["clickEdit", "clickDelete"]);
defineProps<{
  slug: string;
  fsSlug: string;
  editable: boolean;
}>();
</script>
<template>
  <v-list-item class="bg-terciary ma-1 pa-1 text-truncate">
    <template #prepend>
      <v-avatar :rounded="0" size="40" class="mx-2">
        <platform-icon :key="slug" :slug="slug" />
      </v-avatar>
    </template>
    <v-list-item class="bg-primary pr-2 pl-2">
      <span>{{ fsSlug }}</span>
      <template #append>
        <v-slide-x-reverse-transition>
          <v-btn
            v-if="editable"
            rounded="0"
            variant="text"
            size="x-small"
            icon="mdi-pencil"
            class="ml-2"
            @click="$emit('clickEdit')"
          />
        </v-slide-x-reverse-transition>
        <v-slide-x-reverse-transition>
          <v-btn
            v-if="editable"
            rounded="0"
            variant="text"
            size="x-small"
            icon="mdi-delete"
            class="text-romm-red"
            @click="$emit('clickDelete')"
          />
        </v-slide-x-reverse-transition>
      </template>
    </v-list-item>
  </v-list-item>
</template>
