<script setup lang="ts">
import LanguageSelector from "@/components/Settings/UserInterface/LanguageSelector.vue";
import Notification from "@/components/common/Notifications/Notification.vue";
import storeHeartbeat from "@/stores/heartbeat";

const heartbeatStore = storeHeartbeat();
</script>

<template>
    <Notification />
    <v-container id="container" class="pb-0 fill-height justify-center">
        <v-col class="d-flex align-center justify-center pa-0" cols="12">
            <router-view />
        </v-col>
        <v-container width="1100" class="pa-0 justify-center">
            <v-card class="transparent pa-0">
                <v-card-text class="pa-0">
                    <v-row no-gutters>
                        <v-col
                            class="d-flex align-center justify-space-between text-white text-shadow"
                        >
                            <LanguageSelector density="compact" />
                            <v-spacer /><v-spacer />
                            <span
                                class="text-white text-subtitle-1 text-shadow"
                            >
                                {{ heartbeatStore.value.SYSTEM.VERSION }}
                            </span>
                        </v-col>
                    </v-row>
                </v-card-text>
            </v-card>
        </v-container>
    </v-container>
    <div id="language-selector">
        <LanguageSelector density="compact" />
    </div>
    <span id="version" class="text-white text-subtitle-1 text-shadow">
        {{ heartbeatStore.value.SYSTEM.VERSION }}
    </span>
</template>

<style scoped>
#container {
    background-image: url("/assets/auth_background.svg");
    background-size: cover;
    background-position: center;
    max-width: 100vw;
    /* align-items: unset !important; */
}
#version {
    position: absolute !important;
    right: 15px !important;
    bottom: 10px !important;
}
#language-selector {
    position: absolute !important;
    left: 10px !important;
    bottom: 10px !important;
}
</style>
