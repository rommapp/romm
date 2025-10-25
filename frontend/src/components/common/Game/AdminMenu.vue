<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import { useFavoriteToggle } from "@/composables/useFavoriteToggle";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeCollections from "@/stores/collections";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms from "@/stores/roms";
import type { SimpleRom } from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const props = defineProps<{ rom: SimpleRom }>();
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const auth = storeAuth();
const collectionsStore = storeCollections();
const { toggleFavorite } = useFavoriteToggle(emitter);
const romsStore = storeRoms();
const scanningStore = storeScanning();

async function switchFromFavorites() {
  await toggleFavorite(props.rom);
}

async function resetLastPlayed() {
  await romApi
    .updateUserRomProps({
      romId: props.rom.id,
      data: {},
      removeLastPlayed: true,
    })
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: `${props.rom.name} removed from Continue Playing`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });

      romsStore.removeFromContinuePlaying(props.rom);
    })
    .catch((error) => {
      console.error(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    });
}

async function onScan() {
  scanningStore.setScanning(true);
  emitter?.emit("snackbarShow", {
    msg: `Refreshing ${props.rom.name} metadata...`,
    icon: "mdi-loading mdi-spin",
    color: "primary",
  });

  if (!socket.connected) socket.connect();
  socket.emit("scan", {
    platforms: [props.rom.platform_id],
    roms_ids: [props.rom.id],
    type: "quick", // Quick scan so we can filter by selected roms
    apis: heartbeat.getAllMetadataOptions().map((s) => s.value),
  });
}
</script>

<template>
  <v-list class="pa-0">
    <template v-if="auth.scopes.includes('roms.write')">
      <v-list-item
        :disabled="!heartbeat.value.METADATA_SOURCES.ANY_SOURCE_ENABLED"
        class="py-4 pr-5"
        @click="emitter?.emit('showMatchRomDialog', rom)"
      >
        <v-list-item-title class="d-flex">
          <v-icon icon="mdi-search-web" class="mr-2" />{{
            t("rom.manual-match")
          }}
        </v-list-item-title>
        <v-list-item-subtitle>
          {{
            !heartbeat.value.METADATA_SOURCES.ANY_SOURCE_ENABLED
              ? t("rom.no-metadata-source")
              : ""
          }}
        </v-list-item-subtitle>
      </v-list-item>
      <v-list-item
        class="py-4 pr-5"
        @click="emitter?.emit('showEditRomDialog', rom)"
      >
        <v-list-item-title class="d-flex">
          <v-icon icon="mdi-pencil-box" class="mr-2" />{{ t("common.edit") }}
        </v-list-item-title>
      </v-list-item>
      <v-list-item class="py-4 pr-5" @click="onScan">
        <v-list-item-title class="d-flex">
          <v-icon icon="mdi-magnify-scan" class="mr-2" />{{
            t("rom.refresh-metadata")
          }}
        </v-list-item-title>
      </v-list-item>
      <v-divider />
    </template>
    <v-list-item
      v-if="auth.scopes.includes('roms.user.write') && rom.rom_user.last_played"
      class="py-4 pr-5"
      @click="resetLastPlayed"
    >
      <v-list-item-title class="d-flex">
        <v-icon icon="mdi-play-protected-content" class="mr-2" />
        {{ t("rom.remove-from-playing") }}
      </v-list-item-title>
    </v-list-item>
    <v-list-item
      v-if="auth.scopes.includes('collections.write')"
      class="py-4 pr-5"
      @click="switchFromFavorites"
    >
      <v-list-item-title class="d-flex">
        <v-icon
          :icon="
            collectionsStore.isFavorite(rom)
              ? 'mdi-star-remove-outline'
              : 'mdi-star'
          "
          class="mr-2"
        />{{
          collectionsStore.isFavorite(rom)
            ? t("rom.remove-from-favorites")
            : t("rom.add-to-favorites")
        }}
      </v-list-item-title>
    </v-list-item>
    <v-list-item
      v-if="auth.scopes.includes('collections.write')"
      class="py-4 pr-5"
      @click="emitter?.emit('showAddToCollectionDialog', [{ ...rom }])"
    >
      <v-list-item-title class="d-flex">
        <v-icon icon="mdi-bookmark-plus" class="mr-2" />{{
          t("rom.add-to-collection")
        }}
      </v-list-item-title>
    </v-list-item>
    <v-list-item
      v-if="auth.scopes.includes('collections.write')"
      class="py-4 pr-5"
      @click="emitter?.emit('showRemoveFromCollectionDialog', [{ ...rom }])"
    >
      <v-list-item-title class="d-flex">
        <v-icon icon="mdi-bookmark-remove-outline" class="mr-2" />{{
          t("rom.remove-from-collection")
        }}
      </v-list-item-title>
    </v-list-item>
    <template v-if="auth.scopes.includes('roms.write')">
      <v-divider />
      <v-list-item
        class="py-4 pr-5 text-romm-red"
        @click="emitter?.emit('showDeleteRomDialog', [rom])"
      >
        <v-list-item-title class="d-flex">
          <v-icon icon="mdi-delete" class="mr-2" />{{ t("rom.delete") }}
        </v-list-item-title>
      </v-list-item>
    </template>
  </v-list>
</template>
