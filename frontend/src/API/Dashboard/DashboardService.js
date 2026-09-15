import $api from "..";

export default class DashboardService {
    static async get_dashboard_data(params = {}) {
        return await $api.get("/dashboard/", { params });
    }

    static async get_dashboard_charts(params = {}) {
        return await $api.get("/dashboard/charts", { params });
    }

    static async set_monthly_plan(revenueTarget) {
        return await $api.put("/dashboard/plan", {
            revenue_target: revenueTarget,
        });
    }

    static async delete_monthly_plan() {
        return await $api.delete("/dashboard/plan");
    }
}
