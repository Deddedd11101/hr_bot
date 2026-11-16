const tg = window.Telegram?.WebApp;
const byId = (id) => document.getElementById(id);
const status = byId('status');

function make(tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

function chatLink(username, text) {
  if (!/^[A-Za-z0-9_]{5,32}$/.test(username || '')) return null;
  const link = make('a', text);
  link.href = `https://t.me/${username}`;
  link.onclick = event => {
    if (tg?.openTelegramLink) { event.preventDefault(); tg.openTelegramLink(link.href); }
  };
  return link;
}

function fields(id, pairs) {
  for (const [label, value] of pairs) {
    const row = make('div', '');
    const field = make('dd', typeof value === 'object' ? value?.name || 'Не указано' : value || 'Не указано');
    const link = chatLink(value?.username, field.textContent);
    if (link) field.replaceChildren(link);
    row.append(make('dt', label), field);
    byId(id).append(row);
  }
}

async function request(path, data) {
  const response = await fetch(`/employee-cabinet/${path}`, {
    headers: {'X-Telegram-Init-Data': tg.initData, ...(data ? {'Content-Type': 'application/json'} : {})},
    ...(data ? {method: 'POST', body: JSON.stringify(data)} : {}), credentials: 'omit', cache: 'no-store',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(response.status === 403 ? 'Открой кабинет заново через бота.' :
      typeof error?.detail === 'string' ? error.detail : 'Не удалось выполнить запрос.');
  }
  return response;
}

function setupVacation() {
  const form = byId('vacation-form');
  const button = byId('vacation-submit');
  const notice = byId('vacation-status');
  const list = byId('vacation-requests');
  let checked = null;
  async function refresh() {
    const rows = await (await request('vacation/requests')).json();
    list.replaceChildren(...rows.map(row => {
      const item = make('li', '');
      item.append(make('span', `${dateLabel(row.starts_on)} – ${dateLabel(row.ends_on)}`),
        make('small', {pending:'У руководителя', pending_hr:'У HR', approved:'Согласована', rejected:'Отклонена'}[row.status] || row.status));
      return item;
    }));
    if (!rows.length) list.append(make('li', 'Заявок пока нет'));
  }
  form.oninput = () => {
    checked = null;
    notice.textContent = '';
    button.textContent = 'Проверить даты';
  };
  form.onsubmit = async event => {
    event.preventDefault();
    const period = Object.fromEntries(new FormData(form));
    const key = JSON.stringify(period);
    const inputs = [...form.querySelectorAll('input')];
    button.disabled = true;
    inputs.forEach(input => { input.disabled = true; });
    try {
      if (checked === key) {
        await request('vacation/requests', period);
        form.reset();
        checked = null;
        button.textContent = 'Проверить даты';
        notice.textContent = 'Заявка сохранена.';
        await refresh().catch(() => { notice.textContent = 'Заявка сохранена. Список не удалось обновить.'; });
      } else {
        const days = await (await request('vacation/preview', period)).json();
        checked = key;
        notice.textContent = `Календарных: ${days.calendar_days} · рабочих: ${days.workdays} · нерабочих: ${days.non_workdays}`;
        button.textContent = 'Подать заявку';
      }
    } catch (error) {
      notice.textContent = error.message;
    } finally {
      button.disabled = false;
      inputs.forEach(input => { input.disabled = false; });
    }
  };
  void refresh().catch(error => { list.replaceChildren(make('li', error.message)); });
}

function disclosure(title, open = false) {
  const details = make('details', '');
  details.open = open;
  const body = make('div', '');
  details.append(make('summary', title), body);
  return [details, body];
}

function dateLabel(value) { return value?.split('-').reverse().join('.') || 'Дата не указана'; }

function showDevelopment(data, files) {
  const root = byId('development');
  root.append(make('h2', 'Развитие'));
  const adapting = data.active === 'adaptation';
  root.append(make('h3', adapting ? 'Адаптация' : 'ИПР'));
  const plan = make('dl', '');
  plan.id = 'development-stages';
  root.append(plan);
  const describe = item => item && [item.title, dateLabel(item.date), item.status === 'paused' ? 'На паузе' : null].filter(Boolean).join(' · ');
  fields(plan.id, [[adapting ? 'Текущий этап' : 'Последний запуск', describe(data.current)], ['Следующий этап', describe(data.upcoming)]]);
  const materials = files.filter(file => file.material);
  if (materials.length) {
    const [block, body] = disclosure('Материалы адаптации и ИПР');
    const list = make('ul', '');
    for (const file of materials) list.append(fileRow(file));
    body.append(list);
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

function setupColleagues() {
  const field = byId('colleague-search');
  const notice = byId('colleague-status');
  const retry = byId('colleague-retry');
  const root = byId('colleague-groups');
  const normalize = value => (value || '').toLocaleLowerCase('ru').replaceAll('ё', 'е');
  const collator = new Intl.Collator('ru');
  let people = null;
  let loading = false;
  function render() {
    if (!people) return;
    root.replaceChildren();
    const terms = normalize(field.value).trim().split(/\s+/).filter(Boolean);
    const groups = new Map();
    for (const person of people) {
      const label = person.group_name || 'Без группы';
      const searchable = normalize([person.name, person.position, label].join(' '));
      if (!terms.every(term => searchable.includes(term))) continue;
      if (!groups.has(person.group_id)) groups.set(person.group_id, {label, people: []});
      groups.get(person.group_id).people.push(person);
    }
    notice.textContent = groups.size ? '' : people.length ? 'Никого не нашли.' : 'Список коллег пока пуст.';
    const sorted = [...groups.entries()].sort(([a, left], [b, right]) =>
      Number(a == null) - Number(b == null) || collator.compare(left.label, right.label));
    for (const [, group] of sorted) {
      const block = make('div', '');
      block.className = 'directory-group';
      const list = make('ul', '');
      for (const person of group.people) {
        const row = make('li', '');
        const info = make('div', '');
        info.className = 'directory-person';
        const image = make('img', '');
        image.className = 'directory-avatar'; image.src = '/static/favicon.png'; image.alt = '';
        const title = make('div', person.name);
        if (person.position) title.append(make('small', person.position));
        info.append(image, title); row.append(info);
        const link = chatLink(person.username, '');
        if (link) {
          link.className = 'directory-chat';
          link.setAttribute('aria-label', `Открыть чат: ${person.name}`);
          link.title = 'Открыть чат в Telegram';
          const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          const path = document.createElementNS(svg.namespaceURI, 'path');
          svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('aria-hidden', 'true');
          path.setAttribute('d', 'm22 2-7 20-4-9-9-4 20-7ZM22 2 11 13');
          svg.append(path); link.append(svg); row.append(link);
        }
        list.append(row);
      }
      block.append(make('h3', group.label), list); root.append(block);
    }
  }
  async function load() {
    if (people || loading) return;
    loading = true;
    retry.hidden = true;
    notice.textContent = 'Загрузка…';
    try {
      people = await (await request('colleagues')).json();
      people.sort((a, b) => collator.compare(a.name, b.name));
      render();
    } catch (error) {
      notice.textContent = error.message;
      people = null;
      retry.hidden = false;
    } finally { loading = false; }
  }
  retry.onclick = load;
  field.oninput = render;
  return load;
}

function tabs() {
  const navigation = byId('navigation');
  const buttons = Array.from(navigation.querySelectorAll('button'));
  const sections = Array.from(byId('content').querySelectorAll('section'));
  const loadColleagues = setupColleagues();
  let current = 0;
  buttons.forEach((button, index) => {button.onclick = () => {
    const direction = Math.sign(index - current);current = index;
    sections.forEach((section, i) => {section.hidden = (i < 2 ? 0 : i - 1) !== index;});
    buttons.forEach((item, i) => item.setAttribute('aria-selected', String(i === index)));
    byId('marker').style.transform = `translateX(${index * 100}%)`;
    if (!byId('colleagues').hidden) void loadColleagues();
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
    fields('profile', [['Рабочая почта', data.email], ['Рабочие часы', data.hours], ['День рождения', data.birthday], ['Первый рабочий день', data.first_workday?.split('-').reverse().join('.')]]);
    fields('team', [['Руководитель', data.manager], ['Наставник по адаптации', data.adaptation_mentor], ['Наставник по ИПР', data.development_mentor]]);
    showDevelopment(data.development, data.files);
    if (data.vacation) {
      byId('vacation-year').textContent = data.vacation.year;
      for (const [id, days] of [['vacation-used', data.vacation.used_days], ['vacation-remaining', data.vacation.remaining_days]]) {
        byId(id).textContent = days == null ? 'Не указано' : new Intl.NumberFormat('ru', {style:'unit', unit:'day'}).format(days);
      }
    }
    tabs();
    setupVacation();
    if (data.files.length) data.files.forEach(file => byId('files').append(fileRow(file)));
    else byId('files').append(make('li', 'Файлов пока нет'));
    byId('content').hidden = false;
    status.textContent = '';
  } catch (error) {
    status.textContent = error.message;
  }
}

start();
