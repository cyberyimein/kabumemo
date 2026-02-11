<template>
  <section class="panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("transactions.title") }}</h2>
        <p>{{ t("transactions.description") }}</p>
      </div>
      <div class="header-actions">
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
      <div class="form-column">
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

        <form class="surface" @submit.prevent="handleSubmit">
        <h3>
          {{
            isEditing
              ? t("transactions.formTitleEdit")
              : t("transactions.formTitle")
          }}
        </h3>
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
            <span>{{ t("transactions.fields.grossAmount") }}</span>
            <input
              v-model.number="form.gross_amount"
              type="number"
              step="0.01"
              required
            />
          </label>
          <label>
            <span>{{ t("transactions.fields.fundingGroup") }}</span>
            <BaseSelect
              v-model="form.funding_group"
              :options="fundingGroupOptions"
              :placeholder="t('transactions.placeholders.fundingGroup')"
              :empty-label="t('common.states.none')"
            />
          </label>
          <label v-if="tradeType === 'sell'" class="full">
            <span>{{ t("transactions.fields.crossCurrency") }}</span>
            <div class="toggle-group inline-toggle" role="radiogroup">
              <button
                type="button"
                :class="['toggle-pill', { active: form.cross_currency }]"
                @click="setCrossCurrency(true)"
              >
                {{ t("common.toggle.on") }}
              </button>
              <button
                type="button"
                :class="['toggle-pill', { active: !form.cross_currency }]"
                @click="setCrossCurrency(false)"
              >
                {{ t("common.toggle.off") }}
              </button>
            </div>
          </label>
          <label v-if="tradeType === 'sell' && form.cross_currency">
            <span>{{ t("transactions.fields.buyCurrency") }}</span>
            <BaseSelect
              v-model="form.buy_currency"
              :options="crossCurrencyOptions"
            />
          </label>
          <label v-if="tradeType === 'sell' && form.cross_currency">
            <span>{{ t("transactions.fields.sellCurrency") }}</span>
            <BaseSelect
              v-model="form.sell_currency"
              :options="crossCurrencyOptions"
            />
          </label>
          <label v-if="tradeType === 'sell' && form.cross_currency">
            <span>{{ t("transactions.fields.fxFromAmount") }}</span>
            <input
              v-model.number="form.fx_from_amount"
              type="number"
              step="0.01"
              min="0"
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
        <h3>{{ t("transactions.historyTitle", { count: transactions.length }) }}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th v-if="roundYieldMode" class="select-column">
                  {{ t("transactions.roundYield.table.select") }}
                </th>
                <th>{{ t("transactions.table.date") }}</th>
                <th>{{ t("transactions.table.symbol") }}</th>
                <th class="numeric">{{ t("transactions.table.quantity") }}</th>
                <th class="numeric">{{ t("transactions.table.amount") }}</th>
                <th>{{ t("transactions.table.fundingGroup") }}</th>
                <th>{{ t("transactions.table.currency") }}</th>
                <th>{{ t("transactions.table.market") }}</th>
                <th>{{ t("transactions.table.taxed") }}</th>
                <th class="actions-column">{{ t("transactions.table.actions") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!transactions.length">
                <td :colspan="roundYieldMode ? 10 : 9" class="empty">
                  {{ t("transactions.empty") }}
                </td>
              </tr>
              <tr
                v-for="tx in pagedTransactions"
                :key="tx.id"
                :class="[
                  'interactive-row',
                  tx.quantity < 0 ? 'is-sell' : 'is-buy',
                  { 'is-selected': isSelected(tx.id), 'selection-mode': roundYieldMode }
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
                <td>{{ tx.symbol }}</td>
                <td :class="['numeric', { negative: tx.quantity < 0, positive: tx.quantity > 0 }]">
                  {{ formatNumber(tx.quantity) }}
                </td>
                <td class="numeric">{{ formatCurrency(tx.gross_amount, tx.cash_currency) }}</td>
                <td>{{ tx.funding_group }}</td>
                <td>{{ tx.cash_currency }}</td>
                <td>{{ marketLabel(tx.market) }}</td>
                <td>{{ tx.taxed }}</td>
                <td class="actions-column">
                  <div class="row-actions">
                    <button
                      type="button"
                      class="ghost-button"
                      @click.stop="startEditing(tx)"
                    >
                      {{ t("common.actions.edit") }}
                    </button>
                    <button
                      type="button"
                      class="ghost-button danger"
                      @click.stop="confirmDelete(tx)"
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
  FxExchangeRecord,
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
  fxExchanges: FxExchangeRecord[];
}>();

type FxDraft = {
  exchange_date: string;
  from_currency: Currency;
  to_currency: Currency;
  from_amount: number;
  to_amount: number;
  rate: number;
};

type TransactionCreatePayload = {
  transaction: TransactionCreate;
  fxDraft?: FxDraft | null;
};

type UpdateEventPayload = {
  id: string;
  data: TransactionUpdate;
  fxDraft?: FxDraft | null;
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
const tradeType = ref<"buy" | "sell">("buy");
const editingId = ref<string | null>(null);
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

const fxLookup = computed(() => {
  const map = new Map<string, FxExchangeRecord>();
  for (const fx of props.fxExchanges) {
    if (fx.transaction_id) {
      map.set(fx.transaction_id, fx);
    }
  }
  return map;
});

const selectedTransactions = computed(() =>
  selectedTransactionIds.value
    .map((id) => transactionLookup.value.get(id))
    .filter((item): item is Transaction => Boolean(item))
);

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
  buy_currency: Currency | null;
  sell_currency: Currency | null;
  fx_from_amount: number | null;
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
  },
  { immediate: true }
);

