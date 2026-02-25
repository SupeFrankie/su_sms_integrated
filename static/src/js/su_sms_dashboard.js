/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { jsonrpc } from "@web/core/network/rpc";

const TYPE_LABELS = {
    manual: "Manual",
    adhoc: "Ad Hoc",
    staff: "Staff",
    student: "Student",
};

const TYPE_BADGE_CLASS = {
    manual: "bg-secondary",
    adhoc: "bg-success",
    staff: "bg-warning text-dark",
    student: "bg-info text-dark",
};

const STATE_BADGE_CLASS = {
    draft: "bg-secondary",
    queued: "bg-secondary",
    sending: "bg-primary",
    done: "bg-success",
    partial: "bg-warning text-dark",
    failed: "bg-danger",
};

export class SuSmsDashboard extends Component {
    static template = "su_sms_integrated.Dashboard";

    setup() {
        this.action = useService("action");

        this.state = useState({
            loading: true,
            loadingBalance: true,
            balance: "-",
            balanceError: null,
            messages: [],
            deptStats: [],
            totalSent: 0,
            totalCost: 0,
            campaignCount: 0,
            deptCount: 0,
            isManager: false,
        });

        onMounted(() => {
            this.loadStats();
            this.loadBalance();
        });
    }

    async loadStats() {
        try {
            const result = await jsonrpc("/su_sms/dashboard_stats", {});
            this.state.messages = result.messages || [];
            this.state.deptStats = result.dept_stats || [];
            this.state.totalSent = result.total_sent || 0;
            this.state.totalCost = result.total_cost || 0;
            this.state.campaignCount = this.state.messages.length;
            this.state.deptCount = this.state.deptStats.length;
            this.state.isManager = result.is_manager || false;
        } catch (e) {
            console.error("Failed to load SMS stats:", e);
        } finally {
            this.state.loading = false;
        }
    }

    async loadBalance() {
        this.state.loadingBalance = true;
        this.state.balanceError = null;
        try {
            const result = await jsonrpc("/su_sms/balance", {});
            if (result.error) {
                this.state.balanceError = result.error;
                this.state.balance = "-";
            } else {
                this.state.balance = result.balance || "-";
            }
        } catch (e) {
            this.state.balanceError = String(e);
        } finally {
            this.state.loadingBalance = false;
        }
    }

    async refreshBalance() {
        await this.loadBalance();
        await this.loadStats();
    }

    openCompose(smsType = null) {
        const context = {};
        if (smsType) {
            context.default_sms_type = smsType;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Send SMS",
            res_model: "su.sms.compose",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context,
        });
    }

    viewHistory() {
        this.action.doAction("su_sms_integrated.action_su_sms_message");
    }

    // ------------------------------------------------------------------
    // Helpers for template
    // ------------------------------------------------------------------
    formatDate(dateStr) {
        if (!dateStr) return "-";
        try {
            const d = new Date(dateStr);
            return d.toLocaleDateString("en-GB", {
                day: "2-digit",
                month: "short",
                year: "numeric",
            });
        } catch {
            return dateStr;
        }
    }

    formatCost(cost) {
        if (!cost && cost !== 0) return "0.00";
        return Number(cost).toFixed(2);
    }

    typeLabel(type) {
        return TYPE_LABELS[type] || type;
    }

    typeBadge(type) {
        return TYPE_BADGE_CLASS[type] || "bg-secondary";
    }

    stateBadge(state) {
        return STATE_BADGE_CLASS[state] || "bg-secondary";
    }
}

// Register as a client action
registry.category("actions").add("su_sms_dashboard", SuSmsDashboard);
