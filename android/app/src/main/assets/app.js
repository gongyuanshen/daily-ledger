'use strict';

const $ = id => document.getElementById(id);
const titles = {ledger: '我的账本', calendar: '年度日历', stats: '支出统计', more: '更多', products: '商品管理'};
const state = {
  page: 'ledger', bootstrap: null, entries: [], products: [], summary: null,
  filter: {start_day: null, end_day: null, category: null, payment: null, keyword: ''},
  documentBusy: false, documentAction: null, busy: false,
  initialReadDeferred: false, initialDraft: null
};
const draftKey = 'daily-ledger-ui-draft-v1';

function localToday() {
  const date = new Date();
  return `${String(date.getFullYear()).padStart(4, '0')}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function node(tag, className, text) {
  const result = document.createElement(tag);
  if (className) result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
}

function money(amount) { return `¥${amount}`; }

function api(action, payload = {}) {
  if (!window.AndroidLedger || typeof window.AndroidLedger.request !== 'function') {
    throw new Error('运行环境错误：本地账本接口未连接。请通过 Android 应用打开此页面。');
  }
  const response = JSON.parse(window.AndroidLedger.request(JSON.stringify({action, payload})));
  if (response.ok !== true) {
    const error = new Error(response.error.message);
    error.name = response.error.type;
    throw error;
  }
  return response.data;
}

function errorText(error) { return `${error.name}: ${error.message}`; }

function showError(error, context, formId) {
  const message = `${context}\n${errorText(error)}`;
  $('error-message').textContent = message;
  $('error-panel').hidden = false;
  if (!formId) {
    const dialogs = Array.from(document.querySelectorAll('dialog[open]'));
    const visible = dialogs[dialogs.length - 1];
    const fields = {'entry-dialog': 'entry-error', 'product-dialog': 'product-error', 'budget-dialog': 'budget-error', 'filter-dialog': 'filter-error', 'product-picker-dialog': 'picker-error'};
    if (visible) formId = fields[visible.id];
  }
  if (formId) { $(formId).textContent = message; $(formId).hidden = false; }
}

function clearError() { $('error-panel').hidden = true; }

function announce(message) {
  $('notice').textContent = message;
  $('notice').hidden = false;
}

function clearFormError(id) { $(id).hidden = true; $(id).textContent = ''; }

function empty(container, title, description, buttonLabel, onClick) {
  const box = node('div', 'empty-state');
  box.append(node('div', 'empty-symbol', '≡'), node('h3', '', title), node('p', '', description));
  if (buttonLabel) {
    const button = node('button', 'small-button', buttonLabel);
    button.type = 'button'; button.addEventListener('click', onClick); box.append(button);
  }
  container.replaceChildren(box);
}

function openSheet(id) { if (!$(id).open) $(id).showModal(); }
function closeSheet(id) { if ($(id).open) $(id).close(); }

function syncMutationControls() {
  const disabled = state.busy || state.documentBusy;
  for (const id of ['save-entry', 'delete-entry', 'save-product', 'delete-product', 'save-budget', 'delete-budget', 'apply-product', 'export-backup', 'import-backup', 'export-csv', 'export-logs']) {
    $(id).disabled = disabled;
  }
  $('apply-product').disabled = disabled || !state.products.length;
}

function operation(context, errorId, work) {
  if (state.documentBusy) {
    showError(new Error('系统文件操作尚未结束，请先完成或取消文件选择。'), context, errorId);
    return;
  }
  if (state.busy) return;
  state.busy = true; syncMutationControls();
  clearError(); if (errorId) clearFormError(errorId);
  try {
    work();
  } catch (error) {
    showError(error, context, errorId);
  } finally {
    state.busy = false; syncMutationControls();
  }
}

function saveDraft() {
  const entry = {
    id: $('entry-id').value, day: $('entry-day').value, amount: $('entry-amount').value,
    category: $('entry-category').value, payment: $('entry-payment').value, note: $('entry-note').value,
    pending: $('entry-dialog').open
  };
  const product = {id: $('product-id').value, name: $('product-name').value, price: $('product-price').value, pending: $('product-dialog').open};
  const budget = {month: $('stats-month').value, amount: $('budget-amount').value, pending: $('budget-dialog').open};
  sessionStorage.setItem(draftKey, JSON.stringify({entry, product, budget, page: state.page, filter: state.filter, month: $('stats-month').value, year: $('calendar-year').value}));
}

function readDraft() {
  const serialized = sessionStorage.getItem(draftKey);
  if (!serialized) return null;
  const draft = JSON.parse(serialized);
  if (!draft || !titles[draft.page] || !draft.filter || !draft.entry || !draft.product || !draft.budget) {
    throw new Error('保存的界面草稿格式错误，未恢复。');
  }
  state.page = draft.page; state.filter = draft.filter;
  $('stats-month').value = draft.month; $('calendar-year').value = draft.year;
  return draft;
}

function restoreDraft(draft) {
  if (!draft) return;
  if (draft.product.pending) {
    openProduct(draft.product);
    announce('已恢复未保存的商品草稿，请检查后再保存。');
  } else if (draft.budget.pending) {
    $('stats-month').value = draft.budget.month;
    openBudget(draft.budget.amount);
    announce('已恢复未保存的预算草稿，请检查后再保存。');
  } else if (draft.entry.pending) {
    openEntry(draft.entry);
    announce('已恢复未保存的支出草稿，请检查后再保存。');
  }
}

function populateOptions() {
  for (const [values, datalistId, filterId, allLabel] of [
    [state.bootstrap.categories, 'category-options', 'filter-category', '所有分类'],
    [state.bootstrap.payments, 'payment-options', 'filter-payment', '所有支付方式']
  ]) {
    const selected = $(filterId).value;
    $(datalistId).replaceChildren();
    $(filterId).replaceChildren(new Option(allLabel, ''));
    for (const value of values) {
      const option = document.createElement('option'); option.value = value;
      $(datalistId).append(option);
      $(filterId).append(new Option(value, value));
    }
    $(filterId).value = selected;
  }
}

function loadBootstrap() {
  state.bootstrap = api('bootstrap', {today: localToday()});
  $('hero-month').textContent = `${state.bootstrap.month.replace('-', '年')}月支出`;
  $('month-amount').textContent = state.bootstrap.month_amount;
  $('today-amount').textContent = money(state.bootstrap.today_amount);
  $('month-count').textContent = `${state.bootstrap.month_count} 笔`;
  $('runtime-info').textContent = `Python ${state.bootstrap.python_version} · SQLite ${state.bootstrap.sqlite_version}`;
  populateOptions();
}

function filterDescription() {
  const filter = state.filter;
  const items = [];
  if (filter.start_day && filter.end_day === filter.start_day) items.push(filter.start_day);
  else {
    if (filter.start_day) items.push(`从 ${filter.start_day}`);
    if (filter.end_day) items.push(`至 ${filter.end_day}`);
  }
  if (filter.category) items.push(filter.category);
  if (filter.payment) items.push(filter.payment);
  if (filter.keyword) items.push(`关键词：${filter.keyword}`);
  return items.join(' · ');
}

function loadEntries() {
  const result = api('entries', state.filter);
  state.entries = result.entries;
  $('entries-caption').textContent = `${result.count} 笔支出 · 合计 ${money(result.amount)}`;
  const description = filterDescription();
  $('active-filters').hidden = !description; $('filter-dot').hidden = !description;
  $('filter-description').textContent = description;
  const list = $('entries-list'); list.replaceChildren();
  if (!state.entries.length) {
    empty(list, description ? '没有符合条件的支出' : '从第一笔开始', description ? '调整筛选条件，再看看其他记录。' : '早餐、通勤、一本书。把日常记下来，让每一笔花费都有迹可循。', description ? '清除筛选' : '记一笔', description ? clearFilters : () => openEntry());
    return;
  }
  let day = null; let card;
  for (const entry of state.entries) {
    if (entry.day !== day) {
      day = entry.day;
      const group = node('section', 'entry-group');
      const heading = node('div', 'day-heading');
      heading.append(node('strong', '', day), node('span', '', day === localToday() ? '今天' : ''));
      card = node('div', 'entry-card'); group.append(heading, card); list.append(group);
    }
    const row = node('button', 'entry-row'); row.type = 'button';
    row.setAttribute('aria-label', `${entry.day} ${entry.category} ${money(entry.amount)}，点击编辑`);
    const detail = node('div', 'entry-detail');
    detail.append(node('div', 'entry-name', entry.note || entry.category), node('div', 'entry-meta', `${entry.category} · ${entry.payment}`));
    row.append(node('span', 'entry-icon', entry.category.slice(0, 1)), detail, node('strong', 'entry-amount', money(entry.amount)));
    row.addEventListener('click', () => openEntry(entry)); card.append(row);
  }
}

function loadCalendar() {
  const year = Number($('calendar-year').value);
  const result = api('calendar', {year});
  $('year-amount').textContent = money(result.amount);
  $('year-days').textContent = `${result.recorded_days} 天`;
  $('year-count').textContent = `${result.count} 笔`;
  const days = new Map(result.by_day.map(day => [day.day, day]));
  const container = $('calendar-months'); container.replaceChildren();
  for (const month of result.months) {
    const monthNumber = Number(month.month.slice(5));
    const section = node('section', 'calendar-month');
    const heading = node('div', 'calendar-month-heading');
    heading.append(node('h3', '', `${monthNumber}月`), node('span', '', `${month.count} 笔 · ${money(month.amount)}`));
    const grid = node('div', 'calendar-grid');
    for (const weekday of ['一', '二', '三', '四', '五', '六', '日']) grid.append(node('span', 'weekday', weekday));
    // setFullYear keeps years 1..99 literal, unlike the multi-argument Date constructor.
    const first = new Date(); first.setHours(12, 0, 0, 0); first.setFullYear(year, monthNumber - 1, 1);
    const last = new Date(first); last.setMonth(monthNumber, 0);
    const offset = (first.getDay() + 6) % 7;
    for (let blank = 0; blank < offset; blank++) grid.append(node('span', 'calendar-blank'));
    for (let number = 1; number <= last.getDate(); number++) {
      const key = `${month.month}-${String(number).padStart(2, '0')}`;
      const record = days.get(key);
      const button = node('button', `calendar-day${record ? ' recorded' : ''}${key === localToday() ? ' today' : ''}`);
      button.type = 'button'; button.setAttribute('aria-label', `${key}，${record ? `${record.count}笔，${money(record.amount)}` : '无记录'}，查看支出`);
      button.append(node('span', '', String(number)), node('small', '', record ? record.amount : '—'));
      button.addEventListener('click', () => {
        state.filter = {start_day: key, end_day: key, category: null, payment: null, keyword: ''};
        navigate('ledger');
      });
      grid.append(button);
    }
    section.append(heading, grid); container.append(section);
  }
}

function chartRow(label, amount, percent, caption) {
  const row = node('div', 'chart-row'); const heading = node('div', 'chart-label');
  const value = node('strong', '', money(amount));
  if (caption !== undefined) value.append(node('small', '', caption));
  heading.append(node('span', '', label), value);
  const track = node('div', 'bar-track'); const fill = node('div', 'bar-fill');
  fill.style.width = `${percent}%`; track.append(fill); row.append(heading, track); return row;
}

function loadSummary() {
  state.summary = api('summary', {month: $('stats-month').value});
  const summary = state.summary;
  $('stats-amount').textContent = money(summary.amount);
  $('stats-count').textContent = `${summary.count} 笔支出`;
  $('daily-average').textContent = money(summary.daily_average);
  $('month-days').textContent = `${summary.days_in_month} 天`;
  $('edit-budget').textContent = summary.budget === null ? '设置预算' : '修改预算';
  const budget = $('budget-card'); budget.replaceChildren();
  if (summary.budget === null) budget.append(node('p', 'chart-empty', '设一个预算，给这个月的花费留个边界。'));
  else {
    const total = node('div', 'budget-line'); total.append(node('span', '', '本月预算'), node('strong', '', money(summary.budget)));
    const remaining = node('div', 'budget-line');
    const isOver = summary.remaining.startsWith('-');
    remaining.append(node('span', '', isOver ? '已超出预算' : '预算剩余'), node('strong', isOver ? 'over-budget' : '', money(isOver ? summary.over_budget : summary.remaining)));
    budget.append(total, remaining);
  }
  const categories = $('category-chart'); categories.replaceChildren();
  for (const category of summary.by_category) categories.append(chartRow(category.name, category.amount, category.percent, `${category.percent}%`));
  if (!summary.by_category.length) categories.append(node('p', 'chart-empty', '本月还没有支出，分类统计会在这里出现。'));
  const daily = $('daily-chart'); daily.replaceChildren();
  const rows = node('div', 'daily-list');
  for (const day of summary.by_day) rows.append(chartRow(day.day.slice(5).replace('-', '/'), day.amount, day.percent));
  if (summary.by_day.length) daily.append(rows);
  else daily.append(node('p', 'chart-empty', '本月还没有支出，日支出趋势会在这里出现。'));
}

function loadProducts() {
  state.products = api('products').products;
  const container = $('products-list'); container.replaceChildren();
  if (!state.products.length) { empty(container, '常买的，先记个单价', '添加商品后，记账时选择商品和数量，由账本计算金额。', '新增商品', () => openProduct()); return; }
  for (const product of state.products) {
    const row = node('button', 'product-row'); row.type = 'button';
    const name = node('span', ''); name.append(node('strong', '', product.name), node('small', '', '点击编辑商品'));
    row.append(name, node('span', '', `${money(product.price)} / 件`));
    row.addEventListener('click', () => openProduct(product)); container.append(row);
  }
}

function refreshCurrent() {
  loadBootstrap(); loadEntries();
  if (state.page === 'calendar') loadCalendar();
  if (state.page === 'stats') loadSummary();
  if (state.page === 'products') loadProducts();
}

function refreshAfterCommit(message) {
  announce(message);
  try { saveDraft(); refreshCurrent(); }
  catch (error) { showError(error, `${message}但后续草稿更新或页面刷新失败；请勿重复提交。`); }
}

function readPage() {
  try {
    clearError();
    if (state.page === 'ledger') { loadBootstrap(); loadEntries(); }
    else if (state.page === 'calendar') loadCalendar();
    else if (state.page === 'stats') loadSummary();
    else if (state.page === 'products') loadProducts();
  } catch (error) { showError(error, '读取账本失败。请查看错误详情后重新读取。'); }
}

function navigate(page, push = true, read = true) {
  if (!titles[page]) throw new Error(`未知页面：${page}`);
  state.page = page;
  for (const name of Object.keys(titles)) $(`page-${name}`).hidden = name !== page;
  $('page-title').replaceChildren(document.createTextNode(titles[page]), node('span', 'brand-dot'));
  $('header-add').hidden = page === 'products';
  for (const button of document.querySelectorAll('[data-page]')) {
    const active = button.dataset.page === (page === 'products' ? 'more' : page);
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  }
  if (push) history.pushState({page}, '', `#${page}`);
  window.scrollTo(0, 0);
  if (read) readPage();
  saveDraft();
}

