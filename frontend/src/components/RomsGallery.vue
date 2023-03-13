<script setup>
import axios from 'axios'
import { ref } from "vue";


const roms = ref([])


async function getRoms(platform) {
    console.log("Getting roms...")
    await axios.get('http://'+location.hostname+':5000/platforms/'+platform+'/roms').then((response) => {
        console.log("Roms loaded!")
        console.log(response.data.data)
        roms.value = response.data.data
    }).catch((error) => {console.log(error)})
}

function downloadRom(name) {
    console.log("Downloading "+name)
}

function downloadSave(name) {
    console.log("Downloading "+name+" save file")
}

defineExpose({ getRoms })
</script>

<template>
    
    <v-row>
        <v-col v-for="rom in roms" cols="6" xs="6" sm="3" md="3" lg="2">
            <v-hover v-slot="{ isHovering, props }">
                <v-card :elevation="isHovering ? 20 : 3" :class="{ 'on-hover': isHovering }" v-bind="props" >

                    <v-img :src="rom.path_cover_big" :lazy-src="rom.path_cover_small" cover >
                        <template v-slot:placeholder>
                            <div class="d-flex align-center justify-center fill-height">
                                <v-progress-circular color="grey-lighten-4" indeterminate />
                            </div>
                        </template>
                        <!-- <div class="d-flex align-center text-body-1 pt-2 pr-5 pb-2 pl-5 bg-secondary rom-title" :class="{ 'on-hover': isHovering }">{{ rom.name }}</div> -->
                        <div v-if="!rom.slug" class="d-flex align-center text-body-1 pt-2 pr-5 pb-2 pl-5 bg-secondary rom-title" >{{ rom.name }}</div>
                    </v-img>

                    <v-card-text>
                        <v-row>
                            <v-btn size="small" variant="flat" icon="mdi-download" @click="downloadRom(rom.name)" />
                            <v-btn size="small" variant="flat" icon="mdi-content-save-all-outline" @click=" downloadSave(rom.filename)"/>
                            <v-btn v-if="rom.slug" :href="'https://www.igdb.com/games/'+rom.slug" target="_blank" size="small" variant="flat" icon="mdi-information" />
                        </v-row>
                    </v-card-text>

                </v-card>
            </v-hover>
        </v-col>
    </v-row>

</template>

<style scoped>
.v-card .rom-title{
    transition: opacity .4s ease-in-out;
}
.rom-title.on-hover {
    opacity: 0.85;
}
.rom-title:not(.on-hover) {
    opacity: 1;
}

.v-card.on-hover {
    opacity: 1;
}
.v-card:not(.on-hover) {
    opacity: 0.95;
}
</style>