<template>
  <section class="funds-panel surface-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("funds.title") }}</h2>
        <p>{{ t("funds.description") }}</p>
      </div>
      <button type="button" class="refresh-button" @click="$emit('refresh')">
        {{ t("common.actions.refresh") }}
      </button>
    </header>

    <div class="panel-grid">
      <form class="surface" @submit.prevent="handleSubmit">
        <h3>{{ t("funds.formTitle") }}</h3>
        <div class="form-grid">
          <label>
            <span>{{ t("funds.fields.name") }}</span>
            <input
              v-model.trim="form.name"
              type="text"
              required
              :placeholder="t('funds.placeholders.name')"
            />
          </label>
          <label>
            <span>{{ t("funds.fields.currency") }}</span>
            <BaseSelect
              v-model="form.currency"
              :options="currencyOptions"
            />
          </label>
          <label>
            <span>{{ t("funds.fields.initial") }}</span>
            <input
              v-model.number="form.initial_amount"
              type="number"
              step="0.01"
              min="0"
              required
            />
          </label>
          <label class="full">
            <span>{{ t("funds.fields.notes") }}</span>
            <textarea
              v-model.trim="form.notes"
              rows="2"
              :placeholder="t('funds.placeholders.notes')"
            ></textarea>
          </label>
        </div>
        <div class="form-actions">
          <button type="submit" class="primary-btn" :disabled="pending">
            {{ t("funds.submit") }}
          </button>
        </div>
      </form>

      <div class="surface">
        <h3>{{ t("funds.listTitle", { count: fundingGroups.length }) }}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("funds.table.name") }}</th>
                <th>{{ t("funds.table.currency") }}</th>
                <th class="numeric">{{ t("funds.table.initial") }}</th>
                <th>{{ t("funds.table.notes") }}</th>
                <th>{{ t("funds.table.actions") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!fundingGroups.length">
                <td colspan="5" class="empty">{{ t("funds.emptyGroups") }}</td>
              </tr>
              <tr v-for="group in pagedFundingGroups" :key="group.name">
                <td>{{ group.name }}</td>
                <td>{{ currencyLabel(group.currency) }}</td>
                <td class="numeric">
                  {{ formatCurrency(group.initial_amount, group.currency) }}
                </td>
                <td>{{ group.notes || "-" }}</td>
                <td>
                  <button
                    class="danger-btn"
                    type="button"
                    @click="confirmDelete(group.name)"
                  >
                    {{ t("common.actions.delete") }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <PaginationControls
          v-if="groupsTotalItems || groupsTotalPages > 1"
          :page="groupsPage"
          :total-pages="groupsTotalPages"
          :total-items="groupsTotalItems"
          @update:page="setGroupsPage"
        />
      </div>
    </div>

    <div class="surface">
      <h3>{{ t("funds.snapshotTitle") }}</h3>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{{ t("funds.snapshotTable.name") }}</th>
              <th>{{ t("funds.snapshotTable.currency") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.initial") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.cash") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.holdingCost") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.current") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.pl") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.currentYearPl") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.currentYearRatio") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.previousYearPl") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.previousYearRatio") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!funds.length">
              <td colspan="11" class="empty">{{ t("funds.emptySnapshot") }}</td>
            </tr>
            <tr v-for="item in pagedFunds" :key="item.name">
              <td>{{ item.name }}</td>
              <td>{{ currencyLabel(item.currency) }}</td>
              <td class="numeric">{{ formatCurrency(item.initial_amount, item.currency) }}</td>
              <td class="numeric">{{ formatCurrency(item.cash_balance, item.currency) }}</td>
              <td class="numeric">{{ formatCurrency(item.holding_cost, item.currency) }}</td>
              <td class="numeric">{{ formatCurrency(item.current_total, item.currency) }}</td>
              <td :class="['numeric', valueClass(item.total_pl)]">
                {{ formatCurrency(item.total_pl, item.currency) }}
              </td>
              <td :class="['numeric', valueClass(item.current_year_pl)]">
                {{ formatCurrency(item.current_year_pl, item.currency) }}
              </td>
              <td :class="['numeric', ratioClass(item.current_year_pl_ratio)]">
                {{ formatRatio(item.current_year_pl_ratio) }}
              </td>
              <td :class="['numeric', valueClass(item.previous_year_pl)]">
                {{ formatCurrency(item.previous_year_pl, item.currency) }}
              </td>
              <td :class="['numeric', ratioClass(item.previous_year_pl_ratio)]">
                {{ formatRatio(item.previous_year_pl_ratio) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationControls
        v-if="fundsTotalItems || fundsTotalPages > 1"
        :page="fundsPage"
        :total-pages="fundsTotalPages"
        :total-items="fundsTotalItems"
        @update:page="setFundsPage"
      />
    </div>

    <div class="surface">
      <h3>{{ t("funds.aggregateTitle") }}</h3>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{{ t("funds.aggregateTable.currency") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.groups") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.initial") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.cash") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.holdingCost") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.current") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.totalPl") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.currentYearPl") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.currentYearRatio") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.previousYearPl") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.previousYearRatio") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!aggregated.length">
              <td colspan="11" class="empty">{{ t("funds.emptyAggregate") }}</td>
            </tr>
            <tr v-for="item in pagedAggregated" :key="item.currency">
              <td>{{ currencyLabel(item.currency) }}</td>
              <td class="numeric">{{ item.group_count }}</td>
              <td class="numeric">{{ formatCurrency(item.initial_amount, item.currency) }}</td>
              <td class="numeric">{{ formatCurrency(item.cash_balance, item.currency) }}</td>
              <td class="numeric">{{ formatCurrency(item.holding_cost, item.currency) }}</td>
              <td class="numeric">{{ formatCurrency(item.current_total, item.currency) }}</td>
              <td :class="['numeric', valueClass(item.total_pl)]">
                {{ formatCurrency(item.total_pl, item.currency) }}
              </td>
              <td :class="['numeric', valueClass(item.current_year_pl)]">
                {{ formatCurrency(item.current_year_pl, item.currency) }}
              </td>
              <td :class="['numeric', ratioClass(item.current_year_pl_ratio)]">
                {{ formatRatio(item.current_year_pl_ratio) }}
              </td>
              <td :class="['numeric', valueClass(item.previous_year_pl)]">
                {{ formatCurrency(item.previous_year_pl, item.currency) }}
              </td>
              <td :class="['numeric', ratioClass(item.previous_year_pl_ratio)]">
                {{ formatRatio(item.previous_year_pl_ratio) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationControls
        v-if="aggregateTotalItems || aggregateTotalPages > 1"
        :page="aggregatePage"
        :total-pages="aggregateTotalPages"
        :total-items="aggregateTotalItems"
        @update:page="setAggregatePage"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";

import PaginationControls from "./ui/PaginationControls.vue";
import { usePagination } from "@/composables/usePagination";
import type {
  AggregatedFundSnapshot,
  Currency,
  FundSnapshot,
  FundingGroup,
} from "@/types/api";
import BaseSelect from "./ui/BaseSelect.vue";

const props = defineProps<{
  fundingGroups: FundingGroup[];
  funds: FundSnapshot[];
  aggregated: AggregatedFundSnapshot[];
}>();

const emit = defineEmits<{
  (e: "create", payload: FundingGroup): void;
  (e: "delete", name: string): void;
  (e: "refresh"): void;
}>();

const { t } = useI18n();

const pending = ref(false);
const form = reactive<FundingGroup>({
  name: "",
  currency: "JPY",
  initial_amount: 0,
  notes: "",
});

const currencyOptions = computed(() => [
  {
    label: t("common.currencies.JPY"),
    value: "JPY" as Currency,
  },
  {
    label: t("common.currencies.USD"),
    value: "USD" as Currency,
  },
]);

const {
  page: groupsPage,
  totalPages: groupsTotalPages,
  totalItems: groupsTotalItems,
  offset: groupsOffset,
  pageSize: groupsPageSize,
  setPage: setGroupsPage,
} = usePagination(computed(() => props.fundingGroups.length));

const pagedFundingGroups = computed(() =>
  props.fundingGroups.slice(groupsOffset.value, groupsOffset.value + groupsPageSize)
);

const {
  page: fundsPage,
  totalPages: fundsTotalPages,
  totalItems: fundsTotalItems,
  offset: fundsOffset,
  pageSize: fundsPageSize,
  setPage: setFundsPage,
} = usePagination(computed(() => props.funds.length));

const pagedFunds = computed(() =>
  props.funds.slice(fundsOffset.value, fundsOffset.value + fundsPageSize)
);

const {
  page: aggregatePage,
  totalPages: aggregateTotalPages,
  totalItems: aggregateTotalItems,
  offset: aggregateOffset,
  pageSize: aggregatePageSize,
  setPage: setAggregatePage,
} = usePagination(computed(() => props.aggregated.length));

const pagedAggregated = computed(() =>
  props.aggregated.slice(aggregateOffset.value, aggregateOffset.value + aggregatePageSize)
);

function resetForm(): void {
  form.name = "";
  form.currency = "JPY";
  form.initial_amount = 0;
  form.notes = "";
}

function currencyLabel(currency: Currency): string {
  return currency === "USD" ? t("common.currencies.USD") : t("common.currencies.JPY");
}

function formatCurrency(value: number, currency: Currency): string {
  const locale = currency === "USD" ? "en-US" : "ja-JP";
  const formatted = new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);

  if (currency === "JPY") {
    return formatted.replace("￥", "¥");
  }
  return formatted;
}

function formatRatio(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("ja-JP", {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function valueClass(value: number): Record<string, boolean> {
  return {
    positive: value > 1e-9,
    negative: value < -1e-9,
  };
}

function ratioClass(value: number | null): Record<string, boolean> {
  if (value === null || Number.isNaN(value)) {
    return {};
  }
  return {
    positive: value > 1e-6,
    negative: value < -1e-6,
  };
}

async function handleSubmit() {
  if (!form.name) {
    return;
  }
  pending.value = true;
  try {
    const payload: FundingGroup = {
      name: form.name.trim(),
      currency: form.currency,
      initial_amount: Number(form.initial_amount),
      notes: form.notes?.trim() || undefined,
    };
    emit("create", payload);
    resetForm();
  } finally {
    pending.value = false;
  }
}

function confirmDelete(name: string) {
  if (props.fundingGroups.length <= 1) {
    alert(t("funds.confirm.mustKeepOne"));
    return;
  }
  if (window.confirm(t("funds.confirm.delete", { name }))) {
    emit("delete", name);
  }
}
</script>

<style scoped>
.funds-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
  padding: clamp(1.6rem, 3vw, 2.4rem);
  overflow: hidden;
}

.funds-panel::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.08) 58%, rgba(255, 255, 255, 0)),
    radial-gradient(circle at 90% 10%, rgba(255, 200, 67, 0.18), transparent 55%);
  mix-blend-mode: overlay;
  opacity: 0.42;
}