function openEntry(entry) {
  $('entry-form').reset(); clearFormError('entry-error');
  $('entry-id').value = entry ? entry.id : '';
  $('entry-day').value = entry ? entry.day : localToday();
  $('entry-amount').value = entry ? entry.amount : '';
  $('entry-note').value = entry ? entry.note : '';
  $('entry-category').value = entry ? entry.category : '未分类';
  $('entry-payment').value = entry ? entry.payment : '未指定';
  $('entry-title').textContent = entry && entry.id ? '编辑支出' : '记一笔';
  $('delete-entry').hidden = !(entry && entry.id);
  openSheet('entry-dialog'); saveDraft();
}

function resetEntry() { closeSheet('entry-dialog'); $('entry-form').reset(); $('entry-id').value = ''; }

function openProduct(product) {
  $('product-form').reset(); clearFormError('product-error');
  $('product-id').value = product ? product.id : '';
  $('product-name').value = product ? product.name : '';
  $('product-price').value = product ? product.price : '';
  $('product-title').textContent = product && product.id ? '编辑商品' : '新增商品';
  $('delete-product').hidden = !(product && product.id);
  openSheet('product-dialog'); saveDraft();
}

function resetProduct() { closeSheet('product-dialog'); $('product-form').reset(); $('product-id').value = ''; }

