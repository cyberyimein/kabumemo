<template>
  <section class="panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("transactions.title") }}</h2>
        <p>{{ t("transactions.description") }}</p>
      </div>
      <button type="button" class="refresh-button" @click="$emit('refresh')">
        {{ t("common.actions.refresh") }}
      </button>
    </header>

    <div class="panel-grid">
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
          <label>
            <span>{{ t("transactions.fields.cashCurrency") }}</span>
            <BaseSelect
              v-model="form.cash_currency"
              :options="cashCurrencyOptions"
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

      <div class="surface">
        <h3>{{ t("transactions.historyTitle", { count: transactions.length }) }}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
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
                <td colspan="9" class="empty">{{ t("transactions.empty") }}</td>
              </tr>
              <tr
                v-for="tx in pagedTransactions"
                :key="tx.id"
                :class="['interactive-row', tx.quantity < 0 ? 'is-sell' : 'is-buy']"
                tabindex="0"
                @click="prefillFromTransaction(tx)"
                @keydown.enter.prevent="prefillFromTransaction(tx)"
                @keydown.space.prevent="prefillFromTransaction(tx)"
              >
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
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import type {
  FundingGroup,
  TaxStatus,
  Transaction,
  TransactionCreate,
  TransactionUpdate,
} from "@/types/api";
import BaseSelect from "./ui/BaseSelect.vue";
import BaseDatePicker from "./ui/BaseDatePicker.vue";
import PaginationControls from "./ui/PaginationControls.vue";
import { usePagination } from "@/composables/usePagination";

const props = defineProps<{
  transactions: Transaction[];
  fundingGroups: FundingGroup[];
}>();

type UpdateEventPayload = {
  id: string;
  data: TransactionUpdate;
  onDone: (success: boolean) => void;
};

const emit = defineEmits<{
  (e: "create", payload: TransactionCreate): void;
  (e: "refresh"): void;
  (e: "delete", id: string): void;
  (e: "update", payload: UpdateEventPayload): void;
}>();

const { t } = useI18n();

const pending = ref(false);
const tradeType = ref<"buy" | "sell">("buy");
const editingId = ref<string | null>(null);
const isEditing = computed(() => editingId.value !== null);

type TransactionForm = TransactionCreate & { taxed: TaxStatus; memo?: string | null };

const form = reactive<TransactionForm>(resetForm());

const fundingGroupOptions = computed(() =>
  props.fundingGroups.map((group) => ({
    label: group.name,
    value: group.name,
  }))
);

const cashCurrencyOptions = computed(() => [
  {
    label: t("common.currencies.JPY"),
    value: "JPY",
  },
  {
    label: t("common.currencies.USD"),
    value: "USD",
    disabled: form.market === "JP",
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
      form.cash_currency = form.market === "JP" ? "JPY" : group.currency;
    }
  }
);

watch(
  () => form.market,
  (market) => {
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

function populateFormFromTransaction(tx: Transaction) {
  form.trade_date = tx.trade_date;
  form.symbol = tx.symbol;
  form.funding_group = tx.funding_group;
  form.quantity = Math.max(1, Math.floor(Math.abs(Number(tx.quantity))));
  form.gross_amount = Math.abs(Number(tx.gross_amount));
  form.cash_currency = tx.cash_currency;
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
        market: updatePayload.market,
        taxed: updatePayload.taxed,
        memo: normalizedMemo ?? undefined,
      };
      emit("create", createPayload);
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

</style>
