import { defineStore } from "pinia";
import type { UserSchema } from "@/__generated__";

export type User = UserSchema;

export default defineStore("users", {
  state: () => ({
    allUSers: [] as User[],
  }),

  getters: {
    admins: (state) => state.allUSers.filter((user) => user.role === "admin"),
  },

  actions: {
    set(users: User[]) {
      this.allUSers = users;
    },
    add(user: User) {
      this.allUSers = this.allUSers.concat(user);
    },
    update(user: User) {
      this.allUSers = this.allUSers.map((value) => {
        if (value.id === user.id) {
          return user;
        }
        return value;
      });
    },
    remove(userId: number) {
      this.allUSers = this.allUSers.filter((value) => {
        return value.id !== userId;
      });
    },
    reset() {
      this.allUSers = [];
    },
  },
});
