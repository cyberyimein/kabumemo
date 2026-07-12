<template>
  <section class="panel surface-panel app-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("imports.title") }}</h2>
        <p>{{ t("imports.description") }}</p>
      </div>
    </header>

    <div class="panel-grid">
      <form class="surface import-form" @submit.prevent="handlePreview">
        <h3>{{ t("imports.formTitle") }}</h3>
        <div class="report-file-grid">
          <label class="file-field">
            <span>{{ t("imports.fields.domestic") }}</span>
            <input
              ref="domesticInputRef"
              type="file"
              accept=".csv,text/csv"
              @change="onFileChange($event, 'domestic')"
            />
          </label>
          <label class="file-field">
            <span>{{ t("imports.fields.us") }}</span>
            <input
              ref="usInputRef"
              type="file"
              accept=".csv,text/csv"
              @change="onFileChange($event, 'us')"
            />
          </label>
          <label class="file-field">
            <span>{{ t("imports.fields.jpyCash") }}</span>
            <input
              ref="jpyCashInputRef"
              type="file"
              accept=".csv,text/csv"
              @change="onFileChange($event, 'jpyCash')"
            />
          </label>
          <label class="file-field">
            <span>{{ t("imports.fields.foreignCash") }}</span>
            <input
              ref="foreignCashInputRef"
              type="file"
              accept=".csv,text/csv"
              @change="onFileChange($event, 'foreignCash')"
            />
          </label>
        </div>
        <div class="mapping-header">
          <span>{{ t("imports.mappingTitle") }}</span>
          <small>{{ t("imports.mappingHint") }}</small>
        </div>
        <div class="mapping-grid">
          <label>
            <span>{{ t("imports.fields.jpyPositionGroup") }}</span>
            <BaseSelect v-model="positionGroupJpy" :options="jpyGroupOptions" />
          </label>
          <label>
            <span>{{ t("imports.fields.jpySettlementGroup") }}</span>
            <BaseSelect v-model="settlementGroupJpy" :options="jpyGroupOptions" />
          </label>
          <label>
            <span>{{ t("imports.fields.usdPositionGroup") }}</span>
            <BaseSelect v-model="positionGroupUsd" :options="usdGroupOptions" />
          </label>
          <label>
            <span>{{ t("imports.fields.usdSettlementGroup") }}</span>
            <BaseSelect v-model="settlementGroupUsd" :options="usdGroupOptions" />
          </label>
        </div>

        <div v-if="hasSelectedFiles" class="selected-files">
          <div v-if="domesticFile" class="selected-file">
            <span>{{ t("imports.selectedFile", { label: t("imports.fields.domestic"), file: domesticFile.file_name }) }}</span>
            <button type="button" class="ghost-btn" @click="clearSelectedFile('domestic')">
              {{ t("common.actions.cancel") }}
            </button>
          </div>
          <div v-if="usFile" class="selected-file">
            <span>{{ t("imports.selectedFile", { label: t("imports.fields.us"), file: usFile.file_name }) }}</span>
            <button type="button" class="ghost-btn" @click="clearSelectedFile('us')">
              {{ t("common.actions.cancel") }}
            </button>
          </div>
          <div v-if="jpyCashFile" class="selected-file">
            <span>{{ t("imports.selectedFile", { label: t("imports.fields.jpyCash"), file: jpyCashFile.file_name }) }}</span>
            <button type="button" class="ghost-btn" @click="clearSelectedFile('jpyCash')">
              {{ t("common.actions.cancel") }}
            </button>
          </div>
          <div v-if="foreignCashFile" class="selected-file">
            <span>{{ t("imports.selectedFile", { label: t("imports.fields.foreignCash"), file: foreignCashFile.file_name }) }}</span>
            <button type="button" class="ghost-btn" @click="clearSelectedFile('foreignCash')">
              {{ t("common.actions.cancel") }}
            </button>
          </div>
        </div>

        <div class="form-actions">
          <button type="submit" class="primary-btn" :disabled="pendingPreview">
            {{ t("imports.actions.preview") }}
          </button>
          <button
            type="button"
            class="ghost-btn"
            :disabled="(!preview.items.length && !preview.cash_items.length) || pendingApply"
            @click="handleApply"
          >
            {{ t("imports.actions.apply") }}
          </button>
          <button
            type="button"
            class="ghost-btn"
            :disabled="!canResetImport"
            @click="resetImportState"
          >
            {{ t("imports.actions.clear") }}
          </button>
        </div>
        <p v-if="message" class="hint">{{ message }}</p>
      </form>

      <div class="surface import-preview">
        <h3>{{ t("imports.previewTitle", { count: preview.items.length }) }}</h3>
        <ul v-if="preview.warnings.length" class="warnings">
          <li v-for="warning in preview.warnings" :key="warning">{{ warning }}</li>
        </ul>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("imports.table.date") }}</th>
                <th>{{ t("imports.table.symbol") }}</th>
                <th>{{ t("imports.table.market") }}</th>
                <th class="numeric">{{ t("imports.table.quantity") }}</th>
                <th class="numeric">{{ t("imports.table.tradeAmount") }}</th>
                <th class="numeric">{{ t("imports.table.settlementAmount") }}</th>
                <th>{{ t("imports.table.positionGroup") }}</th>
                <th>{{ t("imports.table.settlementGroup") }}</th>
                <th>{{ t("imports.table.accountType") }}</th>
                <th>{{ t("imports.table.taxed") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!preview.items.length">
                <td colspan="10" class="empty">{{ t("imports.empty") }}</td>
              </tr>
              <tr v-for="item in preview.items" :key="item.transaction_id">
                <td>{{ item.trade_date }}</td>
                <td>{{ item.symbol }}</td>
                <td>{{ item.market }}</td>
                <td class="numeric">{{ item.quantity }}</td>
                <td class="numeric">{{ formatCurrency(item.trade_amount, item.trade_currency) }}</td>
                <td class="numeric">{{ formatCurrency(item.settlement_amount, item.settlement_currency) }}</td>
                <td>{{ item.position_group }}</td>
                <td>{{ item.settlement_group }}</td>
                <td>{{ item.broker_account_type }}</td>
                <td>{{ item.taxed }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="surface import-cash-preview">
      <div class="import-subsection-header">
        <div>
          <h3>{{ t("imports.cashPreviewTitle", { count: preview.cash_items.length }) }}</h3>
          <p>{{ t("imports.cashPreviewDescription") }}</p>
        </div>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{{ t("imports.cashTable.date") }}</th>
              <th>{{ t("imports.cashTable.flow") }}</th>
              <th>{{ t("imports.cashTable.category") }}</th>
              <th>{{ t("imports.cashTable.description") }}</th>
              <th class="numeric">{{ t("imports.cashTable.amount") }}</th>
              <th>{{ t("imports.cashTable.link") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!preview.cash_items.length">
              <td colspan="6" class="empty">{{ t("imports.cashEmpty") }}</td>
            </tr>
            <tr v-for="item in preview.cash_items" :key="item.id">
              <td>{{ item.activity_date }}</td>
              <td>{{ t(`imports.cashDirection.${item.direction}`) }}</td>
              <td>{{ t(`imports.cashCategory.${item.category}`) }}</td>
              <td>{{ item.description }}</td>
              <td class="numeric">{{ formatCashAmount(item) }}</td>
              <td>
                <span v-if="item.link_group_id" class="ledger-link">{{ t("imports.cashLinked") }}</span>
                <span v-else>—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="surface import-cash-ledger">
      <div class="import-subsection-header">
        <div>
          <h3>{{ t("imports.cashLedgerTitle", { count: props.cashActivities.length }) }}</h3>
          <p>{{ t("imports.cashLedgerDescription") }}</p>
        </div>
      </div>
      <div class="table-scroll">
        <table>
          <tbody>
            <tr v-if="!props.cashActivities.length">
              <td class="empty">{{ t("imports.cashLedgerEmpty") }}</td>
            </tr>
            <tr v-for="item in props.cashActivities.slice(0, 100)" :key="item.id">
              <td>{{ item.activity_date }}</td>
              <td>{{ t(`imports.cashCategory.${item.category}`) }}</td>
              <td>{{ item.description }}</td>
              <td class="numeric">{{ formatCashAmount(item) }}</td>
              <td><span v-if="item.link_group_id" class="ledger-link">{{ t("imports.cashLinked") }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="lastAppliedCount" class="surface import-undo">
      <div class="import-subsection-header">
        <div>
          <h3>{{ t("imports.undo.title") }}</h3>
          <p>{{ t("imports.undo.description", { count: lastAppliedCount }) }}</p>
        </div>
        <button
          type="button"
          class="ghost-btn danger"
          :disabled="pendingUndo"
          @click="handleUndoLastImport"
        >
          {{ t("imports.actions.undo") }}
        </button>
      </div>
    </div>

    <div class="surface import-duplicates">
      <div class="import-subsection-header">
        <div>
          <h3>{{ t("imports.duplicates.title") }}</h3>
          <p>{{ t("imports.duplicates.description") }}</p>
        </div>
        <button
          type="button"
          class="ghost-btn"
          :disabled="pendingDuplicateScan"
          @click="handleScanDuplicates"
        >
          {{ t("imports.duplicates.actions.scan") }}
        </button>
      </div>

      <p v-if="duplicateReview.groups.length" class="hint">
        {{
          t("imports.duplicates.summary", {
            groups: duplicateReview.groups.length,
            transactions: duplicateReview.duplicate_transaction_count,
            suggested: duplicateReview.suggested_delete_count,
          })
        }}
      </p>
      <p v-else class="hint">
        {{ duplicateReviewLoaded ? t("imports.duplicates.empty") : t("imports.duplicates.idle") }}
      </p>

      <div
        v-for="group in duplicateReview.groups"
        :key="group.group_id"
        class="duplicate-group"
      >
        <div class="duplicate-group__header">
          <div>
            <strong>
              {{
                t("imports.duplicates.groupTitle", {
                  symbol: group.transactions[0]?.symbol ?? "—",
                  date: group.transactions[0]?.trade_date ?? "—",
                  count: group.transactions.length,
                })
              }}
            </strong>
            <p>{{ t("imports.duplicates.reason") }}</p>
          </div>
          <button type="button" class="ghost-btn" @click="selectSuggestedForGroup(group)">
            {{ t("imports.duplicates.actions.selectSuggestedGroup") }}
          </button>
        </div>

        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("imports.duplicates.table.select") }}</th>
                <th>{{ t("imports.duplicates.table.date") }}</th>
                <th>{{ t("imports.duplicates.table.symbol") }}</th>
                <th>{{ t("imports.duplicates.table.market") }}</th>
                <th class="numeric">{{ t("imports.duplicates.table.quantity") }}</th>
                <th class="numeric">{{ t("imports.duplicates.table.tradeAmount") }}</th>
                <th class="numeric">{{ t("imports.duplicates.table.settlementAmount") }}</th>
                <th>{{ t("imports.duplicates.table.fundingGroup") }}</th>
                <th>{{ t("imports.duplicates.table.accountType") }}</th>
                <th>{{ t("imports.duplicates.table.taxed") }}</th>
                <th>{{ t("imports.duplicates.table.status") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in group.transactions" :key="item.id">
                <td>
                  <input
                    type="checkbox"
                    :checked="selectedDuplicateIdSet.has(item.id)"
                    @change="onDuplicateCheckboxChange(item.id, $event)"
                  />
                </td>
                <td>{{ item.trade_date }}</td>
                <td>{{ item.symbol }}</td>
                <td>{{ item.market }}</td>
                <td class="numeric">{{ item.quantity }}</td>
                <td class="numeric">{{ formatCurrency(item.trade_amount ?? item.gross_amount, item.trade_currency ?? item.cash_currency) }}</td>
                <td class="numeric">{{ formatCurrency(item.settlement_amount ?? item.gross_amount, item.settlement_currency ?? item.cash_currency) }}</td>
                <td>{{ item.funding_group }}</td>
                <td>{{ item.broker_account_type }}</td>
                <td>{{ item.taxed }}</td>
                <td>
                  {{
                    group.suggested_delete_ids.includes(item.id)
                      ? t("imports.duplicates.suggestedDelete")
                      : t("imports.duplicates.keepCandidate")
                  }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="duplicateReview.groups.length" class="form-actions">
        <button
          type="button"
          class="danger-btn"
          :disabled="!selectedDuplicateIds.length || pendingDuplicateDelete"
          @click="handleDeleteSelectedDuplicates"
        >
          {{ t("imports.duplicates.actions.deleteSelected", { count: selectedDuplicateIds.length }) }}
        </button>
        <button type="button" class="ghost-btn" @click="selectAllSuggestedDuplicates">
          {{ t("imports.duplicates.actions.selectSuggested") }}
        </button>
        <button
          type="button"
          class="ghost-btn"
          :disabled="!selectedDuplicateIds.length"
          @click="clearDuplicateSelection"
        >
          {{ t("imports.duplicates.actions.clearSelection") }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

import BaseSelect from "@/components/ui/BaseSelect.vue";
import {
  applyBrokerImport,
  deleteTransactionsBatch,
  getSuspiciousDuplicateTransactions,
  previewBrokerImport,
  undoBrokerImport,
} from "@/services/api";
import type {
  BrokerImportFile,
  BrokerImportPreviewResponse,
  CashActivity,
  FundingGroup,
  SuspiciousDuplicateGroup,
  SuspiciousDuplicateResponse,
} from "@/types/api";

const props = defineProps<{
  fundingGroups: FundingGroup[];
  cashActivities: CashActivity[];
}>();

const emit = defineEmits<{
  (e: "imported"): void;
  (e: "notify", payload: { type: "success" | "error" | "info"; message: string }): void;
}>();

const { t } = useI18n();

function createEmptyPreview(): BrokerImportPreviewResponse {
  return {
    items: [],
    cash_items: [],
    warnings: [],
    applied_count: 0,
    skipped_count: 0,
    applied_transaction_ids: [],
    applied_cash_count: 0,
    skipped_cash_count: 0,
    applied_cash_activity_ids: [],
  };
}

function createEmptyDuplicateReview(): SuspiciousDuplicateResponse {
  return {
    groups: [],
    duplicate_transaction_count: 0,
    suggested_delete_count: 0,
  };
}

const domesticInputRef = ref<HTMLInputElement | null>(null);
const usInputRef = ref<HTMLInputElement | null>(null);
const jpyCashInputRef = ref<HTMLInputElement | null>(null);
const foreignCashInputRef = ref<HTMLInputElement | null>(null);
const domesticFile = ref<BrokerImportFile | null>(null);
const usFile = ref<BrokerImportFile | null>(null);
const jpyCashFile = ref<BrokerImportFile | null>(null);
const foreignCashFile = ref<BrokerImportFile | null>(null);
const pendingPreview = ref(false);
const pendingApply = ref(false);
const pendingUndo = ref(false);
const pendingDuplicateScan = ref(false);
const pendingDuplicateDelete = ref(false);
const message = ref("");
const preview = ref<BrokerImportPreviewResponse>(createEmptyPreview());
const duplicateReview = ref<SuspiciousDuplicateResponse>(createEmptyDuplicateReview());
const duplicateReviewLoaded = ref(false);
const selectedDuplicateIds = ref<string[]>([]);
const lastAppliedTransactionIds = ref<string[]>([]);
const lastAppliedCashActivityIds = ref<string[]>([]);
const lastAppliedCount = computed(
  () => lastAppliedTransactionIds.value.length + lastAppliedCashActivityIds.value.length
);

const jpyGroups = computed(() => props.fundingGroups.filter((item) => item.currency === "JPY"));
const usdGroups = computed(() => props.fundingGroups.filter((item) => item.currency === "USD"));
const jpyGroupOptions = computed(() => jpyGroups.value.map((group) => ({ label: group.name, value: group.name })));
const usdGroupOptions = computed(() => usdGroups.value.map((group) => ({ label: group.name, value: group.name })));
const hasSelectedFiles = computed(() => Boolean(
  domesticFile.value || usFile.value || jpyCashFile.value || foreignCashFile.value
));
const canResetImport = computed(() => hasSelectedFiles.value || preview.value.items.length > 0 || Boolean(message.value));
const selectedDuplicateIdSet = computed(() => new Set(selectedDuplicateIds.value));

const positionGroupJpy = ref("JPY");
const settlementGroupJpy = ref("JPY");
const positionGroupUsd = ref("USD");
const settlementGroupUsd = ref("USD");

async function fileToPayload(file: File): Promise<BrokerImportFile> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((value) => {
    binary += String.fromCharCode(value);
  });
  return {
    file_name: file.name,
    content_base64: btoa(binary),
    encoding_hint: null,
  };
}

function resetPreviewState() {
  preview.value = createEmptyPreview();
  message.value = "";
}

function normalizeSelectedIds(ids: string[]): string[] {
  return Array.from(new Set(ids));
}

function resetImportState() {
  domesticFile.value = null;
  usFile.value = null;
  jpyCashFile.value = null;
  foreignCashFile.value = null;
  if (domesticInputRef.value) {
    domesticInputRef.value.value = "";
  }
  if (usInputRef.value) {
    usInputRef.value.value = "";
  }
  if (jpyCashInputRef.value) jpyCashInputRef.value.value = "";
  if (foreignCashInputRef.value) foreignCashInputRef.value.value = "";
  resetPreviewState();
}

function clearSelectedFile(type: "domestic" | "us" | "jpyCash" | "foreignCash") {
  if (type === "domestic") {
    domesticFile.value = null;
    if (domesticInputRef.value) {
      domesticInputRef.value.value = "";
    }
  } else if (type === "us") {
    usFile.value = null;
    if (usInputRef.value) {
      usInputRef.value.value = "";
    }
  } else if (type === "jpyCash") {
    jpyCashFile.value = null;
    if (jpyCashInputRef.value) jpyCashInputRef.value.value = "";
  } else {
    foreignCashFile.value = null;
    if (foreignCashInputRef.value) foreignCashInputRef.value.value = "";
  }
  resetPreviewState();
}

async function onFileChange(event: Event, type: "domestic" | "us" | "jpyCash" | "foreignCash") {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) {
    return;
  }
  const payload = await fileToPayload(file);
  if (type === "domestic") {
    domesticFile.value = payload;
  } else if (type === "us") {
    usFile.value = payload;
  } else if (type === "jpyCash") {
    jpyCashFile.value = payload;
  } else {
    foreignCashFile.value = payload;
  }
  resetPreviewState();
}

function formatCurrency(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "JPY" ? 0 : 2,
  }).format(amount);
}

function formatCashAmount(item: CashActivity): string {
  if (!item.currency) {
    return `${new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 2 }).format(item.amount)} ${t("imports.reportedAmount")}`;
  }
  return formatCurrency(item.amount, item.currency);
}

async function loadDuplicates(silent = false) {
  pendingDuplicateScan.value = true;
  try {
    duplicateReview.value = await getSuspiciousDuplicateTransactions();
    duplicateReviewLoaded.value = true;
    selectedDuplicateIds.value = normalizeSelectedIds(
      duplicateReview.value.groups.flatMap((group) => group.suggested_delete_ids)
    );
    if (!silent) {
      message.value = duplicateReview.value.groups.length
        ? t("imports.duplicates.summary", {
            groups: duplicateReview.value.groups.length,
            transactions: duplicateReview.value.duplicate_transaction_count,
            suggested: duplicateReview.value.suggested_delete_count,
          })
        : t("imports.duplicates.empty");
    }
  } catch (error) {
    emit("notify", {
      type: "error",
      message: error instanceof Error ? error.message : t("imports.duplicates.errors.scan"),
    });
  } finally {
    pendingDuplicateScan.value = false;
  }
}

async function handlePreview() {
  pendingPreview.value = true;
  message.value = "";
  try {
    preview.value = await previewBrokerImport({
      domestic_report: domesticFile.value,
      us_report: usFile.value,
      jpy_cash_report: jpyCashFile.value,
      foreign_cash_report: foreignCashFile.value,
      position_group_jpy: positionGroupJpy.value,
      settlement_group_jpy: settlementGroupJpy.value,
      position_group_usd: positionGroupUsd.value,
      settlement_group_usd: settlementGroupUsd.value,
    });
    message.value = t("imports.previewSummary", {
      count: preview.value.items.length + preview.value.cash_items.length,
      applied: preview.value.applied_count + preview.value.applied_cash_count,
      skipped: preview.value.skipped_count + preview.value.skipped_cash_count,
    });
  } catch (error) {
    emit("notify", { type: "error", message: error instanceof Error ? error.message : t("imports.errors.preview") });
  } finally {
    pendingPreview.value = false;
  }
}

async function handleApply() {
  pendingApply.value = true;
  try {
    preview.value = await applyBrokerImport({
      domestic_report: domesticFile.value,
      us_report: usFile.value,
      jpy_cash_report: jpyCashFile.value,
      foreign_cash_report: foreignCashFile.value,
      position_group_jpy: positionGroupJpy.value,
      settlement_group_jpy: settlementGroupJpy.value,
      position_group_usd: positionGroupUsd.value,
      settlement_group_usd: settlementGroupUsd.value,
      replace_existing_transactions: false,
    });
    lastAppliedTransactionIds.value = [...preview.value.applied_transaction_ids];
    lastAppliedCashActivityIds.value = [...preview.value.applied_cash_activity_ids];
    const successMessage = t("imports.applyDone", {
      count: preview.value.applied_count + preview.value.applied_cash_count,
      skipped: preview.value.skipped_count + preview.value.skipped_cash_count,
    });
    emit("notify", { type: "success", message: successMessage });
    message.value = successMessage;
    await loadDuplicates(true);
    emit("imported");
  } catch (error) {
    emit("notify", { type: "error", message: error instanceof Error ? error.message : t("imports.errors.apply") });
  } finally {
    pendingApply.value = false;
  }
}

function toggleDuplicateSelection(id: string, checked: boolean) {
  if (checked) {
    selectedDuplicateIds.value = normalizeSelectedIds([...selectedDuplicateIds.value, id]);
    return;
  }
  selectedDuplicateIds.value = selectedDuplicateIds.value.filter((item) => item !== id);
}

function onDuplicateCheckboxChange(id: string, event: Event) {
  const target = event.target as HTMLInputElement | null;
  toggleDuplicateSelection(id, Boolean(target?.checked));
}

function selectSuggestedForGroup(group: SuspiciousDuplicateGroup) {
  selectedDuplicateIds.value = normalizeSelectedIds([
    ...selectedDuplicateIds.value,
    ...group.suggested_delete_ids,
  ]);
}

function selectAllSuggestedDuplicates() {
  selectedDuplicateIds.value = normalizeSelectedIds(
    duplicateReview.value.groups.flatMap((group) => group.suggested_delete_ids)
  );
}

function clearDuplicateSelection() {
  selectedDuplicateIds.value = [];
}

async function handleScanDuplicates() {
  await loadDuplicates();
}

async function handleDeleteSelectedDuplicates() {
  const deleteCount = selectedDuplicateIds.value.length;
  if (!deleteCount) {
    return;
  }
  if (!window.confirm(t("imports.duplicates.confirmDelete", { count: deleteCount }))) {
    return;
  }

  pendingDuplicateDelete.value = true;
  try {
    const response = await deleteTransactionsBatch({
      transaction_ids: selectedDuplicateIds.value,
    });
    const deletedIdSet = new Set(response.deleted_transaction_ids);
    lastAppliedTransactionIds.value = lastAppliedTransactionIds.value.filter((id) => !deletedIdSet.has(id));
    selectedDuplicateIds.value = [];
    message.value = t("imports.duplicates.deleted", { count: response.deleted_count });
    emit("notify", {
      type: "success",
      message: t("imports.duplicates.deleted", { count: response.deleted_count }),
    });
    await loadDuplicates(true);
    emit("imported");
  } catch (error) {
    emit("notify", {
      type: "error",
      message: error instanceof Error ? error.message : t("imports.duplicates.errors.delete"),
    });
  } finally {
    pendingDuplicateDelete.value = false;
  }
}

async function handleUndoLastImport() {
  const appliedCount = lastAppliedCount.value;
  if (!appliedCount) {
    return;
  }
  if (!window.confirm(t("imports.undo.confirm", { count: appliedCount }))) {
    return;
  }

  pendingUndo.value = true;
  try {
    const response = await undoBrokerImport({
      transaction_ids: lastAppliedTransactionIds.value,
      cash_activity_ids: lastAppliedCashActivityIds.value,
    });
    lastAppliedTransactionIds.value = [];
    lastAppliedCashActivityIds.value = [];
    resetImportState();
    const deletedCount = response.deleted_transaction_ids.length + response.deleted_cash_activity_ids.length;
    message.value = t("imports.undo.done", { count: deletedCount });
    emit("notify", {
      type: "success",
      message: t("imports.undo.done", { count: deletedCount }),
    });
    await loadDuplicates(true);
    emit("imported");
  } catch (error) {
    emit("notify", {
      type: "error",
      message: error instanceof Error ? error.message : t("imports.undo.errors.undo"),
    });
  } finally {
    pendingUndo.value = false;
  }
}
</script>

<style scoped>
.panel-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  padding: 0 16px 16px;
}

.import-form,
.import-preview,
.import-duplicates {
  min-height: 0;
}

.import-form {
  display: grid;
  gap: 18px;
  padding: 20px;
  border-color: #d8dcd6;
  background: #f7f8f4;
}

.import-form > h3 {
  margin: 0;
  font: 500 18px/1.2 Georgia, "Noto Serif SC", serif;
}

.report-file-grid,
.mapping-grid {
  display: grid;
  gap: 10px;
}

.report-file-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.mapping-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.report-file-grid label,
.mapping-grid label {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 8px;
}

.report-file-grid label > span,
.mapping-grid label > span {
  color: var(--text-dim);
  font-size: 11px;
}

.file-field {
  position: relative;
  min-height: 104px;
  justify-content: space-between;
  padding: 14px;
  overflow: hidden;
  border: 1px solid var(--divider);
  border-radius: 8px;
  background: var(--panel);
  transition: border-color var(--transition), background var(--transition);
}

.file-field:hover {
  border-color: #8ba9a3;
  background: #f1f7f4;
}

.file-field input[type="file"] {
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-faint);
  font-size: 10px;
}

.file-field input[type="file"]::file-selector-button {
  margin-right: 8px;
  padding: 7px 9px;
  border-color: #cbd8d4;
  background: #e7f0ed;
  color: #155c55;
  font-size: 11px;
}

.mapping-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-top: 4px;
  border-top: 1px solid var(--divider);
}

.mapping-header span {
  font-weight: 600;
  font-size: 12px;
}

.mapping-header small {
  color: var(--text-faint);
  font-size: 10px;
}

.mapping-grid :deep(.base-select) {
  min-width: 0;
}

.import-undo,
.import-duplicates,
.import-cash-preview,
.import-cash-ledger {
  margin-top: 1rem;
}

.ledger-link {
  display: inline-flex;
  padding: 0.22rem 0.5rem;
  border-radius: 6px;
  color: var(--accent-strong);
  background: var(--accent-soft);
  font-size: 0.75rem;
  white-space: nowrap;
}

.import-form .form-actions,
.import-duplicates .form-actions {
  justify-content: flex-start;
  gap: 0.8rem;
  flex-wrap: wrap;
}

.selected-files {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
}

.selected-file,
.import-subsection-header,
.duplicate-group__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.8rem;
  flex-wrap: wrap;
}

.selected-file {
  padding: 0.5rem 0.65rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: var(--panel-soft);
}

.import-preview,
.import-cash-preview,
.import-cash-ledger,
.import-duplicates {
  background: rgba(255, 255, 255, 0.76);
}

@media (max-width: 980px) {
  .report-file-grid,
  .mapping-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 600px) {
  .panel-grid {
    padding: 0 10px 10px;
  }

  .report-file-grid,
  .mapping-grid {
    grid-template-columns: 1fr;
  }

  .mapping-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
}

.duplicate-group {
  display: grid;
  gap: 0.9rem;
  margin-top: 1rem;
  padding: 1rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: var(--panel-alt);
}

.duplicate-group__header p,
.import-subsection-header p {
  margin-top: 0.35rem;
  color: var(--text-dim);
  font-size: 0.9rem;
}
</style>
