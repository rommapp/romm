/** Status chip content for MetadataProviderCard; `tone` mirrors RTag's
 *  tone prop. Consumers compute it from heartbeat / probe state. */
export interface ProviderCardStatus {
  tone: "neutral" | "brand" | "success" | "danger" | "warning" | "info";
  icon: string;
  label: string;
}
