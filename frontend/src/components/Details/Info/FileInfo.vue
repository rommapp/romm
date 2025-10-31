<script setup lang="ts">
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { RomFileSchema } from "@/__generated__";
import FileSelectItem from "@/components/Details/Info/FileSelectItem.vue";
import VersionSwitcher from "@/components/Details/VersionSwitcher.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeDownload from "@/stores/download";
import type { DetailedRom } from "@/stores/roms";
import { formatBytes } from "@/utils";

const { t } = useI18n();
const props = defineProps<{ rom: DetailedRom }>();
const downloadStore = storeDownload();
const auth = storeAuth();
const romUser = ref(props.rom.rom_user);
const romInfo = ref([
  { label: "Size", value: formatBytes(props.rom.fs_size_bytes) },
  { label: "SHA-1", value: props.rom.sha1_hash },
  { label: "MD5", value: props.rom.md5_hash },
  { label: "CRC", value: props.rom.crc_hash },
  { label: "Revision", value: props.rom.revision },
]);

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
      <v-row
        v-if="rom.has_simple_single_file"
        class="align-center my-3"
        no-gutters
      >
        <v-col cols="3" xl="2" class="mr-2">
          <span>{{ t("rom.file") }}</span>
        </v-col>
        <v-col>
          <MissingFromFSIcon
            v-if="rom.missing_from_fs"
            :text="`Missing game from filesystem: ${rom.fs_path}/${rom.fs_name}`"
            class="mr-2"
          /><span class="text-body-1">{{ rom.fs_name }}</span>
        </v-col>
      </v-row>
      <v-row v-else class="align-center my-3" no-gutters>
        <v-col cols="3" xl="2" class="mr-2">
          <span>{{ t("rom.files") }}</span>
        </v-col>
        <v-col>
          <v-row class="align-center" no-gutters>
            <v-col v-if="rom.missing_from_fs" cols="auto" class="pr-2">
              <MissingFromFSIcon
                :text="`Missing game from filesystem: ${rom.fs_path}/${rom.fs_name}`"
                :size="25"
              />
            </v-col>
            <v-col>
              <v-select
                v-model="downloadStore.filesToDownload"
                :label="rom.fs_name"
                :items="rom.files"
                :item-props="itemProps"
                density="compact"
                variant="outlined"
                return-object
                multiple
                hide-details
                clearable
                chips
              >
                <template #item="{ item, props: subItemProps }">
                  <v-list-item v-bind="subItemProps">
                    <template #prepend="{ isSelected }">
                      <v-checkbox-btn
                        :model-value="isSelected"
                        density="compact"
                        class="mr-2"
                      />
                    </template>
                    <v-list-item-subtitle class="mt-1">
                      <FileSelectItem :item="item.raw" />
                    </v-list-item-subtitle>
                  </v-list-item>
                </template>
              </v-select>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
      <v-row no-gutters class="align-center my-3">
        <v-col cols="3" xl="2" class="mr-2">
          <span>{{ t("rom.info") }}</span>
        </v-col>
        <v-col class="my-1">
          <v-row no-gutters>
            <v-col v-for="info in romInfo" :key="info.label" cols="12">
              <v-chip
                v-if="info.value"
                size="small"
                class="mt-1 mr-2 px-0"
                label
              >
                <v-chip label> {{ info.label }} </v-chip>
                <span class="px-2">{{ info.value }}</span>
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
            <VersionSwitcher class="mr-2" :rom="rom" />
            <v-tooltip
              v-if="auth.scopes.includes('roms.user.write')"
              location="top"
              class="tooltip"
              transition="fade-transition"
              :text="t('rom.set-as-default')"
              open-delay="300"
            >
              <template #activator="{ props: activatorProps }">
                <v-btn
                  rounded="1"
                  v-bind="activatorProps"
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
