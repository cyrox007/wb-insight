import $api from ".";
export default class DashboardService {
    static async get_dashboard_data() {
        return await $api.get("/dashboard/");
    }
}