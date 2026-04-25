// ── Session ID ───────────────────────────────────────────────────────────────
let sessionId = localStorage.getItem('pointy_session_id');
if (!sessionId) {
  sessionId = crypto.randomUUID();
  localStorage.setItem('pointy_session_id', sessionId);
}

// ── Карта ────────────────────────────────────────────────────────────────────
const map = L.map('map').setView([55.7558, 37.6173], 12);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors',
  maxZoom: 19,
}).addTo(map);

// Состояние метки
let userPin = null;       // L.Marker — метка пользователя
let radiusCircle = null;  // L.Circle — круг вокруг метки
let pinLat = null;
let pinLon = null;
let radiusKm = 0.25;
let pinMode = false;      // ждём клика для постановки метки

// Маркеры результатов
let resultMarkers = [];

// ── Иконка метки пользователя — синий акцент из палитры ──────────────────
const pinIcon = L.divIcon({
  html: `<div style="
    width:26px;height:26px;border-radius:50% 50% 50% 0;
    background:#4175c4;border:3px solid #fff;
    transform:rotate(-45deg);
    box-shadow:0 3px 10px rgba(65,117,196,0.55)">
  </div>`,
  className: '',
  iconSize: [26, 26],
  iconAnchor: [13, 26],
  popupAnchor: [0, -28],
});

// ── Управление меткой ─────────────────────────────────────────────────────
const pinBtn      = document.getElementById('pin-btn');
const pinLabel    = document.getElementById('pin-label');
const radiusGroup = document.getElementById('radius-group');
const clearPinBtn = document.getElementById('clear-pin');

function setPin(lat, lon) {
  pinLat = lat;
  pinLon = lon;

  if (userPin) map.removeLayer(userPin);
  if (radiusCircle) map.removeLayer(radiusCircle);

  userPin = L.marker([lat, lon], { icon: pinIcon, zIndexOffset: 1000 })
    .bindPopup('<b>Точка поиска</b><br>Нажми на карту чтобы переместить')
    .addTo(map);

  drawCircle();
  radiusGroup.classList.add('visible');
  pinLabel.textContent = 'Переместить метку';
  pinBtn.classList.add('active');
}

function drawCircle() {
  if (radiusCircle) map.removeLayer(radiusCircle);
  if (pinLat === null) return;
  radiusCircle = L.circle([pinLat, pinLon], {
    radius: radiusKm * 1000,
    color: '#6c63ff',
    fillColor: '#6c63ff',
    fillOpacity: 0.08,
    weight: 1.5,
    dashArray: '6 4',
  }).addTo(map);
}

function clearPin() {
  if (userPin) { map.removeLayer(userPin); userPin = null; }
  if (radiusCircle) { map.removeLayer(radiusCircle); radiusCircle = null; }
  pinLat = null;
  pinLon = null;
  pinMode = false;
  radiusGroup.classList.remove('visible');
  pinLabel.textContent = 'Поставить метку';
  pinBtn.classList.remove('active', 'waiting');
  map.getContainer().style.cursor = '';
}

// Кнопка "Поставить метку" — включает режим ожидания клика
pinBtn.addEventListener('click', () => {
  pinMode = !pinMode;
  if (pinMode) {
    pinBtn.classList.add('waiting');
    pinLabel.textContent = 'Кликни на карту…';
    map.getContainer().style.cursor = 'crosshair';
  } else {
    pinBtn.classList.remove('waiting');
    pinLabel.textContent = pinLat !== null ? 'Переместить метку' : 'Поставить метку';
    map.getContainer().style.cursor = '';
  }
});

// Клик на карту — ставит метку если режим активен
map.on('click', (e) => {
  if (!pinMode) return;
  pinMode = false;
  pinBtn.classList.remove('waiting');
  map.getContainer().style.cursor = '';
  setPin(e.latlng.lat, e.latlng.lng);
});

// Кнопки радиуса
document.querySelectorAll('.radius-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.radius-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    radiusKm = parseFloat(btn.dataset.km);
    drawCircle();
  });
});

// Убрать метку
clearPinBtn.addEventListener('click', clearPin);