watch(
  () => form.funding_group,
  (groupName) => {
    const group = props.fundingGroups.find((item) => item.name === groupName);
    if (group) {
      if (!form.cross_currency) {
        form.cash_currency = form.market === "JP" ? "JPY" : group.currency;
      } else {
        const defaults = defaultCrossCurrencies(group.currency);
        form.buy_currency = defaults.buy;
        form.sell_currency = defaults.sell;
        form.cash_currency = defaults.buy;
      }
    }
  }
);

watch(
  () => form.market,
  (market) => {
    if (form.cross_currency) {
      return;
    }
    if (market === "JP") {
      form.cash_currency = "JPY";
    } else {
      const group = props.fundingGroups.find(
        (item) => item.name === form.funding_group
      );
      form.cash_currency = group?.currency ?? form.cash_currency ?? "USD";
    }
  },
  { immediate: true }
);

watch(
  () => form.cross_currency,
  (enabled) => {
    if (!enabled) {
      form.buy_currency = null;
      form.sell_currency = null;
      form.fx_from_amount = null;
      return;
    }
    if (tradeType.value !== "sell") {
      form.cross_currency = false;
      return;
    }
    const group = props.fundingGroups.find((item) => item.name === form.funding_group);
    const defaults = defaultCrossCurrencies(group?.currency ?? "USD");
    form.buy_currency = defaults.buy;
    form.sell_currency = defaults.sell;
    form.cash_currency = defaults.buy;
    if (!form.fx_from_amount) {
      form.fx_from_amount = null;
    }
  }
);

