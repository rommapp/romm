<script setup lang="ts">
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import RomListItem from "@/components/common/Game/ListItem.vue";
import firmwareApi from "@/services/api/firmware";
import romApi from "@/services/api/rom";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import type { DetailedRom } from "@/stores/roms";
import { formatBytes, formatTimestamp, getSupportedEJSCores } from "@/utils";
import Player from "@/views/Player/EmulatorJS/Player.vue";
import { isNull } from "lodash";
import { storeToRefs } from "pinia";
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";

const EMULATORJS_VERSION = "4.2.0";

// Props
const { t } = useI18n();
const route = useRoute();
const galleryViewStore = storeGalleryView();
const { defaultAspectRatioScreenshot } = storeToRefs(galleryViewStore);
const heartbeat = storeHeartbeat();
const rom = ref<DetailedRom | null>(null);
const firmwareOptions = ref<FirmwareSchema[]>([]);
const biosRef = ref<FirmwareSchema | null>(null);
const saveRef = ref<SaveSchema | null>(null);
const stateRef = ref<StateSchema | null>(null);
const coreRef = ref<string | null>(null);
const supportedCores = ref<string[]>([]);
const gameRunning = ref(false);
const storedFSOP = localStorage.getItem("fullScreenOnPlay");
const fullScreenOnPlay = ref(isNull(storedFSOP) ? true : storedFSOP === "true");

// Functions
function onPlay() {
  if (rom.value) {
    romApi.updateUserRomProps({
      romId: rom.value.id,
      data: rom.value.rom_user,
      updateLastPlayed: true,
    });
  }

  window.EJS_fullscreenOnLoaded = fullScreenOnPlay.value;
  window.EJS_pathtodata = "/assets/emulatorjs/data/";

  const script = document.createElement("script");
  script.src = "/assets/emulatorjs/data/loader.js";

  script.onerror = () => {
    window.EJS_pathtodata = `https://cdn.emulatorjs.org/${EMULATORJS_VERSION}/data`;
    const fallbackScript = document.createElement("script");
    fallbackScript.src = `https://cdn.emulatorjs.org/${EMULATORJS_VERSION}/data/loader.js`;
    document.body.appendChild(fallbackScript);
  };

  document.body.appendChild(script);
  gameRunning.value = true;
}

function onFullScreenChange() {
  fullScreenOnPlay.value = !fullScreenOnPlay.value;
  localStorage.setItem("fullScreenOnPlay", fullScreenOnPlay.value.toString());
}

onMounted(async () => {
  const romResponse = await romApi.getRom({
    romId: parseInt(route.params.rom as string),
  });
  rom.value = romResponse.data;

  const firmwareResponse = await firmwareApi.getFirmware({
    platformId: romResponse.data.platform_id,
  });
  firmwareOptions.value = firmwareResponse.data;

  supportedCores.value = [...getSupportedEJSCores(rom.value.platform_slug)];

  // Load stored bios, save, state, and core
  const storedSaveID = localStorage.getItem(`player:${rom.value.id}:save_id`);
  if (storedSaveID) {
    saveRef.value =
      rom.value.user_saves?.find((s) => s.id === parseInt(storedSaveID)) ??
      null;
  }

  const storedStateID = localStorage.getItem(`player:${rom.value.id}:state_id`);
  if (storedStateID) {
    stateRef.value =
      rom.value.user_states?.find((s) => s.id === parseInt(storedStateID)) ??
      null;
  } else if (rom.value.user_states) {
    // Otherwise auto select most recent state by last updated date
    stateRef.value =
      rom.value.user_states?.sort((a, b) =>
        b.updated_at.localeCompare(a.updated_at),
      )[0] ?? null;
  }

  const storedBiosID = localStorage.getItem(
    `player:${rom.value.platform_slug}:bios_id`,
  );
  if (storedBiosID) {
    biosRef.value =
      firmwareOptions.value.find((f) => f.id === parseInt(storedBiosID)) ??
      null;
  }

  const storedCore = localStorage.getItem(
    `player:${rom.value.platform_slug}:core`,
  );
  if (storedCore) {
    coreRef.value = storedCore;
  } else {
    // Otherwise auto select first supported core
    coreRef.value = supportedCores.value[0];
  }
});
</script>

