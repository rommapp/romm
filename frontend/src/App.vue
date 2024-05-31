<template>
  <v-app>
    <v-main>
      <span id="bg"></span>

      <v-container class="fill-height justify-center">
        <v-card id="card" class="py-8 px-5" width="800">
          <v-row>
            <v-col>
              <v-img
                src="/assets/isotipo.svg"
                class="mx-auto"
                width="200"
                height="200"
              />
            </v-col>
          </v-row>
          <v-row>
            <v-col>
              <v-empty-state headline="RomM has a new house!"
                ><h3>RomM has been migrated to the rommapp organization.</h3>
                <p>
                  Please switch to
                  <a
                    href="https://hub.docker.com/repository/docker/rommapp/romm"
                    >rommapp/romm</a
                  >, this repository will be no longer maintained.
                </p></v-empty-state
              >
            </v-col>
          </v-row>
        </v-card>
      </v-container>
    </v-main>
  </v-app>
</template>
<style>
body {
  background-color: rgba(var(--v-theme-background));
}
#bg {
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  position: absolute;
  background: url("/assets/login_bg.png") center center;
  background-size: cover;
}
#card {
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(10px);
}
</style>
