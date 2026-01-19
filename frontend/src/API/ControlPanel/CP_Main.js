import $api from "..";

export default class CP_Main {
	static async getControlPanel() {
		return await $api.get('/control-panel');
	}
}