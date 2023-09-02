import { defineStore } from "pinia";

export default defineStore("users", {
    state: () => ({
        all: [],
    }),

    getters: {
        admins: (state) => state.all.filter((user) => user.role === "ADMIN"),
    },

    actions: {
        set(users) {
            this.all = users;
        },
        add(user) {
            this.all = this.all.concat(user);
        },
        update(user) {
            this.all = this.all.map((value) => {
                if (value.id === user.id) {
                    return user;
                }
                return value;
            })
        },
        remove(user) {
            this.all = this.all.filter((value) => {
                return value.id !== user.id;
            })
        },
        reset() {
            this.all = [];
        }
    }
});
