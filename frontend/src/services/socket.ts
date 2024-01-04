import { io } from "socket.io-client";

export default io({
  path: "/ws/socket.io/",
  transports: ["websocket", "polling"],
  autoConnect: false,
});
