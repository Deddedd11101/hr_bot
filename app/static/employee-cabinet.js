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

async function request(path, data, signal) {
  const response = await fetch(`/employee-cabinet/${path}`, {
    headers: {'X-Telegram-Init-Data': tg.initData, ...(data ? {'Content-Type': 'application/json'} : {})},
    ...(data ? {method: 'POST', body: JSON.stringify(data)} : {}), credentials: 'omit', cache: 'no-store', signal,
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
  const pendingMonths = new Map();
  const monthFormat = new Intl.DateTimeFormat('ru', {month:'long', year:'numeric', timeZone:'UTC'});
  let month = new Date().toISOString().slice(0, 7);
  let selecting = start;
  let loadVersion = 0;
  let displayedMonth;

  function shiftMonth(value, delta) {
    const target = new Date(`${value}-01T00:00:00Z`);
    target.setUTCMonth(target.getUTCMonth() + delta);
    const next = target.toISOString().slice(0, 7);
    return /^\d{4}-\d{2}$/.test(next) ? next : null;
  }
  function fetchMonth(value) {
    if (!pendingMonths.has(value)) {
      const load = request(`vacation/calendar?month=${encodeURIComponent(value)}`)
        .then(response => response.json())
        .then(data => { months.set(value, data); return data; })
        .finally(() => pendingMonths.delete(value));
      pendingMonths.set(value, load);
    }
    return pendingMonths.get(value);
  }

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
    if (!months.has(nextMonth)) {
      grid.inert = true;
      grid.setAttribute('aria-busy', 'true');
      calendarStatus.textContent = 'Загрузка календаря…';
      if (!displayedMonth) byId('calendar-month').textContent = monthFormat.format(first);
    }
    try {
      const data = months.get(nextMonth) || await fetchMonth(nextMonth);
      if (version !== loadVersion) return;
      byId('calendar-month').textContent = monthFormat.format(first);
      grid.replaceChildren();
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
      if (displayedMonth !== nextMonth && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
        grid.animate([{opacity:.55},{opacity:1}], {duration:150});
      }
      displayedMonth = nextMonth;
      for (const delta of [-1, 1]) {
        const adjacent = shiftMonth(nextMonth, delta);
        if (adjacent && !months.has(adjacent)) void fetchMonth(adjacent).catch(() => {});
      }
    } catch (error) {
      if (version === loadVersion) {
        displayedMonth = null;
        byId('calendar-month').textContent = monthFormat.format(first);
        grid.replaceChildren();
        calendarStatus.textContent = error.message;
      }
    } finally {
      if (version === loadVersion) {
        grid.inert = false;
        grid.removeAttribute('aria-busy');
      }
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
    const next = shiftMonth(month, delta);
    if (next) void showMonth(next);
  };
  async function refresh() {
    const rows = await (await request('vacation/requests')).json();
    list.replaceChildren(...rows.map(row => {
      const item = make('li', '');
      const dates = make('span', `${dateLabel(row.starts_on)} – ${dateLabel(row.ends_on)}`);
      dates.className = 'vacation-period';
      const badge = make('small', {pending:'У руководителя', pending_hr:'У HR', approved:'Согласована', rejected:'Отклонена'}[row.status] || row.status);
      badge.className = 'vacation-badge';
      badge.dataset.status = row.status;
      item.append(dates, badge);
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
  const avatarLoads = new Map();
  async function showAvatar(image) {
    const id = image.dataset.avatarId;
    if (!avatarLoads.has(id)) {
      avatarLoads.set(id, request(`colleagues/${id}/avatar`).then(response => response.blob()).catch(() => null));
    }
    const blob = await avatarLoads.get(id);
    if (!blob || !image.isConnected) return;
    const url = URL.createObjectURL(blob);
    image.onload = () => {
      URL.revokeObjectURL(url);
      image.classList.add('has-avatar');
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      image.onerror = image.onload = null;
      image.src = '/static/favicon.png';
    };
    image.src = url;
  }
  const avatars = typeof IntersectionObserver === 'function' ? new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      avatars.unobserve(entry.target);
      void showAvatar(entry.target);
    }
  }) : null;
  function render() {
    if (!people) return;
    avatars?.disconnect();
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
        if (avatars && Number.isSafeInteger(person.avatar_id) && person.avatar_id > 0) {
          image.dataset.avatarId = String(person.avatar_id);
          avatars.observe(image);
        }
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
  function showView(view, index) {
    const direction = Math.sign(index - current);
    current = index;
    sections.forEach(section => {section.hidden = section.dataset.view !== view;});
    byId('name').closest('header').hidden = view !== 'profile';
    buttons.forEach((item, i) => {
      if (i === index) item.setAttribute('aria-current', view === 'files' ? 'location' : 'page');
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
  }
  buttons.forEach((button, index) => { button.onclick = () => showView(button.dataset.view, index); });
  byId('documents-open').onclick = () => {
    showView('files', 0);
    byId('documents').querySelector('h2').focus();
  };
  document.querySelectorAll('[data-back-profile]').forEach(crumb => {
    crumb.onclick = () => {
      const fromDocuments = crumb.closest('section').id === 'documents';
      showView('profile', 0);
      (fromDocuments ? byId('documents-open') : buttons[0]).focus();
    };
  });
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

function playCabinetLogo() {
  const mark = byId('cabinet-loader').querySelector('.cabinet-loader-mark');
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
    mark.classList.add('is-ready');
    return;
  }
  const pointCount = 80;
  const shapes = [...mark.querySelectorAll('path')].map(path => {
    const original = path.getAttribute('d');
    const length = path.getTotalLength();
    const target = Array.from({length:pointCount}, (_, i) => path.getPointAtLength(length * i / pointCount));
    const box = path.getBBox();
    const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
    const area = target.reduce((sum, point, i) => {
      const next = target[(i + 1) % pointCount];
      return sum + point.x * next.y - next.x * point.y;
    }, 0);
    const angle = Math.atan2(target[0].y - cy, target[0].x - cx);
    const points = target.map((point, i) => {
      const theta = angle + Math.sign(area || 1) * 2 * Math.PI * i / pointCount;
      const x = cx + Math.cos(theta) * 4.8, y = cy + Math.sin(theta) * 4.8;
      return [x, y, point.x - x, point.y - y];
    });
    return {path, original, points};
  });
  const paint = (shape, morph) => {
    const outline = shape.points.map(([x, y, dx, dy], i) =>
      `${i ? 'L' : 'M'}${(x + dx * morph).toFixed(2)} ${(y + dy * morph).toFixed(2)}`).join('');
    shape.path.setAttribute('d', outline + 'Z');
  };
  shapes.forEach(shape => paint(shape, 0));
  mark.classList.add('is-ready');
  return new Promise(resolve => {
    const start = performance.now();
    let frame;
    const finish = () => {
      clearTimeout(fallback);
      cancelAnimationFrame(frame);
      shapes.forEach(shape => shape.path.setAttribute('d', shape.original));
      resolve();
    };
    const fallback = setTimeout(finish, 1200);
    function tick(now) {
      const elapsed = now - start;
      shapes.forEach((shape, i) => {
        const t = Math.min(1, Math.max(0, (elapsed - 150 - i * 95) / 590));
        paint(shape, .93 * (1 - (1 - t) ** 3));
      });
      if (elapsed < 1030) frame = requestAnimationFrame(tick);
      else finish();
    }
    frame = requestAnimationFrame(tick);
  });
}

function setupDesktopFullscreen() {
  if (!['tdesktop', 'macos', 'unigram'].includes(tg.platform)) return;
  document.documentElement.classList.add('cabinet-desktop');
  if (!tg.isVersionAtLeast?.('8.0')
      || typeof tg.requestFullscreen !== 'function' || typeof tg.exitFullscreen !== 'function') return;
  const button = byId('fullscreen-toggle');
  const preferenceKey = 'hrbot:cabinet:desktop-fullscreen';
  let rememberWindowed = false;
  try { rememberWindowed = localStorage.getItem(preferenceKey) === 'windowed'; } catch {}
  let fullscreenBefore = !!tg.isFullscreen;
  let manualRequest = false;
  let settleAutomatic = () => {};
  const sync = () => {
    const fullscreen = !!tg.isFullscreen;
    document.documentElement.classList.toggle('cabinet-fullscreen', fullscreen);
    button.textContent = fullscreen ? 'Выйти из полноэкранного режима' : 'На весь экран';
  };
  const failure = ({error} = {}) => {
    sync();
    settleAutomatic();
    if (error !== 'ALREADY_FULLSCREEN') {
      if (manualRequest) status.textContent = 'Этот клиент Telegram не смог переключить режим окна.';
      if (error === 'UNSUPPORTED') button.hidden = true;
    }
    manualRequest = false;
  };
  tg.onEvent?.('fullscreenChanged', () => {
    const fullscreen = !!tg.isFullscreen;
    if (fullscreen !== fullscreenBefore) {
      try { localStorage.setItem(preferenceKey, fullscreen ? 'fullscreen' : 'windowed'); } catch {}
      fullscreenBefore = fullscreen;
    }
    manualRequest = false;
    sync();
    settleAutomatic();
  });
  tg.onEvent?.('fullscreenFailed', failure);
  button.onclick = () => {
    status.textContent = '';
    manualRequest = true;
    try {
      if (tg.isFullscreen) tg.exitFullscreen();
      else tg.requestFullscreen();
    } catch {
      failure();
    }
  };
  sync();
  button.hidden = false;
  if (!rememberWindowed && !tg.isFullscreen) {
    return new Promise(resolve => {
      const timeout = setTimeout(resolve, 850);
      settleAutomatic = () => { clearTimeout(timeout); resolve(); };
      try { tg.requestFullscreen(); } catch { failure(); }
    });
  }
}

async function start() {
  if (tg?.isVersionAtLeast?.('6.9')) {
    tg.setHeaderColor?.('#BADA1E');
  }
  tg?.ready();
  if (!tg?.initData) {
    status.textContent = 'Открой кабинет из Telegram командой /cabinet.';
    byId('cabinet-loader').remove();
    return;
  }
  tg.expand();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const profile = request('profile', undefined, controller.signal).then(response => response.json()).finally(() => clearTimeout(timeout));
    const desktop = setupDesktopFullscreen();
    const animation = playCabinetLogo();
    const [data] = await Promise.all([profile, desktop, animation]);
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
    status.textContent = controller.signal.aborted ? 'Кабинет не ответил. Открой его снова через бота.' : error.message;
  } finally {
    const loader = byId('cabinet-loader');
    loader.setAttribute('aria-hidden', 'true');
    loader.classList.add('is-done');
    setTimeout(() => loader.remove(), 200);
  }
}

start();
