<template>
  <div class="dos-wasm-wrapper">
    <h2 v-if="title">{{ title }}</h2>
    <div class="iframe-container" :style="{ height: '100%', width: '100%' }">
      <iframe
        :src="dosWasmUrl"
        height="100%"
        width="100%"
        ref="dosFrame"
        @load="onIframeLoad"
        allowfullscreen
      ></iframe>
    </div>
  </div>
</template>

<script>
export default {
  name: "DosWasmX",
  props: {
    dosWasmUrl: {
      type: String,
      default: "/doswasmx.html",
    },
    title: {
      type: String,
      default: "",
    },
    autostart: {
      type: Boolean,
      default: false,
    },
    fullscreen: {
      type: Boolean,
      default: false,
    },
    romUrl: {
      type: String,
      default: "",
    },
  },
  data() {
    return {
      loaded: false,
    };
  },
  methods: {
    waitForModuleInit(timeout = 10000) {
      return new Promise((resolve, reject) => {
        const start = Date.now();

        const checkModule = () => {
          // Get the window object from the iframe
          const iframeWindow = this.$refs.dosFrame?.contentWindow;

          // Check if myApp has been initialized
          if (
            iframeWindow &&
            iframeWindow.myApp &&
            !iframeWindow.myApp.rivetsData.moduleInitializing
          ) {
            resolve(iframeWindow);
            return;
          }

          // Check for timeout
          if (Date.now() - start > timeout) {
            reject(
              new Error("Timeout waiting for DOS Wasm X module to initialize"),
            );
            return;
          }

          // Check again in a bit
          setTimeout(checkModule, 100);
        };

        checkModule();
      });
    },

    async onIframeLoad() {
      this.loaded = true;
      this.$emit("loaded");

      if (this.autostart && this.$refs.dosFrame) {
        try {
          const iframeWindow = this.$refs.dosFrame.contentWindow;

          if (
            iframeWindow &&
            iframeWindow.myApp &&
            iframeWindow.myApp.loadRom &&
            iframeWindow.myApp.load_file
          ) {
            const response = await fetch(this.romUrl);
            const url = URL.parse(this.romUrl);
            const blob = await response.blob();

            const filename = url.pathname.split("/").pop();
            const file = new File([blob], filename, { type: blob.type });

            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);

            var event = {};
            event.dataTransfer = dataTransfer;

            this.waitForModuleInit()
              .then(() => {
                this.moduleReady = true;
                this.$emit("moduleReady");

                if (this.romUrl) {
                  iframeWindow.myApp.handleDrop(event);
                }
                if (this.fullscreen) {
                  iframeWindow.document
                    .getElementById("canvasDiv")
                    .addEventListener("click", () => {
                      iframeWindow.myApp.fullscreen();
                    });
                }
              })
              .catch((error) => {
                console.error("Error initializing DOS Wasm X module:", error);
              });
          }
        } catch (e) {
          console.warn("Unable to autostart DOS Wasm X:", e);
        }
      }
    },
  },
};
</script>

<style scoped>
.dos-wasm-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 0 auto;
}

.iframe-container {
  border: 1px solid #ccc;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

iframe {
  border: 0;
}
</style>
