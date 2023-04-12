<template>
    <v-list-item class="pa-2 text-body-1">
        <v-row>
            <v-col><p>Name</p></v-col>
            <v-col class="hidden-sm-and-down"><p>File</p></v-col>
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