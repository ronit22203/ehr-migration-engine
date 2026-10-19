"""Graphite workbench theme. Layout stays in the Streamlit script."""

CSS = """
<style>
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
.block-container { padding-top: 1.05rem; padding-bottom: 0.4rem; max-width: 100%; }
.wb-kicker {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #8a8a8a;
  margin: 0;
}
.wb-title {
  font-size: 18px;
  font-weight: 600;
  color: #e8e8e8;
  margin: 0;
  line-height: 1.2;
}
.wb-meta, .wb-check span:first-child {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: #a3a3a3;
}
.wb-check {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.2rem 0;
  border-bottom: 1px solid #3c3c3c;
}
.wb-ok { color: #7dcea0; }
.wb-review { color: #e0b15a; }
.wb-bad { color: #e07a7a; }
.wb-muted { color: #8a8a8a; }
div[data-testid="stExpander"] details {
  border: 1px solid #3c3c3c;
  background: #252526;
}
div[data-testid="stCode"], pre, code, textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
}
</style>
"""
