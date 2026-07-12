<template>
  <section class="funds-panel surface-panel app-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("funds.title") }}</h2>
        <p>{{ t("funds.description") }}</p>
      </div>
      <div class="header-actions">
        <button type="button" class="ghost-btn" @click="settingsOpen = !settingsOpen">
          {{ settingsOpen ? t("funds.actions.closeSettings") : t("funds.actions.settings") }}
        </button>
        <button type="button" class="ghost-btn" @click="advancedOpen = !advancedOpen">
          {{ advancedOpen ? t("funds.actions.closeAdvanced") : t("funds.actions.advanced") }}
        </button>
        <button type="button" class="refresh-button" @click="$emit('refresh')">
          {{ t("common.actions.refresh") }}
        </button>
      </div>
    </header>

    <section class="account-overview">
      <article v-for="item in aggregated" :key="item.currency" class="account-card">
        <div class="account-card__head">
          <div>
            <span class="account-card__eyebrow">{{ t("funds.overview.brokerAccount") }}</span>
            <h3>{{ item.currency }}</h3>
          </div>
          <span class="currency-orb">{{ item.currency === 'JPY' ? '¥' : '$' }}</span>
        </div>
        <strong class="account-card__total">{{ formatCurrency(item.current_total, item.currency) }}</strong>
        <div class="account-card__metrics">
          <span><small>{{ t("funds.snapshotTable.cash") }}</small><b>{{ formatCurrency(item.cash_balance, item.currency) }}</b></span>
          <span><small>{{ t("funds.snapshotTable.holdingCost") }}</small><b>{{ formatCurrency(item.holding_cost, item.currency) }}</b></span>
          <span><small>{{ t("funds.aggregateTable.totalPl") }}</small><b :class="valueClass(item.total_pl)">{{ formatCurrency(item.total_pl, item.currency) }}</b></span>
        </div>
      </article>
    </section>

    <section class="cash-ledger surface">
      <div class="section-toolbar">
        <div>
          <h3>{{ t("funds.cashLedger.title") }}</h3>
          <p class="cash-ledger__description">{{ t("funds.cashLedger.description", { count: cashActivities.length }) }}</p>
        </div>
        <div class="cash-ledger__summary">
          <span>JPY <b>{{ cashActivityCount('JPY') }}</b></span>
          <span>USD <b>{{ cashActivityCount('USD') }}</b></span>
        </div>
      </div>
      <div class="table-scroll">
        <table>
          <thead><tr>
            <th>{{ t("funds.cashLedger.date") }}</th>
            <th>{{ t("funds.cashLedger.type") }}</th>
            <th>{{ t("funds.cashLedger.descriptionColumn") }}</th>
            <th class="numeric">{{ t("funds.cashLedger.amount") }}</th>
            <th>{{ t("common.labels.tags") }}</th>
          </tr></thead>
          <tbody>
            <tr v-if="!recentCashActivities.length"><td colspan="5" class="empty">{{ t("funds.cashLedger.empty") }}</td></tr>
            <tr v-for="activity in recentCashActivities" :key="activity.id">
              <td>{{ activity.activity_date }}</td>
              <td>{{ activity.detail_type || activity.transaction_type }}</td>
              <td class="cash-description">{{ activity.description }}</td>
              <td :class="['numeric', activity.direction === 'in' ? 'positive' : 'negative']">
                {{ activity.direction === 'in' ? '+' : '−' }}{{ formatCurrency(activity.amount, activity.currency || 'JPY') }}
              </td>
              <td><div class="inline-tags"><span class="flat-tag flat-tag--currency">{{ activity.currency || '-' }}</span><span class="flat-tag">{{ activity.category }}</span></div></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="settingsOpen" class="settings-section">
      <div class="section-label">{{ t("funds.actions.settings") }}</div>
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
        <div class="section-toolbar">
          <h3>{{ t("funds.listTitle", { count: fundingGroups.length }) }}</h3>
          <div class="section-toolbar__actions">
            <span v-if="selectedFundingGroup" class="selection-pill">
              {{ selectedFundingGroup.name }}
            </span>
            <button
              type="button"
              class="ghost-btn"
              :disabled="!selectedFundingGroup"
              @click="handleAddCapitalForSelected"
            >
              {{ t("funds.actions.addCapital") }}
            </button>
            <button
              type="button"
              class="danger-btn"
              :disabled="!selectedFundingGroup"
              @click="handleDeleteSelectedGroup"
            >
              {{ t("common.actions.delete") }}
            </button>
          </div>
        </div>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th class="select-column">{{ t("common.select") }}</th>
                <th>{{ t("funds.table.name") }}</th>
                <th class="numeric">{{ t("funds.table.initial") }}</th>
                <th>{{ t("funds.table.notes") }}</th>
                <th>{{ t("common.labels.tags") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!fundingGroups.length">
                <td colspan="5" class="empty">{{ t("funds.emptyGroups") }}</td>
              </tr>
              <tr
                v-for="group in pagedFundingGroups"
                :key="group.name"
                :class="['interactive-row', { 'is-selected': selectedFundingGroupName === group.name }]"
                @click="selectFundingGroup(group.name)"
              >
                <td class="select-column" @click.stop>
                  <input
                    type="radio"
                    name="funding-group-select"
                    :checked="selectedFundingGroupName === group.name"
                    :aria-label="group.name"
                    @change="selectFundingGroup(group.name)"
                  />
                </td>
                <td>{{ group.name }}</td>
                <td class="numeric">
                  {{ formatCurrency(group.initial_amount, group.currency) }}
                </td>
                <td class="notes-cell">{{ group.notes || '-' }}</td>
                <td>
                  <div class="inline-tags">
                    <span class="flat-tag flat-tag--currency">{{ currencyLabel(group.currency) }}</span>
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
              <th class="numeric">{{ t("funds.snapshotTable.initial") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.cash") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.holdingCost") }}</th>
              <th class="numeric">{{ t("funds.snapshotTable.current") }}</th>
              <th>{{ t("common.labels.tags") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!funds.length">
              <td colspan="6" class="empty">{{ t("funds.emptySnapshot") }}</td>
            </tr>
            <tr v-for="item in pagedFunds" :key="item.name">
              <td>{{ item.name }}</td>
              <td class="numeric">{{ formatCurrency(item.initial_amount, item.currency) }}</td>
              <td class="numeric">{{ formatCurrency(item.cash_balance, item.currency) }}</td>
              <td class="numeric">{{ formatCurrency(item.holding_cost, item.currency) }}</td>
              <td class="numeric">{{ formatCurrency(item.current_total, item.currency) }}</td>
              <td>
                <div class="inline-tags">
                  <span class="flat-tag flat-tag--currency">{{ currencyLabel(item.currency) }}</span>
                </div>
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
    </div>

    <div v-if="advancedOpen" class="surface">
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
            readonly
            @blur="handleRateBlur"
          />
        </label>
        <p
          class="exchange-rate-hint"
          :class="{ 'exchange-rate-hint--warning': needsRateReminder }"
        >
          {{
            exchangeRateLoading
              ? t("funds.exchangeRate.loading")
              : needsRateReminder
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
              <th class="numeric">{{ t("funds.aggregateTable.initial") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.cash") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.holdingCost") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.current") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.totalPl") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.currentYearPl") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.currentYearRatio") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.previousYearPl") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.previousYearRatio") }}</th>
              <th class="numeric">{{ t("funds.aggregateTable.olderPl") }}</th>
              <th>{{ t("common.labels.tags") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!combinedTotals">
              <td colspan="12" class="empty">{{ t("funds.emptyAggregate") }}</td>
            </tr>
            <tr v-else class="combined-row">
              <td>
                {{
                  t("funds.aggregateTable.combinedLabel", {
                    currency: currencyLabel(combinedTotals.currency),
                  })
                }}
              </td>
              <td class="numeric">{{ formatCurrency(combinedTotals.initial_amount, combinedTotals.currency) }}</td>
              <td class="numeric">{{ formatCurrency(combinedTotals.cash_balance, combinedTotals.currency) }}</td>
              <td class="numeric">{{ formatCurrency(combinedTotals.holding_cost, combinedTotals.currency) }}</td>
              <td class="numeric">{{ formatCurrency(combinedTotals.current_total, combinedTotals.currency) }}</td>
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
              <td :class="['numeric', valueClass(olderCombinedPl)]">
                {{ formatCurrency(olderCombinedPl, combinedTotals.currency) }}
              </td>
              <td>
                <div class="inline-tags">
                  <span class="flat-tag">{{ t("funds.aggregateTable.groups") }} {{ combinedTotals.group_count }}</span>
                  <span class="flat-tag">{{ t("funds.exchangeRate.label") }} {{ effectiveExchangeRate ? effectiveExchangeRate.toFixed(2) : '-' }}</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="advancedOpen" class="surface fx-panel">
      <header class="fx-header">
        <div>
          <h3>{{ t("funds.fx.title") }}</h3>
          <p class="fx-description">{{ t("funds.fx.description") }}</p>
        </div>
        <div class="section-toolbar__actions">
          <button
            type="button"
            class="danger-btn"
            :disabled="!selectedFxExchange"
            @click="deleteSelectedFx"
          >
            {{ t("common.actions.delete") }}
          </button>
          <button
            type="button"
            class="ghost-btn"
            @click="fxPanelOpen = !fxPanelOpen"
          >
            {{ fxPanelOpen ? t("funds.fx.collapse") : t("funds.fx.expand") }}
          </button>
        </div>
      </header>

      <div v-if="fxPanelOpen" class="fx-body">
        <div v-if="fxMissingRows.length" class="fx-alert">
          <p>{{ t("funds.fx.missingHint") }}</p>
          <ul>
            <li v-for="row in fxMissingRows" :key="row.id">
              {{ row.label }}
            </li>
          </ul>
        </div>

        <form class="fx-form" @submit.prevent="handleFxSubmit">
          <div class="form-grid">
            <label>
              <span>{{ t("funds.fx.fields.date") }}</span>
              <BaseDatePicker v-model="fxForm.exchange_date" />
            </label>
            <label>
              <span>{{ t("funds.fx.fields.from") }}</span>
              <BaseSelect v-model="fxForm.from_currency" :options="currencyOptions" />
            </label>
            <label>
              <span>{{ t("funds.fx.fields.to") }}</span>
              <BaseSelect v-model="fxForm.to_currency" :options="currencyOptions" />
            </label>
            <label>
              <span>{{ t("funds.fx.fields.amount") }}</span>
              <input
                v-model.number="fxForm.from_amount"
                type="number"
                step="0.01"
                min="0"
                required
              />
            </label>
            <label>
              <span>{{ t("funds.fx.fields.rate") }}</span>
              <input
                v-model.number="fxForm.rate"
                type="number"
                step="0.0001"
                min="0"
                required
              />
            </label>
            <label>
              <span>{{ t("funds.fx.fields.bind") }}</span>
              <select v-model="fxForm.transaction_id">
                <option value="">{{ t("funds.fx.fields.unbound") }}</option>
                <option
                  v-for="item in fxRequiredTransactions"
                  :key="item.id"
                  :value="item.id"
                >
                  {{ item.label }}
                </option>
              </select>
            </label>
            <label class="full">
              <span>{{ t("funds.fx.fields.notes") }}</span>
              <textarea v-model.trim="fxForm.notes" rows="2"></textarea>
            </label>
          </div>
          <div class="form-actions">
            <button type="submit" class="primary-btn">
              {{ t("funds.fx.submit") }}
            </button>
          </div>
        </form>

        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th class="select-column">{{ t("common.select") }}</th>
                <th>{{ t("funds.fx.table.date") }}</th>
                <th class="numeric">{{ t("funds.fx.table.fromAmount") }}</th>
                <th class="numeric">{{ t("funds.fx.table.toAmount") }}</th>
                <th>{{ t("funds.fx.fields.notes") }}</th>
                <th>{{ t("common.labels.tags") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!fxExchanges.length">
                <td colspan="6" class="empty">{{ t("funds.fx.empty") }}</td>
              </tr>
              <tr
                v-for="item in fxExchanges"
                :key="item.id"
                :class="['interactive-row', { 'is-selected': selectedFxExchangeId === item.id }]"
                @click="selectFxExchange(item.id)"
              >
                <td class="select-column" @click.stop>
                  <input
                    type="radio"
                    name="fx-select"
                    :checked="selectedFxExchangeId === item.id"
                    :aria-label="item.id"
                    @change="selectFxExchange(item.id)"
                  />
                </td>
                <td>{{ item.exchange_date }}</td>
                <td class="numeric">
                  {{ formatCurrency(item.from_amount, item.from_currency) }}
                </td>
                <td class="numeric">
                  {{ formatCurrency(item.to_amount, item.to_currency) }}
                </td>
                <td class="notes-cell">{{ item.notes || '-' }}</td>
                <td>
                  <div class="inline-tags">
                    <span class="flat-tag">{{ currencyLabel(item.from_currency) }} → {{ currencyLabel(item.to_currency) }}</span>
                    <span class="flat-tag">{{ t("funds.fx.table.rate") }} {{ item.rate }}</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-if="advancedOpen" class="surface">
      <div class="section-toolbar">
        <div>
          <h3>{{ t("funds.stockSplits.title") }}</h3>
          <p class="capital-history-description">
            {{ t("funds.stockSplits.description") }}
          </p>
        </div>
        <div class="section-toolbar__actions">
          <button
            type="button"
            class="danger-btn"
            :disabled="!selectedStockSplit"
            @click="deleteSelectedStockSplit"
          >
            {{ t("common.actions.delete") }}
          </button>
        </div>
      </div>
      <form class="fx-form" @submit.prevent="handleStockSplitSubmit">
        <div class="form-grid">
          <label>
            <span>{{ t("funds.stockSplits.fields.date") }}</span>
            <BaseDatePicker v-model="stockSplitForm.effective_date" />
          </label>
          <label>
            <span>{{ t("funds.stockSplits.fields.symbol") }}</span>
            <input
              v-model.trim="stockSplitForm.symbol"
              type="text"
              required
              :placeholder="t('funds.stockSplits.placeholders.symbol')"
            />
          </label>
          <label>
            <span>{{ t("funds.stockSplits.fields.market") }}</span>
            <BaseSelect v-model="stockSplitForm.market" :options="marketOptions" />
          </label>
          <label>
            <span>{{ t("funds.stockSplits.fields.ratioBefore") }}</span>
            <input
              v-model.number="stockSplitForm.ratio_before"
              type="number"
              step="0.0001"
              min="0"
              required
            />
          </label>
          <label>
            <span>{{ t("funds.stockSplits.fields.ratioAfter") }}</span>
            <input
              v-model.number="stockSplitForm.ratio_after"
              type="number"
              step="0.0001"
              min="0"
              required
            />
          </label>
          <label class="full">
            <span>{{ t("funds.stockSplits.fields.notes") }}</span>
            <textarea v-model.trim="stockSplitForm.notes" rows="2"></textarea>
          </label>
        </div>
        <div class="form-actions">
          <button type="submit" class="primary-btn" :disabled="stockSplitPending">
            {{ t("funds.stockSplits.submit") }}
          </button>
        </div>
      </form>

      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="select-column">{{ t("common.select") }}</th>
              <th>{{ t("funds.stockSplits.table.date") }}</th>
              <th>{{ t("funds.stockSplits.table.symbol") }}</th>
              <th>{{ t("funds.stockSplits.table.market") }}</th>
              <th>{{ t("funds.stockSplits.table.ratio") }}</th>
              <th>{{ t("funds.stockSplits.table.notes") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!stockSplits.length">
              <td colspan="6" class="empty">{{ t("funds.stockSplits.empty") }}</td>
            </tr>
            <tr
              v-for="item in pagedStockSplits"
              :key="item.id"
              :class="['interactive-row', { 'is-selected': selectedStockSplitId === item.id }]"
              @click="selectStockSplit(item.id)"
            >
              <td class="select-column" @click.stop>
                <input
                  type="radio"
                  name="stock-split-select"
                  :checked="selectedStockSplitId === item.id"
                  :aria-label="item.id"
                  @change="selectStockSplit(item.id)"
                />
              </td>
              <td>{{ item.effective_date }}</td>
              <td>{{ item.symbol }}</td>
              <td>{{ marketLabel(item.market) }}</td>
              <td>{{ formatSplitRatio(item.ratio_before, item.ratio_after) }}</td>
              <td class="notes-cell">{{ item.notes || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationControls
        v-if="stockSplitsTotalItems || stockSplitsTotalPages > 1"
        :page="stockSplitsPage"
        :total-pages="stockSplitsTotalPages"
        :total-items="stockSplitsTotalItems"
        @update:page="setStockSplitsPage"
      />
    </div>

    <div v-if="advancedOpen" class="surface">
      <div class="capital-history-header">
        <div>
          <h3>{{ t("funds.capitalHistory.title") }}</h3>
          <p class="capital-history-description">
            {{ t("funds.capitalHistory.description") }}
          </p>
        </div>
        <div class="section-toolbar__actions">
          <span v-if="capitalTotalItems" class="capital-history-count">
            {{ t("funds.capitalHistory.count", { count: capitalTotalItems }) }}
          </span>
        </div>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="select-column">{{ t("common.select") }}</th>
              <th>{{ t("funds.capitalHistory.table.effectiveDate") }}</th>
              <th>{{ t("funds.capitalHistory.table.group") }}</th>
              <th class="numeric">{{ t("funds.capitalHistory.table.amount") }}</th>
              <th>{{ t("funds.capitalHistory.table.notes") }}</th>
              <th>{{ t("common.labels.tags") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!capitalTotalItems">
              <td colspan="6" class="empty">
                {{ t("funds.capitalHistory.empty") }}
              </td>
            </tr>
            <tr
              v-for="record in pagedCapitalAdjustments"
              :key="record.id"
              :class="['interactive-row', { 'is-selected': selectedCapitalAdjustmentId === record.id }]"
              @click="selectCapitalAdjustment(record.id)"
            >
              <td class="select-column" @click.stop>
                <input
                  type="radio"
                  name="capital-select"
                  :checked="selectedCapitalAdjustmentId === record.id"
                  :aria-label="record.id"
                  @change="selectCapitalAdjustment(record.id)"
                />
              </td>
              <td>{{ formatEffectiveDate(record.effective_date) }}</td>
              <td>{{ record.funding_group }}</td>
              <td class="numeric">{{ formatCurrency(record.amount, capitalCurrency(record)) }}</td>
              <td class="notes-cell">{{ record.notes || '-' }}</td>
              <td>
                <div class="inline-tags">
                    <span class="flat-tag flat-tag--currency">{{ currencyLabel(capitalCurrency(record)) }}</span>
                  <span
                    v-if="isFutureEffectiveDate(record.effective_date)"
                    class="flat-tag"
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
            <BaseDatePicker v-model="capitalForm.effective_date" />
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
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import PaginationControls from "./ui/PaginationControls.vue";
import BaseDatePicker from "./ui/BaseDatePicker.vue";
import { usePagination } from "@/composables/usePagination";
import { getUsdJpyRate } from "@/services/api";
import type {
  AggregatedFundSnapshot,
  CashActivity,
  Currency,
  FxExchangeCreate,
  FxExchangeRecord,
  FundSnapshot,
  FundingCapitalAdjustment,
  FundingCapitalAdjustmentRequest,
  FundingGroup,
  Market,
  StockSplit,
  StockSplitPayload,
  Transaction,
} from "@/types/api";
import BaseSelect from "./ui/BaseSelect.vue";

const props = defineProps<{
  fundingGroups: FundingGroup[];
  funds: FundSnapshot[];
  aggregated: AggregatedFundSnapshot[];
  capitalAdjustments: FundingCapitalAdjustment[];
  stockSplits: StockSplit[];
  fxExchanges: FxExchangeRecord[];
  transactions: Transaction[];
  cashActivities: CashActivity[];
}>();

type CapitalAdditionEvent = {
  data: FundingCapitalAdjustmentRequest;
  onDone: (success: boolean) => void;
};

type StockSplitEvent = {
  data: StockSplitPayload;
  onDone: (success: boolean) => void;
};

const emit = defineEmits<{
  (e: "create", payload: FundingGroup): void;
  (e: "delete", name: string): void;
  (e: "refresh"): void;
  (e: "add-capital", payload: CapitalAdditionEvent): void;
  (e: "add-stock-split", payload: StockSplitEvent): void;
  (e: "delete-stock-split", splitId: string): void;
  (e: "add-fx", payload: FxExchangeCreate): void;
  (e: "delete-fx", exchangeId: string): void;
}>();

const { t } = useI18n();

const pending = ref(false);
const settingsOpen = ref(false);
const advancedOpen = ref(false);
const recentCashActivities = computed(() =>
  [...props.cashActivities].sort((a, b) => b.activity_date.localeCompare(a.activity_date)).slice(0, 12)
);
function cashActivityCount(currency: Currency): number {
  return props.cashActivities.filter((item) => item.currency === currency).length;
}
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
const stockSplitPending = ref(false);
const fxPanelOpen = ref(true);
const selectedFundingGroupName = ref<string | null>(null);
const selectedFxExchangeId = ref<string | null>(null);
const selectedCapitalAdjustmentId = ref<string | null>(null);
const selectedStockSplitId = ref<string | null>(null);

const selectedFundingGroup = computed(() => {
  if (!selectedFundingGroupName.value) {
    return null;
  }
  return props.fundingGroups.find((group) => group.name === selectedFundingGroupName.value) ?? null;
});

const selectedFxExchange = computed(() => {
  if (!selectedFxExchangeId.value) {
    return null;
  }
  return props.fxExchanges.find((item) => item.id === selectedFxExchangeId.value) ?? null;
});

const selectedCapitalAdjustment = computed(() => {
  if (!selectedCapitalAdjustmentId.value) {
    return null;
  }
  return props.capitalAdjustments.find((item) => item.id === selectedCapitalAdjustmentId.value) ?? null;
});

const selectedStockSplit = computed(() => {
  if (!selectedStockSplitId.value) {
    return null;
  }
  return props.stockSplits.find((item) => item.id === selectedStockSplitId.value) ?? null;
});

const capitalValid = computed(() => {
  return (
    capitalDialog.group !== null &&
    capitalForm.amount !== null &&
    capitalForm.amount > 0 &&
    capitalForm.effective_date.trim().length > 0
  );
});

watch(
  () => props.fundingGroups,
  (groups) => {
    if (selectedFundingGroupName.value && !groups.some((group) => group.name === selectedFundingGroupName.value)) {
      selectedFundingGroupName.value = null;
    }
  },
  { immediate: true }
);

watch(
  () => props.fxExchanges,
  (items) => {
    if (selectedFxExchangeId.value && !items.some((item) => item.id === selectedFxExchangeId.value)) {
      selectedFxExchangeId.value = null;
    }
  },
  { immediate: true }
);

watch(
  () => props.capitalAdjustments,
  (items) => {
    if (selectedCapitalAdjustmentId.value && !items.some((item) => item.id === selectedCapitalAdjustmentId.value)) {
      selectedCapitalAdjustmentId.value = null;
    }
  },
  { immediate: true }
);

watch(
  () => props.stockSplits,
  (items) => {
    if (selectedStockSplitId.value && !items.some((item) => item.id === selectedStockSplitId.value)) {
      selectedStockSplitId.value = null;
    }
  },
  { immediate: true }
);

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

const marketOptions = computed(() => [
  {
    label: t("common.toggle.market.jp"),
    value: "JP" as Market,
  },
  {
    label: t("common.toggle.market.us"),
    value: "US" as Market,
  },
]);

type StockSplitFormState = {
  symbol: string;
  market: Market;
  effective_date: string;
  ratio_before: number;
  ratio_after: number;
  notes: string;
};

const stockSplitForm = reactive<StockSplitFormState>({
  symbol: "",
  market: "JP",
  effective_date: todayIso(),
  ratio_before: 1,
  ratio_after: 1,
  notes: "",
});

type FxFormState = {
  exchange_date: string;
  from_currency: Currency;
  to_currency: Currency;
  from_amount: number;
  rate: number;
  transaction_id: string;
  notes: string;
};

const fxForm = reactive<FxFormState>({
  exchange_date: todayIso(),
  from_currency: "JPY",
  to_currency: "USD",
  from_amount: 0,
  rate: 0,
  transaction_id: "",
  notes: "",
});

const fundingGroupCurrency = computed<Record<string, Currency>>(() => {
  return props.fundingGroups.reduce((acc, group) => {
    acc[group.name] = group.currency;
    return acc;
  }, {} as Record<string, Currency>);
});

const marketCurrency = (market: Transaction["market"]): Currency =>
  market === "US" ? "USD" : "JPY";

const fxLookup = computed(() => {
  const map = new Map<string, FxExchangeRecord>();
  props.fxExchanges.forEach((item) => {
    if (item.transaction_id) {
      map.set(item.transaction_id, item);
    }
  });
  return map;
});

const fxRequiredTransactions = computed(() => {
  return props.transactions
    .filter((tx) => {
      return tx.cross_currency && !fxLookup.value.has(tx.id);
    })
    .map((tx) => ({
      id: tx.id,
      label: `${tx.trade_date} ${tx.symbol} · ${tx.id.slice(0, 6)}`,
    }));
});

const fxMissingRows = computed(() =>
  fxRequiredTransactions.value.map((item) => ({
    id: item.id,
    label: item.label,
  }))
);

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

const sortedStockSplits = computed(() => {
  return [...props.stockSplits].sort((a, b) => {
    if (a.effective_date === b.effective_date) {
      return a.symbol.localeCompare(b.symbol);
    }
    return b.effective_date.localeCompare(a.effective_date);
  });
});

const {
  page: stockSplitsPage,
  totalPages: stockSplitsTotalPages,
  totalItems: stockSplitsTotalItems,
  offset: stockSplitsOffset,
  pageSize: stockSplitsPageSize,
  setPage: setStockSplitsPage,
} = usePagination(computed(() => sortedStockSplits.value.length), {
  pageSize: 10,
});

const pagedStockSplits = computed(() =>
  sortedStockSplits.value.slice(
    stockSplitsOffset.value,
    stockSplitsOffset.value + stockSplitsPageSize
  )
);

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

const BASE_CURRENCY: Currency = "JPY";
const exchangeRateInput = ref<string | number>("");
const exchangeRateLoading = ref(false);

onMounted(() => {
  void loadUsdJpyRate();
});

async function loadUsdJpyRate() {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return;
  }

  exchangeRateLoading.value = true;
  try {
    const rate = await getUsdJpyRate();
    exchangeRateInput.value = rate.toFixed(2);
    lastValidExchangeRate.value = rate;
  } catch {
    // Keep the field empty so the aggregate table clearly shows that JPY conversion is unavailable.
  } finally {
    exchangeRateLoading.value = false;
  }
}

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
  () => needsExchangeRate.value && !effectiveExchangeRate.value && !exchangeRateLoading.value
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

  return {
    currency: BASE_CURRENCY,
    group_count: bucket.group_count,
    initial_amount: roundCurrency(bucket.initial_amount),
    cash_balance: roundCurrency(bucket.cash_balance),
    holding_cost: roundCurrency(bucket.holding_cost),
    current_total: roundCurrency(bucket.current_total),
    total_pl: roundCurrency(bucket.total_pl),
    current_year_pl: roundCurrency(bucket.current_year_pl),
    current_year_pl_ratio: roundRatio(computeRatio(bucket.current_year_pl, bucket.baseline_current)),
    previous_year_pl: roundCurrency(bucket.previous_year_pl),
    previous_year_pl_ratio: roundRatio(computeRatio(bucket.previous_year_pl, bucket.baseline_previous)),
  };
});

const olderCombinedPl = computed(() => {
  if (!combinedTotals.value) {
    return 0;
  }
  return roundCurrency(
    combinedTotals.value.total_pl
      - combinedTotals.value.current_year_pl
      - combinedTotals.value.previous_year_pl
  );
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
    exchangeRateInput.value = parsed.toFixed(2);
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

function marketLabel(market: Market): string {
  return market === "US" ? t("common.toggle.market.us") : t("common.toggle.market.jp");
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

function formatSplitRatio(before: number, after: number): string {
  return `${before}:${after}`;
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

function selectFundingGroup(name: string) {
  selectedFundingGroupName.value = name;
}

function handleAddCapitalForSelected() {
  if (!selectedFundingGroup.value) {
    return;
  }
  openCapitalDialog(selectedFundingGroup.value);
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

function handleStockSplitSubmit() {
  if (!stockSplitForm.symbol.trim()) {
    return;
  }
  if (stockSplitForm.ratio_before <= 0 || stockSplitForm.ratio_after <= 0) {
    return;
  }
  stockSplitPending.value = true;
  emit("add-stock-split", {
    data: {
      symbol: stockSplitForm.symbol.trim(),
      market: stockSplitForm.market,
      effective_date: stockSplitForm.effective_date,
      ratio_before: Number(stockSplitForm.ratio_before),
      ratio_after: Number(stockSplitForm.ratio_after),
      notes: stockSplitForm.notes.trim() || undefined,
    },
    onDone(success) {
      stockSplitPending.value = false;
      if (!success) {
        return;
      }
      stockSplitForm.symbol = "";
      stockSplitForm.market = "JP";
      stockSplitForm.effective_date = todayIso();
      stockSplitForm.ratio_before = 1;
      stockSplitForm.ratio_after = 1;
      stockSplitForm.notes = "";
    },
  });
}

function handleFxSubmit() {
  if (fxForm.from_currency === fxForm.to_currency) {
    return;
  }
  const payload: FxExchangeCreate = {
    exchange_date: fxForm.exchange_date,
    from_currency: fxForm.from_currency,
    to_currency: fxForm.to_currency,
    from_amount: Number(fxForm.from_amount),
    rate: Number(fxForm.rate),
    transaction_id: fxForm.transaction_id || undefined,
    notes: fxForm.notes?.trim() || undefined,
  };
  emit("add-fx", payload);
  fxForm.exchange_date = todayIso();
  fxForm.from_currency = "JPY";
  fxForm.to_currency = "USD";
  fxForm.from_amount = 0;
  fxForm.rate = 0;
  fxForm.transaction_id = "";
  fxForm.notes = "";
}

function selectFxExchange(id: string) {
  selectedFxExchangeId.value = id;
}

function confirmDeleteFx(id: string) {
  if (window.confirm(t("funds.fx.confirmDelete"))) {
    emit("delete-fx", id);
  }
}

function deleteSelectedFx() {
  if (!selectedFxExchange.value) {
    return;
  }
  confirmDeleteFx(selectedFxExchange.value.id);
}

function selectStockSplit(id: string) {
  selectedStockSplitId.value = id;
}

function deleteSelectedStockSplit() {
  if (!selectedStockSplit.value) {
    return;
  }
  if (window.confirm(t("funds.stockSplits.confirmDelete"))) {
    emit("delete-stock-split", selectedStockSplit.value.id);
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

function handleDeleteSelectedGroup() {
  if (!selectedFundingGroup.value) {
    return;
  }
  confirmDelete(selectedFundingGroup.value.name);
}

function selectCapitalAdjustment(id: string) {
  selectedCapitalAdjustmentId.value = id;
}
</script>

<style scoped>
.funds-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: clamp(1.6rem, 3vw, 2.4rem);
  overflow: hidden;
}

.funds-panel::before {
  content: none;
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

.header-actions { display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap; justify-content: flex-end; }
.account-overview { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.account-card { padding: 1.35rem 1.5rem; border-radius: var(--radius-lg); color: #f8f5ec; background: linear-gradient(135deg, #123a3e, #205a58); box-shadow: 0 12px 28px rgba(17, 57, 61, 0.14); }
.account-card:nth-child(2) { background: linear-gradient(135deg, #172f3d, #31566a); }
.account-card__head { display: flex; align-items: flex-start; justify-content: space-between; }
.account-card__eyebrow { color: rgba(255,255,255,.62); font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; }
.account-card h3 { margin-top: .15rem; font-size: 1rem; }
.currency-orb { display: grid; place-items: center; width: 2.25rem; height: 2.25rem; border: 1px solid rgba(255,255,255,.24); border-radius: 50%; font-size: 1.1rem; }
.account-card__total { display: block; margin: 1rem 0 1.25rem; font-size: clamp(1.7rem, 3vw, 2.4rem); font-variant-numeric: tabular-nums; }
.account-card__metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: .75rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,.15); }
.account-card__metrics span { display: grid; gap: .25rem; }
.account-card__metrics small { color: rgba(255,255,255,.58); }
.account-card__metrics b { font-size: .9rem; font-variant-numeric: tabular-nums; }
.account-card .positive { color: #8ad7b7; }
.account-card .negative { color: #ffadad; }
.cash-ledger { padding: 0; overflow: hidden; }
.cash-ledger .section-toolbar { padding: 1.2rem 1.35rem 0; }
.cash-ledger__description { margin-top: .35rem; color: var(--text-dim); font-size: .84rem; }
.cash-ledger__summary { display: flex; gap: .5rem; }
.cash-ledger__summary span { padding: .35rem .65rem; border-radius: 999px; background: var(--panel-soft); color: var(--text-dim); font-size: .78rem; }
.cash-description { min-width: 240px; color: var(--text-dim); }
.settings-section { display: grid; gap: 1rem; padding-top: .5rem; }
.section-label { color: var(--text-faint); font-size: .76rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }

@media (max-width: 760px) {
  .account-overview { grid-template-columns: 1fr; }
  .account-card__metrics { grid-template-columns: 1fr; }
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
  background: var(--panel-alt);
  box-shadow: none;
  padding: clamp(1.3rem, 2.6vw, 1.8rem);
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

.notes-cell {
  min-width: 180px;
  max-width: 320px;
  white-space: normal;
  line-height: 1.45;
  color: var(--text-dim);
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

.fx-panel {
  gap: 1.2rem;
}

.fx-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.fx-description {
  margin: 0.4rem 0 0;
  color: var(--text-dim);
  font-size: 0.85rem;
}

.fx-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.fx-form {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.fx-alert {
  padding: 0.8rem 1rem;
  border-radius: var(--radius-md);
  border: 1px solid rgba(255, 111, 29, 0.3);
  background: rgba(255, 200, 67, 0.1);
  color: var(--accent);
  font-size: 0.85rem;
}

.fx-alert ul {
  margin: 0.5rem 0 0;
  padding-left: 1.1rem;
}

.primary-btn {
  align-self: flex-end;
}

.table-scroll {
  overflow: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: var(--panel);
  box-shadow: none;
}

.table-scroll table {
  min-width: 560px;
}

.table-scroll thead {
  background: var(--panel-soft);
  color: var(--text-dim);
  text-transform: none;
  letter-spacing: 0;
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
  background: rgba(30, 156, 90, 0.04);
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

.ghost-btn {
  border: 1px solid var(--divider);
  background: #fff;
  color: var(--text);
  padding: 0.45rem 0.9rem;
  border-radius: var(--radius-sm);
  font-weight: 600;
  transition: background 0.2s ease, color 0.2s ease;
}

.ghost-btn:hover {
  background: var(--panel-soft);
  color: var(--accent-strong);
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

.interactive-row {
  cursor: pointer;
  transition: background var(--transition), box-shadow var(--transition);
}

.interactive-row.is-selected {
  box-shadow: inset 0 0 0 1px rgba(30, 156, 90, 0.28);
  background: rgba(30, 156, 90, 0.06);
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

@media (max-width: 720px) {
  .aggregate-controls {
    grid-template-columns: 1fr;
    gap: 0.45rem;
  }
}

@media (max-width: 768px) {
  .funds-panel {
    padding: 1.3rem;
  }

  .table-scroll table {
    min-width: 520px;
  }

  .fx-header {
    flex-direction: column;
    align-items: flex-start;
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
