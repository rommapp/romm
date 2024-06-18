<script setup lang="ts">
import PlatformIcon from "@/components/common/Platform/Icon.vue";
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
  <v-card rounded="0" elevation="0">
    <v-card-text class="pa-1">
      <v-list-item class="bg-terciary pa-1 text-truncate">
        <template #prepend>
          <platform-icon
            class="mx-2"
            :key="slug"
            :slug="slug"
          />
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
                class="ml-0"
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
    </v-card-text>
  </v-card>
</template>
