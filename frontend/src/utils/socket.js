import { io } from "socket.io-client";

const socket = io({
  path: "/ws/socket.io/",
  transports: ["websocket", "polling"],
  autoConnect: false,
});

export default socket;
