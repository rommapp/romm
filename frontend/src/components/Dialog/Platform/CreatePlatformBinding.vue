<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCreatePlatformBindingDialog", () => {
  show.value = true;
});
</script>
<template>
  <v-dialog v-model="show" max-width="500px" :scrim="false">
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-controller" class="ml-5 mr-2" />
          </v-col>
          <v-col>
            <v-btn
              @click="show = false"
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>
      <v-divider class="border-opacity-25" :thickness="1" />

      <v-card-text>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="show = false" class="bg-terciary">Cancel</v-btn>
          <v-btn :disabled="true" class="text-romm-green bg-terciary ml-5">
            Create
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
