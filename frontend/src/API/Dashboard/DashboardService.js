import $api from "..";

export default class DashboardService {
    static async get_dashboard_data() {
        return await $api.get("/dashboard/");
    }

    static async get_dashboard_charts(params = {}) {
        return await $api.get("/dashboard/charts", { params });
    }
}