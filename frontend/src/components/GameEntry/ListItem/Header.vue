<template>
    <v-list-item class="pl-2 pr-2 pb-2 ml-3 mr-3 text-body-1">
        <v-row class="">
            <v-col cols="3"><p>Name</p></v-col>
            <v-col cols="4" class="hidden-sm-and-down"><p>File</p></v-col>
            <v-col class="hidden-sm-and-down"><p>Platform</p></v-col>
            <v-col class="hidden-sm-and-down"><p>Size</p></v-col>
            <v-col class="hidden-sm-and-down"><p>Region</p></v-col>
            <v-col class="hidden-sm-and-down"><p>Revision</p></v-col>
        </v-row>
        <template v-slot:prepend><v-avatar/></template>
        <template v-slot:append>
            <v-col class="pa-0 ml-1">
                <v-btn disabled size="x-small" variant="text"/>
                <v-btn size="x-small" variant="text" disabled/>
            </v-col>
            <v-btn size="x-small" variant="text" disabled/>
        </template>
    </v-list-item>
</template>