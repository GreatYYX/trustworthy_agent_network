const README_URL = "README.md";

const contentEl = document.getElementById("content");
const titleEl = document.getElementById("page-title");

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderMarkdown(markdown) {
  const headingMatch = markdown.match(/^#\s+(.+)$/m);
  let body = markdown;

  if (headingMatch) {
    const mainTitle = headingMatch[1].trim();
    if (titleEl) titleEl.textContent = mainTitle;
    document.title = mainTitle;
    body = markdown.replace(/^#\s+.+\n?/, "");
  }

  if (!window.marked) {
    contentEl.innerHTML = `<pre>${escapeHtml(body)}</pre>`;
    return;
  }

  contentEl.innerHTML = window.marked.parse(body, {
    breaks: true,
    gfm: true,
  });
}

async function loadReadme() {
  try {
    const response = await fetch(`${README_URL}?t=${Date.now()}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const markdown = await response.text();
    if (!markdown.trim()) {
      throw new Error("README.md is empty");
    }

    renderMarkdown(markdown);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    contentEl.innerHTML = `
      <div class="placeholder">
        <h2>Paper abstract unavailable</h2>
        <p>Could not load <code>README.md</code>.</p>
        <p>Error: ${escapeHtml(message)}</p>
      </div>
    `;
  }
}

loadReadme();
