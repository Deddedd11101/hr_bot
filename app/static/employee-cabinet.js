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
    const field = make('dd', typeof value === 'object' ? value?.name || 'Не указано' : value || 'Не указано');
    if (value?.username && /^[A-Za-z0-9_]{5,32}$/.test(value.username)) {
      const link = make('a', field.textContent);
      link.href = `https://t.me/${value.username}`;
      link.onclick = event => { if (tg?.openTelegramLink) { event.preventDefault(); tg.openTelegramLink(link.href); } };
      field.replaceChildren(link);
    }
    row.append(make('dt', label), field);
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

function disclosure(title, open = false) {
  const details = make('details', '');
  details.open = open;
  const body = make('div', '');
  details.append(make('summary', title), body);
  return [details, body];
}

function dateLabel(value) { return value?.split('-').reverse().join('.') || 'Дата не указана'; }

function showDevelopment(data) {
  const root = byId('development');
  root.append(make('h2', 'Развитие'));
  for (const [key, title, rows] of [['adaptation', 'Адаптация', data.adaptation], ['development', 'Цикл развития', data.cycle]]) {
    const [block, body] = disclosure(title, data.active === key);
    const list = make('ul', '');
    for (const item of rows) {
      const line = make('li', ''), name = make('div', item.title);
      name.append(make('small', dateLabel(item.date)));
      const state = {planned:'Запланировано', started:'Начато', completed:'Завершено', done:'Завершено', failed:'Требует внимания', paused:'На паузе'};
      line.append(name, make('small', state[item.status] || ''));list.append(line);
    }
    body.append(rows.length ? list : make('p', 'Этапы пока не запланированы.'));
    root.append(block);
  }
  if (!data.grade) return;
  const [block, body] = disclosure('Оценка грейда');
  const grade = data.grade;
  body.append(make('h2', grade.label || 'Оценка навыков'), make('small', dateLabel(grade.date)));
  const rows = grade.categories;
  if (rows.length >= 3) {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 200 200');svg.setAttribute('class', 'radar');svg.setAttribute('aria-hidden', 'true');
    for (const scale of [.25,.5,.75,1,0]) {
      const polygon = document.createElementNS(ns, 'polygon');
      polygon.setAttribute('points', rows.map(({percent}, i) => {
        const angle = 2 * Math.PI * i / rows.length - Math.PI / 2, r = 85 * (scale || Math.max(0, Math.min(100, percent)) / 100);
        return [100 + r * Math.cos(angle), 100 + r * Math.sin(angle)].join(',');
      }).join(' '));
      if (scale) polygon.setAttribute('class','grid');
      else { polygon.setAttribute('fill','var(--accent)');polygon.setAttribute('fill-opacity','.2'); }
      svg.append(polygon);
    }
    body.append(svg);
  }
  const list = make('ul', '');
  for (const item of rows) {
    const line = make('li', item.name);line.append(make('strong', `${item.percent}%`));list.append(line);
  }
  body.append(list);root.append(block);
}

function tabs() {
  const navigation = byId('navigation');
  const buttons = Array.from(navigation.querySelectorAll('button'));
  const sections = Array.from(byId('content').querySelectorAll('section'));
  let current = 0;
  buttons.forEach((button, index) => {button.onclick = () => {
    const direction = Math.sign(index - current);current = index;
    sections.forEach((section, i) => {section.hidden = (i < 2 ? 0 : i - 1) !== index;});
    buttons.forEach((item, i) => item.setAttribute('aria-selected', String(i === index)));
    byId('marker').style.transform = `translateX(${index * 100}%)`;
    if (direction && !matchMedia('(prefers-reduced-motion: reduce)').matches) byId('content').animate(
      [{opacity:.65, transform:`translateX(${12 * direction}px)`},{opacity:1, transform:'translateX(0)'}], {duration:220});
    window.scrollTo(0, 0);
  };});
  navigation.hidden = false;
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
  if (tg?.isVersionAtLeast?.('6.9')) {
    tg.setHeaderColor?.('#BADA1E');
  }
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
    showDevelopment(data.development);
    tabs();
    if (data.files.length) data.files.forEach(file => byId('files').append(fileRow(file)));
    else byId('files').append(make('li', 'Файлов пока нет'));
    byId('content').hidden = false;
    status.textContent = '';
  } catch (error) {
    status.textContent = error.message;
  }
}

start();
