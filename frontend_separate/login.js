const API_BASE = 'https://your-backend-api.herokuapp.com'  // Update with actual backend URL

const f = document.getElementById('f')
const msg = document.getElementById('msg')
f.addEventListener('submit', async (e) => {
  e.preventDefault()
  msg.textContent = ''
  const email = document.getElementById('email').value
  const password = document.getElementById('password').value
  const r = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email, password})
  })
  if (r.ok) {
    const data = await r.json()
    localStorage.setItem('token', data.token)
    location.href = '/leads.html'
  } else {
    msg.textContent = 'Invalid email or password'
  }
})
