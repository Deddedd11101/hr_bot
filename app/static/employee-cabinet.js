const tg = window.Telegram?.WebApp;
const byId = (id) => document.getElementById(id);
const status = byId('status');

function make(tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

function fields(id, pairs) {
  for (const [label, value] of pairs) {
    const row = make('div', '');
    row.append(make('dt', label), make('dd', value || 'Не указано'));
    byId(id).append(row);
  }
}

async function request(path) {
  const response = await fetch(`/employee-cabinet/${path}`, {
    headers: {'X-Telegram-Init-Data': tg.initData}, credentials: 'omit', cache: 'no-store',
  });
  if (!response.ok) throw new Error(response.status === 403 ? 'Открой кабинет заново через бота.' : 'Не удалось загрузить данные.');
  return response;
}

function fileRow(file) {
  const row = make('li', '');
  const title = make('div', file.name);
  if (file.size) title.append(make('small', `${Math.max(1, Math.round(file.size / 1024))} КБ`));
  const button = make('button', 'Скачать');
  button.onclick = async () => {
    button.disabled = true;
    status.textContent = '';
    try {
      const response = await request(`files/${file.id}`);
      const url = URL.createObjectURL(await response.blob());
      const anchor = make('a', '');
      anchor.href = url;
      anchor.download = file.name;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (error) {
      status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
  row.append(title, button);
  return row;
}

async function start() {
  tg?.ready();
  if (!tg?.initData) {
    status.textContent = 'Открой кабинет из Telegram командой /cabinet.';
    return;
  }
  tg.expand();
  status.textContent = 'Загрузка…';
  try {
    const data = await (await request('profile')).json();
    byId('name').textContent = data.name || 'Профиль сотрудника';
    byId('position').textContent = data.position || '';
    fields('profile', [['Рабочая почта', data.email], ['Рабочие часы', data.hours], ['Первый рабочий день', data.first_workday?.split('-').reverse().join('.')]]);
    fields('team', [['Руководитель', data.manager], ['Наставник по адаптации', data.adaptation_mentor], ['Наставник по ИПР', data.development_mentor]]);
    if (data.files.length) data.files.forEach(file => byId('files').append(fileRow(file)));
    else byId('files').append(make('li', 'Файлов пока нет'));
    byId('content').hidden = false;
    status.textContent = '';
  } catch (error) {
    status.textContent = error.message;
  }
}

start();