watch(
  () => form.buy_currency,
  (value) => {
    if (form.cross_currency && value) {
      form.cash_currency = value;
    }
  }
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
    cash_currency: "JPY",
    cross_currency: false,
    buy_currency: null,
    sell_currency: null,
    market: "JP",
    taxed: "Y",
    memo: "",
    fx_from_amount: null,
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
  prefillFromTransaction(tx);
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
  form.quantity = Math.max(1, Math.floor(Math.abs(Number(tx.quantity))));
  form.gross_amount = Math.abs(Number(tx.gross_amount));
  form.cash_currency = tx.cash_currency;
  form.cross_currency = tx.cross_currency;
  form.buy_currency = tx.buy_currency ?? null;
  form.sell_currency = tx.sell_currency ?? null;
  form.taxed = tx.taxed;
  form.memo = tx.memo ?? "";

  const fx = fxLookup.value.get(tx.id);
  if (tx.cross_currency && fx) {
    form.fx_from_amount = Number(fx.from_amount);
  } else if (tx.cross_currency) {
    form.fx_from_amount = null;
  } else {
    form.fx_from_amount = null;
  }
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

function startEditing(tx: Transaction) {
  if (roundYieldMode.value) {
    exitRoundYieldMode();
  }
  editingId.value = tx.id;
  setTradeType(tx.quantity < 0 ? "sell" : "buy");
  setMarket(tx.market === "US" ? "US" : "JP");
  populateFormFromTransaction(tx);
}

function cancelEditing() {
  resetFormState();
}

async function handleSubmit() {
  if (!form.trade_date || !form.symbol || !form.funding_group) {
    return;
  }
  if (tradeType.value === "sell" && form.cross_currency) {
    if (!form.buy_currency || !form.sell_currency || form.buy_currency === form.sell_currency) {
      return;
    }
    if (form.fx_from_amount !== null && form.fx_from_amount <= 0) {
      emit("notify", {
        type: "error",
        message: t("transactions.validation.fxAmountRequired"),
      });
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
      cash_currency: form.cash_currency,
      cross_currency: form.cross_currency,
      buy_currency: form.cross_currency ? form.buy_currency ?? undefined : undefined,
      sell_currency: form.cross_currency ? form.sell_currency ?? undefined : undefined,
      market: form.market,
      taxed: form.taxed,
      memo: normalizedMemo,
    };

    const fxSellAmount = form.fx_from_amount ?? null;
    const fxDraft: FxDraft | null =
      form.cross_currency && fxSellAmount && fxSellAmount > 0
        ? {
            exchange_date: form.trade_date,
            from_currency: form.sell_currency as Currency,
            to_currency: form.buy_currency as Currency,
            from_amount: Number(fxSellAmount),
            to_amount: Number(form.gross_amount),
            rate: computeFxRate(
              form.sell_currency as Currency,
              form.buy_currency as Currency,
              Number(fxSellAmount),
              Number(form.gross_amount)
            ),
          }
        : null;

    if (isEditing.value && editingId.value) {
      await new Promise<void>((resolve) => {
        emit("update", {
          id: editingId.value as string,
          data: updatePayload,
          fxDraft,
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
        cross_currency: updatePayload.cross_currency,
        buy_currency: updatePayload.buy_currency ?? undefined,
        sell_currency: updatePayload.sell_currency ?? undefined,
        market: updatePayload.market,
        taxed: updatePayload.taxed,
        memo: normalizedMemo ?? undefined,
      };
      emit("create", { transaction: createPayload, fxDraft });
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

function setCrossCurrency(value: boolean) {
  form.cross_currency = value;
}

function defaultCrossCurrencies(groupCurrency: Currency) {
  if (groupCurrency === "USD") {
    return { buy: "USD" as Currency, sell: "JPY" as Currency };
  }
  return { buy: "JPY" as Currency, sell: "USD" as Currency };
}

function computeFxRate(
  fromCurrency: Currency,
  toCurrency: Currency,
  fromAmount: number,
  toAmount: number
): number {
  if (!fromAmount || !toAmount) {
    return 0;
  }
  if (fromCurrency === "JPY" && toCurrency === "USD") {
    return fromAmount / toAmount;
  }
  if (fromCurrency === "USD" && toCurrency === "JPY") {
    return toAmount / fromAmount;
  }
  return fromAmount / toAmount;
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
  gap: 1.75rem;
  padding: clamp(1.5rem, 3vw, 2rem);
  border-radius: var(--radius-lg);
  border: 1px solid var(--divider);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
  overflow: hidden;
}

.panel::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.85), rgba(255, 255, 255, 0.12) 48%, rgba(255, 255, 255, 0.05)),
    repeating-linear-gradient(90deg, transparent 0 42px, rgba(0, 0, 0, 0.04) 42px 43px);
  mix-blend-mode: overlay;
  opacity: 0.45;
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
  border-radius: 999px;
  font-size: 0.85rem;
  letter-spacing: 0.4px;
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
  grid-template-columns: minmax(320px, 420px) 1fr;
}

.form-column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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
  padding: clamp(1.25rem, 2.5vw, 1.75rem);
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.surface h3 {
  font-size: 0.95rem;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: var(--text-faint);
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem 1.25rem;
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
  font-weight: 600;
  letter-spacing: 0.4px;
  text-transform: uppercase;
  color: var(--text-faint);
}

.form-grid input,
.form-grid textarea {
  border: 1px solid var(--divider);
  border-radius: var(--radius-md);
  padding: 0.55rem 0.75rem;
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
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  align-items: start;
}

.toggle-group {
  align-self: stretch;
  display: flex;
  justify-content: flex-start;
  width: 100%;
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
  padding: 0.45rem 1.15rem;
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

.select-column {
  width: 3.25rem;
  text-align: center;
}

.select-column input {
  width: 1.15rem;
  height: 1.15rem;
  accent-color: var(--accent);
  cursor: pointer;
}

.actions-column {
  width: 1%;
  white-space: nowrap;
  text-align: right;
}

.row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.ghost-button {
  border: 1px solid var(--divider);
  background: transparent;
  color: var(--text-dim);
  padding: 0.3rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  cursor: pointer;
  transition: color var(--transition), border-color var(--transition), background var(--transition);
}

.ghost-button:hover:not(:disabled) {
  color: var(--accent);
  border-color: rgba(15, 167, 201, 0.45);
  background: rgba(15, 167, 201, 0.08);
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
  background: linear-gradient(180deg, rgba(11, 61, 145, 0.08), rgba(11, 61, 145, 0));
  color: var(--accent);
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 1.2px;
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
  background: rgba(141, 164, 255, 0.08);
}

.interactive-row {
  cursor: pointer;
  transition: background var(--transition), transform var(--transition), box-shadow var(--transition);
}

.interactive-row.is-buy {
  background: linear-gradient(90deg, rgba(15, 167, 201, 0.08), transparent 65%);
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--accent-cyan) 18%, transparent),
    transparent 65%
  );
  box-shadow: inset 0.35rem 0 0 rgba(15, 167, 201, 0.35);
  box-shadow: inset 0.35rem 0 0 color-mix(in srgb, var(--accent-cyan) 55%, transparent);
}

.interactive-row.is-sell {
  background: linear-gradient(90deg, rgba(225, 57, 45, 0.08), transparent 65%);
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--accent-red) 20%, transparent),
    transparent 65%
  );
  box-shadow: inset 0.35rem 0 0 rgba(225, 57, 45, 0.35);
  box-shadow: inset 0.35rem 0 0 color-mix(in srgb, var(--accent-red) 55%, transparent);
}

.interactive-row.selection-mode {
  cursor: pointer;
}

.interactive-row.is-selected {
  box-shadow: inset 0 0 0 2px color-mix(in srgb, var(--accent-warm) 55%, transparent);
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--accent-warm) 32%, transparent),
    transparent 65%
  ) !important;
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