// ── Маркеры результатов ───────────────────────────────────────────────────
const markerIcon = L.divIcon({
  className: '',
  html: `<div style="
    width:14px;height:14px;
    background:#7c3aed;
    border:2px solid white;
    border-radius:50%;
    box-shadow:0 2px 4px rgba(0,0,0,0.3)
  "></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
  popupAnchor: [0, -10],
});

function clearResultMarkers() {
  resultMarkers.forEach(m => map.removeLayer(m));
  resultMarkers = [];
}

function createPopupContent(place) {
  const statusHtml = place.is_open
    ? '<span style="color:#22c55e;font-weight:500">Открыто</span>'
    : '<span style="color:#ef4444;font-weight:500">Закрыто</span>';

  const hoursHtml = place.hours
    ? `<div style="font-size:12px;color:#666;margin-top:2px">${place.hours}</div>`
    : '';

  const cleanReason = (place.reason || '')
    .replace(/тип запроса:\s*\w+,?\s*/g, '')
    .replace(/минусы:.*$/s, '')
    .replace(/\[fallback\]\s*/g, '')
    .trim()
    .replace(/,\s*$/, '');

  const reasonHtml = cleanReason
    ? `<div style="font-size:12px;color:#444;margin-top:6px;line-height:1.4">${cleanReason}</div>`
    : '';

  const linkHtml = place.maps_url
    ? `<a href="${place.maps_url}" target="_blank"
         style="display:inline-block;margin-top:8px;background:#2d5be3;
                color:white;padding:4px 12px;border-radius:6px;
                font-size:12px;text-decoration:none">
         Открыть в 2GIS →
       </a>`
    : '';

  return `
    <div style="font-family:Inter,sans-serif;min-width:200px;padding:4px">
      <div style="font-weight:600;font-size:14px;margin-bottom:4px">${place.name}</div>
      <div style="font-size:12px;color:#666;margin-bottom:4px">${place.address}</div>
      ${statusHtml}
      ${hoursHtml}
      ${reasonHtml}
      ${linkHtml}
    </div>
  `;
}

function renderPlaces(places) {
  clearResultMarkers();
  if (!places.length) return;

  const bounds = [];

  places.forEach(p => {
    const marker = L.marker([p.lat, p.lon], { icon: markerIcon })
      .bindPopup(L.popup({ maxWidth: 280 }).setContent(createPopupContent(p)));

    marker.addTo(map);
    resultMarkers.push(marker);
    bounds.push([p.lat, p.lon]);
  });

  // Включаем в bounds и метку пользователя
  if (pinLat !== null) bounds.push([pinLat, pinLon]);

  if (bounds.length) {
    map.flyToBounds(bounds, { padding: [60, 60], maxZoom: 16, duration: 0.8 });
  }
}

// ── Чат ──────────────────────────────────────────────────────────────────────
const messagesEl = document.getElementById('messages');
const inputEl    = document.getElementById('input');
const sendBtn    = document.getElementById('send-btn');

function appendBubble(role, html) {
  const wrap = document.createElement('div');
  wrap.className = `bubble-wrap ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = html;
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showTyping() {
  const wrap = document.createElement('div');
  wrap.className = 'bubble-wrap agent';
  wrap.id = 'typing-indicator';
  wrap.innerHTML = `<div class="typing"><span></span><span></span><span></span></div>`;
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderMarkdown(text) {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank">$1</a>')
    .replace(/\n/g,'<br>');
}

function setLoading(on) {
  sendBtn.disabled = on;
  inputEl.disabled = on;
}

async function sendQuery(query) {
  if (!query.trim()) return;

  // Покажем пользователю что ищем — с контекстом метки
  let contextNote = '';
  if (pinLat !== null) {
    const labels = { 0.25: '250 м', 1: '1 км', 50: 'вся Москва' };
    contextNote = ` <span style="opacity:.6;font-size:12px">[метка, радиус ${labels[radiusKm] || radiusKm + ' км'}]</span>`;
  }

  appendBubble('user', escapeHtml(query) + contextNote);
  addToHistory(query);
  inputEl.value = '';
  setLoading(true);
  showTyping();

  try {
    const body = { query, radius_km: radiusKm };
    if (pinLat !== null) { body.lat = pinLat; body.lon = pinLon; }

    const res = await fetch('/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': sessionId,
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    hideTyping();
    appendBubble('agent', renderMarkdown(data.message));
    renderPlaces(data.places || []);
    saveToLocalHistory(query);
  } catch (err) {
    hideTyping();
    appendBubble('agent', `<span style="color:#f44336">Ошибка: ${err.message}</span>`);
  } finally {
    setLoading(false);
    inputEl.focus();
  }
}

sendBtn.addEventListener('click', () => sendQuery(inputEl.value));
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) sendQuery(inputEl.value);
});

document.querySelectorAll('.example-btn').forEach(btn => {
  btn.addEventListener('click', () => sendQuery(btn.dataset.query));
});

// ── Бургер / История поиска ───────────────────────────────────────────────
const burgerBtn     = document.getElementById('burger-btn');
const historyDrawer = document.getElementById('history-drawer');
const historyClose  = document.getElementById('history-close');
const historyList   = document.getElementById('history-list');

const searchHistory = [];

burgerBtn.addEventListener('click', () => {
  const isOpen = historyDrawer.classList.toggle('open');
  burgerBtn.classList.toggle('active', isOpen);
});

historyClose.addEventListener('click', () => {
  historyDrawer.classList.remove('open');
  burgerBtn.classList.remove('active');
});

// ── История (localStorage → drawer) ──────────────────────────────────────
function addToHistory(query) {
  const history = JSON.parse(localStorage.getItem('search_history') || '[]');
  if (history.length && history[0].query === query) return;
  history.unshift({ query, timestamp: new Date().toLocaleString('ru-RU') });
  history.splice(20);
  localStorage.setItem('search_history', JSON.stringify(history));
  renderDrawerHistory();
}

function saveToLocalHistory(query) {
  addToHistory(query);
}

function renderDrawerHistory() {
  const history = JSON.parse(localStorage.getItem('search_history') || '[]');

  const empty = historyList.querySelector('.history-empty');
  if (history.length && empty) empty.remove();
  if (!history.length) {
    historyList.innerHTML = '<div class="history-empty">Пока пусто</div>';
    return;
  }

  historyList.innerHTML = history.map(h => `
    <div class="history-item" data-query="${escapeHtml(h.query)}">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      ${escapeHtml(h.query)}
    </div>
  `).join('');

  historyList.querySelectorAll('.history-item').forEach(el => {
    el.addEventListener('click', () => {
      historyDrawer.classList.remove('open');
      burgerBtn.classList.remove('active');
      sendQuery(el.dataset.query);
    });
  });
}

// ── Приветственное сообщение ──────────────────────────────────────────────
appendBubble('agent',
  'Привет! Я помогу найти подходящее место в Москве. ' +
  'Опиши что ищешь — для работы, поесть или что-то красивое. ' +
  'Например: <em>«тихое кафе для работы с ноутбуком»</em> ' +
  'или <em>«хочу поесть хинкали рядом с Арбатом»</em>.'
);

// Заполняем drawer историей из localStorage при загрузке
renderDrawerHistory();
