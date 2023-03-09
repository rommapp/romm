<script>
import axios from 'axios'
export default {
    data() {
        return {
            cover_lazy: 'http://asgard:5173/assets/emulation/resources/placeholder/cover.png',
            roms: [
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/pokemon fire red.png',
                    name: "Pokemon Fire Red",
                    link: "https://www.igdb.com/games/pokemon-firered"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/castlevania - aria of sorrow.png',
                    name: "Castlevania - Aria of Sorrow",
                    link: "https://www.igdb.com/games/castlevania-aria-of-sorrow"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/wario land 4.png',
                    name: "Wario Land 4",
                    link: "https://www.igdb.com/games/wario-land-4"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/pokemon ruby.png',
                    name: "Pokemon Ruby",
                    link: "https://www.igdb.com/games/pokemon-ruby"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/pokemon fire red.png',
                    name: "Pokemon Fire Red",
                    link: "https://www.igdb.com/games/pokemon-firered"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/castlevania - aria of sorrow.png',
                    name: "Castlevania - Aria of Sorrow",
                    link: "https://www.igdb.com/games/castlevania-aria-of-sorrow"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/wario land 4.png',
                    name: "Wario Land 4",
                    link: "https://www.igdb.com/games/wario-land-4"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/pokemon ruby.png',
                    name: "Pokemon Ruby",
                    link: "https://www.igdb.com/games/pokemon-ruby"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/pokemon fire red.png',
                    name: "Pokemon Fire Red",
                    link: "https://www.igdb.com/games/pokemon-firered"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/castlevania - aria of sorrow.png',
                    name: "Castlevania - Aria of Sorrow",
                    link: "https://www.igdb.com/games/castlevania-aria-of-sorrow"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/wario land 4.png',
                    name: "Wario Land 4",
                    link: "https://www.igdb.com/games/wario-land-4"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/pokemon ruby.png',
                    name: "Pokemon Ruby",
                    link: "https://www.igdb.com/games/pokemon-ruby"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/pokemon fire red.png',
                    name: "Pokemon Fire Red",
                    link: "https://www.igdb.com/games/pokemon-firered"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/castlevania - aria of sorrow.png',
                    name: "Castlevania - Aria of Sorrow",
                    link: "https://www.igdb.com/games/castlevania-aria-of-sorrow"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/wario land 4.png',
                    name: "Wario Land 4",
                    link: "https://www.igdb.com/games/wario-land-4"
                },
                {
                    cover: 'http://asgard:5173/assets/emulation/resources/gba/pokemon ruby.png',
                    name: "Pokemon Ruby",
                    link: "https://www.igdb.com/games/pokemon-ruby"
                }
            ]
        }
    },
    methods: {
        downloadRom(name){
            console.log("Downloading "+name)
        }
    }
}
</script>

<template>
    
    <v-row>
        <v-col v-for="rom in roms" :key="rom.name" cols="6" sm="4" md="2" lg="2">
            <v-hover v-slot="{ isHovering, props }">
                <v-card :elevation="isHovering ? 20 : 3" :class="{ 'on-hover': isHovering }" v-bind="props" >

                    <v-img :src="rom.cover" :lazy-src="cover_lazy" cover >
                        <template v-slot:placeholder>
                            <div class="d-flex align-center justify-center fill-height">
                                <v-progress-circular color="grey-lighten-4" indeterminate />
                            </div>
                        </template>
                        <v-btn class="fill-height" color="transparent" block :href="rom.link"></v-btn>            
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
