<script setup lang="ts">
import RSection from "@/components/common/RSection.vue";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeUsers, { type User } from "@/stores/users";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath, formatTimestamp } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onMounted, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const userSearch = ref("");
const { xs } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const usersStore = storeUsers();
const { allUsers } = storeToRefs(usersStore);
const auth = storeAuth();
const HEADERS = [
  {
    title: "",
    align: "start",
    sortable: false,
    key: "avatar_path",
    width: "40px",
  },
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "username",
  },
  {
    title: "Role",
    align: "start",
    sortable: true,
    key: "role",
  },
  {
    title: "Last active",
    align: "start",
    sortable: true,
    key: "last_active",
  },
  {
    title: "Enabled",
    align: "start",
    sortable: true,
    key: "enabled",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;
const PER_PAGE_OPTIONS = [10, 25, 50, 100];
const page = ref(1);
const storedUsersPerPage = parseInt(localStorage.getItem("usersPerPage") ?? "");
const usersPerPage = ref(isNaN(storedUsersPerPage) ? 25 : storedUsersPerPage);
const pageCount = ref(0);
emitter?.on("updateDataTablePages", updateDataTablePages);

// Functions
function updateDataTablePages() {
  pageCount.value = Math.ceil(usersStore.allUsers.length / usersPerPage.value);
}

function disableUser(user: User) {
  userApi.updateUser(user).catch(({ response, message }) => {
    emitter?.emit("snackbarShow", {
      msg: `Unable to disable/enable user: ${
        response?.data?.detail || response?.statusText || message
      }`,
      icon: "mdi-close-circle",
      color: "red",
      timeout: 5000,
    });
  });
}

onMounted(() => {
  userApi
    .fetchUsers()
    .then(({ data }) => {
      usersStore.set(data);
    })
    .catch((error) => {
      console.log(error);
    });
});
</script>

<template>
  <r-section icon="mdi-account" title="Users">
    <template #content>
      <v-text-field
        v-model="userSearch"
        prepend-inner-icon="mdi-magnify"
        label="Search"
        rounded="0"
        single-line
        hide-details
        clearable
        density="comfortable"
        class="bg-secondary"
      />
      <v-data-table
        v-model:items-per-page="usersPerPage"
        v-model:page="page"
        :items-per-page-options="PER_PAGE_OPTIONS"
        :search="userSearch"
        :headers="HEADERS"
        :items="allUsers"
        :sort-by="[{ key: 'username', order: 'asc' }]"
        fixed-header
        fixed-footer
        hide-default-footer
      >
        <template #header.actions>
          <v-btn
            prepend-icon="mdi-plus"
            variant="outlined"
            class="text-romm-accent-1"
            @click="emitter?.emit('showCreateUserDialog', null)"
          >
            Add
          </v-btn>
        </template>
        <template #item.avatar_path="{ item }">
          <v-avatar>
            <v-img
              :src="
                item.avatar_path
                  ? `/assets/romm/assets/${item.avatar_path}?ts=${item.updated_at}`
                  : defaultAvatarPath
              "
            />
          </v-avatar>
        </template>
        <template #item.last_active="{ item }">
          {{ formatTimestamp(item.last_active) }}
        </template>
        <template #item.enabled="{ item }">
          <v-switch
            v-model="item.enabled"
            color="romm-accent-1"
            :disabled="item.id == auth.user?.id"
            hide-details
            @change="disableUser(item)"
          />
        </template>
        <template #item.actions="{ item }">
          <v-btn-group divided density="compact">
            <v-btn
              size="small"
              @click="emitter?.emit('showEditUserDialog', item)"
            >
              <v-icon>mdi-pencil</v-icon>
            </v-btn>
            <v-btn
              class="text-romm-red"
              size="small"
              @click="emitter?.emit('showDeleteUserDialog', item)"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
          </v-btn-group>
        </template>

        <template #bottom>
          <v-divider />
          <div>
            <v-row no-gutters class="pa-1 align-center justify-center">
              <v-col cols="8" sm="9" md="10" class="px-3">
                <v-pagination
                  :show-first-last-page="!xs"
                  v-model="page"
                  rounded="0"
                  active-color="romm-accent-1"
                  :length="pageCount"
                />
              </v-col>
              <v-col>
                <v-select
                  v-model="usersPerPage"
                  class="pa-2"
                  label="Users per page"
                  density="compact"
                  variant="outlined"
                  :items="PER_PAGE_OPTIONS"
                  hide-details
                />
              </v-col>
            </v-row>
          </div>
        </template>
      </v-data-table>
    </template>
  </r-section>
</template>
