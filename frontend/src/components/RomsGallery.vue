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


defineExpose({ getRoms })
</script>

<template>
    
    <v-row>
        <v-col v-for="rom in roms" cols="6" sm="4" md="2" lg="2">
            <v-hover v-slot="{ isHovering, props }">
                <v-card :elevation="isHovering ? 20 : 3" :class="{ 'on-hover': isHovering }" v-bind="props" >

                    <v-img :src="rom.path_cover_big" :lazy-src="rom.path_cover_small" cover >
                        <template v-slot:placeholder>
                            <div class="d-flex align-center justify-center fill-height">
                                <v-progress-circular color="grey-lighten-4" indeterminate />
                            </div>
                        </template>
                        <div v-if="isHovering" class="d-flex align-center fill-height pl-5 pr-5" block ><h3>{{ rom.name }}</h3></div>
                    </v-img>

                    <v-card-text>
                        <v-row>
                            <v-btn size="small" variant="flat" icon="mdi-download" @click="downloadRom(rom.name)" />
                            <v-btn size="small" variant="flat" icon="mdi-content-save-all-outline" @click="" />
                            <v-btn v-if="rom.slug" :href="'https://www.igdb.com/games/'+rom.slug" target="_blank" size="small" variant="flat" icon="mdi-information" />
                        </v-row>
                    </v-card-text>

                </v-card>
            </v-hover>
        </v-col>
    </v-row>

</template>

<style scoped>
  .v-card .v-btn{
    transition: opacity .4s ease-in-out;
  }
  .v-card.on-hover {
    opacity: 1;
  }
  .v-card:not(.on-hover) {
    opacity: 1;
  }
  .show-title {
    color: rgba(255, 255, 255, 1) !important;
  }
</style>