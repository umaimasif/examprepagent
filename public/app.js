// ---- AI Exam Prep Agent frontend ----
const $ = (id) => document.getElementById(id);
const STUDENT_ID = "default"; // single-user demo; wire to real auth later

let lectureId = null;
let currentQuiz = [];

async function api(path, body) {
  const res = await fetch("/api" + path, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

const esc = (s) =>
  String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

// ---------- Step 1: process ----------
$("process-btn").onclick = async () => {
  const url = $("url").value.trim();
  const subject = $("subject").value.trim();
  if (!url || !subject) {
    $("process-status").textContent = "Enter a URL and a subject.";
    return;
  }
  $("process-btn").disabled = true;
  $("process-status").textContent = "Extracting transcript and generating… (can take ~20-40s)";
  try {
    const data = await api("/process", {
      url,
      subject,
      syllabus: $("syllabus").value.trim() || null,
      student_id: STUDENT_ID,
    });
    lectureId = data.lecture_id;
    renderNotes(data.notes);
    renderQuestions(data.questions);
    $("notes-card").classList.remove("hidden");
    $("questions-card").classList.remove("hidden");
    $("tutor-card").classList.remove("hidden");
    $("quiz-card").classList.remove("hidden");
    $("process-status").textContent =
      `Done. ${data.transcript_chars} transcript chars, ${data.chunks_indexed} chunks indexed.`;
  } catch (e) {
    $("process-status").textContent = "Error: " + e.message;
  } finally {
    $("process-btn").disabled = false;
  }
};

// ---------- Step 2: notes ----------
function renderNotes(n) {
  let h = `<p>${esc(n.summary || "")}</p>`;
  if (n.topics?.length)
    h += `<div>${n.topics.map((t) => `<span class="pill">${esc(t)}</span>`).join("")}</div>`;
  h += section("Concise notes", (n.concise_notes || []).map(esc));
  h += section(
    "Key definitions",
    (n.key_definitions || []).map((d) => `<b>${esc(d.term)}</b>: ${esc(d.definition)}`)
  );
  h += section(
    "Formulas",
    (n.formulas || []).map((f) => `<b>${esc(f.name)}</b>: ${esc(f.formula)} — ${esc(f.meaning)}`)
  );
  h += section("Examples", (n.examples || []).map(esc));
  h += section("Memorize", (n.memorize || []).map(esc));
  $("notes").innerHTML = h;
}

function section(title, items) {
  if (!items.length) return "";
  return `<div class="qblock"><h3>${title}</h3><ol>${items
    .map((i) => `<li>${i}</li>`)
    .join("")}</ol></div>`;
}

// ---------- Step 3: questions ----------
function renderQuestions(q) {
  let h = "";
  h += qSection("Short answer", (q.short || []).map((x) => tag(x.topic) + esc(x.question)));
  h += qSection("Long answer", (q.long || []).map((x) => tag(x.topic) + esc(x.question)));
  h += qSection(
    "MCQs",
    (q.mcq || []).map(
      (x) =>
        tag(x.topic) +
        esc(x.question) +
        "<ul>" +
        (x.options || []).map((o) => `<li>${esc(o)}</li>`).join("") +
        `</ul><i>Answer: ${esc(x.answer)}</i>`
    )
  );
  h += qSection(
    "True / False",
    (q.true_false || []).map((x) => tag(x.topic) + esc(x.statement) + ` — <i>${esc(x.answer)}</i>`)
  );
  h += qSection("Scenario", (q.scenario || []).map((x) => tag(x.topic) + esc(x.question)));
  $("questions").innerHTML = h;
}

const tag = (t) => `<span class="topic-tag">[${esc(t || "General")}]</span> `;

function qSection(title, items) {
  if (!items.length) return "";
  return `<div class="qblock"><h3>${title}</h3><ol>${items
    .map((i) => `<li>${i}</li>`)
    .join("")}</ol></div>`;
}

// ---------- Step 4: tutor ----------
$("tutor-btn").onclick = async () => {
  const question = $("tutor-q").value.trim();
  if (!question || !lectureId) return;
  $("tutor-answer").innerHTML = "<div class='status'>Thinking…</div>";
  try {
    const data = await api("/tutor", { lecture_id: lectureId, question, top_k: 5 });
    $("tutor-answer").innerHTML = `<div class="tutor-box">${esc(data.answer)}</div>`;
  } catch (e) {
    $("tutor-answer").innerHTML = `<div class="status">Error: ${esc(e.message)}</div>`;
  }
};

// ---------- Step 5: quiz + progress ----------
$("quiz-btn").onclick = async () => {
  if (!lectureId) return;
  const data = await api("/quiz", { lecture_id: lectureId, num_mcq: 5 });
  currentQuiz = data.quiz || [];
  if (!currentQuiz.length) {
    $("quiz-form").innerHTML = "<div class='status'>No MCQs available for this lecture.</div>";
    return;
  }
  $("quiz-form").innerHTML = currentQuiz
    .map(
      (q, i) =>
        `<div class="quiz-q"><b>${i + 1}. ${esc(q.question)}</b> ${tag(q.topic)}` +
        (q.options || [])
          .map(
            (o) =>
              `<label><input type="radio" name="q${i}" value="${esc(o)}"> ${esc(o)}</label>`
          )
          .join("") +
        "</div>"
    )
    .join("");
  $("submit-quiz-btn").classList.remove("hidden");
  $("quiz-result").innerHTML = "";
};

$("submit-quiz-btn").onclick = async () => {
  const answers = currentQuiz.map((q, i) => {
    const sel = document.querySelector(`input[name="q${i}"]:checked`);
    return {
      question: q.question,
      topic: q.topic,
      selected: sel ? sel.value : "",
      correct: q.answer,
    };
  });
  const result = await api("/quiz/submit", {
    lecture_id: lectureId,
    student_id: STUDENT_ID,
    answers,
  });
  $("quiz-result").innerHTML =
    `<div class="tutor-box">Score: <b>${result.score}/${result.total}</b> (${result.percent}%)</div>`;
};

$("progress-btn").onclick = async () => {
  const data = await api("/progress/" + STUDENT_ID);
  const topics = data.topics || {};
  let h = "<h3>Topic mastery</h3>";
  if (!Object.keys(topics).length) h += "<div class='status'>Take a quiz first.</div>";
  for (const [name, pct] of Object.entries(topics)) {
    const low = pct < 60 ? " low" : "";
    h += `<div class="bar-row"><span class="name">${esc(name)}</span>
      <div class="bar${low}"><span style="width:${pct}%"></span></div>
      <span>${pct}%</span></div>`;
  }
  if (data.recommendations?.length) {
    h += "<h3>Recommendations</h3>";
    h += data.recommendations.map((r) => `<div class="rec">⚠ ${esc(r)}</div>`).join("");
  }
  $("progress").innerHTML = h;
};
