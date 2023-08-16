<script setup>
import { ref, inject } from "vue";
import { useTheme } from "vuetify";
import { VDataTable } from "vuetify/labs/VDataTable";
import CreateUserDialog from "@/components/Dialog/User/CreateUser.vue";
import EditUserDialog from "@/components/Dialog/User/EditUser.vue";
import DeleteUserDialog from "@/components/Dialog/User/DeleteUser.vue";
import version from "../../../package";

// Props
const emitter = inject("emitter");

const tab = ref("general");

const usersHeaders = [
  {
    title: "Username",
    align: "start",
    sortable: true,
    key: "username",
  },
  {
    title: "Rol",
    align: "start",
    sortable: true,
    key: "rol",
  },
  { align: "end", key: "actions", sortable: false },
];
const users = ref([
  {
    id: 1,
    username: "User 1",
    rol: "Admin",
  },
  {
    id: 2,
    username: "User 2",
    rol: "user",
  },
  {
    id: 3,
    username: "User 3",
    rol: "Admin",
  },
  {
    id: 4,
    username: "User 4",
    rol: "user",
  },
  {
    id: 5,
    username: "User 5",
    rol: "user",
  },
  {
    id: 6,
    username: "User 6",
    rol: "user",
  },
  {
    id: 7,
    username: "User 7",
    rol: "Admin",
  },
  {
    id: 8,
    username: "User 8",
    rol: "user",
  },
  {
    id: 9,
    username: "User 9",
    rol: "Admin",
  },
  {
    id: 10,
    username: "User 10",
    rol: "user",
  },
  {
    id: 11,
    username: "User 13123",
    rol: "Admin",
  },
  {
    id: 12,
    username: "User 2",
    rol: "user",
  },
  {
    id: 13,
    username: "User 3",
    rol: "Admin",
  },
  {
    id: 14,
    username: "User 4",
    rol: "user",
  },
  {
    id: 15,
    username: "User 5",
    rol: "user",
  },
  {
    id: 16,
    username: "User 6",
    rol: "user",
  },
  {
    id: 17,
    username: "User 7",
    rol: "Admin",
  },
  {
    id: 18,
    username: "User 8",
    rol: "user",
  },
  {
    id: 19,
    username: "User 9",
    rol: "Admin",
  },
]);
const usersPerPage = ref(5);

const theme = useTheme();
const darkMode =
  localStorage.getItem("theme") == "rommDark" ? ref(true) : ref(false);
const ROMM_VERSION = version.version;

// Functions
function toggleTheme() {
  theme.global.name.value = darkMode.value ? "rommDark" : "rommLight";
  darkMode.value
    ? localStorage.setItem("theme", "rommDark")
    : localStorage.setItem("theme", "rommLight");
}
</script>
<template>
  <!-- Settings tabs -->
  <v-app-bar elevation="0" density="compact">
    <v-tabs v-model="tab" slider-color="rommAccent1" class="bg-primary">
      <v-tab value="general" rounded="0"> General </v-tab>
      <v-tab value="ui" rounded="0">User Interface</v-tab>
    </v-tabs>
  </v-app-bar>

  <!-- General tab -->
  <v-window v-model="tab">
    <v-window-item value="general">
      <v-row class="pa-1">
        <v-col>
          <v-card rounded="0">
            <v-card-text class="pa-0">
              <v-data-table
                v-model:items-per-page="usersPerPage"
                :headers="usersHeaders"
                :items="users"
                :sort-by="[{ key: 'username', order: 'asc' }]"
              >
                <template v-slot:top>
                  <v-toolbar class="bg-terciary">
                    <v-toolbar-title
                      ><v-icon class="mr-3">mdi-account-group</v-icon
                      >Users</v-toolbar-title
                    >

                    <v-btn
                      prepend-icon="mdi-plus"
                      variant="outlined"
                      @click="emitter.emit('showCreateUserDialog')"
                    >
                      Create user
                    </v-btn>

                    <create-user-dialog />

                    <edit-user-dialog />

                    <delete-user-dialog />
                  </v-toolbar>
                </template>
                <template v-slot:item.actions="{ item }">
                  <v-icon
                    class="me-2"
                    @click="emitter.emit('showEditUserDialog', item.raw)"
                  >
                    mdi-pencil
                  </v-icon>
                  <v-icon
                    class="text-red"
                    @click="emitter.emit('showDeleteUserDialog', item.raw)"
                    >mdi-delete</v-icon
                  >
                </template>
              </v-data-table>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-window-item>

    <!-- User Interface tab -->
    <v-window-item value="ui">
      <v-row class="pa-4" no-gutters>
        <v-switch
          @change="toggleTheme()"
          v-model="darkMode"
          prepend-icon="mdi-theme-light-dark"
          hide-details
          inset
        />
      </v-row>
    </v-window-item>
  </v-window>

  <v-bottom-navigation :elevation="0" height="36" class="text-caption">
    <v-row class="align-center justify-center" no-gutters>
      <span class="text-rommAccent1">RomM</span>
      <span class="ml-1">{{ ROMM_VERSION }}</span>
    </v-row>
  </v-bottom-navigation>
</template>
