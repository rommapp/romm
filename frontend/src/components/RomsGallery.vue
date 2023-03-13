<script setup>
import axios from 'axios'
import { ref } from "vue";


const roms = ref([])


async function getRoms(platform) {
    console.log("Getting roms...")
    await axios.get('http://localhost:5000/platforms/'+platform+'/roms').then((response) => {
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
                    </v-img>

                    <v-card-text>
                        <v-row>
                            <div class="text-caption font-weight-bold d-flex align-center">
                                <v-col>{{ rom.name }}</v-col>
                                <v-btn size="small" variant="flat" icon="mdi-download" @click="downloadRom(rom.name)" />
                            </div>
                        </v-row>
                    </v-card-text>

                </v-card>
            </v-hover>
        </v-col>
    </v-row>

</template>
