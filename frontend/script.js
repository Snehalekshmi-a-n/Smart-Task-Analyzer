const API_BASE = 'http://127.0.0.1:8000';
const state = {
  tasks: [],
  isLoading: false,
};

const form = document.querySelector('#task-form');
const tableBody = document.querySelector('#task-table tbody');
const noTasksRow = document.querySelector('#no-tasks');
const analyzeBtn = document.querySelector('#analyze-btn');
const statusEl = document.querySelector('#status');
const resultsEl = document.querySelector('#results');
const strategySelect = document.querySelector('#strategy');
const analysisMeta = document.querySelector('#analysis-meta');

document.querySelector('#clear-tasks').addEventListener('click', () => {
  state.tasks = [];
  renderTasks();
});

document.querySelector('#load-json').addEventListener('click', () => {
  const raw = document.querySelector('#json-input').value.trim();
  if (!raw) return;

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      throw new Error('JSON must be an array of tasks.');
    }
    state.tasks = parsed.map((task, index) => ({
      id: index + 1,
      title: task.title || `Task ${index + 1}`,
      due_date: task.due_date || '',
      estimated_hours: Number(task.estimated_hours) || 2,
      importance: Number(task.importance) || 5,
      dependencies: task.dependencies || [],
    }));
    renderTasks();
  } catch (error) {
    alert(`Invalid JSON: ${error.message}`);
  }
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  const task = {
    id: state.tasks.length + 1,
    title: formData.get('title').trim(),
    due_date: formData.get('due_date') || null,
    estimated_hours: Number(formData.get('estimated_hours') || 0),
    importance: Number(formData.get('importance') || 0),
    dependencies: [],
  };

  if (!task.title) {
    return alert('Title is required.');
  }

  state.tasks.push(task);
  form.reset();
  renderTasks();
});

tableBody.addEventListener('click', (event) => {
  if (!event.target.matches('[data-delete]')) return;
  const id = Number(event.target.dataset.delete);
  state.tasks = state.tasks.filter((task) => task.id !== id);

  state.tasks = state.tasks.map((task, index) => ({
    ...task,
    id: index + 1,
    dependencies: task.dependencies
      .map((dep) => (dep === id ? null : dep))
      .filter((dep) => dep !== null && dep <= state.tasks.length),
  }));

  renderTasks();
});

tableBody.addEventListener('input', (event) => {
  if (!event.target.matches('[data-deps]')) return;
  const id = Number(event.target.dataset.deps);
  const task = state.tasks.find((t) => t.id === id);
  if (!task) return;
  task.dependencies = parseDependencies(event.target.value).filter(
    (dep) => dep !== id && dep <= state.tasks.length
  );
});

analyzeBtn.addEventListener('click', async () => {
  if (!state.tasks.length) {
    return setStatus('Add at least one task before analyzing.', 'error');
  }

  setLoading(true);
  setStatus('Analyzing tasks...', undefined);
  try {
    const payload = {
      strategy: strategySelect.value,
      tasks: state.tasks,
    };

    const response = await fetch(`${API_BASE}/api/tasks/analyze/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || 'Server returned an error. Please try again.'
      );
    }

    const data = await response.json();
    setStatus('Analysis complete.', 'success');
    renderResults(data);
  } catch (error) {
    console.error(error);
    setStatus(error.message, 'error');
    resultsEl.innerHTML = '';
  } finally {
    setLoading(false);
  }
});

function parseDependencies(value) {
  if (!value) return [];
  return value
    .split(',')
    .map((id) => Number(id.trim()))
    .filter((id) => Number.isInteger(id) && id > 0);
}

function renderTasks() {
  tableBody.innerHTML = '';
  state.tasks.forEach((task) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${task.id}</td>
      <td>${task.title}</td>
      <td>${task.due_date || '—'}</td>
      <td>${task.estimated_hours}</td>
      <td>${task.importance}</td>
      <td>
        <input
          type="text"
          class="deps-input"
          data-deps="${task.id}"
          placeholder="e.g. 1,3"
          value="${task.dependencies.join(', ')}"
        />
      </td>
      <td>
        <button class="btn btn-secondary" data-delete="${task.id}">
          Remove
        </button>
      </td>
    `;
    tableBody.appendChild(row);
  });

  noTasksRow.style.display = state.tasks.length ? 'none' : 'block';
}

function renderResults(data) {
  analysisMeta.textContent = `${data.strategy} • ${new Date(
    data.generated_at
  ).toLocaleString()}`;

  resultsEl.innerHTML = '';
  data.tasks.forEach((task) => {
    const badgeInfo = getBadge(task.score / 100);
    const card = document.createElement('article');
    card.className = 'result-card';
    card.innerHTML = `
      <div class="card-header">
        <h3>${task.title}</h3>
        <span class="badge ${badgeInfo.class}">${badgeInfo.label}</span>
      </div>
      <p class="score">${task.score.toFixed(2)} pts</p>
      <p>${task.explanation}</p>
      <ul class="task-meta">
        <li><strong>Due:</strong> ${task.due_date || '—'}</li>
        <li><strong>Hours:</strong> ${task.estimated_hours}</li>
        <li><strong>Importance:</strong> ${task.importance}/10</li>
        <li><strong>Dependencies:</strong> ${task.dependencies.join(', ') || '—'}</li>
      </ul>
      ${
        task.cycle_issue
          ? '<p class="cycle-issue">⚠ Part of a dependency cycle</p>'
          : ''
      }
    `;
    resultsEl.appendChild(card);
  });
}

function getBadge(score) {
  if (score >= 0.75) return { class: 'high', label: 'High Priority' };
  if (score >= 0.5) return { class: 'medium', label: 'Medium Priority' };
  return { class: 'low', label: 'Low Priority' };
}

function setStatus(message, type) {
  statusEl.textContent = message || '';
  statusEl.className = type ? type : '';
}

function setLoading(isLoading) {
  state.isLoading = isLoading;
  analyzeBtn.disabled = isLoading;
  analyzeBtn.textContent = isLoading ? 'Analyzing…' : 'Analyze Tasks';
}

renderTasks();

