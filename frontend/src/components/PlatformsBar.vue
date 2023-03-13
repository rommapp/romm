<script setup>
import axios from 'axios'
import { ref } from "vue";
import { useTheme } from "vuetify";


const platforms = ref([])
const scanOverwrite = ref(false)
const theme = useTheme()
const darkMode = (localStorage.getItem('theme') == 'dark') ? ref(true) : ref(false)


async function getPlatforms() {
    console.log("Getting platforms...")
    await axios.get('http://localhost:5000/platforms').then((response) => {
        console.log("Platforms loaded!")
        console.log(response.data.data)
        platforms.value = response.data.data
    }).catch((error) => {console.log(error)})
}

async function scan() {
    console.log("scanning...")
    await axios.get('http://localhost:5000/scan?overwrite='+scanOverwrite.value).then((response) => {
        console.log("scan completed")
        console.log(response.data)
        getPlatforms()
    }).catch((error) => {console.log(error)})
}

function toggleTheme () {
    theme.global.name.value = darkMode.value ? "dark" : "light"
    darkMode.value ? localStorage.setItem('theme', 'dark') : localStorage.setItem('theme', 'light')
}


getPlatforms()
</script>

<template>
    
    <v-navigation-drawer width="250" permanent>
        <v-list>
            <v-list-item prepend-icon="mdi mdi-controller">Rom Manager</v-list-item>
        </v-list>

        <v-divider ></v-divider>

        <v-list nav>
            <v-list-item v-for="platform in platforms" 
                :title="platform.name" 
                :value="platform.slug"
                :key="platform"
                @:click="$emit('currentPlatform', platform.slug)"/>
        </v-list>

        <v-divider ></v-divider>

        <v-list>
            <v-row>
                <div class="font-weight-bold d-flex align-center justify-center fill-height ml-3">
                    <v-col>
                        <v-btn color="secondary" prepend-icon="mdi mdi-magnify-scan" @click="scan()" inset >Scan</v-btn>
                    </v-col>
                    <v-col class="font-weight-bold d-flex align-center justify-center ml-3">
                        <v-checkbox v-model="scanOverwrite" label="Force"></v-checkbox>
                    </v-col>
                </div>
            </v-row>
        </v-list>

        <v-divider ></v-divider>

        <v-list>
            <div class="font-weight-bold d-flex align-center justify-center fill-height">
                <v-switch prepend-icon="mdi mdi-brightness-6" v-model="darkMode" @change="toggleTheme()" inset class="ml-3"/>
            </div>
        </v-list>

    </v-navigation-drawer>

</template>
