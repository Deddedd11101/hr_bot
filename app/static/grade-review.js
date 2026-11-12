const tg = window.Telegram?.WebApp;
const byId = id => document.getElementById(id);
const view = byId('view');
const actions = byId('actions');
const status = byId('status');
let model, answers, busy = false, index = 0;
let reviewing = false;

function add(tag, text, parent = view, className = '') {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  parent.append(node);
  return node;
}

function button(text, click, parent = view, className = '') {
  const node = add('button', text, parent, className);
  node.type = 'button';
  node.disabled = busy;
  node.onclick = click;
  return node;
}

async function request(method = 'GET', data) {
  const response = await fetch(location.pathname.replace(/\/$/, '') + '/answers', {
    method,
    headers: {'X-Telegram-Init-Data': tg.initData, 'Content-Type': 'application/json'},
    body: data && JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : 'Не удалось сохранить ответы.');
  return result;
}

function go(i, review = false) {
  const direction = i < index ? 'back' : 'forward';
  index = i;
  reviewing = review;
  status.textContent = '';
  render();
  delete view.dataset.motion;
  void view.offsetWidth;
  view.dataset.motion = direction;
  byId('scroll').scrollTop = 0;
}

function updateProgress() {
  const progress = byId('progress');
  const count = Object.keys(answers).length;
  const total = model.questions.length;
  progress.hidden = false;
  progress.setAttribute('aria-valuemax', total);
  progress.setAttribute('aria-valuenow', count);
  byId('progress-fill').style.transform = `scaleX(${count / total})`;
}

function render() {
  const items = model.questions;
  const count = Object.keys(answers).length;
  updateProgress();
  view.replaceChildren();
  actions.replaceChildren();
  if (reviewing) {
    add('h2', model.editable ? 'Проверь ответы' : 'Ответы сохранены');
    items.forEach((item, i) => {
      const value = answers[item.key];
      const label = value === undefined ? 'Без ответа' : value === null ? 'Пропущен'
        : item.options ? value : value.length > 100 && model.editable ? value.slice(0, 100) + '…' : value;
      const row = model.editable ? button('', () => go(i), view, 'row') : add('div', '', view, 'row');
      add('span', item.title, row);
      add('span', label, row, 'muted');
    });
    if (model.editable) {
      button(model.completed ? 'Сохранить изменения' : 'Подтвердить ответы', save, actions, 'primary').disabled =
        busy || count !== items.length;
    }
    return;
  }

  const item = items[index];
  add('p', [`${index + 1} / ${items.length}`, item.group].filter(Boolean).join(' · '), view, 'muted');
  add('h2', item.title);
  let selected = answers[item.key];
  let field;
  if (item.options) {
    const grid = add('div', '', view, 'options');
    const controls = [];
    const options = [...Object.entries(item.options), [null, item.skip]];
    for (const [value, title] of options) {
      const control = button(value === null ? title : `${value}. ${title}`, () => {
        selected = value;
        answers[item.key] = value;
        updateProgress();
        for (const [node, choice] of controls) node.setAttribute('aria-pressed', String(choice === value));
        next.disabled = false;
      }, grid, 'option');
      control.setAttribute('aria-pressed', String(selected === value));
      controls.push([control, value]);
    }
  } else {
    field = add('textarea', '');
    field.maxLength = 4096;
    field.setAttribute('aria-label', item.title);
    field.value = selected ?? '';
    field.oninput = () => {
      answers[item.key] = field.value.trim() || null;
      updateProgress();
    };
  }
  if (index > 0) button('Назад', () => go(index - 1), actions);
  if (count || model.completed) button('Все ответы', () => go(index, true), actions);
  const next = button(index + 1 === items.length ? 'Проверить ответы' : 'Далее', () => {
    if (field) answers[item.key] = field.value.trim() || null;
    if (index + 1 === items.length) go(index, true);
    else go(index + 1);
  }, actions, 'primary');
  next.disabled = Boolean(item.options && selected === undefined);
}

async function save() {
  if (busy) return;
  busy = true;
  render();
  status.textContent = 'Сохраняем ответы…';
  try {
    const result = await request('PUT', {answers, revision: model.revision});
    model.revision = result.revision;
    model.completed = true;
    status.textContent = 'Ответы сохранены.';
  } catch (error) {
    status.textContent = error.message;
  } finally {
    busy = false;
    render();
  }
}

async function start() {
  tg?.ready();
  if (!tg?.initData) {
    status.textContent = 'Открой опрос кнопкой из приглашения в Telegram.';
    return;
  }
  tg.expand();
  if (tg.isVersionAtLeast?.('6.9')) tg.setHeaderColor?.('#BADA1E');
  if (tg.isVersionAtLeast?.('7.10')) tg.setBottomBarColor?.('#FFFFFF');
  try {
    model = await request();
    answers = {...model.answers};
    byId('subject').textContent = model.subject;
    status.textContent = '';
    reviewing = model.completed || !model.editable;
    render();
  } catch (error) {
    status.textContent = error.message;
    button('Обновить', () => location.reload());
  }
}

start();
