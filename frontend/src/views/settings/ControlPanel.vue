<script setup>
import { ref } from "vue";
import { useTheme } from "vuetify";
import { VDataTable } from "vuetify/labs/VDataTable";
import version from "../../../package";

// Props
const tab = ref("general");
const dialogCreate = ref(false);
const dialogDelete = ref(false);
const editedItem = ref({
  username: "",
  password: "",
  rol: "",
});
const usersHeaders = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "name",
  },
  {
    title: "Rol",
    align: "start",
    sortable: true,
    key: "rol",
  },
  { title: "Actions", align: "end", key: "actions", sortable: false },
];
const users = ref([
  {
    name: "User 1",
    rol: "Admin",
  },
  {
    name: "User 2",
    rol: "user",
  },
  {
    name: "User 3",
    rol: "Admin",
  },
  {
    name: "User 4",
    rol: "user",
  },
  {
    name: "User 5",
    rol: "user",
  },
  {
    name: "User 6",
    rol: "user",
  },
  {
    name: "User 7",
    rol: "Admin",
  },
  {
    name: "User 8",
    rol: "user",
  },
  {
    name: "User 9",
    rol: "Admin",
  },
  {
    name: "User 10",
    rol: "user",
  },
  {
    name: "User 1",
    rol: "Admin",
  },
  {
    name: "User 2",
    rol: "user",
  },
  {
    name: "User 3",
    rol: "Admin",
  },
  {
    name: "User 4",
    rol: "user",
  },
  {
    name: "User 5",
    rol: "user",
  },
  {
    name: "User 6",
    rol: "user",
  },
  {
    name: "User 7",
    rol: "Admin",
  },
  {
    name: "User 8",
    rol: "user",
  },
  {
    name: "User 9",
    rol: "Admin",
  },
  {
    name: "User 10",
    rol: "user",
  },
]);
const rolSelect = ref("user");
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
                :sort-by="[{ key: 'name', order: 'asc' }]"
              >
                <template v-slot:top>
                  <v-toolbar class="bg-terciary">
                    <v-toolbar-title
                      ><v-icon class="mr-3">mdi-account-group</v-icon
                      >Users</v-toolbar-title
                    >
                    <v-dialog
                      v-model="dialogCreate"
                      max-width="500px"
                      :scrim="false"
                    >
                      <template v-slot:activator="{ props }">
                        <v-btn
                          v-bind="props"
                          prepend-icon="mdi-plus"
                          variant="outlined"
                        >
                          Create user
                        </v-btn>
                      </template>
                      <v-card>
                        <v-toolbar density="compact" class="bg-terciary">
                          <v-row class="align-center" no-gutters>
                            <v-col cols="10">
                              <v-icon icon="mdi-account" class="ml-5 mr-2" />
                            </v-col>
                            <v-col>
                              <v-btn
                                @click="dialogCreate = false"
                                class="bg-terciary"
                                rounded="0"
                                variant="text"
                                icon="mdi-close"
                                block
                              />
                            </v-col>
                          </v-row>
                        </v-toolbar>
                        <v-divider class="border-opacity-25" :thickness="1" />

                        <v-card-text>
                          <v-row class="pa-2" no-gutters>
                            <v-col>
                              <v-text-field
                                rounded="0"
                                variant="outlined"
                                v-model="editedItem.username"
                                label="Username"
                              ></v-text-field>
                            </v-col>
                          </v-row>
                          <v-row class="pa-2" no-gutters>
                            <v-col>
                              <v-text-field
                                rounded="0"
                                variant="outlined"
                                v-model="editedItem.password"
                                label="Password"
                              ></v-text-field>
                            </v-col>
                          </v-row>
                          <v-row class="pa-2" no-gutters>
                            <v-col>
                              <v-select
                                v-model="rolSelect"
                                rounded="0"
                                variant="outlined"
                                :items="['admin', 'user']"
                                label="Rol"
                              ></v-select>
                            </v-col>
                          </v-row>
                          <v-row class="justify-center pa-2" no-gutters>
                            <v-btn @click="dialogCreate = false" class="bg-terciary"
                              >Cancel</v-btn
                            >
                            <v-btn
                              class="text-rommGreen bg-terciary ml-5"
                              @click=""
                              >Create</v-btn
                            >
                          </v-row>
                        </v-card-text>
                      </v-card>
                    </v-dialog>
                    <v-dialog v-model="dialogDelete" max-width="500px">
                      <v-card>
                        <v-card-title class="text-h5"
                          >Are you sure you want to delete this
                          item?</v-card-title
                        >
                        <v-card-actions>
                          <v-spacer></v-spacer>
                          <v-btn variant="text" @click="closeDelete"
                            >Cancel</v-btn
                          >
                          <v-btn variant="text" @click="deleteItemConfirm"
                            >OK</v-btn
                          >
                          <v-spacer></v-spacer>
                        </v-card-actions>
                      </v-card>
                    </v-dialog>
                  </v-toolbar>
                </template>
                <template v-slot:item.actions="{ item }">
                  <v-icon class="me-2" @click=""> mdi-pencil </v-icon>
                  <v-icon @click=""> mdi-delete </v-icon>
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
