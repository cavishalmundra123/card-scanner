"""UI helpers — SVG icons and reusable HTML components for Card Scanner."""

import os
import streamlit as st

# ── SVG icons (Lucide style, MIT license) ─────────────────────────────────────
# Inline SVG keeps things zero-dependency. Stroke color is set via currentColor.

ICON_BRIEFCASE = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
  <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
</svg>"""

ICON_USER = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
  <circle cx="12" cy="7" r="4"/>
</svg>"""

ICON_UPLOAD = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
  <polyline points="17 8 12 3 7 8"/>
  <line x1="12" y1="3" x2="12" y2="15"/>
</svg>"""

ICON_SEARCH = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="11" cy="11" r="8"/>
  <line x1="21" y1="21" x2="16.65" y2="16.65"/>
</svg>"""

ICON_CONTACTS = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
  <circle cx="9" cy="7" r="4"/>
  <path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
  <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
</svg>"""

ICON_DOWNLOAD = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
  <polyline points="7 10 12 15 17 10"/>
  <line x1="12" y1="15" x2="12" y2="3"/>
</svg>"""

ICON_KEY = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
</svg>"""

ICON_LIGHTBULB = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M9 18h6"/>
  <path d="M10 22h4"/>
  <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/>
</svg>"""

ICON_LOGOUT = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
  <polyline points="16 17 21 12 16 7"/>
  <line x1="21" y1="12" x2="9" y2="12"/>
</svg>"""

ICON_FILE = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
  <polyline points="14 2 14 8 20 8"/>
</svg>"""

ICON_CAMERA = """<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
  <circle cx="12" cy="13" r="4"/>
</svg>"""


def icon(svg_template: str, size: int = 20, color: str = "#1f4e79") -> str:
    """Render an icon at given size/color. Returns HTML string."""
    return svg_template.format(size=size, color=color)


def load_css(css_path: str = "static/style.css") -> None:
    """Inject the app stylesheet. Call once near the top of app.py."""
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_app_header() -> None:
    """Top-of-page brand lockup: briefcase icon + name + tagline."""
    st.markdown(f"""
    <div class="app-header">
        {icon(ICON_BRIEFCASE, size=34, color="#1f4e79")}
        <h1>Card Scanner</h1>
    </div>
    <p class="app-tagline">Scan business cards. Find contacts instantly.</p>
    """, unsafe_allow_html=True)


def render_section_header(title: str, caption: str, icon_svg: str = ICON_UPLOAD) -> None:
    """Reusable section header with icon + title + caption."""
    st.markdown(f"""
    <div class="section-header">
        {icon(icon_svg, size=22, color="#1f4e79")}
        <h2>{title}</h2>
    </div>
    <p class="section-caption">{caption}</p>
    """, unsafe_allow_html=True)


def render_user_card(username: str, email: str) -> None:
    """Sidebar user identity block."""
    st.markdown(f"""
    <div class="user-card">
        <div class="name">
            {icon(ICON_USER, size=16, color="#1f4e79")}
            <span>{username}</span>
        </div>
        <div class="email">{email}</div>
    </div>
    """, unsafe_allow_html=True)


def render_stat_card(label: str, value, sublabel: str = None) -> None:
    """Hero stat card — gradient background, big number."""
    sub_html = f'<div class="label" style="margin-top:8px; opacity:0.75;">{sublabel}</div>' if sublabel else ""
    st.markdown(f"""
    <div class="stat-card">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_label(text: str, icon_svg: str = None) -> None:
    """Uppercase section label in sidebar."""
    icon_html = icon(icon_svg, size=14, color="#64748b") if icon_svg else ""
    st.markdown(f"""
    <div class="sidebar-section-label">{icon_html}<span>{text}</span></div>
    """, unsafe_allow_html=True)


def render_tip(text: str) -> None:
    """Yellow tip card in sidebar."""
    st.markdown(f"""
    <div class="tip-card">
        {icon(ICON_LIGHTBULB, size=16, color="#a16207")}
        <span>{text}</span>
    </div>
    """, unsafe_allow_html=True)
