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
  let busy = false;
  const picker = byId('vacation-picker');
  const grid = byId('calendar-grid');
  const calendarStatus = byId('calendar-status');
  const start = form.elements.starts_on;
  const end = form.elements.ends_on;
  const buttons = [[byId('vacation-start'), start], [byId('vacation-end'), end]];
  const months = new Map();
  const monthFormat = new Intl.DateTimeFormat('ru', {month:'long', year:'numeric', timeZone:'UTC'});
  let month = new Date().toISOString().slice(0, 7);
  let selecting = start;
  let loadVersion = 0;

  function updateDates() {
    for (const [control, field] of buttons) {
      const label = field === start ? 'Начало' : 'Последний день';
      control.textContent = field.value ? `${label}: ${dateLabel(field.value)}` : label;
      control.setAttribute('aria-expanded', String(!picker.hidden && selecting === field));
    }
    button.disabled = busy || !start.value || !end.value;
  }
  async function showMonth(nextMonth) {
    month = nextMonth;
    const version = ++loadVersion;
    const first = new Date(`${month}-01T00:00:00Z`);
    byId('calendar-month').textContent = monthFormat.format(first);
    grid.replaceChildren();
    calendarStatus.textContent = 'Загрузка календаря…';
    try {
      if (!months.has(month)) {
        const loaded = await (await request(`vacation/calendar?month=${encodeURIComponent(nextMonth)}`)).json();
        months.set(nextMonth, loaded);
      }
      if (version !== loadVersion) return;
      const data = months.get(nextMonth);
      for (const name of ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']) grid.append(make('small', name));
      for (let i = 0; i < (first.getUTCDay() + 6) % 7; i++) grid.append(make('span', ''));
      for (const day of data.days) {
        const cell = make('button', String(Number(day.date.slice(-2))));
        cell.type = 'button';
        cell.disabled = day.date < data.today || (selecting === end && !!start.value && day.date < start.value);
        cell.classList.toggle('is-off', !day.workday);
        cell.classList.toggle('is-range', !!end.value && day.date > start.value && day.date < end.value);
        cell.setAttribute('aria-pressed', String(day.date === start.value || day.date === end.value));
        cell.setAttribute('aria-label', `${dateLabel(day.date)}, ${day.workday ? 'рабочий день' : 'нерабочий день'}`);
        cell.onclick = () => {
          selecting.value = day.date;
          if (start.value && end.value && start.value > end.value) end.value = '';
          if (selecting === start && !end.value) {
            selecting = end;
            void showMonth(month);
          } else {
            picker.hidden = true;
            buttons.find(([, field]) => field === selecting)[0].focus();
          }
          checked = null;
          notice.textContent = '';
          button.textContent = 'Проверить даты';
          updateDates();
        };
        grid.append(cell);
      }
      calendarStatus.textContent = 'Серый фон — нерабочий день';
    } catch (error) {
      if (version === loadVersion) calendarStatus.textContent = error.message;
    }
  }
  for (const [control, field] of buttons) control.onclick = () => {
    const wasOpen = !picker.hidden && selecting === field;
    selecting = field;
    picker.hidden = wasOpen;
    if (!wasOpen) void showMonth((field.value || start.value).slice(0, 7) || month);
    updateDates();
  };
  for (const [id, delta] of [['month-prev', -1], ['month-next', 1]]) byId(id).onclick = () => {
    const target = new Date(`${month}-01T00:00:00Z`);
    target.setUTCMonth(target.getUTCMonth() + delta);
    const next = target.toISOString().slice(0, 7);
    if (/^\d{4}-\d{2}$/.test(next)) void showMonth(next);
  };
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
  updateDates();
  form.onsubmit = async event => {
    event.preventDefault();
    if (busy || !start.value || !end.value) return;
    const period = Object.fromEntries(new FormData(form));
    const key = JSON.stringify(period);
    busy = true;
    picker.hidden = true;
    buttons.forEach(([control]) => { control.disabled = true; });
    updateDates();
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
      busy = false;
      buttons.forEach(([control]) => { control.disabled = false; });
      updateDates();
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
  const stages = [];
  if (data.current) stages.push(['Текущий этап', describe(data.current)]);
  if (data.upcoming) stages.push(['Следующий этап', describe(data.upcoming)]);
  if (stages.length) fields(plan.id, stages);
  else plan.remove();
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

async function loadKnowledge() {
  const notice = byId('knowledge-status');
  const root = byId('knowledge-items');
  root.replaceChildren();
  notice.textContent = 'Загрузка…';
  function render(items, target) {
    const list = make('ul', '');
    for (const item of items) {
      const row = make('li', '');
      if (item.children) {
        const [section, body] = disclosure(item.label);
        render(item.children, body);
        row.append(section);
      } else {
        const url = new URL(item.url);
        if (!['http:', 'https:'].includes(url.protocol)) continue;
        const link = make('a', item.label);
        link.href = url.href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        row.append(link);
      }
      list.append(row);
    }
    target.append(list);
  }
  try {
    const items = await (await request('knowledge')).json();
    render(items, root);
    notice.textContent = items.length ? '' : 'Материалов пока нет.';
  } catch (error) {
    notice.textContent = error.message;
  }
}

function tabs() {
  const navigation = byId('navigation');
  const buttons = Array.from(navigation.querySelectorAll('button'));
  const sections = Array.from(byId('content').querySelectorAll('section'));
  const loadColleagues = setupColleagues();
  let transition;
  let current = 0;
  buttons.forEach((button, index) => {button.onclick = () => {
    const direction = Math.sign(index - current);
    current = index;
    const view = button.dataset.view;
    sections.forEach(section => {section.hidden = section.dataset.view !== view;});
    byId('name').closest('header').hidden = view !== 'profile';
    buttons.forEach(item => {
      if (item === button) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
    });
    byId('marker').style.transform = `translateX(${index * 100}%)`;
    if (view === 'colleagues') void loadColleagues();
    if (view === 'knowledge') void loadKnowledge();
    if (direction && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      transition?.cancel();
      transition = byId('content').animate(
        [{opacity:.7, transform:`translateX(${8 * direction}px)`},{opacity:1, transform:'translateX(0)'}],
        {duration:200, easing:'cubic-bezier(.2,.75,.3,1)'});
    }
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
    fields('profile', [['Рабочая почта', data.email], ['Рабочие часы', data.hours], ['День рождения', data.birthday]]);
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
