import $api from "..";

export default class CP_Roles {
    static async getRolesList() {
        return await $api.get("/control-panel/roles/");
    }
    static async assignRoleToUser(user_id, role) {
        return await $api.post("/control-panel/roles/", {user_id, role});
    }
    static async deleteRoleFromUser(user_id, role_code) {
        return await $api.delete(`/control-panel/roles/${user_id}/${role_code}`)
    }
}
