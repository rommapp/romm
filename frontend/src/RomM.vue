<script setup lang="ts">
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import api from "@/services/api/index";
import userApi from "@/services/api/user";
import router from "@/plugins/router";
import languageStore from "@/stores/language";
import { storeToRefs } from "pinia";
import { onBeforeMount, ref } from "vue";
import { useI18n } from "vue-i18n";

// Props
const heartbeat = storeHeartbeat();
const auth = storeAuth();
const configStore = storeConfig();
const { locale } = useI18n();
const storeLanguage = languageStore();
const { defaultLanguage, languages } = storeToRefs(storeLanguage);
const selectedLanguage = ref(
  languages.value.find(
    (lang) => lang.value === localStorage.getItem("settings.locale"),
  ) || defaultLanguage.value,
);
locale.value = selectedLanguage.value.value;
storeLanguage.setLanguage(selectedLanguage.value);

// Functions
onBeforeMount(async () => {
  await api.get("/heartbeat").then(async ({ data: data }) => {
    heartbeat.set(data);
    if (heartbeat.value.SHOW_SETUP_WIZARD) {
      router.push({ name: "setup" });
    } else {
      await userApi
        .fetchCurrentUser()
        .then(({ data: user }) => {
          auth.setUser(user);
        })
        .catch((error) => {
          console.error(error);
        });

      await api.get("/config").then(({ data: data }) => {
        configStore.set(data);
      });
    }
  });
});
</script>
<template>
  <v-app>
    <v-main class="h-100">
      <router-view />
    </v-main>
  </v-app>
</template>
