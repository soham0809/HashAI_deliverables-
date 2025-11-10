const token = localStorage.getItem('token')
if (!token) location.href = '/login'

const tbody = document.querySelector('#t tbody')
const msg = document.getElementById('msg')
const logout = document.getElementById('logout')
const prevBtn = document.getElementById('prev')
const nextBtn = document.getElementById('next')
const pageLbl = document.getElementById('page')
let page = 1
let limit = 5
let pages = 1
let adding = false

logout.onclick = () => { localStorage.removeItem('token'); location.href = '/login' }

async function load() {
  tbody.innerHTML = ''
  const r = await fetch(`/api/leads?page=${page}&limit=${limit}`, { headers: { 'Authorization': 'Bearer ' + token } })
  if (!r.ok) { location.href = '/login'; return }
  const data = await r.json()
  pages = data.pages || 1
  pageLbl.textContent = `Page ${data.page} / ${pages}`
  prevBtn.disabled = data.page <= 1
  nextBtn.disabled = data.page >= pages
  data.leads.forEach(l => {
    const tr = document.createElement('tr')
    tr.setAttribute('data-id', l.id)
    tr.innerHTML = `<td class="px-3 py-2">${l.name}</td><td class="px-3 py-2">${l.email}</td><td class="px-3 py-2">${l.phone}</td><td class="px-3 py-2">${l.status}</td><td class="px-3 py-2"><button data-id="${l.id}" class="edit px-2 py-1 bg-yellow-500 text-white rounded">Edit</button> <button data-id="${l.id}" class="del px-2 py-1 bg-red-600 text-white rounded">Delete</button></td>`
    tbody.appendChild(tr)
  })
}

function toEdit(tr) {
  const id = tr.getAttribute('data-id')
  const tds = tr.querySelectorAll('td')
  const name = tds[0].textContent
  const email = tds[1].textContent
  const phone = tds[2].textContent
  const status = tds[3].textContent
  tds[0].innerHTML = `<input class="e-name border rounded px-2 py-1 w-full" value="${name}">`
  tds[1].innerHTML = `<input class="e-email border rounded px-2 py-1 w-full" type="email" value="${email}">`
  tds[2].innerHTML = `<input class="e-phone border rounded px-2 py-1 w-full" value="${phone}">`
  tds[3].innerHTML = `<select class="e-status border rounded px-2 py-1 w-full">\n    <option ${status==='New'?'selected':''}>New</option>\n    <option ${status==='In Progress'?'selected':''}>In Progress</option>\n    <option ${status==='Converted'?'selected':''}>Converted</option>\n  </select>`
  tds[4].innerHTML = `<button data-id="${id}" class="save px-2 py-1 bg-blue-600 text-white rounded">Save</button> <button data-id="${id}" class="cancel px-2 py-1 bg-gray-200 rounded">Cancel</button>`
}

tbody.addEventListener('click', async (e) => {
  if (e.target.classList.contains('del')) {
    const id = e.target.getAttribute('data-id')
    await fetch('/api/leads/' + id, { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + token } })
    load()
  }
  if (e.target.classList.contains('edit')) {
    const tr = e.target.closest('tr')
    toEdit(tr)
  }
  if (e.target.classList.contains('save')) {
    const tr = e.target.closest('tr')
    const id = e.target.getAttribute('data-id')
    const body = {
      name: tr.querySelector('.e-name').value,
      email: tr.querySelector('.e-email').value,
      phone: tr.querySelector('.e-phone').value,
      status: tr.querySelector('.e-status').value
    }
    await fetch('/api/leads/' + id, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token }, body: JSON.stringify(body) })
    load()
  }
  if (e.target.classList.contains('cancel')) {
    load()
  }
})

prevBtn.onclick = () => { if (page > 1) { page--; load() } }
nextBtn.onclick = () => { if (page < pages) { page++; load() } }

const form = document.getElementById('add')
form.addEventListener('submit', async (e) => {
  e.preventDefault()
  if (adding) return
  adding = true
  const btn = form.querySelector('button[type="submit"]')
  if (btn) btn.disabled = true
  msg.textContent = ''
  try {
    const body = {
      name: document.getElementById('name').value,
      email: document.getElementById('lemail').value,
      phone: document.getElementById('phone').value,
      status: document.getElementById('status').value
    }
    const r = await fetch('/api/leads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
      body: JSON.stringify(body)
    })
    if (r.ok) {
      form.reset()
      await load()
    } else {
      msg.textContent = 'Failed to add lead'
    }
  } finally {
    adding = false
    if (btn) btn.disabled = false
  }
})

load()
