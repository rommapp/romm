<script setup>
import { ref, inject, onMounted } from "vue";
import { VDataTable } from "vuetify/labs/VDataTable";
import { fetchUsersApi, updateUserApi } from "@/services/api";
import storeAuth from "@/stores/auth";
import { defaultAvatarPath } from "@/utils/utils";
import CreateUserDialog from "@/components/Dialog/User/CreateUser.vue";
import EditUserDialog from "@/components/Dialog/User/EditUser.vue";
import DeleteUserDialog from "@/components/Dialog/User/DeleteUser.vue";

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
    title: "Username",
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
    title: "Enabled",
    align: "start",
    sortable: true,
    key: "enabled",
  },
  { align: "end", key: "actions", sortable: false },
];

const PER_PAGE_OPTIONS = [
  { value: 5, title: "5" },
  { value: 10, title: "10" },
  { value: 25, title: "25" },
  { value: -1, title: "$vuetify.dataFooter.itemsPerPageAll" },
];

// Props
const emitter = inject("emitter");
const users = ref([]);
const usersPerPage = ref(5);
const userSearch = ref("");

function disableUser(user) {
  updateUserApi(user).catch(({ response, message }) => {
    emitter.emit("snackbarShow", {
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
  fetchUsersApi()
    .then(({ data }) => {
      users.value = data;
    })
    .catch((error) => {
      console.log(error);
    });
});
</script>
<template>
  <v-card rounded="0" elevation="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button"
        ><v-icon class="mr-3">mdi-account-group</v-icon>Users</v-toolbar-title
      >
      <v-btn
        prepend-icon="mdi-plus"
        variant="outlined"
        class="text-romm-accent-1"
        @click="emitter.emit('showCreateUserDialog')"
      >
        Add user
      </v-btn>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text class="pa-0">
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
        :items-per-page-options="PER_PAGE_OPTIONS"
        v-model:items-per-page="usersPerPage"
        :search="userSearch"
        :headers="HEADERS"
        :items="users"
        :sort-by="[{ key: 'username', order: 'asc' }]"
      >
        <template v-slot:item.avatar_path="{ item }">
          <v-avatar>
            <v-img
              :src="
                item.selectable.avatar_path
                  ? `/assets/romm/resources/${item.selectable.avatar_path}`
                  : defaultAvatarPath
              "
            />
          </v-avatar>
        </template>
        <template v-slot:item.enabled="{ item }">
          <v-switch
            :disabled="item.selectable.id == auth.user?.id"
            v-model="item.selectable.enabled"
            @change="disableUser(item.selectable)"
            hide-details
          />
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn
            class="mr-2 bg-terciary"
            size="small"
            rounded="0"
            @click="emitter.emit('showEditUserDialog', { ...item.raw })"
          >
            <v-icon>mdi-pencil</v-icon>
          </v-btn>
          <v-btn
            size="small"
            rounded="0"
            class="bg-terciary text-romm-red"
            @click="emitter.emit('showDeleteUserDialog', item.raw)"
            ><v-icon>mdi-delete</v-icon></v-btn
          >
        </template>
      </v-data-table>
    </v-card-text>

    <create-user-dialog />
    <edit-user-dialog />
    <delete-user-dialog />
  </v-card>
</template>
