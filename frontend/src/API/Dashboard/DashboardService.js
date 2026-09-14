import $api from "..";

export default class DashboardService {
    static async get_dashboard_data(params = {}) {
        return await $api.get("/dashboard/", { params });
    }

    static async get_dashboard_charts(params = {}) {
        return await $api.get("/dashboard/charts", { params });
    }
}
