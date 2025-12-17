import $api from ".";

export default class ControlPanelService {
    static async getControlPanel() {
        return await $api.get('/control-panel');
    }
    static async getUserList() {
        return await $api.get('/control-panel/users')
    }
}