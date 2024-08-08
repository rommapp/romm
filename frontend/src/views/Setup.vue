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
const { xs, smAndDown } = useDisplay();
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
  role: "admin",
});
const step = ref(1);
const filledAdminUser = computed(
  () =>
    defaultAdminUser.value.username != "" &&
    defaultAdminUser.value.password != ""
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
  <span id="bg" />

  <v-container class="fill-height justify-center">
    <v-card class="translucent-dark px-3" elevation="0">
      <v-img src="/assets/isotipo.svg" class="mx-auto mt-4" width="70" />
      <v-stepper
        :mobile="smAndDown"
        class="bg-transparent"
        :width="xs ? '' : smAndDown ? 400 : 700"
        max-width="700"
        v-model="step"
        flat
      >
        <template v-slot:default="{ prev, next }">
          <v-stepper-header>
            <v-stepper-item
              class="text-white text-shadow"
              title="Create an admin user"
              :value="1"
            ></v-stepper-item>

            <v-divider></v-divider>

            <v-stepper-item
              class="text-white text-shadow"
              title="Check metadata sources"
              :value="2"
            ></v-stepper-item>

            <!-- <v-divider></v-divider> -->

            <!-- <v-stepper-item title="Finish" :value="3"></v-stepper-item> -->
          </v-stepper-header>

          <v-stepper-window>
            <v-stepper-window-item :value="1" :key="1">
              <v-row no-gutters>
                <v-col>
                  <v-row v-if="smAndDown" no-gutters class="text-center mb-6">
                    <v-col>
                      <span>Create an admin user</span>
                    </v-col>
                  </v-row>
                  <v-row class="text-white justify-center mt-3" no-gutters>
                    <v-col cols="10" md="8">
                      <v-form @submit.prevent>
                        <v-text-field
                          v-model="defaultAdminUser.username"
                          required
                          prepend-inner-icon="mdi-account"
                          type="text"
                          label="Username"
                          variant="underlined"
                        />
                        <v-text-field
                          v-model="defaultAdminUser.password"
                          required
                          prepend-inner-icon="mdi-lock"
                          :type="visiblePassword ? 'text' : 'password'"
                          label="Password"
                          variant="underlined"
                          :append-inner-icon="
                            visiblePassword ? 'mdi-eye-off' : 'mdi-eye'
                          "
                          @click:append-inner="
                            visiblePassword = !visiblePassword
                          "
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
                  <v-row v-if="smAndDown" no-gutters class="text-center mb-6">
                    <v-col>
                      <span>Check metadata sources</span>
                    </v-col>
                  </v-row>
                  <v-row class="justify-center align-center" no-gutters>
                    <v-col id="sources">
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

            <!-- <v-stepper-window-item :value="3" :key="3">
              <v-row class="text-center" no-gutters>
                <v-col>
                  <span>Finished!</span>
                </v-col>
              </v-row>
            </v-stepper-window-item> -->
          </v-stepper-window>

          <v-stepper-actions :disabled="!filledAdminUser">
            <template #prev>
              <v-btn class="text-white text-shadow" :ripple="false" :disabled="isFirstStep" @click="prev">{{
                isFirstStep ? "" : "previous"
              }}</v-btn>
            </template>
            <template #next>
              <v-btn class="text-white text-shadow" @click="!isLastStep ? next() : finishWizard()">{{
                !isLastStep ? "Next" : "Finish"
              }}</v-btn>
            </template>
          </v-stepper-actions>
        </template>
      </v-stepper>
    </v-card>

    <div id="version" class="position-absolute">
      <span class="text-white">{{ heartbeat.value.VERSION }}</span>
    </div>
  </v-container>
</template>

<style>
#bg {
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  position: absolute;
  background: url("/assets/login_bg.png") center center;
  background-size: cover;
}
#sources {
  max-width: 300px;
}
#version {
  text-shadow: 1px 1px 1px #000000, 0 0 1px #000000;
  bottom: 0.3rem;
  right: 0.5rem;
}
</style>
