"""FoodPlanner.AI — conversational meal-planning assistant."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.chat.orchestrator import (
    STAGE_LABELS,
    accept_plan_and_shop,
    confirm_inventory,
    generate_plan,
    get_detailed_recipe,
    handle_message,
    ingest_photo,
    ingest_typed_inventory,
    new_session,
    start_new_plan,
    start_substitution,
)
from src.memory import load_profile, save_profile, save_session
from src.schemas import InventoryItem, UserProfile
from src.waste_tracker import build_recommendations, compute_analytics


st.set_page_config(
    page_title="FoodPlanner.AI",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
      .stApp {
        background: radial-gradient(1000px 500px at 85% -10%, rgba(255,122,89,0.10) 0%, transparent 60%),
                    #12141a !important;
        font-family: "Inter", "Segoe UI", sans-serif;
      }
      section[data-testid="stSidebar"] {
        background: #171a22 !important;
        border-right: 1px solid #262b38;
      }
      h1, h2, h3, .fp-brand {
        font-family: "Outfit", "Segoe UI", sans-serif !important;
        color: #f3ede4 !important;
        letter-spacing: -0.01em;
      }
      .fp-brand h1 {
        background: linear-gradient(90deg, #ffb15c 0%, #ff7a59 45%, #f4536e 100%);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent !important;
        font-weight: 700;
      }
      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3 {
        color: #ffb08f !important;
      }
      .fp-sub { color: #9aa3b2; font-size: 1.02rem; margin-top: -0.4rem; }
      .fp-progress {
        display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.75rem 0 1rem;
      }
      .fp-chip {
        padding: 0.28rem 0.7rem; border-radius: 999px; font-size: 0.78rem;
        background: #1b1f29; border: 1px solid #2b3040; color: #9aa3b2;
      }
      .fp-chip.active {
        background: linear-gradient(90deg, #ff8a5c, #f4536e); color: #ffffff;
        border-color: transparent; font-weight: 600;
        box-shadow: 0 2px 10px rgba(244,83,110,0.35);
      }
      .fp-chip.done { background: #2a2028; color: #ffb08f; border-color: #3b2c33; }
      .user-bubble {
        background: linear-gradient(135deg, #ff8a5c 0%, #f4536e 100%);
        color: #ffffff; padding: 0.85rem 1.05rem; border-radius: 18px 18px 4px 18px;
        margin: 0.45rem 0 0.45rem 18%;
        box-shadow: 0 3px 14px rgba(244,83,110,0.25);
      }
      .user-bubble * { color: #ffffff !important; }
      .bot-bubble {
        background: #1b1f29; color: #e8eaf0; padding: 0.9rem 1.05rem;
        border-radius: 18px 18px 18px 4px; margin: 0.45rem 18% 0.45rem 0;
        border: 1px solid #2b3040;
        box-shadow: 0 2px 10px rgba(0,0,0,0.25);
        line-height: 1.55;
      }
      .bot-bubble * { color: #e8eaf0 !important; }
      .bot-bubble em { color: #9aa3b2 !important; }
      .bot-bubble strong, .user-bubble strong { font-weight: 650; color: #ffc9a8 !important; }
      .user-bubble strong { color: #ffffff !important; }
      .meal-card {
        background: #1b1f29; border: 1px solid #2b3040; color: #e8eaf0;
        border-left: 3px solid #ff7a59;
        border-radius: 14px; padding: 0.95rem 1.1rem; margin: 0.55rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.25);
      }
      .meal-card * { color: #e8eaf0 !important; }
      .meal-card strong { color: #ffc9a8 !important; }
      .meal-card em { color: #9aa3b2 !important; }
      .stButton > button {
        border: 1px solid #2b3040 !important;
        background: #1b1f29 !important;
        color: #dfe3ea !important;
        border-radius: 12px !important;
        transition: all 0.15s ease;
      }
      .stButton > button:hover {
        border-color: #ff7a59 !important;
        color: #ffffff !important;
        box-shadow: 0 2px 12px rgba(255,122,89,0.25);
      }
      .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #ff8a5c, #f4536e) !important;
        color: #ffffff !important;
        border-color: transparent !important;
        font-weight: 600;
      }
      div[data-testid="stChatInput"] textarea { color: #e8eaf0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _md_to_html(text: str) -> str:
    """Convert the bot's lightweight markdown to HTML for the styled bubbles.

    Messages are injected into raw HTML divs, where Streamlit does not parse
    markdown — without this, users see literal ** and _ characters.
    """
    s = html.escape(text)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s, flags=re.DOTALL)
    s = re.sub(r"^###\s+(.+)$", r"<strong>\1</strong>", s, flags=re.MULTILINE)
    s = re.sub(r"(?<![\w])_([^_\n][^_]*?)_(?![\w])", r"<em>\1</em>", s, flags=re.DOTALL)
    s = s.replace("- [ ] ", "&#9744; ")
    return s.replace("\n", "<br>")


def _init() -> None:
    if "profile" not in st.session_state:
        st.session_state.profile = load_profile() or UserProfile()
    if "chat" not in st.session_state:
        st.session_state.chat = new_session(
            st.session_state.profile if st.session_state.profile.profile_confirmed else None,
            use_llm=True,
        )
    if "use_llm" not in st.session_state:
        st.session_state.use_llm = True


_init()
profile: UserProfile = st.session_state.profile
chat = st.session_state.chat
chat.use_llm = st.session_state.use_llm

# ---- Header ----
c1, c2, c3 = st.columns([3, 1, 1])
with c1:
    st.markdown('<div class="fp-brand"><h1>FoodPlanner.AI</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="fp-sub">Plan meals from what you already have.</div>', unsafe_allow_html=True)
with c2:
    if st.button("New Plan", use_container_width=True):
        if profile.profile_confirmed:
            st.session_state.chat = start_new_plan(chat, profile)
        else:
            st.session_state.chat = new_session(None, use_llm=st.session_state.use_llm)
        st.rerun()
with c3:
    if st.button("Edit Profile", use_container_width=True):
        profile.profile_confirmed = False
        save_profile(profile)
        st.session_state.chat = new_session(None, use_llm=st.session_state.use_llm)
        st.rerun()

# Progress
stage_order = [s for s, _ in STAGE_LABELS]
cur = chat.stage
chips = []
reached = True
for key, label in STAGE_LABELS:
    if key == cur:
        chips.append(f'<span class="fp-chip active">{label}</span>')
        reached = False
    elif reached:
        chips.append(f'<span class="fp-chip done">{label}</span>')
    else:
        chips.append(f'<span class="fp-chip">{label}</span>')
st.markdown(f'<div class="fp-progress">{"".join(chips)}</div>', unsafe_allow_html=True)

# ---- Sidebar ----
with st.sidebar:
    st.header("Your profile")
    st.session_state.use_llm = st.toggle("Use Claude for vision/planning", value=st.session_state.use_llm)
    chat.use_llm = st.session_state.use_llm
    if profile.profile_confirmed:
        st.write(f"**Diet:** {profile.diet_type}")
        st.write(f"**Rules:** {', '.join(profile.cultural_rules) or 'None'}")
        st.write(f"**Allergies:** {', '.join(profile.allergies) or 'None'}")
        st.write(f"**Servings:** {profile.servings}")
        st.write(f"**Cook time:** ~{profile.time_limit_min} min")
    else:
        st.info("Complete your profile in chat to begin.")

    inv_count = len([i for i in chat.inventory if not i.exclude_from_plan])
    meal_count = len(chat.plan.plan) if chat.plan else 0
    st.divider()
    st.write(f"**Inventory items:** {inv_count}")
    st.write(f"**Planned meals:** {meal_count}")
    if st.button("Clear current inventory"):
        chat.inventory = []
        save_session(chat)
        st.rerun()
    if chat.gap_list and st.button("View shopping list"):
        st.markdown(chat.gap_list.markdown)

    st.divider()
    if st.button("Waste tracker", use_container_width=True):
        st.session_state.show_tracer = not st.session_state.get("show_tracer", False)

# ---- Waste & purchasing tracer ----
if st.session_state.get("show_tracer"):
    analytics = compute_analytics(profile.user_id)
    with st.expander("Waste & purchasing tracker", expanded=True):
        if analytics["snapshot_count"] == 0:
            st.info(
                "No inventory history yet. Upload a fridge or pantry photo and confirm the "
                "detected ingredients — each confirmed inventory becomes a snapshot here."
            )
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric(
                "Current at-risk",
                f"{analytics['current_at_risk_percentage']:.0f}%",
                f"{analytics['current_at_risk_count']} items",
                delta_color="off",
            )
            m2.metric("Average at-risk (all snapshots)", f"{analytics['average_at_risk_percentage']:.0f}%")
            m3.metric("Confirmed waste events", analytics["confirmed_waste_events"])

            latest_date = (analytics["latest_snapshot_at"] or "")[:10]
            st.caption(f"Latest snapshot: {latest_date} · {analytics['snapshot_count']} snapshots recorded")

            if analytics["current_top_at_risk"]:
                st.markdown(
                    "**Use first right now:** "
                    + ", ".join(analytics["current_top_at_risk"])
                )

            series = analytics["at_risk_percentage_series"]
            if len(series) >= 2:
                st.markdown("**At-risk % over time**")
                st.line_chart(
                    {"At-risk %": [p["at_risk_percentage"] for p in series]},
                    height=180,
                )

            if analytics["repeated_at_risk"]:
                st.markdown("**Repeatedly at risk** _(at risk — not confirmed waste)_")
                for r in analytics["repeated_at_risk"]:
                    st.markdown(
                        f"- **{r['ingredient']}** — at risk in {r['occurrences']} recent "
                        f"inventories (confidence {r['confidence']:.0%})"
                    )

            if analytics["unresolved"]:
                st.markdown(
                    "**Possibly unused (unknown outcome):** "
                    + ", ".join(analytics["unresolved"])
                    + " — these disappeared from your latest inventory; I haven’t assumed they were wasted."
                )

            if analytics["most_wasted"]:
                st.markdown("**Confirmed waste** _(you told me these were spoiled or thrown away)_")
                for w in analytics["most_wasted"]:
                    st.markdown(f"- **{w['ingredient']}** — {w['count']} time{'s' if w['count'] > 1 else ''}")

            recs = build_recommendations(profile.user_id)
            if recs:
                st.markdown("**Purchase suggestions**")
                for rec in recs:
                    label = {
                        "buy_less": f"Buy around {rec.suggested_reduction_percentage}% less",
                        "smaller_package": "Choose a smaller package of",
                        "wait_before_buying": "Wait before buying more",
                    }.get(rec.recommendation_type, "Buy less")
                    st.markdown(
                        f"""
                        <div class="meal-card">
                          <strong>{label} {rec.ingredient}</strong><br>
                          <em>{rec.reason}</em><br>
                          Confidence: {rec.confidence:.0%} · based on {len(rec.supporting_snapshot_ids)} snapshots
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            elif analytics["snapshot_count"] < 3:
                st.caption(
                    "Purchase suggestions appear after at least 3 confirmed inventories, "
                    "so recommendations are based on real patterns rather than one-off events."
                )

