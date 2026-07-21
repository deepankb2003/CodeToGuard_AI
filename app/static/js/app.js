const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"];
const SEVERITY_CLASS = {
  critical: "sev-critical",
  high: "sev-high",
  medium: "sev-medium",
  low: "sev-low",
  info: "sev-info",
};

const listEl = document.getElementById("review-list");
const listStatusEl = document.getElementById("review-list-status");
const emptyEl = document.getElementById("detail-empty");
const detailEl = document.getElementById("detail-content");
const repoFilterEl = document.getElementById("repo-filter");
const refreshBtn = document.getElementById("refresh-btn");
const runReviewBtn = document.getElementById("run-review-btn");
const runStatusEl = document.getElementById("run-status");
const prNumberEl = document.getElementById("pr-number");
const rowTemplate = document.getElementById("finding-row-template");

let activeReviewId = null;
let filterTimer = null;
let currentFindings = [];
let activeSeverity = null;

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json();
}

function severityClass(severity) {
  return SEVERITY_CLASS[severity] || SEVERITY_CLASS.info;
}

function formatTime(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function countBySeverity(findings) {
  const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  for (const f of findings) {
    if (f.severity in counts) counts[f.severity] += 1;
  }
  return counts;
}

async function loadReviews() {
  listStatusEl.hidden = false;
  listStatusEl.classList.remove("error");
  listStatusEl.textContent = "Loading reviews…";

  const repo = repoFilterEl.value.trim();
  const url = repo ? `/reviews?repo=${encodeURIComponent(repo)}` : "/reviews";

  let reviews;
  try {
    reviews = await fetchJSON(url);
  } catch (err) {
    listStatusEl.textContent = `Couldn't load reviews (${err.message}).`;
    listStatusEl.classList.add("error");
    listEl.innerHTML = "";
    return;
  }

  if (reviews.length === 0) {
    listStatusEl.textContent = repo
      ? `No reviews found for "${repo}".`
      : "No reviews yet. They'll show up here once a PR webhook fires.";
    listEl.innerHTML = "";
    clearDetailIfNotIn(reviews);
    return;
  }

  listStatusEl.hidden = true;
  renderReviewList(reviews);
  clearDetailIfNotIn(reviews);
}

function clearDetailIfNotIn(reviews) {
  if (activeReviewId === null) return;
  if (reviews.some((r) => r.id === activeReviewId)) return;

  activeReviewId = null;
  detailEl.hidden = true;
  detailEl.innerHTML = "";
  emptyEl.hidden = false;
}

function renderReviewList(reviews) {
  listEl.innerHTML = "";
  for (const review of reviews) {
    const li = document.createElement("li");
    const card = document.createElement("div");
    card.className = "review-card" + (review.id === activeReviewId ? " active" : "");
    card.dataset.reviewId = review.id;

    const top = document.createElement("div");
    top.className = "review-card-top";
    const repoSpan = document.createElement("span");
    repoSpan.className = "review-repo";
    repoSpan.textContent = review.repo_full_name;
    const prSpan = document.createElement("span");
    prSpan.className = "review-pr";
    prSpan.textContent = `#${review.pr_number}`;
    top.append(repoSpan, prSpan);

    const title = document.createElement("p");
    title.className = "review-title";
    title.textContent = review.pr_title;

    const bottom = document.createElement("div");
    bottom.className = "review-card-bottom";
    const time = document.createElement("span");
    time.className = "review-time";
    time.textContent = formatTime(review.created_at);
    const badge = document.createElement("span");
    badge.className = "review-time";
    badge.textContent = review.finding_count === 1 ? "1 finding" : `${review.finding_count} findings`;
    bottom.append(time, badge);

    card.append(top, title, bottom);
    card.addEventListener("click", () => selectReview(review.id));
    li.appendChild(card);
    listEl.appendChild(li);
  }
}

async function selectReview(id) {
  activeReviewId = id;
  document.querySelectorAll(".review-card").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.reviewId) === id);
  });

  emptyEl.hidden = true;
  detailEl.hidden = false;
  detailEl.innerHTML = `<div class="list-status">Loading review…</div>`;

  let review;
  try {
    review = await fetchJSON(`/reviews/${id}`);
  } catch (err) {
    detailEl.innerHTML = `<div class="list-status error">Couldn't load review ${id} (${err.message}).</div>`;
    return;
  }

  renderDetail(review);
}

