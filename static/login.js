const f = document.getElementById('f')
const msg = document.getElementById('msg')
f.addEventListener('submit', async (e) => {
  e.preventDefault()
  msg.textContent = ''
  const email = document.getElementById('email').value
  const password = document.getElementById('password').value
  const r = await fetch('/api/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email, password})
  })
  if (r.ok) {
    const data = await r.json()
    localStorage.setItem('token', data.token)
    location.href = '/leads'
  } else {
    msg.textContent = 'Invalid email or password'
  }
})
