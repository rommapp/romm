<script setup>
import axios from 'axios'
defineProps({ currentPlatform: { type: String, required: false } })

const mockRoms = {
    gba: [
        {
            cover: '/assets/emulation/resources/gba/pokemon fire red.png',
            cover_lazy: '/assets/emulation/resources/gba/pokemon fire red_xs.png',
            name: "Pokemon Fire Red",
            link: "https://www.igdb.com/games/pokemon-firered"
        },
        {
            cover: '/assets/emulation/resources/gba/castlevania - aria of sorrow.png',
            cover_lazy: '/assets/emulation/resources/gba/castlevania - aria of sorrow_xs.png',
            name: "Castlevania - Aria of Sorrow",
            link: "https://www.igdb.com/games/castlevania-aria-of-sorrow"
        },
        {
            cover: '/assets/emulation/resources/gba/wario land 4.png',
            cover_lazy: '/assets/emulation/resources/gba/wario land 4_xs.png',
            name: "Wario Land 4",
            link: "https://www.igdb.com/games/wario-land-4"
        },
        {
            cover: '/assets/emulation/resources/gba/pokemon ruby.png',
            cover_lazy: '/assets/emulation/resources/gba/pokemon ruby_xs.png',
            name: "Pokemon Ruby",
            link: "https://www.igdb.com/games/pokemon-ruby"
        },
        {
            cover: '/assets/emulation/resources/gba/pokemon fire red.png',
            cover_lazy: '/assets/emulation/resources/gba/pokemon fire red_xs.png',
            name: "Pokemon Fire Red",
            link: "https://www.igdb.com/games/pokemon-firered"
        },
        {
            cover: '/assets/emulation/resources/gba/castlevania - aria of sorrow.png',
            cover_lazy: '/assets/emulation/resources/gba/castlevania - aria of sorrow_xs.png',
            name: "Castlevania - Aria of Sorrow",
            link: "https://www.igdb.com/games/castlevania-aria-of-sorrow"
        },
        {
            cover: '/assets/emulation/resources/gba/wario land 4.png',
            cover_lazy: '/assets/emulation/resources/gba/wario land 4_xs.png',
            name: "Wario Land 4",
            link: "https://www.igdb.com/games/wario-land-4"
        },
        {
            cover: '/assets/emulation/resources/gba/pokemon ruby.png',
            cover_lazy: '/assets/emulation/resources/gba/pokemon ruby_xs.png',
            name: "Pokemon Ruby",
            link: "https://www.igdb.com/games/pokemon-ruby"
        },
        {
            cover: '/assets/emulation/resources/gba/pokemon fire red.png',
            cover_lazy: '/assets/emulation/resources/gba/pokemon fire red_xs.png',
            name: "Pokemon Fire Red",
            link: "https://www.igdb.com/games/pokemon-firered"
        },
        {
            cover: '/assets/emulation/resources/gba/castlevania - aria of sorrow.png',
            cover_lazy: '/assets/emulation/resources/gba/castlevania - aria of sorrow_xs.png',
            name: "Castlevania - Aria of Sorrow",
            link: "https://www.igdb.com/games/castlevania-aria-of-sorrow"
        },
        {
            cover: '/assets/emulation/resources/gba/wario land 4.png',
            cover_lazy: '/assets/emulation/resources/gba/wario land 4_xs.png',
            name: "Wario Land 4",
            link: "https://www.igdb.com/games/wario-land-4"
        },
        {
            cover: '/assets/emulation/resources/gba/pokemon ruby.png',
            cover_lazy: '/assets/emulation/resources/gba/pokemon ruby_xs.png',
            name: "Pokemon Ruby",
            link: "https://www.igdb.com/games/pokemon-ruby"
        },
        {
            cover: '/assets/emulation/resources/gba/pokemon fire red.png',
            cover_lazy: '/assets/emulation/resources/gba/pokemon fire red_xs.png',
            name: "Pokemon Fire Red",
            link: "https://www.igdb.com/games/pokemon-firered"
        },
        {
            cover: '/assets/emulation/resources/gba/castlevania - aria of sorrow.png',
            cover_lazy: '/assets/emulation/resources/gba/castlevania - aria of sorrow_xs.png',
            name: "Castlevania - Aria of Sorrow",
            link: "https://www.igdb.com/games/castlevania-aria-of-sorrow"
        },
        {
            cover: '/assets/emulation/resources/gba/wario land 4.png',
            cover_lazy: '/assets/emulation/resources/gba/wario land 4_xs.png',
            name: "Wario Land 4",
            link: "https://www.igdb.com/games/wario-land-4"
        },
        {
            cover: '/assets/emulation/resources/gba/pokemon ruby.png',
            cover_lazy: '/assets/emulation/resources/gba/pokemon ruby_xs.png',
            name: "Pokemon Ruby",
            link: "https://www.igdb.com/games/pokemon-ruby"
        },
        {
            cover: '/assets/emulation/resources/gba/pokemon fire red.png',
            cover_lazy: '/assets/emulation/resources/gba/pokemon fire red_xs.png',
            name: "Pokemon Fire Red",
            link: "https://www.igdb.com/games/pokemon-firered"
        },
        {
            cover: '/assets/emulation/resources/gba/castlevania - aria of sorrow.png',
            cover_lazy: '/assets/emulation/resources/gba/castlevania - aria of sorrow_xs.png',
            name: "Castlevania - Aria of Sorrow",
            link: "https://www.igdb.com/games/castlevania-aria-of-sorrow"
        },
        {
            cover: '/assets/emulation/resources/gba/wario land 4.png',
            cover_lazy: '/assets/emulation/resources/gba/wario land 4_xs.png',
            name: "Wario Land 4",
            link: "https://www.igdb.com/games/wario-land-4"
        },
        {
            cover: '/assets/emulation/resources/gba/pokemon ruby.png',
            cover_lazy: '/assets/emulation/resources/gba/pokemon ruby_xs.png',
            name: "Pokemon Ruby",
            link: "https://www.igdb.com/games/pokemon-ruby"
        }
    ],
    gb: [
        {
            cover: '/assets/emulation/resources/gb/pokemon red.png',
            cover_lazy: '/assets/emulation/resources/gb/pokemon red_xs.png',
            name: "Pokemon Red",
            link: "https://www.igdb.com/games/pokemon-red"
        }
    ]
}

const downloadRom = (name) => {
    console.log("Downloading "+name)
}
</script>

<template>
    
    <v-row>
        <v-col v-for="rom in mockRoms[currentPlatform]" cols="6" sm="4" md="2" lg="2">
            <v-hover v-slot="{ isHovering, props }">
                <v-card :elevation="isHovering ? 20 : 3" :class="{ 'on-hover': isHovering }" v-bind="props" >

                    <v-img :src="rom.cover" :lazy-src="rom.cover_lazy" cover >
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
