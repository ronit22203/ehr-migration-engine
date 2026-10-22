"""Slate workbench theme. The main canvas stays white; side panes sit on cool off-white."""

CSS = """
<style>
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stToolbar"], [data-testid="stBottom"] {
  background-color: #ffffff;
}
[data-testid="stHeader"] { display: none; }
.block-container { padding-top: 0.85rem; padding-bottom: 0.25rem; max-width: 100%; }
[data-testid="stVerticalBlock"] { gap: 0.4rem; }

[data-testid="stColumn"]:has(.wb-pane) {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0.45rem 0.65rem 0.55rem;
  height: calc(100vh - 8.25rem);
  overflow-y: auto;
  align-self: start;
}
[data-testid="stColumn"]:has(.wb-pane) button {
  min-height: 1.65rem;
  padding-top: 0.1rem;
  padding-bottom: 0.1rem;
}
[data-testid="stMarkdown"]:has(.wb-center) { display: none; }
[data-testid="stColumn"]:has(.wb-center) [data-testid="stImage"] img {
  max-height: calc(100vh - 13rem);
  width: auto !important;
  max-width: 100%;
}

.stMarkdown p.wb-kicker {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  line-height: 1.3;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
  margin: 0;
  white-space: nowrap;
}
.stMarkdown p.wb-title {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
  line-height: 1.2;
}
[data-testid="stRadio"] p {
  line-height: 1.25;
  margin: 0;
}
.wb-meta, .wb-check span:first-child {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: #64748b;
}
.wb-check {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.2rem 0;
  border-bottom: 1px solid #e2e8f0;
}
.wb-ok { color: #0f172a; }
.wb-review { color: #64748b; }
.wb-bad { color: #0f172a; }
.wb-muted { color: #64748b; }

h1, h2, h3, p, label, .stText {
  color: #334155;
}
[data-testid="stCaptionContainer"] {
  color: #64748b;
  opacity: 1;
}

button[data-testid="stBaseButton-primary"] {
  background: #0f172a;
  color: #ffffff;
  border: 1px solid #0f172a;
}
button[data-testid="stBaseButton-primary"] * {
  color: #ffffff;
  background: transparent;
}
button[data-testid="stBaseButton-secondary"] {
  background: #ffffff;
  color: #334155;
  border: 1px solid #e2e8f0;
}
button[data-testid="stBaseButton-secondary"] * {
  color: #334155;
  background: transparent;
}

div[data-testid="stExpander"] details {
  border: 1px solid #e2e8f0;
  background: #ffffff;
  border-radius: 8px;
}
div[data-testid="stCode"], pre, code, textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
  background-color: #ffffff;
  color: #334155;
  border-color: #e2e8f0;
}

.wb-table {
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}
.wb-table table {
  width: 100%;
  border-collapse: collapse;
  background: #ffffff;
}
.wb-table th, .wb-table td {
  border-bottom: 1px solid #e2e8f0;
  color: #334155;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  text-align: left;
  padding: 0.35rem 0.55rem;
}
.wb-table th {
  background: #f8fafc;
  color: #0f172a;
  font-weight: 600;
}
.wb-table tr:last-child td { border-bottom: 0; }
</style>
"""