function renderDetail(review) {
  detailEl.innerHTML = "";
  currentFindings = review.findings;
  activeSeverity = null;

  const header = document.createElement("div");
  header.className = "detail-header";

  const left = document.createElement("div");
  const h2 = document.createElement("h2");
  h2.textContent = review.pr_title;
  const sub = document.createElement("div");
  sub.className = "detail-sub";
  sub.innerHTML = `${escapeHtml(review.repo_full_name)} <span class="dot">&middot;</span> PR #${review.pr_number} <span class="dot">&middot;</span> ${escapeHtml(formatTime(review.created_at))}`;
  left.append(h2, sub);

  const counts = countBySeverity(review.findings);
  const summary = document.createElement("div");
  summary.className = "detail-summary";
  for (const sev of SEVERITY_ORDER) {
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = "summary-pill";
    pill.dataset.severity = sev;
    const dot = document.createElement("span");
    dot.className = `severity-dot ${severityClass(sev)}`;
    pill.append(dot, document.createTextNode(`${counts[sev]} ${sev}`));

    if (counts[sev] === 0) {
      pill.disabled = true;
    } else {
      pill.addEventListener("click", () => {
        activeSeverity = activeSeverity === sev ? null : sev;
        updatePillStates();
        renderFindingGroups(currentFindings, activeSeverity);
      });
    }

    summary.appendChild(pill);
  }

  header.append(left, summary);
  detailEl.appendChild(header);

  const groupsContainer = document.createElement("div");
  groupsContainer.id = "findings-groups";
  detailEl.appendChild(groupsContainer);

  if (review.findings.length === 0) {
    const none = document.createElement("div");
    none.className = "no-findings";
    none.textContent = "✅ No findings — this PR came back clean.";
    groupsContainer.appendChild(none);
    return;
  }

  renderFindingGroups(currentFindings, activeSeverity);
}

function updatePillStates() {
  document.querySelectorAll(".summary-pill").forEach((pill) => {
    pill.classList.toggle("active", pill.dataset.severity === activeSeverity);
  });
}

function renderFindingGroups(findings, filterSeverity) {
  const container = document.getElementById("findings-groups");
  container.innerHTML = "";

  const bySeverity = {};
  for (const f of findings) {
    (bySeverity[f.severity] ||= []).push(f);
  }

  const severities = filterSeverity ? [filterSeverity] : SEVERITY_ORDER;
  let rendered = 0;

  for (const sev of severities) {
    const group = bySeverity[sev];
    if (!group || group.length === 0) continue;
    rendered += group.length;

    const section = document.createElement("div");
    section.className = "findings-group";
    const h3 = document.createElement("h3");
    h3.textContent = `${sev} (${group.length})`;
    const ul = document.createElement("ul");
    ul.className = "finding-list";

    for (const finding of group) {
      ul.appendChild(renderFindingRow(finding));
    }

    section.append(h3, ul);
    container.appendChild(section);
  }

  if (rendered === 0) {
    const none = document.createElement("div");
    none.className = "no-findings";
    none.textContent = `No ${filterSeverity} findings.`;
    container.appendChild(none);
  }
}

function renderFindingRow(finding) {
  const node = rowTemplate.content.firstElementChild.cloneNode(true);
  const cls = severityClass(finding.severity);

  node.querySelector(".severity-dot").classList.add(cls);
  node.querySelector(".agent-tag").textContent = finding.source_agent;
  node.querySelector(".location").textContent = finding.line
    ? `${finding.file}:${finding.line}`
    : finding.file;
  node.querySelector(".finding-message").textContent = finding.message;
  const label = node.querySelector(".severity-label");
  label.textContent = finding.severity;
  label.classList.add(cls);

  return node;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

refreshBtn.addEventListener("click", () => {
  loadReviews();
  if (activeReviewId !== null) selectReview(activeReviewId);
});

repoFilterEl.addEventListener("input", () => {
  clearTimeout(filterTimer);
  filterTimer = setTimeout(loadReviews, 300);
});

runReviewBtn.addEventListener("click", async () => {
  const repo = repoFilterEl.value.trim();
  const prNumberRaw = prNumberEl.value.trim();
  if (!repo || !repo.includes("/")) {
    showRunStatus('Enter a repo as "owner/name" first.', true);
    return;
  }

  runReviewBtn.disabled = true;
  const target = prNumberRaw ? `PR #${prNumberRaw}` : "its latest open PR";
  showRunStatus(`Running a full review on ${repo}'s ${target} — this can take up to a minute…`, false);

  try {
    const body = { repo_full_name: repo };
    if (prNumberRaw) body.pr_number = Number(prNumberRaw);

    const res = await fetch("/reviews/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `${res.status} ${res.statusText}`);
    }

    hideRunStatus();
    await loadReviews();
    await selectReview(data.id);
  } catch (err) {
    showRunStatus(err.message, true);
  } finally {
    runReviewBtn.disabled = false;
  }
});

function showRunStatus(text, isError) {
  runStatusEl.hidden = false;
  runStatusEl.textContent = text;
  runStatusEl.classList.toggle("error", isError);
}

function hideRunStatus() {
  runStatusEl.hidden = true;
}

loadReviews();
