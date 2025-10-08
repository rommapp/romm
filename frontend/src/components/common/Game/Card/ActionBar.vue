<script setup lang="ts">
import type { Emitter } from "mitt";
import { computed, inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import PlayBtn from "@/components/common/Game/PlayBtn.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeDownload from "@/stores/download";
import storeHeartbeat from "@/stores/heartbeat";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import {
  isNintendoDSRom,
  isEJSEmulationSupported,
  isRuffleEmulationSupported,
} from "@/utils";

const props = defineProps<{ rom: SimpleRom; sizeActionBar: number }>();
const { t } = useI18n();
const emit = defineEmits(["menu-open", "menu-close"]);
const downloadStore = storeDownload();
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
const configStore = storeConfig();
const heartbeatStore = storeHeartbeat();

const computedSize = computed(() => {
  return props.sizeActionBar === 1 ? "small" : "x-small";
});

const isNDSRom = computed(() => {
  return isNintendoDSRom(props.rom);
});

const isEmulationSupported = computed(() => {
  return (
    isEJSEmulationSupported(
      props.rom.platform_slug,
      heartbeatStore.value,
      configStore.config,
    ) ||
    isRuffleEmulationSupported(
      props.rom.platform_slug,
      heartbeatStore.value,
      configStore.config,
    )
  );
});

const menuOpen = ref(false);

watch(menuOpen, (val) => {
  emit(val ? "menu-open" : "menu-close");
});
</script>

<template>
  <v-row no-gutters class="text-white">
    <v-col class="d-flex">
      <v-btn
        class="action-bar-btn-small flex-grow-1"
        :size="computedSize"
        :disabled="downloadStore.value.includes(rom.id) || rom.missing_from_fs"
        icon="mdi-download"
        variant="text"
        rounded="0"
        :aria-label="`${t('rom.download')} ${rom.name}`"
        @click.prevent="romApi.downloadRom({ rom })"
      />
    </v-col>
    <v-col v-if="isEmulationSupported" class="d-flex">
      <PlayBtn
        :rom="rom"
        icon-embedded
        class="action-bar-btn-small flex-grow-1"
        :size="computedSize"
        variant="text"
        rounded="0"
        @click.prevent
      />
    </v-col>
    <v-col v-if="isNDSRom" class="d-flex">
      <v-btn
        :disabled="rom.missing_from_fs"
        class="action-bar-btn-small flex-grow-1"
        :size="computedSize"
        icon="mdi-qrcode"
        variant="text"
        rounded="0"
        :aria-label="`Show ${rom.name} QR code`"
        @click.prevent
        @click="emitter?.emit('showQRCodeDialog', rom)"
      />
    </v-col>
    <v-col
      v-if="
        auth.scopes.includes('roms.write') ||
        auth.scopes.includes('roms.user.write') ||
        auth.scopes.includes('collections.write')
      "
      class="d-flex"
    >
      <v-menu v-model="menuOpen" location="bottom">
        <template #activator="{ props: menuProps }">
          <v-btn
            class="action-bar-btn-small flex-grow-1"
            :size="computedSize"
            v-bind="menuProps"
            icon="mdi-dots-vertical"
            variant="text"
            rounded="0"
            :aria-label="`${rom.name} admin menu`"
            @click.prevent
          />
        </template>
        <AdminMenu :rom="rom" />
      </v-menu>
    </v-col>
  </v-row>
</template>

<style scoped>
.action-bar-btn-small {
  max-height: 250px;
  width: unset;
}
</style>