function openBudget(draftAmount) {
  clearFormError('budget-error');
  $('budget-month-caption').textContent = `${$('stats-month').value} 的支出预算`;
  $('budget-amount').value = draftAmount !== undefined ? draftAmount : (state.summary.budget === null ? '' : state.summary.budget);
  $('delete-budget').hidden = !state.summary || state.summary.budget === null;
  openSheet('budget-dialog'); saveDraft();
}

function openFilter() {
  const filter = state.filter;
  $('filter-start').value = filter.start_day || ''; $('filter-end').value = filter.end_day || '';
  $('filter-category').value = filter.category || ''; $('filter-payment').value = filter.payment || '';
  $('filter-keyword').value = filter.keyword; clearFormError('filter-error');
  openSheet('filter-dialog');
}

function clearFilters() {
  state.filter = {start_day: null, end_day: null, category: null, payment: null, keyword: ''};
  readPage(); saveDraft();
}

function shiftMonth(direction) {
  const [year, month] = $('stats-month').value.split('-').map(Number);
  const date = new Date(); date.setHours(12, 0, 0, 0); date.setFullYear(year, month - 1 + direction, 1);
  if (date.getFullYear() < 1 || date.getFullYear() > 9999) { showError(new Error('年份须在 1 至 9999 之间。'), '无法切换月份。'); return; }
  $('stats-month').value = `${String(date.getFullYear()).padStart(4, '0')}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  readPage(); saveDraft();
}

function openProductPicker() {
  clearFormError('picker-error');
  state.products = api('products').products;
  $('picker-product').replaceChildren();
  for (const product of state.products) $('picker-product').append(new Option(`${product.name} · ${money(product.price)} / 件`, product.id));
  $('product-picker-form').reset();
  $('picker-empty').hidden = !!state.products.length;
  if (!state.products.length) empty($('picker-empty'), '还没有商品', '先在「更多 → 商品管理」中添加商品，再按数量填写金额。');
  $('picker-product').disabled = !state.products.length;
  $('apply-product').disabled = !state.products.length || state.documentBusy;
  openSheet('product-picker-dialog');
}

function startDocuments(action) {
  if (state.documentBusy || state.busy) throw new Error('另一个操作尚未结束，请先完成或取消。');
  if (!window.AndroidLedger || typeof window.AndroidLedger.documents !== 'function') throw new Error('运行环境错误：系统文件接口未连接。');
  state.documentAction = action;
  state.documentBusy = true; syncMutationControls();
  try {
    window.AndroidLedger.documents(JSON.stringify({action, payload: action === 'csv' ? state.filter : {}}));
  } catch (error) {
    state.documentBusy = false; state.documentAction = null; syncMutationControls(); throw error;
  }
}

function resetAfterRestore() {
  for (const dialog of document.querySelectorAll('dialog[open]')) dialog.close();
  for (const form of document.querySelectorAll('form')) form.reset();
  $('entry-id').value = ''; $('product-id').value = '';
  state.bootstrap = null; state.entries = []; state.products = []; state.summary = null;
  state.filter = {start_day: null, end_day: null, category: null, payment: null, keyword: ''};
  $('stats-month').value = localToday().slice(0, 7); $('calendar-year').value = localToday().slice(0, 4);
  for (const id of ['entries-list', 'products-list', 'calendar-months', 'budget-card', 'category-chart', 'daily-chart', 'category-options', 'payment-options']) $(id).replaceChildren();
  for (const id of ['month-amount', 'today-amount', 'month-count', 'stats-amount', 'stats-count', 'daily-average', 'month-days', 'year-amount', 'year-days', 'year-count']) $(id).textContent = '—';
  $('entries-caption').textContent = '正在读取恢复后的账本…';
  $('active-filters').hidden = true; $('filter-dot').hidden = true;
  sessionStorage.removeItem(draftKey);
}

window.onDocumentBusy = busy => {
  state.documentBusy = busy;
  syncMutationControls();
};

window.onDocumentResult = result => {
  const deferred = state.initialReadDeferred;
  const draft = state.initialDraft;
  state.initialReadDeferred = false; state.initialDraft = null;
  state.documentBusy = false; state.documentAction = null; syncMutationControls();
  if (result.cancelled === true) {
    if (deferred) {
      try { finishInitialization(draft); }
      catch (error) { showError(error, '文件选择已取消，但读取账本失败。'); }
    }
    announce('已取消文件操作，账本未因此操作而改变。'); return;
  }
  if (result.ok !== true) {
    const error = new Error(result.error.message); error.name = result.error.type;
    if (deferred) {
      // After an interrupted restore its commit status can be unknown. Re-read actual
      // storage and do not reopen an edit draft tied to the previous database.
      try {
        if (result.action === 'restore') resetAfterRestore();
        finishInitialization(result.action === 'restore' ? null : draft);
      } catch (readError) { error.message += `\n重新读取账本也失败：${errorText(readError)}`; }
    }
    showError(error, result.action === 'restore' ? '恢复账本失败。请查看错误详情。' : '文件操作失败。请查看错误详情。');
    return;
  }
  clearError();
  if (result.action === 'restore') {
    try { resetAfterRestore(); refreshCurrent(); saveDraft(); }
    catch (error) { showError(error, '备份已恢复，但后续草稿清理或页面刷新失败。旧表单已关闭，请重新读取。'); }
  } else if (deferred) {
    try { finishInitialization(draft); }
    catch (error) { showError(error, '文件操作已完成，但读取账本失败。'); }
  }
  announce(result.message);
};

window.handleAndroidBack = () => {
  const dialogs = Array.from(document.querySelectorAll('dialog[open]'));
  if (dialogs.length) { dialogs[dialogs.length - 1].close(); saveDraft(); return true; }
  if (state.page === 'products') { navigate('more', false); return true; }
  if (state.page !== 'ledger') { navigate('ledger', false); return true; }
  return false;
};

for (const button of document.querySelectorAll('[data-close]')) button.addEventListener('click', () => { closeSheet(button.dataset.close); saveDraft(); });
for (const button of document.querySelectorAll('[data-page]')) button.addEventListener('click', () => navigate(button.dataset.page));
for (const dialog of document.querySelectorAll('dialog')) dialog.addEventListener('close', saveDraft);
for (const formId of ['entry-form', 'product-form', 'budget-form']) {
  $(formId).addEventListener('input', saveDraft); $(formId).addEventListener('change', saveDraft);
}
window.addEventListener('popstate', event => {
  for (const dialog of document.querySelectorAll('dialog[open]')) dialog.close();
  navigate(event.state && event.state.page ? event.state.page : 'ledger', false);
});
window.addEventListener('error', event => {
  const error = event.error instanceof Error ? event.error : new Error(event.message);
  showError(error, '界面发生错误，详情如下。');
});
window.addEventListener('unhandledrejection', event => showError(event.reason instanceof Error ? event.reason : new Error(String(event.reason)), '界面操作失败，详情如下。'));

$('add-entry').addEventListener('click', () => openEntry());
$('header-add').addEventListener('click', () => openEntry());
$('open-filter').addEventListener('click', openFilter);
$('clear-filter').addEventListener('click', clearFilters);
$('retry-load').addEventListener('click', () => { try { clearError(); refreshCurrent(); } catch (error) { showError(error, '重新读取账本失败。'); } });
$('open-products').addEventListener('click', () => navigate('products'));
$('add-product').addEventListener('click', () => openProduct());
$('edit-budget').addEventListener('click', () => { try { if (!state.summary) loadSummary(); openBudget(); } catch (error) { showError(error, '读取预算失败。'); } });
$('choose-product').addEventListener('click', () => { try { openProductPicker(); } catch (error) { showError(error, '读取商品失败。', 'entry-error'); } });

$('entry-form').addEventListener('submit', event => {
  event.preventDefault();
  operation('保存支出失败，表单内容已保留。', 'entry-error', () => {
    api('save_entry', {id: $('entry-id').value || null, day: $('entry-day').value, amount: $('entry-amount').value, note: $('entry-note').value, category: $('entry-category').value, payment: $('entry-payment').value});
    resetEntry(); refreshAfterCommit('支出已保存。');
  });
});
$('delete-entry').addEventListener('click', () => {
  if (!confirm('确定删除这笔支出？删除后无法撤销。')) return;
  operation('删除支出失败。', 'entry-error', () => { api('delete_entry', {id: $('entry-id').value}); resetEntry(); refreshAfterCommit('支出已删除。'); });
});
$('product-form').addEventListener('submit', event => {
  event.preventDefault();
  operation('保存商品失败，表单内容已保留。', 'product-error', () => {
    api('save_product', {id: $('product-id').value || null, name: $('product-name').value, price: $('product-price').value});
    resetProduct(); refreshAfterCommit('商品已保存。');
  });
});
$('delete-product').addEventListener('click', () => {
  if (!confirm('确定删除这个商品？历史支出不会改变。')) return;
  operation('删除商品失败。', 'product-error', () => { api('delete_product', {id: $('product-id').value}); resetProduct(); refreshAfterCommit('商品已删除，历史支出保持原样。'); });
});
$('budget-form').addEventListener('submit', event => {
  event.preventDefault();
  operation('保存预算失败，表单内容已保留。', 'budget-error', () => {
    api('save_budget', {month: $('stats-month').value, amount: $('budget-amount').value});
    closeSheet('budget-dialog'); $('budget-form').reset(); refreshAfterCommit('月度预算已保存。');
  });
});
$('delete-budget').addEventListener('click', () => {
  if (!confirm(`确定移除 ${$('stats-month').value} 的预算？支出记录不会改变。`)) return;
  operation('移除预算失败。', 'budget-error', () => { api('delete_budget', {month: $('stats-month').value}); closeSheet('budget-dialog'); $('budget-form').reset(); refreshAfterCommit('月度预算已移除。'); });
});
$('product-picker-form').addEventListener('submit', event => {
  event.preventDefault();
  operation('计算商品金额失败，原金额已保留。', 'picker-error', () => {
    const add = document.querySelector('input[name="amount-mode"]:checked').value === 'add';
    const result = api('product_amount', {id: $('picker-product').value, quantity: $('picker-quantity').value, current_amount: add ? $('entry-amount').value : '0', add});
    $('entry-amount').value = result.amount;
    if (!$('entry-note').value) $('entry-note').value = result.description;
    else if (add) $('entry-note').value += `；${result.description}`;
    closeSheet('product-picker-dialog'); saveDraft();
  });
});
$('filter-form').addEventListener('submit', event => {
  event.preventDefault(); clearFormError('filter-error');
  const candidate = {start_day: $('filter-start').value || null, end_day: $('filter-end').value || null, category: $('filter-category').value || null, payment: $('filter-payment').value || null, keyword: $('filter-keyword').value};
  if (candidate.start_day && candidate.end_day && candidate.start_day > candidate.end_day) { showError(new Error('起始日期不能晚于结束日期。'), '筛选日期无效。', 'filter-error'); return; }
  state.filter = candidate; closeSheet('filter-dialog'); navigate('ledger');
});
for (const button of document.querySelectorAll('[data-range]')) button.addEventListener('click', () => {
  const today = localToday();
  $('filter-start').value = button.dataset.range === 'all' ? '' : button.dataset.range === 'today' ? today : `${today.slice(0, 7)}-01`;
  const end = new Date(); end.setHours(12, 0, 0, 0); end.setMonth(end.getMonth() + 1, 0);
  $('filter-end').value = button.dataset.range === 'all' ? '' : button.dataset.range === 'today' ? today : `${today.slice(0, 7)}-${String(end.getDate()).padStart(2, '0')}`;
});
$('calendar-year').addEventListener('change', () => { readPage(); saveDraft(); });
for (const [id, direction] of [['previous-year', -1], ['next-year', 1]]) $(id).addEventListener('click', () => {
  const year = Number($('calendar-year').value) + direction;
  if (year < 1 || year > 9999) { showError(new Error('年份须在 1 至 9999 之间。'), '无法切换年份。'); return; }
  $('calendar-year').value = String(year); readPage(); saveDraft();
});
$('stats-month').addEventListener('change', () => { readPage(); saveDraft(); });
$('previous-month').addEventListener('click', () => shiftMonth(-1));
$('next-month').addEventListener('click', () => shiftMonth(1));
for (const [id, action] of [['export-backup', 'backup'], ['export-csv', 'csv'], ['export-logs', 'logs']]) $(id).addEventListener('click', () => {
  try { clearError(); startDocuments(action); } catch (error) { showError(error, '无法打开系统文件选择器。'); }
});
$('import-backup').addEventListener('click', () => {
  if (!confirm('恢复会整体替换当前账本，不会合并记录。\n\n所选备份验证通过后，系统会先在应用内备份当前账本，再执行恢复。\n\n确定选择备份文件？')) return;
  try { clearError(); startDocuments('restore'); } catch (error) { showError(error, '无法开始恢复账本。'); }
});

function finishInitialization(draft) {
  loadBootstrap();
  history.replaceState({page: state.page}, '', `#${state.page}`);
  navigate(state.page, false, false);
  readPage(); restoreDraft(draft);
}

function initialize() {
  $('stats-month').value = localToday().slice(0, 7); $('calendar-year').value = localToday().slice(0, 4);
  const draft = readDraft();
  if (!window.AndroidLedger) throw new Error('运行环境错误：本地账本接口未连接。请通过 Android 应用打开此页面。');
  if (typeof window.AndroidLedger.documentsPending !== 'function' || typeof window.AndroidLedger.ready !== 'function') throw new Error('运行环境错误：本地文件生命周期接口未连接。');
  state.documentBusy = window.AndroidLedger.documentsPending(); syncMutationControls();
  state.initialReadDeferred = state.documentBusy; state.initialDraft = draft;
  // Native must learn that callbacks exist even while restore blocks database reads.
  window.AndroidLedger.ready();
  if (state.documentBusy) { navigate(state.page, false, false); return; }
  state.initialDraft = null;
  finishInitialization(draft);
}

try { initialize(); } catch (error) { showError(error, '账本初始化失败。请查看错误详情。'); }
