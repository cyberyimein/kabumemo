<template>
  <section class="panel surface-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("tax.title") }}</h2>
        <p>{{ t("tax.descriptionAnnual") }}</p>
      </div>
      <button type="button" class="refresh-button" @click="loadSettlements">
        {{ t("common.actions.refresh") }}
      </button>
    </header>

    <div class="panel-grid">
      <form class="surface tax-form" @submit.prevent="handleSubmit">
        <h3>{{ t("tax.annualTitle") }}</h3>
        <div class="form-grid">
          <label>
            <span>{{ t("common.labels.year") }}</span>
            <input v-model.number="form.year" type="number" min="2000" max="2100" required />
          </label>
          <label>
            <span>{{ t("tax.fields.payerGroup") }}</span>
            <select v-model="form.funding_group">
              <option v-for="group in jpyGroups" :key="group.name" :value="group.name">{{ group.name }}</option>
            </select>
          </label>
          <label>
            <span>{{ t("tax.fields.amount") }}</span>
            <input v-model.number="form.amount" type="number" min="0" step="0.01" required />
          </label>
          <label>
            <span>{{ t("tax.fields.currency") }}</span>
            <input value="JPY" disabled type="text" />
          </label>
          <label class="full">
            <span>{{ t("common.labels.memo") }}</span>
            <input v-model="form.notes" type="text" />
          </label>
        </div>
        <div class="form-actions">
          <button type="submit" class="primary-btn">{{ t("common.actions.create") }}</button>
        </div>
      </form>

      <div class="surface tax-history">
        <h3>{{ t("tax.historyTitle", { count: settlements.length }) }}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("common.labels.year") }}</th>
                <th>{{ t("tax.table.fundingGroup") }}</th>
                <th class="numeric">{{ t("tax.fields.amount") }}</th>
                <th>{{ t("tax.historyTable.recordedAt") }}</th>
                <th>{{ t("common.actions.delete") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!settlements.length">
                <td colspan="5" class="empty">{{ t("tax.historyEmpty") }}</td>
              </tr>
              <tr v-for="item in settlements" :key="item.id">
                <td>{{ item.year }}</td>
                <td>{{ item.funding_group }}</td>
                <td class="numeric">{{ formatCurrency(item.amount, item.currency) }}</td>
                <td>{{ item.recorded_at }}</td>
                <td>
                  <button type="button" class="ghost-btn danger" @click="handleDelete(item.id)">
                    {{ t("common.actions.delete") }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="section-note">{{ t("tax.pendingSummary", { count: pendingTransactions.length }) }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";

import { createAnnualTaxSettlement, deleteAnnualTaxSettlement, getAnnualTaxSettlements } from "@/services/api";
import type { AnnualTaxSettlement, FundingGroup, Transaction } from "@/types/api";

const props = defineProps<{
  pendingTransactions: Transaction[];
  fundingGroups: FundingGroup[];
}>();

const emit = defineEmits<{
  (e: "changed"): void;
  (e: "notify", payload: { type: "success" | "error" | "info"; message: string }): void;
}>();

const { t } = useI18n();
const settlements = ref<AnnualTaxSettlement[]>([]);
const form = reactive({
  year: new Date().getFullYear(),
  funding_group: "JPY",
  amount: 0,
  notes: "",
});

const jpyGroups = computed(() => props.fundingGroups.filter((group) => group.currency === "JPY"));

function formatCurrency(amount: number, currency: string): string {
  return new Intl.NumberFormat("ja-JP", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "JPY" ? 0 : 2,
  }).format(amount);
}

async function loadSettlements() {
  try {
    settlements.value = await getAnnualTaxSettlements();
  } catch (error) {
    emit("notify", { type: "error", message: error instanceof Error ? error.message : t("tax.errors.load") });
  }
}

async function handleSubmit() {
  try {
    await createAnnualTaxSettlement({
      year: form.year,
      funding_group: form.funding_group,
      amount: form.amount,
      currency: "JPY",
      notes: form.notes || null,
    });
    form.amount = 0;
    form.notes = "";
    await loadSettlements();
    emit("changed");
    emit("notify", { type: "success", message: t("tax.toasts.updated") });
  } catch (error) {
    emit("notify", { type: "error", message: error instanceof Error ? error.message : t("tax.errors.save") });
  }
}

async function handleDelete(id: string) {
  try {
    await deleteAnnualTaxSettlement(id);
    await loadSettlements();
    emit("changed");
    emit("notify", { type: "success", message: t("tax.toasts.deleted") });
  } catch (error) {
    emit("notify", { type: "error", message: error instanceof Error ? error.message : t("tax.errors.delete") });
  }
}

onMounted(() => {
  if (jpyGroups.value.length && !jpyGroups.value.some((group) => group.name === form.funding_group)) {
    form.funding_group = jpyGroups.value[0].name;
  }
  void loadSettlements();
});
</script>

<style scoped>
.tax-form,
.tax-history {
  min-height: 100%;
}
</style>