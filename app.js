const agentSelect = document.getElementById('agent-select');
const inputText   = document.getElementById('input-text');
const startBtn    = document.getElementById('start-btn');
const outputGroup = document.getElementById('output-group');
const outputBox   = document.getElementById('output-text');

async function loadAgents() {
  try {
    const res  = await fetch('/agents');
    const data = await res.json();

    agentSelect.innerHTML = '';

    if (!data.agents || data.agents.length === 0) {
      agentSelect.innerHTML = '<option value="" disabled selected>No agents found</option>';
      return;
    }

    const placeholder = document.createElement('option');
    placeholder.value    = '';
    placeholder.disabled = true;
    placeholder.selected = true;
    placeholder.textContent = 'Select an agent…';
    agentSelect.appendChild(placeholder);

    data.agents.forEach(name => {
      const opt = document.createElement('option');
      opt.value       = name;
      opt.textContent = name;
      agentSelect.appendChild(opt);
    });

    agentSelect.addEventListener('change', () => {
      startBtn.disabled = agentSelect.value === '';
    });
  } catch (err) {
    agentSelect.innerHTML = '<option value="" disabled selected>Failed to load agents</option>';
    console.error(err);
  }
}

function setRunning(running) {
  if (running) {
    startBtn.disabled   = true;
    startBtn.classList.add('running');
    startBtn.innerHTML  = '<span class="spinner"></span>Running…';
  } else {
    startBtn.disabled   = false;
    startBtn.classList.remove('running');
    startBtn.textContent = 'Start';
  }
}

function showOutput(text, isError = false) {
  outputGroup.style.display = 'flex';
  outputBox.classList.toggle('error', isError);
  outputBox.textContent = text;
  outputBox.scrollTop   = outputBox.scrollHeight;
}

function appendOutput(text) {
  outputBox.textContent += text;
  outputBox.scrollTop    = outputBox.scrollHeight;
}

startBtn.addEventListener('click', async () => {
  const agent = agentSelect.value;
  const input = inputText.value.trim();

  if (!agent) return;

  setRunning(true);
  outputGroup.style.display = 'flex';
  outputBox.classList.remove('error');
  outputBox.textContent = '';

  try {
    const res = await fetch('/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent, input }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      showOutput(`Error: ${err.detail || res.statusText}`, true);
      setRunning(false);
      return;
    }

    // Stream the response line by line
    const reader  = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      appendOutput(decoder.decode(value, { stream: true }));
    }
  } catch (err) {
    showOutput(`Network error: ${err.message}`, true);
  } finally {
    setRunning(false);
  }
});

loadAgents();
