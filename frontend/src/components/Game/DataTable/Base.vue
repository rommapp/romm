<script setup>
import { ref, inject } from "vue";
import { useRouter } from "vue-router";
import { downloadRomApi } from "@/services/api";
import storeDownload from "@/stores/download";
import useRomsStore from "@/stores/roms";
import { VDataTable } from "vuetify/labs/VDataTable";
import AdminMenu from "@/components/AdminMenu/Base.vue";

// Props
const emitter = inject("emitter");
const props = defineProps(["filteredRoms"]);
const location = window.location.origin;
const router = useRouter();
const downloadStore = storeDownload();
const romsStore = useRomsStore();
const saveFiles = ref(false);
const romsPerPage = ref(-1);
const HEADERS = [
  {
    title: "",
    align: "start",
    sortable: false,
    key: "path_cover_s",
  },
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "r_name",
  },
  {
    title: "File",
    align: "start",
    sortable: true,
    key: "file_name",
  },
  {
    title: "Size",
    align: "start",
    sortable: true,
    key: "file_size",
  },
  {
    title: "Reg",
    align: "start",
    sortable: true,
    key: "region",
  },
  {
    title: "Rev",
    align: "start",
    sortable: true,
    key: "revision",
  },
  { align: "end", key: "actions", sortable: false },
];
const PER_PAGE_OPTIONS = [
  { value: -1, title: "$vuetify.dataFooter.itemsPerPageAll" },
];

function rowClick(_, row) {
  router.push(
    `/platform/${row.item.selectable.p_slug}/${row.item.selectable.id}`
  );
}
</script>

<template>
  <v-data-table
    :items-per-page="romsPerPage"
    :items-per-page-options="PER_PAGE_OPTIONS"
    items-per-page-text=""
    :headers="HEADERS"
    :item-value="item => item"
    :items="filteredRoms"
    @click:row="rowClick"
    show-select
    v-model="romsStore.selected"
    @update:model-value="emitter.emit('refreshSelected')"
  >
    <template v-slot:item.path_cover_s="{ item }">
      <v-avatar :rounded="0">
        <v-progress-linear
          color="romm-accent-1"
          :active="downloadStore.value.includes(item.selectable.id)"
          :indeterminate="true"
          absolute
        />
        <v-img
          :src="`/assets/romm/resources/${item.selectable.path_cover_s}`"
          :lazy-src="`/assets/romm/resources/${item.selectable.path_cover_s}`"
          min-height="150"
        />
      </v-avatar>
    </template>
    <template v-slot:item.file_size="{ item }">
      <span
        >{{ item.selectable.file_size }}
        {{ item.selectable.file_size_units }}</span
      >
    </template>
    <template v-slot:item.actions="{ item }">
      <template v-if="item.selectable.multi">
        <v-btn
          class="my-1"
          rounded="0"
          @click.stop="downloadRomApi(item.selectable)"
          :disabled="downloadStore.value.includes(item.selectable.id)"
          download
          size="small"
          variant="text"
          ><v-icon>mdi-download</v-icon></v-btn
        >
      </template>
      <template v-else>
        <v-btn
          class="my-1"
          rounded="0"
          @click.stop=""
          :href="`${location}${item.selectable.download_path}`"
          download
          size="small"
          variant="text"
          ><v-icon>mdi-download</v-icon></v-btn
        >
      </template>
      <v-btn
        size="small"
        variant="text"
        :disabled="!saveFiles"
        class="my-1"
        rounded="0"
        ><v-icon>mdi-content-save-all</v-icon></v-btn
      >
      <v-menu location="bottom">
        <template v-slot:activator="{ props }">
          <v-btn
            rounded="0"
            v-bind="props"
            size="small"
            variant="text"
            class="my-1"
            ><v-icon>mdi-dots-vertical</v-icon></v-btn
          >
        </template>
        <admin-menu :rom="item.selectable" />
      </v-menu>
    </template>
  </v-data-table>
</template>