.funds-panel > * {
  position: relative;
  z-index: 1;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(199, 210, 220, 0.6);
}

.panel-header h2 {
  font-size: 1.3rem;
  letter-spacing: 0.6px;
  color: var(--accent);
}

.panel-header p {
  margin-top: 0.4rem;
  color: var(--text-dim);
  font-size: 0.88rem;
}

.panel-grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: minmax(320px, 420px) 1fr;
}

@media (max-width: 1024px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }
}

.surface {
  border-radius: var(--radius-lg);
  border: 1px solid var(--divider);
  background: linear-gradient(180deg, var(--panel-alt), var(--panel));
  box-shadow: var(--shadow-soft);
  padding: clamp(1.3rem, 2.6vw, 1.8rem);
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.surface h3 {
  font-size: 0.95rem;
  letter-spacing: 1.1px;
  text-transform: uppercase;
  color: var(--text-faint);
}

.primary-btn {
  align-self: flex-end;
}

.table-scroll {
  overflow: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
}

.table-scroll table {
  min-width: 560px;
}

.table-scroll thead {
  background: linear-gradient(180deg, rgba(11, 61, 145, 0.08), rgba(11, 61, 145, 0));
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.65px;
  font-size: 0.78rem;
}

.table-scroll th,
.table-scroll td {
  padding: 0.8rem 1rem;
  border-bottom: 1px solid var(--divider);
  font-size: 0.95rem;
  color: var(--text);
}

.numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
  white-space: nowrap;
}

.table-scroll tbody tr:hover {
  background: rgba(15, 167, 201, 0.08);
}

.empty {
  text-align: center;
  color: var(--text-faint);
}


.danger-btn {
  border-radius: 999px;
  border: 1px solid rgba(225, 57, 45, 0.5);
  background: linear-gradient(180deg, rgba(225, 57, 45, 0.15), rgba(225, 57, 45, 0.08));
  color: var(--accent-red);
  padding: 0.4rem 1rem;
  font-size: 0.82rem;
  letter-spacing: 0.45px;
  cursor: pointer;
  transition: transform var(--transition), box-shadow var(--transition);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.danger-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-soft);
}

.positive {
  color: var(--accent-cyan);
  font-weight: 600;
}

.negative {
  color: var(--accent-red);
  font-weight: 600;
}
</style>
