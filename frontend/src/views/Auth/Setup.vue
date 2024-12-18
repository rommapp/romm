<script setup lang="ts">
import router from "@/plugins/router";
import { refetchCSRFToken } from "@/services/api/index";
import userApi from "@/services/api/user";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { xs } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const visiblePassword = ref(false);
// Use a computed property to reactively update metadataOptions based on heartbeat
const metadataOptions = computed(() => [
  {
    name: "IGDB",
    value: "igdb",
    logo_path: "/assets/scrappers/igdb.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.IGDB_API_ENABLED,
  },
  {
    name: "MobyGames",
    value: "moby",
    logo_path: "/assets/scrappers/moby.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.MOBY_API_ENABLED,
  },
  {
    name: "SteamgridDB",
    value: "sgdb",
    logo_path: "/assets/scrappers/sgdb.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_ENABLED,
  },
]);
const defaultAdminUser = ref({
  username: "",
  password: "",
  email: "",
  role: "admin",
});
const step = ref(1); // 1: Create admin user, 2: Check metadata sources, 3: Finish
const filledAdminUser = computed(
  () =>
    defaultAdminUser.value.username != "" &&
    defaultAdminUser.value.password != "",
);
const isFirstStep = computed(() => step.value == 1);
const isLastStep = computed(() => step.value == 2);

// Functions
async function finishWizard() {
  await userApi
    .createUser(defaultAdminUser.value)
    .then(async () => {
      await refetchCSRFToken();
      router.push({ name: "login" });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to create user: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
    });
}
</script>

<template>
  <v-card class="translucent-dark px-3" width="700">
    <v-img src="/assets/isotipo.svg" class="mx-auto mt-6" width="70" />
    <v-stepper :mobile="xs" class="bg-transparent" v-model="step" flat>
      <template #default="{ prev, next }">
        <v-stepper-header>
          <v-stepper-item :value="1">
            <template #title>
              <span class="text-white text-shadow">Create an admin user</span>
            </template>
          </v-stepper-item>

          <v-divider></v-divider>

          <v-stepper-item :value="2">
            <template #title>
              <span class="text-white text-shadow">Check metadata sources</span>
            </template>
          </v-stepper-item>
        </v-stepper-header>

        <v-stepper-window>
          <v-stepper-window-item :value="1" :key="1">
            <v-row no-gutters>
              <v-col>
                <v-row v-if="xs" no-gutters class="text-center">
                  <v-col>
                    <span>Create an admin user</span>
                  </v-col>
                </v-row>
                <v-row class="text-white justify-center mt-3" no-gutters>
                  <v-col cols="10" md="8">
                    <v-form @submit.prevent>
                      <v-text-field
                        v-model="defaultAdminUser.username"
                        label="Username *"
                        type="text"
                        required
                        autocomplete="on"
                        prepend-inner-icon="mdi-account"
                        variant="underlined"
                      />
                      <v-text-field
                        v-model="defaultAdminUser.email"
                        label="Email"
                        type="text"
                        required
                        autocomplete="on"
                        prepend-inner-icon="mdi-account"
                        variant="underlined"
                      />
                      <v-text-field
                        v-model="defaultAdminUser.password"
                        label="Password *"
                        :type="visiblePassword ? 'text' : 'password'"
                        required
                        autocomplete="on"
                        prepend-inner-icon="mdi-lock"
                        :append-inner-icon="
                          visiblePassword ? 'mdi-eye-off' : 'mdi-eye'
                        "
                        @click:append-inner="visiblePassword = !visiblePassword"
                        @keydown.enter="filledAdminUser && next()"
                        variant="underlined"
                      />
                    </v-form>
                  </v-col>
                </v-row>
              </v-col>
            </v-row>
          </v-stepper-window-item>

          <v-stepper-window-item :value="2" :key="2">
            <v-row no-gutters>
              <v-col>
                <v-row v-if="xs" no-gutters class="text-center mb-6">
                  <v-col>
                    <span>Check metadata sources</span>
                  </v-col>
                </v-row>
                <v-row class="justify-center align-center" no-gutters>
                  <v-col :max-width="300" id="sources">
                    <v-list-item
                      v-for="source in metadataOptions"
                      class="text-white text-shadow"
                      :title="source.name"
                      :subtitle="
                        source.disabled ? 'API key missing or invalid' : ''
                      "
                    >
                      <template #prepend>
                        <v-avatar size="30" rounded="1">
                          <v-img :src="source.logo_path" />
                        </v-avatar>
                      </template>
                      <template #append>
                        <span class="ml-2" v-if="source.disabled">❌</span>
                        <span class="ml-2" v-else>✅</span>
                      </template>
                    </v-list-item>
                  </v-col>
                </v-row>
              </v-col>
            </v-row>
          </v-stepper-window-item>
        </v-stepper-window>

        <v-stepper-actions :disabled="!filledAdminUser">
          <template #prev>
            <v-btn
              class="text-white text-shadow"
              :ripple="false"
              :disabled="isFirstStep"
              @click="prev"
            >
              {{ isFirstStep ? "" : "previous" }}
            </v-btn>
          </template>
          <template #next>
            <v-btn
              class="text-white text-shadow"
              @click="!isLastStep ? next() : finishWizard()"
            >
              {{ !isLastStep ? "Next" : "Finish" }}
            </v-btn>
          </template>
        </v-stepper-actions>
      </template>
    </v-stepper>
  </v-card>
</template>
