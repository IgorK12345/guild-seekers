let mode = 'register';
const $ = id => document.getElementById(id);
function setMode(value) {
  mode = value;
  $('register-tab').classList.toggle('active', value === 'register');
  $('login-tab').classList.toggle('active', value === 'login');
  $('hero-label').hidden = value === 'login';
  $('hero-name').required = value === 'register';
  $('password').autocomplete = value === 'login' ? 'current-password' : 'new-password';
  $('form-title').textContent = value === 'login' ? 'С возвращением, искатель' : 'Создайте своего героя';
  $('form-subtitle').textContent = value === 'login' ? 'Приключение продолжается.' : 'Первый меч уже ждёт вас.';
  $('submit-auth').textContent = value === 'login' ? 'Войти в гильдию →' : 'Начать приключение →';
  $('auth-error').textContent = '';
}
$('register-tab').onclick = () => setMode('register');
$('login-tab').onclick = () => setMode('login');
$('auth-form').onsubmit = async event => {
  event.preventDefault();
  const button = $('submit-auth'); button.disabled = true; $('auth-error').textContent = '';
  try {
    const body = {username: $('username').value.trim(), password: $('password').value};
    if (mode === 'register') body.name = $('hero-name').value.trim();
    const response = await fetch(`/api/auth/${mode}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Проверьте поля: логин от 3 символов, имя от 2, пароль от 8.');
    window.location.href = '/game';
  } catch (error) { $('auth-error').textContent = error.message === 'Failed to fetch' ? 'Нет связи с сервером. Проверьте, запущена ли игра.' : error.message; }
  finally { button.disabled = false; }
};
fetch('/api/character').then(r => { if (r.ok) location.replace('/game'); }).catch(() => {});
