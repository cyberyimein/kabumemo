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
                    <div class="actions-cell">
                      <button
                        class="ghost-btn"
                        type="button"
                        @click="openCapitalDialog(group)"
                      >
                        {{ t("funds.actions.addCapital") }}
                      </button>
                      <button
                        class="danger-btn"
                        type="button"
                        @click="confirmDelete(group.name)"
                      >
                        {{ t("common.actions.delete") }}
                      </button>
                    </div>
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
      <div class="aggregate-controls">
        <label class="exchange-rate-field">
          <span>{{ t("funds.exchangeRate.label") }}</span>
          <input
            v-model="exchangeRateInput"
            type="number"
            inputmode="decimal"
            step="1"
            min="0"
            placeholder="150.00"
            @blur="handleRateBlur"
          />
        </label>
        <p
          class="exchange-rate-hint"
          :class="{ 'exchange-rate-hint--warning': needsRateReminder }"
        >
          {{
            needsRateReminder
              ? t("funds.exchangeRate.required")
              : t("funds.exchangeRate.helper")
          }}
        </p>
        <p v-if="rateError" class="exchange-rate-error">{{ rateError }}</p>
      </div>
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
            <tr v-if="combinedTotals" class="combined-row">
              <td>
                {{
                  t("funds.aggregateTable.combinedLabel", {
                    currency: currencyLabel(combinedTotals.currency),
                  })
                }}
              </td>
              <td class="numeric">{{ combinedTotals.group_count }}</td>
              <td class="numeric">
                {{ formatCurrency(combinedTotals.initial_amount, combinedTotals.currency) }}
              </td>
              <td class="numeric">
                {{ formatCurrency(combinedTotals.cash_balance, combinedTotals.currency) }}
              </td>
              <td class="numeric">
                {{ formatCurrency(combinedTotals.holding_cost, combinedTotals.currency) }}
              </td>
              <td class="numeric">
                {{ formatCurrency(combinedTotals.current_total, combinedTotals.currency) }}
              </td>
              <td :class="['numeric', valueClass(combinedTotals.total_pl)]">
                {{ formatCurrency(combinedTotals.total_pl, combinedTotals.currency) }}
              </td>
              <td :class="['numeric', valueClass(combinedTotals.current_year_pl)]">
                {{ formatCurrency(combinedTotals.current_year_pl, combinedTotals.currency) }}
              </td>
              <td :class="['numeric', ratioClass(combinedTotals.current_year_pl_ratio)]">
                {{ formatRatio(combinedTotals.current_year_pl_ratio) }}
              </td>
              <td :class="['numeric', valueClass(combinedTotals.previous_year_pl)]">
                {{ formatCurrency(combinedTotals.previous_year_pl, combinedTotals.currency) }}
              </td>
              <td :class="['numeric', ratioClass(combinedTotals.previous_year_pl_ratio)]">
                {{ formatRatio(combinedTotals.previous_year_pl_ratio) }}
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

    <div class="surface">
      <div class="capital-history-header">
        <div>
          <h3>{{ t("funds.capitalHistory.title") }}</h3>
          <p class="capital-history-description">
            {{ t("funds.capitalHistory.description") }}
          </p>
        </div>
        <span v-if="capitalTotalItems" class="capital-history-count">
          {{ t("funds.capitalHistory.count", { count: capitalTotalItems }) }}
        </span>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{{ t("funds.capitalHistory.table.effectiveDate") }}</th>
              <th>{{ t("funds.capitalHistory.table.group") }}</th>
              <th class="numeric">{{ t("funds.capitalHistory.table.amount") }}</th>
              <th>{{ t("funds.capitalHistory.table.currency") }}</th>
              <th>{{ t("funds.capitalHistory.table.notes") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!capitalTotalItems">
              <td colspan="5" class="empty">
                {{ t("funds.capitalHistory.empty") }}
              </td>
            </tr>
            <tr v-for="record in pagedCapitalAdjustments" :key="record.id">
              <td>{{ formatEffectiveDate(record.effective_date) }}</td>
              <td>{{ record.funding_group }}</td>
              <td class="numeric">{{ formatCurrency(record.amount, capitalCurrency(record)) }}</td>
              <td>{{ currencyLabel(capitalCurrency(record)) }}</td>
              <td>
                <div class="capital-notes-cell">
                  <span>{{ record.notes || "-" }}</span>
                  <span
                    v-if="isFutureEffectiveDate(record.effective_date)"
                    class="capital-status capital-status--scheduled"
                  >
                    {{ t("funds.capitalHistory.futureBadge") }}
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationControls
        v-if="capitalTotalItems || capitalTotalPages > 1"
        :page="capitalPage"
        :total-pages="capitalTotalPages"
        :total-items="capitalTotalItems"
        @update:page="setCapitalPage"
      />
    </div>

    <div
      v-if="capitalDialog.open"
      class="modal-backdrop"
      @click.self="closeCapitalDialog"
    >
      <div class="modal-panel" role="dialog" aria-modal="true">
        <header class="modal-header">
          <h3>
            {{
              t("funds.capitalDialog.title", {
                name: capitalDialog.group?.name ?? "",
              })
            }}
          </h3>
          <p class="modal-description">
            {{ t("funds.capitalDialog.description") }}
          </p>
        </header>
        <form class="modal-form" @submit.prevent="handleCapitalSubmit">
          <label>
            <span>{{ t("funds.capitalDialog.amount") }}</span>
            <input
              v-model.number="capitalForm.amount"
              type="number"
              min="0"
              step="0.01"
              required
            />
          </label>
          <label>
            <span>{{ t("funds.capitalDialog.date") }}</span>
            <input v-model="capitalForm.effective_date" type="date" required />
          </label>
          <label>
            <span>{{ t("funds.capitalDialog.notes") }}</span>
            <textarea v-model.trim="capitalForm.notes" rows="3"></textarea>
          </label>
          <div class="modal-actions">
            <button
              type="button"
              class="ghost-btn"
              :disabled="capitalPending"
              @click="closeCapitalDialog"
            >
              {{ t("common.actions.cancel") }}
            </button>
            <button
              type="submit"
              class="primary-btn"
              :disabled="!capitalValid || capitalPending"
            >
              {{ t("funds.capitalDialog.submit") }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import PaginationControls from "./ui/PaginationControls.vue";
import { usePagination } from "@/composables/usePagination";
import type {
  AggregatedFundSnapshot,
  Currency,
  FundSnapshot,
  FundingCapitalAdjustment,
  FundingCapitalAdjustmentRequest,
  FundingGroup,
} from "@/types/api";
import BaseSelect from "./ui/BaseSelect.vue";

const props = defineProps<{
  fundingGroups: FundingGroup[];
  funds: FundSnapshot[];
  aggregated: AggregatedFundSnapshot[];
  capitalAdjustments: FundingCapitalAdjustment[];
}>();

type CapitalAdditionEvent = {
  data: FundingCapitalAdjustmentRequest;
  onDone: (success: boolean) => void;
};

const emit = defineEmits<{
  (e: "create", payload: FundingGroup): void;
  (e: "delete", name: string): void;
  (e: "refresh"): void;
  (e: "add-capital", payload: CapitalAdditionEvent): void;
}>();

const { t } = useI18n();

const pending = ref(false);
const form = reactive<FundingGroup>({
  name: "",
  currency: "JPY",
  initial_amount: 0,
  notes: "",
});

const todayIso = () => new Date().toISOString().slice(0, 10);

type CapitalFormState = {
  amount: number | null;
  effective_date: string;
  notes: string;
};

const capitalDialog = reactive({
  open: false,
  group: null as FundingGroup | null,
});

const capitalForm = reactive<CapitalFormState>({
  amount: null,
  effective_date: todayIso(),
  notes: "",
});

const capitalPending = ref(false);
const capitalValid = computed(() => {
  return (
    capitalDialog.group !== null &&
    capitalForm.amount !== null &&
    capitalForm.amount > 0 &&
    capitalForm.effective_date.trim().length > 0
  );
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

const fundingGroupCurrency = computed<Record<string, Currency>>(() => {
  return props.fundingGroups.reduce((acc, group) => {
    acc[group.name] = group.currency;
    return acc;
  }, {} as Record<string, Currency>);
});

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

const sortedCapitalAdjustments = computed(() => {
  return [...props.capitalAdjustments].sort((a, b) => {
    if (a.effective_date === b.effective_date) {
      return b.id.localeCompare(a.id);
    }
    return b.effective_date.localeCompare(a.effective_date);
  });
});

const {
  page: capitalPage,
  totalPages: capitalTotalPages,
  totalItems: capitalTotalItems,
  offset: capitalOffset,
  pageSize: capitalPageSize,
  setPage: setCapitalPage,
} = usePagination(computed(() => sortedCapitalAdjustments.value.length), {
  pageSize: 25,
});

const pagedCapitalAdjustments = computed(() =>
  sortedCapitalAdjustments.value.slice(
    capitalOffset.value,
    capitalOffset.value + capitalPageSize
  )
);

const BASE_CURRENCY: Currency = "JPY";
const exchangeRateInput = ref<string | number>("150");

function normalizeRateInput(): string {
  const value = exchangeRateInput.value;
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : "";
  }
  if (typeof value === "string") {
    return value;
  }
  return "";
}

const hasRateInput = computed(() => normalizeRateInput().trim().length > 0);
const parsedExchangeRate = computed<number | null>(() => {
  const raw = normalizeRateInput().trim();
  if (!raw) {
    return null;
  }
  const value = Number.parseFloat(raw);
  return Number.isFinite(value) && value > 0 ? value : null;
});

const lastValidExchangeRate = ref<number | null>(parsedExchangeRate.value);
watch(parsedExchangeRate, (value: number | null) => {
  if (value && value > 0) {
    lastValidExchangeRate.value = value;
  }
});

const effectiveExchangeRate = computed<number | null>(() =>
  parsedExchangeRate.value ?? lastValidExchangeRate.value
);

const needsExchangeRate = computed(() =>
  props.aggregated.some((item) => item.currency !== BASE_CURRENCY)
);

const needsRateReminder = computed(
  () => needsExchangeRate.value && !effectiveExchangeRate.value
);

const rateError = computed(() => {
  if (!hasRateInput.value) {
    return "";
  }
  return parsedExchangeRate.value ? "" : t("funds.exchangeRate.invalid");
});

type CombinedAccumulator = {
  group_count: number;
  initial_amount: number;
  cash_balance: number;
  holding_cost: number;
  current_total: number;
  total_pl: number;
  current_year_pl: number;
  previous_year_pl: number;
  baseline_current: number;
  baseline_previous: number;
};

function makeAccumulator(): CombinedAccumulator {
  return {
    group_count: 0,
    initial_amount: 0,
    cash_balance: 0,
    holding_cost: 0,
    current_total: 0,
    total_pl: 0,
    current_year_pl: 0,
    previous_year_pl: 0,
    baseline_current: 0,
    baseline_previous: 0,
  };
}

function convertToBase(value: number, currency: Currency, rate: number | null): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  if (currency === BASE_CURRENCY) {
    return value;
  }
  if (!rate || rate <= 0) {
    return 0;
  }
  return value * rate;
}

function roundCurrency(value: number): number {
  return Math.round(value * 100) / 100;
}

function computeRatio(numerator: number, denominator: number): number | null {
  return Math.abs(denominator) > 1e-9 ? numerator / denominator : null;
}

function roundRatio(value: number | null): number | null {
  if (value === null) {
    return null;
  }
  return Math.round(value * 1_000_000) / 1_000_000;
}

function finalizeAccumulator(bucket: CombinedAccumulator): AggregatedFundSnapshot {
  const currentRatio = roundRatio(computeRatio(bucket.current_year_pl, bucket.baseline_current));
  const previousRatio = roundRatio(
    computeRatio(bucket.previous_year_pl, bucket.baseline_previous)
  );

  return {
    currency: BASE_CURRENCY,
    group_count: bucket.group_count,
    initial_amount: roundCurrency(bucket.initial_amount),
    cash_balance: roundCurrency(bucket.cash_balance),
    holding_cost: roundCurrency(bucket.holding_cost),
    current_total: roundCurrency(bucket.current_total),
    total_pl: roundCurrency(bucket.total_pl),
    current_year_pl: roundCurrency(bucket.current_year_pl),
    current_year_pl_ratio: currentRatio,
    previous_year_pl: roundCurrency(bucket.previous_year_pl),
    previous_year_pl_ratio: previousRatio,
  };
}

const combinedTotals = computed<AggregatedFundSnapshot | null>(() => {
  if (!props.aggregated.length) {
    return null;
  }

  const rate = effectiveExchangeRate.value;
  if (needsExchangeRate.value && (!rate || rate <= 0)) {
    return null;
  }

  const bucket = makeAccumulator();

  props.aggregated.forEach((item) => {
    const baselineCurrent = item.current_total - item.current_year_pl;
    const baselinePrevious = baselineCurrent - item.previous_year_pl;

    bucket.group_count += item.group_count;
    bucket.initial_amount += convertToBase(item.initial_amount, item.currency, rate);
    bucket.cash_balance += convertToBase(item.cash_balance, item.currency, rate);
    bucket.holding_cost += convertToBase(item.holding_cost, item.currency, rate);
    bucket.current_total += convertToBase(item.current_total, item.currency, rate);
    bucket.total_pl += convertToBase(item.total_pl, item.currency, rate);
    bucket.current_year_pl += convertToBase(item.current_year_pl, item.currency, rate);
    bucket.previous_year_pl += convertToBase(item.previous_year_pl, item.currency, rate);
    bucket.baseline_current += convertToBase(baselineCurrent, item.currency, rate);
    bucket.baseline_previous += convertToBase(baselinePrevious, item.currency, rate);
  });

  return finalizeAccumulator(bucket);
});

function handleRateBlur() {
  const raw = normalizeRateInput().trim();

  if (!raw) {
    lastValidExchangeRate.value = null;
    exchangeRateInput.value = "";
    return;
  }

  const parsed = parsedExchangeRate.value;
  if (parsed && parsed > 0) {
    const formatted = parsed.toFixed(2);
    exchangeRateInput.value = formatted;
    lastValidExchangeRate.value = parsed;
    return;
  }

  if (lastValidExchangeRate.value !== null) {
    exchangeRateInput.value = lastValidExchangeRate.value.toFixed(2);
  } else {
    exchangeRateInput.value = "";
  }
}

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

function capitalCurrency(record: FundingCapitalAdjustment): Currency {
  return fundingGroupCurrency.value[record.funding_group] ?? "JPY";
}

function formatEffectiveDate(value: string): string {
  return value || "-";
}

function isFutureEffectiveDate(value: string): boolean {
  if (!value) {
    return false;
  }
  return value > todayIso();
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

function openCapitalDialog(group: FundingGroup) {
  capitalDialog.open = true;
  capitalDialog.group = group;
  capitalForm.amount = null;
  capitalForm.effective_date = todayIso();
  capitalForm.notes = "";
}

function closeCapitalDialog() {
  if (capitalPending.value) {
    return;
  }
  capitalDialog.open = false;
  capitalDialog.group = null;
}

function handleCapitalSubmit() {
  if (!capitalDialog.group || !capitalValid.value) {
    return;
  }
  capitalPending.value = true;
  const payload: FundingCapitalAdjustmentRequest = {
    funding_group: capitalDialog.group.name,
    amount: Number(capitalForm.amount),
    effective_date: capitalForm.effective_date,
    notes: capitalForm.notes?.trim() || undefined,
  };
  emit("add-capital", {
    data: payload,
    onDone(success) {
      capitalPending.value = false;
      if (success) {
        closeCapitalDialog();
      }
    },
  });
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

.capital-history-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.capital-history-description {
  margin: 0.35rem 0 0;
  color: var(--text-dim);
  font-size: 0.85rem;
}

.capital-history-count {
  color: var(--text-dim);
  font-size: 0.85rem;
  align-self: center;
  white-space: nowrap;
}

.capital-status {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.1rem 0.6rem;
  border-radius: 999px;
  font-size: 0.7rem;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-weight: 600;
}

.capital-status--scheduled {
  background: rgba(15, 167, 201, 0.08);
  border: 1px solid rgba(15, 167, 201, 0.35);
  color: var(--accent);
}

.capital-notes-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
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

.aggregate-controls {
  display: grid;
  gap: 0.35rem 1.5rem;
  grid-template-columns: minmax(220px, 260px) 1fr;
  align-items: center;
}

.exchange-rate-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.exchange-rate-field span {
  font-size: 0.82rem;
  color: var(--text-dim);
  letter-spacing: 0.35px;
}

.exchange-rate-field input {
  border-radius: var(--radius-md);
  border: 1px solid rgba(97, 123, 177, 0.4);
  padding: 0.45rem 0.65rem;
  background: rgba(255, 255, 255, 0.85);
  font-size: 0.95rem;
  color: var(--text);
  transition: border-color var(--transition), box-shadow var(--transition);
}

.exchange-rate-field input:focus {
  outline: none;
  border-color: rgba(15, 167, 201, 0.6);
  box-shadow: 0 0 0 2px rgba(15, 167, 201, 0.18);
}

.exchange-rate-hint {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-faint);
}

.exchange-rate-hint--warning {
  color: var(--accent);
  font-weight: 600;
}

.actions-cell {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.ghost-btn {
  border: 1px solid var(--divider);
  background: transparent;
  color: var(--text);
  padding: 0.45rem 0.9rem;
  border-radius: var(--radius-sm);
  font-weight: 600;
  transition: background 0.2s ease, color 0.2s ease;
}

.ghost-btn:hover {
  background: rgba(15, 167, 201, 0.1);
  color: var(--accent);
}

.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(6, 24, 54, 0.5);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  z-index: 2000;
}

.modal-panel {
  width: min(420px, 100%);
  border-radius: var(--radius-lg);
  background: var(--panel);
  border: 1px solid var(--divider);
  box-shadow: var(--shadow-strong);
  padding: clamp(1.2rem, 2vw, 1.6rem);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--accent);
}

.modal-description {
  margin: 0.3rem 0 0;
  color: var(--text-dim);
  font-size: 0.9rem;
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.modal-form label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: var(--text-dim);
}

.modal-form input,
.modal-form textarea {
  border-radius: var(--radius-sm);
  border: 1px solid var(--divider);
  padding: 0.6rem 0.8rem;
  background: var(--panel-alt);
  color: var(--text);
  font-size: 0.95rem;
}

.modal-form textarea {
  resize: vertical;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.exchange-rate-error {
  margin: 0;
  font-size: 0.8rem;
  color: var(--accent-red);
  font-weight: 600;
}

@media (max-width: 720px) {
  .aggregate-controls {
    grid-template-columns: 1fr;
    gap: 0.45rem;
  }
}

.combined-row {
  background: linear-gradient(90deg, rgba(15, 167, 201, 0.09), rgba(15, 167, 201, 0));
  font-weight: 600;
}

.combined-row .numeric {
  font-weight: 600;
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
