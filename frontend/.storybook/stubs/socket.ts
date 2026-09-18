// Storybook-only: no websocket to the app server.

const socket = {
  connected: false,
  auth: {} as Record<string, unknown>,
  connect() {},
  disconnect() {},
  on() {},
  off() {},
  emit() {},
};

export default socket;
