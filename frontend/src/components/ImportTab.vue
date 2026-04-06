<template>
  <section class="panel surface-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("imports.title") }}</h2>
        <p>{{ t("imports.description") }}</p>
      </div>
    </header>

    <div class="panel-grid">
      <form class="surface import-form" @submit.prevent="handlePreview">
        <h3>{{ t("imports.formTitle") }}</h3>
        <div class="form-grid">
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
        </div>

        <div class="form-actions">
          <button type="submit" class="primary-btn" :disabled="pendingPreview">
            {{ t("imports.actions.preview") }}
          </button>
          <button
            type="button"
            class="ghost-btn"
            :disabled="!preview.items.length || pendingApply"
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

    <div v-if="lastAppliedTransactionIds.length" class="surface import-undo">
      <div class="import-subsection-header">
        <div>
          <h3>{{ t("imports.undo.title") }}</h3>
          <p>{{ t("imports.undo.description", { count: lastAppliedTransactionIds.length }) }}</p>
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
} from "@/services/api";
import type {
  BrokerImportFile,
  BrokerImportPreviewResponse,
  FundingGroup,
  SuspiciousDuplicateGroup,
  SuspiciousDuplicateResponse,
} from "@/types/api";

const props = defineProps<{
  fundingGroups: FundingGroup[];
}>();

const emit = defineEmits<{
  (e: "imported"): void;
  (e: "notify", payload: { type: "success" | "error" | "info"; message: string }): void;
}>();

const { t } = useI18n();

function createEmptyPreview(): BrokerImportPreviewResponse {
  return {
    items: [],
    warnings: [],
    applied_count: 0,
    skipped_count: 0,
    applied_transaction_ids: [],
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
const domesticFile = ref<BrokerImportFile | null>(null);
const usFile = ref<BrokerImportFile | null>(null);
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

const jpyGroups = computed(() => props.fundingGroups.filter((item) => item.currency === "JPY"));
const usdGroups = computed(() => props.fundingGroups.filter((item) => item.currency === "USD"));
const jpyGroupOptions = computed(() => jpyGroups.value.map((group) => ({ label: group.name, value: group.name })));
const usdGroupOptions = computed(() => usdGroups.value.map((group) => ({ label: group.name, value: group.name })));
const hasSelectedFiles = computed(() => Boolean(domesticFile.value || usFile.value));
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
  if (domesticInputRef.value) {
    domesticInputRef.value.value = "";
  }
  if (usInputRef.value) {
    usInputRef.value.value = "";
  }
  resetPreviewState();
}

function clearSelectedFile(type: "domestic" | "us") {
  if (type === "domestic") {
    domesticFile.value = null;
    if (domesticInputRef.value) {
      domesticInputRef.value.value = "";
    }
  } else {
    usFile.value = null;
    if (usInputRef.value) {
      usInputRef.value.value = "";
    }
  }
  resetPreviewState();
}

async function onFileChange(event: Event, type: "domestic" | "us") {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) {
    return;
  }
  const payload = await fileToPayload(file);
  if (type === "domestic") {
    domesticFile.value = payload;
  } else {
    usFile.value = payload;
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
      position_group_jpy: positionGroupJpy.value,
      settlement_group_jpy: settlementGroupJpy.value,
      position_group_usd: positionGroupUsd.value,
      settlement_group_usd: settlementGroupUsd.value,
    });
    message.value = t("imports.previewSummary", {
      count: preview.value.items.length,
      applied: preview.value.applied_count,
      skipped: preview.value.skipped_count,
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
      position_group_jpy: positionGroupJpy.value,
      settlement_group_jpy: settlementGroupJpy.value,
      position_group_usd: positionGroupUsd.value,
      settlement_group_usd: settlementGroupUsd.value,
      replace_existing_transactions: false,
    });
    lastAppliedTransactionIds.value = [...preview.value.applied_transaction_ids];
    const successMessage = t("imports.applyDone", {
      count: preview.value.applied_count,
      skipped: preview.value.skipped_count,
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
  const appliedCount = lastAppliedTransactionIds.value.length;
  if (!appliedCount) {
    return;
  }
  if (!window.confirm(t("imports.undo.confirm", { count: appliedCount }))) {
    return;
  }

  pendingUndo.value = true;
  try {
    const response = await deleteTransactionsBatch({
      transaction_ids: lastAppliedTransactionIds.value,
    });
    lastAppliedTransactionIds.value = [];
    resetImportState();
    message.value = t("imports.undo.done", { count: response.deleted_count });
    emit("notify", {
      type: "success",
      message: t("imports.undo.done", { count: response.deleted_count }),
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
.import-form,
.import-preview,
.import-duplicates {
  min-height: 100%;
}

.import-undo,
.import-duplicates {
  margin-top: 1rem;
}

.import-form .form-actions,
.import-duplicates .form-actions {
  justify-content: flex-start;
  gap: 0.8rem;
  flex-wrap: wrap;
}

.file-field {
  justify-content: flex-start;
}

.selected-files {
  display: grid;
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
  padding: 0.85rem 1rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: var(--panel-soft);
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
