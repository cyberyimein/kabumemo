<template>
  <section class="panel app-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("transactions.title") }}</h2>
        <p>{{ t("transactions.description") }}</p>
      </div>
      <div class="header-actions">
        <button
          v-if="!roundYieldMode"
          type="button"
          class="primary-btn header-button header-button--primary"
          @click="manualFormOpen = !manualFormOpen"
        >
          {{ manualFormOpen ? t("transactions.manual.close") : t("transactions.manual.open") }}
        </button>
        <template v-if="roundYieldMode">
          <button
            type="button"
            class="ghost-button header-button"
            :disabled="calculatingYield"
            @click="exitRoundYieldMode"
          >
            {{ t("transactions.roundYield.cancel") }}
          </button>
          <button
            type="button"
            class="primary-btn header-button header-button--primary"
            :disabled="calculatingYield"
            :aria-disabled="!canCalculateYield"
            @click="handleCalculateYield"
          >
            <span v-if="calculatingYield" class="spinner-inline"></span>
            {{ t("transactions.roundYield.calculate") }}
          </button>
        </template>
        <button
          v-else
          type="button"
          class="ghost-button header-button"
          @click="enterRoundYieldMode"
        >
          {{ t("transactions.roundYield.enter") }}
        </button>
        <button type="button" class="refresh-button header-button" @click="$emit('refresh')">
          {{ t("common.actions.refresh") }}
        </button>
      </div>
    </header>

    <div class="panel-grid">
      <div v-if="roundYieldMode || manualFormOpen || isEditing" class="form-column">
        <transition name="summary-fade">
          <div
            v-if="roundYieldMode"
            class="round-yield-summary"
            role="region"
            :aria-live="hasAttemptedYield ? 'assertive' : 'polite'"
          >
            <p>
              {{
                t("transactions.roundYield.selectionSummary", {
                  count: selectedTransactionCount,
                  total: transactions.length,
                })
              }}
            </p>
            <p class="hint">
              {{ t("transactions.roundYield.selectionHint") }}
            </p>
            <ul v-if="selectedTransactionCount" class="selection-breakdown">
              <li>
                {{ t("transactions.roundYield.buyCount", { count: selectedBuyCount }) }}
              </li>
              <li>
                {{ t("transactions.roundYield.sellCount", { count: selectedSellCount }) }}
              </li>
              <li>
                {{
                  t("transactions.roundYield.netQuantity", {
                    quantity: formatNumber(selectedNetQuantity),
                  })
                }}
              </li>
            </ul>
            <ul v-if="hasAttemptedYield && selectionIssues.length" class="selection-issues">
              <li v-for="issue in selectionIssues" :key="issue">
                {{ issue }}
              </li>
            </ul>
            <p v-if="hasAttemptedYield && yieldError" class="error-banner">
              {{ yieldError }}
            </p>
          </div>
        </transition>

        <form class="surface manual-entry" @submit.prevent="handleSubmit">
        <div class="manual-entry__header">
          <div>
            <h3>{{ isEditing ? t("transactions.formTitleEdit") : t("transactions.formTitle") }}</h3>
            <p>{{ t("transactions.manual.hint") }}</p>
          </div>
          <button v-if="!isEditing" type="button" class="ghost-button" @click="manualFormOpen = false">{{ t("common.actions.close") }}</button>
        </div>
        <p v-if="isEditing" class="editing-hint">
          {{ t("transactions.editingHint") }}
        </p>
        <div class="toggle-row">
          <div
            class="toggle-group"
            role="radiogroup"
            :aria-label="t('transactions.tradeTypeLabel')"
          >
            <button
              type="button"
              :class="['toggle-pill', 'trade-toggle', 'trade-buy', { active: tradeType === 'buy' }]"
              @click="setTradeType('buy')"
            >
              {{ t("common.toggle.buy") }}
            </button>
            <button
              type="button"
              :class="['toggle-pill', 'trade-toggle', 'trade-sell', { active: tradeType === 'sell' }]"
              @click="setTradeType('sell')"
            >
              {{ t("common.toggle.sell") }}
            </button>
          </div>
          <div
            class="toggle-group"
            role="radiogroup"
            :aria-label="t('transactions.marketLabel')"
          >
            <button
              type="button"
              :class="['toggle-pill', 'market-toggle', { active: form.market === 'JP' }]"
              @click="setMarket('JP')"
            >
              {{ t("common.toggle.market.jp") }}
            </button>
            <button
              type="button"
              :class="['toggle-pill', 'market-toggle', { active: form.market === 'US' }]"
              @click="setMarket('US')"
            >
              {{ t("common.toggle.market.us") }}
            </button>
          </div>
        </div>
        <div class="form-grid">
          <label>
            <span>{{ t("transactions.fields.tradeDate") }}</span>
            <BaseDatePicker v-model="form.trade_date" />
          </label>
          <label>
            <span>{{ t("transactions.fields.symbol") }}</span>
            <input
              v-model.trim="form.symbol"
              type="text"
              required
              :placeholder="t('transactions.placeholders.symbol')"
            />
          </label>
          <label>
            <span>{{ t("transactions.fields.quantity") }}</span>
            <input
              v-model.number="form.quantity"
              type="number"
              min="1"
              step="1"
              required
            />
          </label>
          <label>
            <span>{{ t("transactions.fields.positionGroup") }}</span>
            <BaseSelect
              v-model="form.funding_group"
              :options="fundingGroupOptions"
              :placeholder="t('transactions.placeholders.fundingGroup')"
              :empty-label="t('common.states.none')"
            />
          </label>
          <label v-if="tradeType === 'sell'">
            <span>{{ t("transactions.fields.settlementGroup") }}</span>
            <BaseSelect
              v-model="form.settlement_group"
              :options="fundingGroupOptions"
              :placeholder="t('transactions.placeholders.settlementGroup')"
              :empty-label="t('common.states.none')"
            />
          </label>
          <label v-if="tradeType === 'sell'">
            <span>{{ t("transactions.fields.tradeCurrency") }}</span>
            <BaseSelect
              v-model="form.trade_currency"
              :options="crossCurrencyOptions"
            />
          </label>
          <label v-if="tradeType === 'sell'">
            <span>{{ t("transactions.fields.tradeAmount") }}</span>
            <input
              v-model.number="form.trade_amount"
              type="number"
              step="0.01"
              min="0"
              required
            />
          </label>
          <label v-if="tradeType === 'sell'">
            <span>{{ t("transactions.fields.settlementCurrency") }}</span>
            <BaseSelect
              v-model="form.settlement_currency"
              :options="crossCurrencyOptions"
            />
          </label>
          <label>
            <span>{{ tradeType === 'sell' ? t("transactions.fields.settlementAmount") : t("transactions.fields.grossAmount") }}</span>
            <input
              v-model.number="form.gross_amount"
              type="number"
              step="0.01"
              required
            />
          </label>
          <label>
            <span>{{ t("transactions.fields.taxed") }}</span>
            <BaseSelect
              v-model="form.taxed"
              :options="taxOptions"
              :disabled="tradeType === 'buy'"
            />
          </label>
          <label class="memo-field">
            <span>{{ t("transactions.fields.memo") }}</span>
            <textarea
              v-model.trim="form.memo"
              rows="2"
              :placeholder="t('transactions.placeholders.memo')"
            ></textarea>
          </label>
        </div>
        <div class="form-actions">
          <button
            v-if="isEditing"
            type="button"
            class="ghost-button"
            :disabled="pending"
            @click="cancelEditing"
          >
            {{ t("common.actions.cancel") }}
          </button>
          <button type="submit" class="primary-btn" :disabled="pending">
            {{
              isEditing
                ? t("transactions.update")
                : t("transactions.submit")
            }}
          </button>
        </div>
        </form>
      </div>

      <div class="surface">
        <div class="section-toolbar">
          <h3>{{ t("transactions.historyTitle", { count: transactions.length }) }}</h3>
          <div class="section-toolbar__actions">
            <span v-if="activeTransaction && !roundYieldMode" class="selection-pill">
              {{ activeTransaction.symbol }} · {{ activeTransaction.trade_date }}
            </span>
            <button
              v-if="!roundYieldMode"
              type="button"
              class="ghost-button"
              :disabled="!activeTransaction"
              @click="editActiveTransaction"
            >
              {{ t("common.actions.edit") }}
            </button>
            <button
              v-if="!roundYieldMode"
              type="button"
              class="ghost-button danger"
              :disabled="!activeTransaction"
              @click="deleteActiveTransaction"
            >
              {{ t("common.actions.delete") }}
            </button>
          </div>
        </div>
        <div v-if="activeTransaction" class="selection-details">
          <span class="selection-details__label">{{ t("common.labels.memo") }}</span>
          <p class="selection-details__content">{{ activeTransaction.memo || "-" }}</p>
        </div>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th v-if="roundYieldMode" class="select-column">{{ t("common.select") }}</th>
                <th>{{ t("transactions.table.date") }}</th>
                <th>{{ t("transactions.table.symbol") }}</th>
                <th class="numeric">{{ t("transactions.table.quantity") }}</th>
                <th class="numeric">{{ t("transactions.table.amount") }}</th>
                <th>{{ t("transactions.table.details") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!transactions.length">
                <td :colspan="roundYieldMode ? 6 : 5" class="empty">
                  {{ t("transactions.empty") }}
                </td>
              </tr>
              <tr
                v-for="tx in pagedTransactions"
                :key="tx.id"
                :class="[
                  'interactive-row',
                  tx.quantity < 0 ? 'is-sell' : 'is-buy',
                  {
                    'is-selected': roundYieldMode ? isSelected(tx.id) : activeTransactionId === tx.id,
                    'selection-mode': roundYieldMode,
                  }
                ]"
                tabindex="0"
                @click="handleRowActivation(tx)"
                @keydown.enter.prevent="handleRowActivation(tx)"
                @keydown.space.prevent="handleRowActivation(tx)"
              >
                <td v-if="roundYieldMode" class="select-column" @click.stop>
                  <input
                    type="checkbox"
                    :checked="isSelected(tx.id)"
                    :aria-label="t('transactions.roundYield.table.selectRow', { symbol: tx.symbol, date: tx.trade_date })"
                    @change="toggleSelection(tx.id)"
                  />
                </td>
                <td>{{ tx.trade_date }}</td>
                <td><div class="instrument-cell"><strong>{{ tx.symbol }}</strong><small>{{ marketLabel(tx.market) }}</small></div></td>
                <td :class="['numeric', { negative: tx.quantity < 0, positive: tx.quantity > 0 }]">
                  {{ formatNumber(tx.quantity) }}
                </td>
                <td class="numeric">{{ formatCurrency(tx.gross_amount, tx.cash_currency) }}</td>
                <td>
                  <div class="inline-tags">
                    <span class="flat-tag" :class="tx.quantity < 0 ? 'flat-tag--sell' : 'flat-tag--buy'">
                      {{ tx.quantity < 0 ? t("common.toggle.sell") : t("common.toggle.buy") }}
                    </span>
                    <span class="flat-tag" v-if="(tx.settlement_group || tx.funding_group) === (tx.position_group || tx.funding_group)">{{ tx.position_group || tx.funding_group }}</span>
                    <span class="flat-tag" v-else>
                      {{ tx.position_group || tx.funding_group }} → {{ tx.settlement_group || tx.funding_group }}
                    </span>
                    <span
                      v-if="(tx.settlement_currency || tx.cash_currency) !== (tx.settlement_group || tx.funding_group)"
                      class="flat-tag flat-tag--currency"
                    >{{ tx.settlement_currency || tx.cash_currency }}</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <PaginationControls
          v-if="transactionsTotalItems || transactionsTotalPages > 1"
          :page="transactionsPage"
          :total-pages="transactionsTotalPages"
          :total-items="transactionsTotalItems"
          @update:page="setTransactionsPage"
        />
      </div>
    </div>
  </section>

  <div
    v-if="yieldResult"
    class="modal-backdrop"
    role="dialog"
    :aria-label="t('transactions.roundYield.dialogTitle')"
    aria-modal="true"
    @click.self="closeYieldResult"
  >
    <div class="modal-panel" tabindex="-1">
      <header class="modal-header">
        <h3>{{ t("transactions.roundYield.dialogTitle") }}</h3>
        <button type="button" class="ghost-button" @click="closeYieldResult">
          {{ t("transactions.roundYield.close") }}
        </button>
      </header>
      <section class="modal-body">
        <p class="modal-intro">
          {{
            t("transactions.roundYield.dialogSummary", {
              symbol: yieldResult.symbol,
              group: yieldResult.funding_group,
              currency: yieldResult.cash_currency,
            })
          }}
        </p>
        <dl class="metrics-grid">
          <div>
            <dt>{{ t("transactions.roundYield.metrics.totalBuy") }}</dt>
            <dd>{{ formatCurrency(yieldResult.total_buy_amount, yieldResult.cash_currency) }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.totalSell") }}</dt>
            <dd>{{ formatCurrency(yieldResult.total_sell_amount, yieldResult.cash_currency) }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.grossProfit") }}</dt>
            <dd>{{ formatCurrency(yieldResult.gross_profit, yieldResult.cash_currency) }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.netProfit") }}</dt>
            <dd>{{ formatCurrency(yieldResult.net_profit, yieldResult.cash_currency) }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.return") }}</dt>
            <dd>{{ formatPercent(yieldResult.return_ratio) }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.returnAfterTax") }}</dt>
            <dd>{{ formatPercent(yieldResult.return_after_tax) }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.annualized") }}</dt>
            <dd>{{ formatPercent(yieldResult.annualized_return) }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.annualizedAfterTax") }}</dt>
            <dd>{{ formatPercent(yieldResult.annualized_return_after_tax) }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.holdingDays") }}</dt>
            <dd>{{ t("transactions.roundYield.holdingDaysValue", { days: yieldResult.holding_days }) }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.taxTotal") }}</dt>
            <dd>{{ formatCurrency(yieldResult.tax_total, yieldResult.cash_currency) }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.windowStart") }}</dt>
            <dd>{{ yieldResult.trade_window_start }}</dd>
          </div>
          <div>
            <dt>{{ t("transactions.roundYield.metrics.windowEnd") }}</dt>
            <dd>{{ yieldResult.trade_window_end }}</dd>
          </div>
        </dl>
      </section>
      <footer class="modal-footer">
        <button type="button" class="primary-btn" @click="closeYieldResult">
          {{ t("transactions.roundYield.close") }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import type {
  Currency,
  FundingGroup,
  TaxStatus,
  Transaction,
  TransactionCreate,
  TransactionUpdate,
  RoundTripYieldResponse,
} from "@/types/api";
import BaseSelect from "./ui/BaseSelect.vue";
import BaseDatePicker from "./ui/BaseDatePicker.vue";
import PaginationControls from "./ui/PaginationControls.vue";
import { usePagination } from "@/composables/usePagination";
import { ApiError, calculateRoundYield } from "@/services/api";

const props = defineProps<{
  transactions: Transaction[];
  fundingGroups: FundingGroup[];
}>();

type TransactionCreatePayload = {
  transaction: TransactionCreate;
};

type UpdateEventPayload = {
  id: string;
  data: TransactionUpdate;
  onDone: (success: boolean) => void;
};

const emit = defineEmits<{
  (e: "create", payload: TransactionCreatePayload): void;
  (e: "refresh"): void;
  (e: "delete", id: string): void;
  (e: "update", payload: UpdateEventPayload): void;
  (
    e: "notify",
    payload: { type: "success" | "error" | "info"; message: string }
  ): void;
}>();

const { t, locale } = useI18n();

const pending = ref(false);
const manualFormOpen = ref(false);
const tradeType = ref<"buy" | "sell">("buy");
const editingId = ref<string | null>(null);
const activeTransactionId = ref<string | null>(null);
const isEditing = computed(() => editingId.value !== null);

const roundYieldMode = ref(false);
const selectedTransactionIds = ref<string[]>([]);
const calculatingYield = ref(false);
const yieldError = ref<string | null>(null);
const yieldResult = ref<RoundTripYieldResponse | null>(null);
const hasAttemptedYield = ref(false);

const selectedTransactionCount = computed(() => selectedTransactionIds.value.length);

const transactionLookup = computed(() => {
  const map = new Map<string, Transaction>();
  for (const tx of props.transactions) {
    map.set(tx.id, tx);
  }
  return map;
});

const selectedTransactions = computed(() =>
  selectedTransactionIds.value
    .map((id) => transactionLookup.value.get(id))
    .filter((item): item is Transaction => Boolean(item))
);

const activeTransaction = computed(() => {
  if (!activeTransactionId.value) {
    return null;
  }
  return transactionLookup.value.get(activeTransactionId.value) ?? null;
});

const selectedBuyCount = computed(() =>
  selectedTransactions.value.filter((tx) => tx.quantity > 0).length
);

const selectedSellCount = computed(() =>
  selectedTransactions.value.filter((tx) => tx.quantity < 0).length
);

const selectedNetQuantity = computed(() =>
  selectedTransactions.value.reduce((sum, tx) => sum + tx.quantity, 0)
);

const selectionIssues = computed(() => {
  const issues: string[] = [];
  const txs = selectedTransactions.value;
  if (txs.length < 2) {
    issues.push(t("transactions.roundYield.validation.minimum"));
    return issues;
  }

  const symbols = new Set(txs.map((tx) => tx.symbol));
  if (symbols.size > 1) {
    issues.push(t("transactions.roundYield.validation.symbol"));
  }

  const groups = new Set(txs.map((tx) => tx.funding_group));
  if (groups.size > 1) {
    issues.push(t("transactions.roundYield.validation.fundingGroup"));
  }

  const markets = new Set(txs.map((tx) => tx.market));
  if (markets.size > 1) {
    issues.push(t("transactions.roundYield.validation.market"));
  }

  const currencies = new Set(txs.map((tx) => tx.cash_currency));
  if (currencies.size > 1) {
    issues.push(t("transactions.roundYield.validation.currency"));
  }

  const netQuantity = selectedNetQuantity.value;
  if (Math.abs(netQuantity) > 1e-6) {
    issues.push(
      t("transactions.roundYield.validation.netQuantityMismatch", {
        quantity: formatNumber(netQuantity),
      })
    );
  }

  return issues;
});

const canCalculateYield = computed(() => selectionIssues.value.length === 0);
const primarySelectionIssue = computed(() => selectionIssues.value[0] ?? null);

type TransactionForm = TransactionCreate & {
  taxed: TaxStatus;
  memo?: string | null;
  settlement_group: string;
  trade_currency: Currency;
  trade_amount: number;
  settlement_currency: Currency;
};

const form = reactive<TransactionForm>(resetForm());

const fundingGroupOptions = computed(() =>
  props.fundingGroups.map((group) => ({
    label: group.name,
    value: group.name,
  }))
);

const crossCurrencyOptions = computed(() => [
  {
    label: t("common.currencies.JPY"),
    value: "JPY",
  },
  {
    label: t("common.currencies.USD"),
    value: "USD",
  },
]);

const taxOptions = computed(() => [
  {
    label: t("transactions.taxOptions.Y"),
    value: "Y",
  },
  {
    label: t("transactions.taxOptions.N"),
    value: "N",
  },
]);

watch(
  () => form.quantity,
  (qty) => {
    const numericQty = Number(qty);
    if (Number.isNaN(numericQty)) {
      form.quantity = 1;
      return;
    }
    const normalized = Math.max(1, Math.floor(Math.abs(numericQty)));
    if (normalized !== qty) {
      form.quantity = normalized;
    }
  }
);

watch(
  tradeType,
  (type) => {
    if (isEditing.value) {
      return;
    }
    form.taxed = type === "sell" ? "N" : "Y";
    if (type === "buy") {
      form.settlement_group = form.funding_group;
    }
  },
  { immediate: true }
);

watch(
  () => form.funding_group,
  (groupName) => {
    const group = props.fundingGroups.find((item) => item.name === groupName);
    if (group) {
      if (tradeType.value === "buy" || !form.settlement_group) {
        form.settlement_group = group.name;
      }
      if (tradeType.value === "buy") {
        const currency = groupCurrency(group.name) ?? group.currency;
        form.settlement_currency = currency;
        form.cash_currency = currency;
        form.trade_currency = form.market === "US" ? "USD" : "JPY";
      }
    }
  }
);

watch(
  () => form.market,
  (market) => {
    if (market === "JP") {
      form.trade_currency = "JPY";
      form.settlement_currency = "JPY";
      form.cash_currency = "JPY";
      return;
    }
    form.trade_currency = "USD";
    const settlementCurrency = groupCurrency(
      tradeType.value === "buy" ? form.funding_group : form.settlement_group || form.funding_group
    );
    form.settlement_currency = settlementCurrency ?? form.settlement_currency ?? "USD";
    form.cash_currency = form.settlement_currency;
  },
  { immediate: true }
);

watch(
  () => form.settlement_group,
  (groupName) => {
    if (tradeType.value !== "sell") {
      return;
    }
    const currency = groupCurrency(groupName);
    if (!currency) {
      return;
    }
    form.settlement_currency = currency;
    form.cash_currency = currency;
  },
  { immediate: true }
);

watch(
  () => props.transactions,
  (transactions) => {
    if (!selectedTransactionIds.value.length) {
      return;
    }
    const available = new Set(transactions.map((tx) => tx.id));
    selectedTransactionIds.value = selectedTransactionIds.value.filter((id) =>
      available.has(id)
    );
    if (activeTransactionId.value && !available.has(activeTransactionId.value)) {
      activeTransactionId.value = null;
    }
  }
);

watch(
  selectedTransactionIds,
  () => {
    if (yieldError.value) {
      yieldError.value = null;
    }
    hasAttemptedYield.value = false;
  }
);

const sortedTransactions = computed(() =>
  [...props.transactions].sort((a, b) => (a.trade_date < b.trade_date ? 1 : -1))
);

const transactionsTotal = computed(() => props.transactions.length);
const {
  page: transactionsPage,
  totalPages: transactionsTotalPages,
  totalItems: transactionsTotalItems,
  offset: transactionsOffset,
  pageSize: transactionsPageSize,
  setPage: setTransactionsPage,
} = usePagination(transactionsTotal);

const pagedTransactions = computed(() =>
  sortedTransactions.value.slice(
    transactionsOffset.value,
    transactionsOffset.value + transactionsPageSize
  )
);

function resetForm(): TransactionForm {
  return {
    trade_date: new Date().toISOString().slice(0, 10),
    symbol: "",
    quantity: 1,
    gross_amount: 0,
    funding_group: "",
    settlement_group: "",
    cash_currency: "JPY",
    trade_currency: "JPY",
    trade_amount: 0,
    settlement_currency: "JPY",
    cross_currency: false,
    market: "JP",
    taxed: "Y",
    memo: "",
  };
}

function resetFormState() {
  editingId.value = null;
  Object.assign(form, resetForm());
  tradeType.value = "buy";
}

function enterRoundYieldMode() {
  roundYieldMode.value = true;
  selectedTransactionIds.value = [];
  yieldError.value = null;
  yieldResult.value = null;
  calculatingYield.value = false;
  hasAttemptedYield.value = false;
  if (isEditing.value) {
    resetFormState();
  }
}

function exitRoundYieldMode() {
  roundYieldMode.value = false;
  selectedTransactionIds.value = [];
  yieldError.value = null;
  yieldResult.value = null;
  calculatingYield.value = false;
  hasAttemptedYield.value = false;
}

function isSelected(id: string): boolean {
  return selectedTransactionIds.value.includes(id);
}

function toggleSelection(id: string) {
  if (!roundYieldMode.value) {
    return;
  }
  const exists = isSelected(id);
  selectedTransactionIds.value = exists
    ? selectedTransactionIds.value.filter((item) => item !== id)
    : [...selectedTransactionIds.value, id];
}

function handleRowActivation(tx: Transaction) {
  if (roundYieldMode.value) {
    toggleSelection(tx.id);
    return;
  }
  selectActiveTransaction(tx.id);
}

function selectActiveTransaction(id: string) {
  activeTransactionId.value = id;
}

function resolveErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return t("transactions.roundYield.genericError");
}

async function handleCalculateYield() {
  if (calculatingYield.value) {
    return;
  }

  hasAttemptedYield.value = true;

  if (!canCalculateYield.value) {
    const message =
      primarySelectionIssue.value ??
      t("transactions.roundYield.validation.minimum");
    yieldResult.value = null;
    yieldError.value = null;
    emit("notify", { type: "error", message });
    return;
  }

  calculatingYield.value = true;
  yieldError.value = null;

  try {
    const result = await calculateRoundYield({
      transaction_ids: selectedTransactionIds.value,
    });
    yieldResult.value = result;
  } catch (error: unknown) {
    yieldResult.value = null;
    const message = resolveErrorMessage(error);
    yieldError.value = message;
    emit("notify", { type: "error", message });
  } finally {
    calculatingYield.value = false;
  }
}

function closeYieldResult() {
  yieldResult.value = null;
}

function populateFormFromTransaction(tx: Transaction) {
  form.trade_date = tx.trade_date;
  form.symbol = tx.symbol;
  form.funding_group = tx.funding_group;
  form.settlement_group = tx.settlement_group ?? tx.funding_group;
  form.quantity = Math.max(1, Math.floor(Math.abs(Number(tx.quantity))));
  form.gross_amount = Math.abs(Number(tx.gross_amount));
  form.cash_currency = tx.cash_currency;
  form.trade_currency = tx.trade_currency ?? (tx.market === "US" ? "USD" : "JPY");
  form.trade_amount = Math.abs(Number(tx.trade_amount ?? tx.gross_amount));
  form.settlement_currency = tx.settlement_currency ?? tx.cash_currency;
  form.cross_currency = false;
  form.taxed = tx.taxed;
  form.memo = tx.memo ?? "";
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("ja-JP", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatCurrency(value: number, currency: string): string {
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

function formatPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat(locale.value, {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function marketLabel(value: string): string {
  return value === "US"
    ? t("common.toggle.market.us")
    : t("common.toggle.market.jp");
}

function prefillFromTransaction(tx: Transaction) {
  if (isEditing.value) {
    return;
  }
  setTradeType(tx.quantity < 0 ? "sell" : "buy");
  setMarket(tx.market === "US" ? "US" : "JP");
  populateFormFromTransaction(tx);
}

function confirmDelete(tx: Transaction) {
  const confirmed = window.confirm(
    t("transactions.confirm.delete", {
      symbol: tx.symbol,
      date: tx.trade_date,
    })
  );
  if (confirmed) {
    emit("delete", tx.id);
  }
}

function editActiveTransaction() {
  if (!activeTransaction.value) {
    return;
  }
  startEditing(activeTransaction.value);
}

function deleteActiveTransaction() {
  if (!activeTransaction.value) {
    return;
  }
  confirmDelete(activeTransaction.value);
}

function startEditing(tx: Transaction) {
  if (roundYieldMode.value) {
    exitRoundYieldMode();
  }
  editingId.value = tx.id;
  manualFormOpen.value = true;
  setTradeType(tx.quantity < 0 ? "sell" : "buy");
  setMarket(tx.market === "US" ? "US" : "JP");
  populateFormFromTransaction(tx);
}

function cancelEditing() {
  resetFormState();
  manualFormOpen.value = false;
}

async function handleSubmit() {
  if (!form.trade_date || !form.symbol || !form.funding_group) {
    return;
  }
  if (tradeType.value === "sell" && !form.settlement_group) {
    return;
  }
  if (tradeType.value === "sell") {
    const settlementGroupCurrency = groupCurrency(form.settlement_group);
    if (settlementGroupCurrency && settlementGroupCurrency !== form.settlement_currency) {
      emit("notify", {
        type: "error",
        message: t("transactions.validation.settlementCurrencyMismatch"),
      });
      return;
    }
    if (Number(form.trade_amount) <= 0 || Number(form.gross_amount) <= 0) {
      return;
    }
  }
  pending.value = true;
  try {
    const signedQuantity =
      tradeType.value === "sell"
        ? -Math.abs(Number(form.quantity))
        : Math.abs(Number(form.quantity));
    const trimmedMemo = form.memo?.trim() ?? "";
    const normalizedMemo = trimmedMemo.length ? trimmedMemo : null;
    const updatePayload: TransactionUpdate = {
      trade_date: form.trade_date,
      symbol: form.symbol,
      quantity: signedQuantity,
      gross_amount: Number(form.gross_amount),
      funding_group: form.funding_group,
      cash_currency: tradeType.value === "sell" ? form.settlement_currency : form.cash_currency,
      position_group: form.funding_group,
      settlement_group: tradeType.value === "sell" ? form.settlement_group : form.funding_group,
      trade_currency: tradeType.value === "sell" ? form.trade_currency : undefined,
      trade_amount: tradeType.value === "sell" ? Number(form.trade_amount) : undefined,
      settlement_currency: tradeType.value === "sell" ? form.settlement_currency : undefined,
      settlement_amount: tradeType.value === "sell" ? Number(form.gross_amount) : undefined,
      cross_currency: false,
      market: form.market,
      taxed: form.taxed,
      memo: normalizedMemo,
    };

    if (isEditing.value && editingId.value) {
      await new Promise<void>((resolve) => {
        emit("update", {
          id: editingId.value as string,
          data: updatePayload,
          onDone: (success: boolean) => {
            if (success) {
              resetFormState();
            }
            resolve();
          },
        });
      });
    } else {
      const createPayload: TransactionCreate = {
        trade_date: updatePayload.trade_date,
        symbol: updatePayload.symbol,
        quantity: updatePayload.quantity,
        gross_amount: updatePayload.gross_amount,
        funding_group: updatePayload.funding_group,
        cash_currency: updatePayload.cash_currency,
        position_group: updatePayload.position_group,
        settlement_group: updatePayload.settlement_group,
        trade_currency: updatePayload.trade_currency,
        trade_amount: updatePayload.trade_amount,
        settlement_currency: updatePayload.settlement_currency,
        settlement_amount: updatePayload.settlement_amount,
        cross_currency: false,
        market: updatePayload.market,
        taxed: updatePayload.taxed,
        memo: normalizedMemo ?? undefined,
      };
      emit("create", { transaction: createPayload });
      setTransactionsPage(1);
      resetFormState();
    }
  } finally {
    pending.value = false;
  }
}

function setTradeType(type: "buy" | "sell") {
  tradeType.value = type;
}

function groupCurrency(name: string | null | undefined): Currency | null {
  if (!name) {
    return null;
  }
  return props.fundingGroups.find((group) => group.name === name)?.currency ?? null;
}

function setMarket(type: "JP" | "US") {
  form.market = type;
}
</script>

<style scoped>
.panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: clamp(1.5rem, 3vw, 2rem);
  border-radius: var(--radius-lg);
  border: 1px solid var(--divider);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
  overflow: hidden;
}

.panel::before {
  content: none;
}

.panel > * {
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
  font-size: 1.35rem;
  letter-spacing: 0.6px;
  color: var(--accent);
}

.panel-header p {
  margin-top: 0.4rem;
  color: var(--text-dim);
  font-size: 0.9rem;
}

.summary-fade-enter-active,
.summary-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.summary-fade-enter-from,
.summary-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.header-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.35rem;
  padding: 0.55rem 1.1rem;
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  letter-spacing: 0;
}

.header-button--primary {
  padding: 0.55rem 1.6rem;
  font-weight: 600;
}

.spinner-inline {
  display: inline-block;
  width: 0.9rem;
  height: 0.9rem;
  border-radius: 50%;
  border: 2px solid rgba(15, 167, 201, 0.25);
  border-top-color: var(--accent);
  margin-right: 0.5rem;
  animation: spin 0.75s linear infinite;
  vertical-align: middle;
}

.panel-grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: 1fr;
}

.form-column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-column > .surface {
  border: 1px solid var(--divider);
}

.manual-entry { background: #fff; padding: 1.2rem 1.3rem; }
.manual-entry__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding-bottom: .9rem; border-bottom: 1px solid var(--divider); }
.manual-entry__header p { margin-top: .3rem; color: var(--text-faint); font-size: .8rem; }

@media (max-width: 1024px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }
}

.surface {
  border-radius: var(--radius-lg);
  border: 1px solid var(--divider);
  background: var(--panel-alt);
  box-shadow: none;
  padding: clamp(1.25rem, 2.5vw, 1.75rem);
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.surface h3 {
  font-size: 1rem;
  letter-spacing: -0.01em;
  text-transform: none;
  color: var(--text);
}

.editing-hint {
  margin: -0.25rem 0 0.5rem;
  font-size: 0.85rem;
  color: var(--accent);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}


.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: .85rem 1rem;
  align-items: end;
}

.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: var(--text-dim);
}

.form-grid label span {
  font-weight: 500;
  letter-spacing: 0;
  text-transform: none;
  color: var(--text-faint);
}

.form-grid input,
.form-grid textarea {
  border: 1px solid var(--divider);
  border-radius: var(--radius-md);
  min-height: 42px;
  padding: 0.6rem 0.75rem;
  font-size: 0.95rem;
  background: var(--panel);
  color: var(--text);
  box-shadow: inset 0 1px 2px rgba(14, 30, 64, 0.06);
  transition: border-color var(--transition), box-shadow var(--transition);
}

.form-grid input:focus,
.form-grid textarea:focus {
  outline: none;
  border-color: rgba(15, 167, 201, 0.45);
  box-shadow: 0 0 0 3px rgba(15, 167, 201, 0.12);
}

.form-grid textarea {
  min-height: 4.25rem;
  resize: vertical;
}

.memo-field {
  align-self: stretch;
  grid-column: span 2;
}

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .memo-field {
    grid-column: 1;
  }
}

@media (max-width: 768px) {
  .panel {
    padding: 1.2rem;
  }

  .header-actions {
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .table-scroll table {
    min-width: 520px;
  }

  .form-actions {
    flex-wrap: wrap;
  }
}



.toggle-row {
  display: flex;
  gap: .75rem;
  align-items: start;
}

.toggle-group {
  align-self: stretch;
  display: flex;
  justify-content: flex-start;
  width: auto;
  padding: 0.25rem;
  border-radius: 999px;
  border: 1px solid var(--divider);
  background: var(--panel);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.35);
  gap: 0.2rem;
}

@media (max-width: 768px) {
  .toggle-row {
    grid-template-columns: 1fr;
  }

  .toggle-group {
    justify-content: center;
  }
}

.toggle-pill {
  border: none;
  background: transparent;
  color: var(--text-dim);
  min-height: 32px;
  padding: 0.35rem 1rem;
  border-radius: 999px;
  font-size: 0.85rem;
  letter-spacing: 0.45px;
  cursor: pointer;
  transition: background var(--transition), color var(--transition), transform var(--transition), box-shadow var(--transition);
}

.toggle-pill:hover {
  color: var(--accent);

.inline-toggle {
  align-self: flex-start;
}
}

.toggle-pill.active:not(.trade-toggle) {
  background: linear-gradient(180deg, var(--panel), rgba(15, 167, 201, 0.12));
  color: var(--accent);
  box-shadow: inset 0 0 0 1px rgba(15, 167, 201, 0.2), 0 6px 12px -8px rgba(15, 167, 201, 0.45);
  transform: translateY(-1px);
}

.toggle-pill.trade-toggle {
  font-weight: 600;
}

.toggle-pill.trade-buy:hover {
  color: var(--accent-cyan);
}

.toggle-pill.trade-sell:hover {
  color: var(--accent-red);
}

.toggle-pill.trade-buy.active {
  background: linear-gradient(180deg, rgba(15, 167, 201, 0.16), rgba(15, 167, 201, 0.28));
  color: var(--accent-cyan);
  box-shadow: inset 0 0 0 1px rgba(15, 167, 201, 0.35), 0 6px 14px -8px rgba(15, 167, 201, 0.45);
  transform: translateY(-1px);
}

.toggle-pill.trade-sell.active {
  background: linear-gradient(180deg, rgba(225, 57, 45, 0.18), rgba(225, 57, 45, 0.32));
  color: var(--accent-red);
  box-shadow: inset 0 0 0 1px rgba(225, 57, 45, 0.35), 0 6px 14px -8px rgba(225, 57, 45, 0.45);
  transform: translateY(-1px);
}

.primary-btn {
  align-self: flex-end;
}

.table-scroll {
  overflow: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: var(--panel);
}

.table-scroll table {
  min-width: 640px;
}

.instrument-cell { display: grid; gap: .15rem; }
.instrument-cell strong { font-size: .94rem; letter-spacing: .01em; }
.instrument-cell small { color: var(--text-faint); font-size: .7rem; }

.select-column {
  width: 3rem;
  text-align: center;
}

.select-column input {
  width: 1.15rem;
  height: 1.15rem;
  accent-color: var(--accent);
  cursor: pointer;
}

.ghost-button {
  border: 1px solid var(--divider);
  background: #fff;
  color: var(--text-dim);
  padding: 0.3rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  cursor: pointer;
  transition: color var(--transition), border-color var(--transition), background var(--transition);
}

.ghost-button:hover:not(:disabled) {
  color: var(--accent-strong);
  border-color: rgba(30, 156, 90, 0.24);
  background: var(--panel-soft);
}

.ghost-button.danger {
  color: var(--accent-red);
  border-color: rgba(244, 67, 54, 0.45);
}

.ghost-button.danger:hover:not(:disabled) {
  background: rgba(244, 67, 54, 0.08);
}

.ghost-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.table-scroll thead {
  background: var(--panel-soft);
  color: var(--text-dim);
  font-size: 0.78rem;
  text-transform: none;
  letter-spacing: 0;
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
  background: rgba(30, 156, 90, 0.04);
}

.interactive-row {
  cursor: pointer;
  transition: background var(--transition), box-shadow var(--transition);
}

.interactive-row.selection-mode {
  cursor: pointer;
}

.interactive-row.is-selected {
  box-shadow: inset 0 0 0 1px rgba(30, 156, 90, 0.28);
  background: rgba(30, 156, 90, 0.06) !important;
}

.selection-details {
  display: grid;
  gap: 0.35rem;
  padding: 0.9rem 1rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: #fff;
}

.selection-details__label {
  font-size: 0.76rem;
  color: var(--text-faint);
}

.selection-details__content {
  color: var(--text-dim);
  line-height: 1.5;
}

.interactive-row.is-buy:hover {
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--accent-cyan) 32%, transparent),
    transparent 65%
  );
}

.interactive-row.is-sell:hover {
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--accent-red) 34%, transparent),
    transparent 65%
  );
}

.interactive-row:focus-visible {
  outline: 2px solid var(--accent-cyan);
  outline-offset: -2px;
}

.interactive-row:active {
  transform: scale(0.995);
}

.round-yield-summary {
  margin: 0 0 0.85rem;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  border: 1px dashed color-mix(in srgb, var(--accent-warm) 45%, transparent);
  background: color-mix(in srgb, var(--accent-warm) 16%, transparent);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: var(--text-dim);
}

.round-yield-summary .hint {
  font-style: italic;
  color: color-mix(in srgb, var(--accent-warm) 45%, var(--text-faint));
}

.selection-breakdown {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.4rem 0.75rem;
  padding-left: 1rem;
  color: color-mix(in srgb, var(--accent-warm) 55%, var(--text));
}

.selection-breakdown li {
  list-style: disc;
  white-space: nowrap;
}

.selection-issues {
  margin: 0.25rem 0 0;
  padding-left: 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  color: color-mix(in srgb, var(--accent-warm) 60%, var(--text));
  font-size: 0.85rem;
}

.selection-issues li {
  list-style: disc;
}

.error-banner {
  margin-top: 0.25rem;
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-sm);
  background: rgba(244, 67, 54, 0.12);
  border: 1px solid rgba(244, 67, 54, 0.32);
  color: var(--accent-red);
  font-size: 0.85rem;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(8, 15, 30, 0.48);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  z-index: 999;
}

.modal-panel {
  width: min(620px, 100%);
  background: var(--panel);
  border-radius: var(--radius-lg);
  border: 1px solid var(--divider);
  box-shadow: var(--shadow-strong);
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 90vh;
  overflow: hidden;
}

.modal-header,
.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  background: linear-gradient(180deg, rgba(11, 61, 145, 0.08), transparent);
}

.modal-footer {
  justify-content: flex-end;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.05rem;
  color: var(--accent);
}

.modal-body {
  padding: 0 1.5rem 1.5rem;
  overflow-y: auto;
  color: var(--text);
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.modal-intro {
  margin: 0;
  font-size: 0.95rem;
  color: var(--text-dim);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
}

.metrics-grid div {
  background: rgba(15, 167, 201, 0.05);
  border-radius: var(--radius-md);
  padding: 0.9rem;
  border: 1px solid rgba(15, 167, 201, 0.12);
}

.metrics-grid dt {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-faint);
  margin-bottom: 0.25rem;
}

.metrics-grid dd {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text);
}
.empty {
  text-align: center;
  color: var(--text-faint);
}

.negative {
  color: var(--accent-red);
  font-weight: 600;
}

.positive {
  color: var(--accent-cyan);
  font-weight: 600;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

</style>
