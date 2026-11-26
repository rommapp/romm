// Replaces the package's types, which import `@/types` and so resolve into `src/`.
declare module "vue3-pdf-app" {
  import type { DefineComponent } from "vue";

  /** pdf.js application object, limited to the members the viewers touch. */
  export interface PdfApp {
    page: number;
    pagesCount: number;
    eventBus: {
      on: (
        event: string,
        handler: (payload: { pageNumber: number }) => void,
      ) => void;
    };
  }

  /** Element ids the library wires its custom toolbar controls to. */
  export interface PdfToolbarIdConfig {
    sidebarToggle?: string;
    pageNumber?: string;
    numPages?: string;
    zoomIn?: string;
    zoomOut?: string;
    firstPage?: string;
    previousPage?: string;
    nextPage?: string;
    lastPage?: string;
    download?: string;
  }

  const VuePdfApp: DefineComponent<{
    pdf?: string | ArrayBuffer;
    theme?: "light" | "dark";
    title?: boolean;
    fileName?: string;
    pageNumber?: number;
    config?: Record<string, unknown>;
    idConfig?: PdfToolbarIdConfig;
    onPagesRendered?: (pdfApp: PdfApp) => void;
  }>;

  export default VuePdfApp;
}
