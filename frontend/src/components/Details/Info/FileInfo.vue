<script setup lang="ts">
import type { RomFileSchema } from "@/__generated__";
import VersionSwitcher from "@/components/Details/VersionSwitcher.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeDownload from "@/stores/download";
import type { DetailedRom } from "@/stores/roms";
import { formatBytes } from "@/utils";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const props = defineProps<{ rom: DetailedRom }>();
const downloadStore = storeDownload();
const auth = storeAuth();
const romUser = ref(props.rom.rom_user);
const romInfo = ref([
  { label: "SHA-1", value: props.rom.sha1_hash },
  { label: "MD5", value: props.rom.md5_hash },
  { label: "CRC", value: props.rom.crc_hash },
]);

// Functions
async function toggleMainSibling() {
  romUser.value.is_main_sibling = !romUser.value.is_main_sibling;
  romApi.updateUserRomProps({
    romId: props.rom.id,
    data: romUser.value,
  });
}

function itemProps(item: RomFileSchema) {
  return {
    key: item.id,
    title: item.full_path.replace(props.rom.full_path, ""),
    value: item,
  };
}

watch(
  () => props.rom,
  async () => (romUser.value = props.rom.rom_user),
);
</script>
<template>
  <v-row no-gutters>
    <v-col>
      <v-row v-if="!rom.multi" class="align-center my-3" no-gutters>
        <v-col cols="3" xl="2" class="mr-2">
          <span>{{ t("rom.file") }}</span>
        </v-col>
        <v-col>
          <span class="text-body-1">{{ rom.fs_name }}</span>
        </v-col>
      </v-row>
      <v-row v-if="rom.multi" class="align-center my-3" no-gutters>
        <v-col cols="3" xl="2" class="mr-2">
          <span>{{ t("rom.files") }}</span>
        </v-col>
        <v-col>
          <v-select
            v-model="downloadStore.filesToDownload"
            :label="rom.fs_name"
            :items="rom.files"
            :itemProps="itemProps"
            rounded="0"
            density="compact"
            variant="outlined"
            return-object
            multiple
            hide-details
            clearable
            chips
          >
            <template #item="{ item, props }">
              <v-list-item v-bind="props">
                <template v-slot:prepend="{ isSelected }">
                  <v-checkbox-btn
                    :model-value="isSelected"
                    density="compact"
                    class="mr-2"
                  />
                </template>
                <v-list-item-subtitle class="mt-1">
                  <v-chip
                    color="primary"
                    size="x-small"
                    class="mr-1"
                    v-if="item.raw.category"
                    >{{ item.raw.category.toLocaleUpperCase() }}</v-chip
                  >
                  <v-chip size="x-small">{{
                    formatBytes(item.raw.file_size_bytes)
                  }}</v-chip>
                </v-list-item-subtitle>
              </v-list-item>
            </template>
          </v-select>
        </v-col>
      </v-row>
      <v-row no-gutters class="align-center my-3">
        <v-col cols="3" xl="2" class="mr-2">
          <span>{{ t("rom.info") }}</span>
        </v-col>
        <v-col class="my-1">
          <v-row no-gutters>
            <v-col cols="12">
              <v-chip size="small" class="mr-2 px-0" label>
                <v-chip label>{{ t("rom.size") }}</v-chip
                ><span class="px-2">{{ formatBytes(rom.fs_size_bytes) }}</span>
              </v-chip>
            </v-col>
            <v-col v-for="info in romInfo" cols="12">
              <v-chip
                v-if="info.value"
                size="small"
                class="mt-1 mr-2 px-0"
                label
              >
                <v-chip label>{{ info.label }}</v-chip
                ><span class="px-2">{{ info.value }}</span>
              </v-chip>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
      <v-row v-if="rom.tags.length > 0" class="align-center my-3" no-gutters>
        <v-col cols="3" xl="2" class="mr-2">
          <span>{{ t("rom.tags") }}</span>
        </v-col>
        <v-col>
          <v-chip
            v-for="tag in rom.tags"
            :key="tag"
            size="small"
            class="mr-2"
            label
            color="primary"
            variant="tonal"
          >
            {{ tag }}
          </v-chip>
        </v-col>
      </v-row>
      <v-row
        v-if="rom.siblings.length > 0"
        class="align-center my-3"
        no-gutters
      >
        <v-col cols="3" xl="2" class="mr-2">
          <span>{{ t("rom.switch-version") }}</span>
        </v-col>
        <v-col>
          <v-row class="align-center" no-gutters>
            <version-switcher class="mr-2" :rom="rom" />
            <v-tooltip
              v-if="auth.scopes.includes('roms.user.write')"
              location="top"
              class="tooltip"
              transition="fade-transition"
              :text="t('rom.set-as-default')"
              open-delay="300"
            >
              <template #activator="{ props }">
                <v-btn
                  rounded="1"
                  v-bind="props"
                  variant="flat"
                  class="my-1 text-grey-lighten-2"
                  style="padding: 10px 14px"
                  @click="toggleMainSibling"
                >
                  <v-icon
                    :class="romUser.is_main_sibling ? '' : 'mr-1'"
                    :color="romUser.is_main_sibling ? 'primary' : ''"
                  >
                    {{
                      romUser.is_main_sibling
                        ? "mdi-checkbox-outline"
                        : "mdi-checkbox-blank-outline"
                    }}
                  </v-icon>
                  {{ romUser.is_main_sibling ? "" : t("rom.default") }}
                </v-btn>
              </template>
            </v-tooltip>
          </v-row>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>