# ---- Chat history ----
# Interactive widgets (editors, buttons, uploaders) are rendered ONLY on the most
# recent message of each kind; older messages show static content. This prevents
# StreamlitDuplicateElementKey crashes when e.g. two meal-card messages exist.
def _last_idx(kind: str):
    idxs = [i for i, m in enumerate(chat.messages) if m.role == "assistant" and m.kind == kind]
    return idxs[-1] if idxs else None


last_review_idx = _last_idx("inventory_review")
last_cards_idx = _last_idx("meal_cards")

for msg_idx, msg in enumerate(chat.messages):
    if msg.role == "user":
        st.markdown(f'<div class="user-bubble">{_md_to_html(msg.content)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="bot-bubble">{_md_to_html(msg.content)}</div>', unsafe_allow_html=True)

        if msg.kind == "inventory_review" and msg_idx == last_review_idx:
            st.subheader("Editable inventory")
            for idx, item in enumerate(list(chat.inventory)):
                cols = st.columns([3, 1, 1, 1, 1])
                with cols[0]:
                    new_name = st.text_input("Item", value=item.display_name, key=f"inv_name_{item.id}", label_visibility="collapsed")
                    item.display_name = new_name
                    item.normalized_name = new_name.strip().lower()
                with cols[1]:
                    item.opened = st.checkbox("Opened", value=item.opened, key=f"open_{item.id}")
                with cols[2]:
                    item.use_soon_user_flag = st.checkbox("Use soon", value=item.use_soon_user_flag, key=f"soon_{item.id}")
                with cols[3]:
                    item.exclude_from_plan = st.checkbox("Exclude", value=item.exclude_from_plan, key=f"ex_{item.id}")
                with cols[4]:
                    if st.button("Remove", key=f"rm_{item.id}"):
                        chat.inventory = [i for i in chat.inventory if i.id != item.id]
                        st.rerun()
            add_col1, add_col2 = st.columns([3, 1])
            with add_col1:
                extra = st.text_input("Add ingredient", key=f"add_ing_{msg_idx}", placeholder="e.g. chickpea flour")
            with add_col2:
                if st.button("Add", key=f"add_btn_inv_{msg_idx}"):
                    if extra.strip():
                        chat.inventory.append(
                            InventoryItem(
                                normalized_name=extra.strip().lower(),
                                display_name=extra.strip(),
                                source="typed",
                            )
                        )
                        st.rerun()
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("Confirm inventory", type="primary", key=f"confirm_inv_btn_{msg_idx}"):
                    st.session_state.chat = confirm_inventory(chat, profile)
                    save_session(st.session_state.chat)
                    st.rerun()
            with b2:
                if st.button("Add another photo", key=f"add_photo_btn_{msg_idx}"):
                    st.session_state.chat.stage = "inventory"
                    st.session_state.chat.awaiting = "inventory_input"
                    st.rerun()
            with b3:
                if st.button("Start over inventory", key=f"start_over_inv_{msg_idx}"):
                    chat.inventory = []
                    chat.stage = "inventory"
                    st.rerun()

        if msg.kind == "meal_cards" and chat.plan:
            interactive = msg_idx == last_cards_idx
            for meal in chat.plan.plan:
                st.markdown(
                    f"""
                    <div class="meal-card">
                      <strong>Day {meal.day or meal.night} — {meal.meal_type.title()}</strong><br>
                      <span style="font-size:1.15rem">{meal.recipe}</span><br>
                      <em>{meal.why_selected or ''}</em><br><br>
                      <strong>Uses from your kitchen:</strong> {', '.join(meal.ingredients_from_inventory) or '—'}<br>
                      <strong>Missing:</strong> {', '.join(meal.missing_ingredients) or 'None'}<br>
                      <strong>Time:</strong> {meal.time_min} min · <strong>Servings:</strong> {meal.servings}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if not interactive:
                    continue
                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    if st.button(f"Replace Day {meal.day or meal.night}", key=f"rep_{msg_idx}_{meal.night}_{meal.meal_type}"):
                        st.session_state.chat, st.session_state.profile = handle_message(
                            chat, profile, f"Replace day {meal.day or meal.night}"
                        )
                        st.rerun()
                with mc2:
                    if meal.missing_ingredients and st.button(
                        f"Help with {meal.missing_ingredients[0]}", key=f"miss_{msg_idx}_{meal.night}_{meal.meal_type}"
                    ):
                        st.session_state.chat = start_substitution(
                            chat, profile, meal.missing_ingredients[0], meal.recipe
                        )
                        save_session(st.session_state.chat)
                        st.rerun()
                with mc3:
                    if st.button(f"View steps {meal.day or meal.night}", key=f"steps_{msg_idx}_{meal.night}_{meal.meal_type}"):
                        with st.spinner("Writing the full recipe…"):
                            st.session_state.chat = get_detailed_recipe(
                                chat, profile, day=int(meal.day or meal.night)
                            )
                        save_session(st.session_state.chat)
                        st.rerun()

# Photo upload panel — rendered once whenever the conversation is at the inventory step.
if chat.stage == "inventory":
    up = st.file_uploader(
        "Fridge / pantry photo",
        type=["jpg", "jpeg", "png", "webp"],
        key=f"upload_{len(chat.messages)}",
    )
    cam = st.camera_input("Or take a photo", key=f"cam_{len(chat.messages)}")
    file = up or cam
    if file is not None and st.button("Detect ingredients from photo", key=f"detect_{len(chat.messages)}"):
        raw = file.getvalue()
        media = getattr(file, "type", None) or "image/jpeg"
        with st.spinner("Reading your photo…"):
            st.session_state.chat = ingest_photo(chat, raw, media_type=media)
        save_session(st.session_state.chat)
        st.rerun()

# Quick replies
if chat.quick_replies:
    st.caption("Quick replies")
    cols = st.columns(min(4, len(chat.quick_replies)))
    for i, qr in enumerate(chat.quick_replies):
        with cols[i % len(cols)]:
            if st.button(qr, key=f"qr_{len(chat.messages)}_{i}"):
                # Special short-circuits
                if qr.lower() == "yes, generate plan":
                    st.session_state.chat = generate_plan(chat, profile)
                elif qr.lower() in {"confirm plan", "accept plan"}:
                    if qr.lower() == "accept plan" and chat.plan and not chat.plan.confirmed:
                        st.session_state.chat, st.session_state.profile = handle_message(chat, profile, "Accept plan")
                    else:
                        st.session_state.chat = accept_plan_and_shop(chat, profile)
                elif qr.lower() == "confirm inventory":
                    st.session_state.chat = confirm_inventory(chat, profile)
                else:
                    st.session_state.chat, st.session_state.profile = handle_message(chat, profile, qr)
                save_session(st.session_state.chat)
                if st.session_state.profile.profile_confirmed:
                    save_profile(st.session_state.profile)
                st.rerun()

# Chat input
prompt = st.chat_input("Message FoodPlanner.AI…")
if prompt:
    st.session_state.chat, st.session_state.profile = handle_message(chat, profile, prompt)
    save_session(st.session_state.chat)
    if st.session_state.profile.profile_confirmed:
        save_profile(st.session_state.profile)
    st.rerun()