<template>
  <v-row v-if="rom" class="align-center justify-center scroll" no-gutters>
    <v-col
      v-if="gameRunning"
      cols="12"
      md="8"
      xl="10"
      id="game-wrapper"
      :style="`aspect-ratio: ${defaultAspectRatioScreenshot}`"
      class="bg-primary"
      rounded
    >
      <player
        :rom="rom"
        :state="stateRef"
        :save="saveRef"
        :bios="biosRef"
        :core="coreRef"
      />
    </v-col>

    <v-col
      cols="12"
      :sm="!gameRunning ? 10 : 10"
      :md="!gameRunning ? 8 : 4"
      :xl="!gameRunning ? 6 : 2"
    >
      <v-row class="px-3 mt-6" no-gutters>
        <v-col>
          <v-img
            class="mx-auto"
            width="250"
            src="/assets/emulatorjs/powered_by_emulatorjs.png"
          />
          <v-divider class="my-4" />
          <rom-list-item :rom="rom" with-filename />
          <v-divider class="my-4" />
          <v-select
            v-if="supportedCores.length > 1"
            :disabled="gameRunning"
            v-model="coreRef"
            class="my-1"
            rounded="0"
            hide-details
            variant="outlined"
            clearable
            label="Core"
            :items="
              supportedCores.map((c) => ({
                title: c,
                value: c,
              }))
            "
          />
          <v-select
            v-model="biosRef"
            :disabled="gameRunning"
            class="my-1"
            hide-details
            rounded="0"
            variant="outlined"
            clearable
            :label="t('common.firmware')"
            :items="
              firmwareOptions.map((f) => ({
                title: f.file_name,
                value: f,
              })) ?? []
            "
          />
          <v-select
            v-model="saveRef"
            :disabled="gameRunning"
            class="my-1"
            hide-details
            variant="outlined"
            clearable
            rounded="0"
            :label="t('common.save')"
            :items="
              rom.user_saves?.map((s) => ({
                title: s.file_name,
                subtitle: `${s.emulator} - ${formatBytes(s.file_size_bytes)}`,
                value: s,
              })) ?? []
            "
          >
            <template #selection="{ item }">
              <v-list-item class="py-4" :title="item.value.file_name ?? ''">
                <template #append>
                  <v-chip size="x-small" class="ml-1" color="orange" label>{{
                    item.value.emulator
                  }}</v-chip>
                  <v-chip size="x-small" class="ml-1" label>
                    {{ formatTimestamp(item.value.updated_at) }}
                  </v-chip>
                  <v-chip size="x-small" class="ml-1" label
                    >{{ formatBytes(item.value.file_size_bytes) }}
                  </v-chip>
                </template>
              </v-list-item>
            </template>
            <template #item="{ props, item }">
              <v-list-item
                class="py-4"
                v-bind="props"
                :title="item.value.file_name ?? ''"
              >
                <template #append>
                  <v-chip size="x-small" class="ml-1" color="orange" label>{{
                    item.value.emulator
                  }}</v-chip>
                  <v-chip size="x-small" class="ml-1" label>
                    {{ formatTimestamp(item.value.updated_at) }}
                  </v-chip>
                  <v-chip size="x-small" class="ml-1" label
                    >{{ formatBytes(item.value.file_size_bytes) }}
                  </v-chip>
                </template>
              </v-list-item>
            </template>
          </v-select>
          <v-select
            v-model="stateRef"
            :disabled="gameRunning"
            class="my-1"
            hide-details
            rounded="0"
            variant="outlined"
            clearable
            :label="t('common.state')"
            :items="
              rom.user_states?.map((s) => ({
                title: s.file_name,
                subtitle: `${s.emulator} - ${formatBytes(s.file_size_bytes)}`,
                value: s,
              })) ?? []
            "
          >
            <template #selection="{ item }">
              <v-list-item class="pa-0" :title="item.value.file_name ?? ''">
                <template #append>
                  <v-chip size="x-small" class="ml-1" color="orange" label>{{
                    item.value.emulator
                  }}</v-chip>
                  <v-chip size="x-small" class="ml-1" label
                    >{{ formatBytes(item.value.file_size_bytes) }}
                  </v-chip>
                  <v-chip size="small" class="ml-1" label>
                    {{ formatTimestamp(item.value.updated_at) }}
                  </v-chip>
                </template>
              </v-list-item>
            </template>
            <template #item="{ props, item }">
              <v-list-item
                class="py-4"
                v-bind="props"
                :title="item.value.file_name ?? ''"
              >
                <template #append>
                  <v-chip size="x-small" class="ml-1" color="orange" label>{{
                    item.value.emulator
                  }}</v-chip>
                  <v-chip size="x-small" class="ml-1" label
                    >{{ formatBytes(item.value.file_size_bytes) }}
                  </v-chip>
                  <v-chip size="small" class="ml-1" label>
                    {{ formatTimestamp(item.value.updated_at) }}
                  </v-chip>
                </template>
              </v-list-item>
            </template>
          </v-select>
          <!-- <v-select
            class="my-1"
            hide-details
            variant="outlined"
            clearable
            rounded="0"
            disabled
            label="Patch"
            :items="[
              'Advance Wars Balance (AW1) by Kartal',
              'War Room Sturm (AW1) by Kartal',
            ]"
          /> -->
        </v-col>
      </v-row>
      <v-row class="px-3 py-3 text-center" no-gutters>
        <v-col>
          <v-divider class="my-4" />
          <v-row class="align-center" no-gutters>
            <v-col>
              <v-btn
                block
                size="large"
                rounded="0"
                @click="onFullScreenChange"
                :disabled="gameRunning"
                :variant="fullScreenOnPlay ? 'flat' : 'outlined'"
                :color="fullScreenOnPlay ? 'romm-accent-1' : ''"
                ><v-icon class="mr-1">{{
                  fullScreenOnPlay
                    ? "mdi-checkbox-outline"
                    : "mdi-checkbox-blank-outline"
                }}</v-icon
                >{{ t("play.full-screen") }}</v-btn
              >
            </v-col>
            <v-col
              cols="12"
              :sm="gameRunning ? 12 : 7"
              :xl="gameRunning ? 12 : 9"
            >
              <v-btn
                color="romm-accent-1"
                block
                :disabled="gameRunning"
                rounded="0"
                variant="outlined"
                size="large"
                prepend-icon="mdi-play"
                @click="onPlay()"
                >{{ t("play.play") }}
              </v-btn>
            </v-col>
          </v-row>
          <v-btn
            class="mt-4"
            block
            rounded="0"
            variant="outlined"
            size="large"
            prepend-icon="mdi-refresh"
            @click="$router.go(0)"
            >{{ t("play.reset-session") }}
          </v-btn>
          <v-btn
            class="mt-4"
            block
            rounded="0"
            variant="outlined"
            size="large"
            prepend-icon="mdi-arrow-left"
            @click="
              $router.push({
                name: 'rom',
                params: { rom: rom?.id },
              })
            "
            >{{ t("play.back-to-game-details") }}
          </v-btn>
          <v-btn
            class="mt-4"
            block
            rounded="0"
            variant="outlined"
            size="large"
            prepend-icon="mdi-arrow-left"
            @click="
              $router.push({
                name: 'platform',
                params: { platform: rom?.platform_id },
              })
            "
            >{{ t("play.back-to-gallery") }}
          </v-btn>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>
