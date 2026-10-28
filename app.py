"""CloudForenX: paper-matched, demonstration-only digital evidence Streamlit prototype.

Matches the six-screen navigation and core workflow in Gulia (2026),
International Journal of Engineering in Computer Science, 8(2), 163-174.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from storage import (add_custody_note, create_session_store, file_path,
                     get_custody, get_record, get_records, save_evidence, verify_evidence)

st.set_page_config(page_title="CloudForenX | Digital Evidence Integrity", page_icon="🔐",
                   layout="wide", initial_sidebar_state="expanded")

# Streamlit-native layout and colors, close to screenshots in the published paper.
st.markdown("""
<style>
.stApp { background: #0e1117; }
section[data-testid="stSidebar"] { background:#262730; border-right:1px solid #393b48; }
[data-testid="stSidebarNav"] { display:none; }
.block-container { max-width:1100px; padding-top:2.0rem; padding-bottom:3.0rem; }
h1,h2,h3 { letter-spacing:-.018em; }
h1 { font-weight:770!important; margin-bottom:.6rem!important; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { font-weight:500; }
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] { gap:0.15rem; }
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label { padding:.27rem .35rem; border-radius:8px; }
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover { background:#343743; }
div.stButton>button[kind="primary"], div.stFormSubmitButton>button[kind="primary"] {
  background:#313543; border:1px solid #616a7c; color:#f3f6ff;
  border-radius:9px; font-weight:650;
}
div.stButton>button[kind="primary"]:hover, div.stFormSubmitButton>button[kind="primary"]:hover {
  background:#414b5d; border-color:#8b9cac; color:#fff;
}
[data-testid="stAlert"] {border-radius:8px;}
.cf-caption {color:#a4a6b1; font-size:.98rem; margin:-.25rem 0 1.5rem;}
.cf-label {color:#aeb7c7; font-size:.78rem; font-weight:730; text-transform:uppercase; letter-spacing:.13em; margin-bottom:.5rem;}
.cf-note {font-size:.83rem; color:#b0b6c3;}
.cf-digest {background:#172d44; color:#6fc4ff; border:1px solid #294661; padding:1rem;
  border-radius:9px; overflow-wrap:anywhere; font-family:ui-monospace,Consolas,monospace; font-size:.92rem; margin:.3rem 0 1rem;}
</style>
""", unsafe_allow_html=True)

if "store_root" not in st.session_state:
    st.session_state.store_root = create_session_store()
root = st.session_state.store_root

PAGES = ["Upload Evidence", "Dashboard", "Verify Integrity", "Chain of Custody",
         "Guidance", "Awareness Quiz"]
TYPES = ["Image", "Document", "Chat / Email", "System Log", "Audio / Video", "Other"]
QUIZ = [
 ("What is the main purpose of a SHA-256 hash?", ["Encrypt evidence", "Check file integrity", "Compress evidence"], 1),
 ("A file changes after a single character is edited. What should happen to its SHA-256 digest?", ["It generally changes", "It always remains the same", "The file is automatically repaired"], 0),
 ("What does chain of custody document?", ["Who handled evidence and when", "Only the file size", "Only the file extension"], 0),
 ("Before analysing original evidence, what is a safer practice?", ["Overwrite the original", "Make and document an authorised working copy", "Post it publicly"], 1),
 ("Does this educational prototype provide court-certified forensic storage?", ["Yes", "No"], 1),
]


def intro(title: str, description: str) -> None:
    st.title(title)
    st.markdown(f'<div class="cf-caption">{escape(description)}</div>', unsafe_allow_html=True)


def table_csv(rows: list[dict], cols: list[str]) -> bytes:
    frame = pd.DataFrame(rows, columns=cols)
    return frame.to_csv(index=False).encode("utf-8-sig")


def choose_record(label: str, key: str):
    records = get_records(root)
    ids = [r["id"] for r in records]
    names = {r["id"]: f"ID {r['id']} | {r['case_id']} | {r['evidence_name']}" for r in records}
    if not ids:
        return None
    return st.selectbox(label, ids, format_func=lambda i: names[i], key=key)


with st.sidebar:
    st.markdown("### 🔐 CloudForenX")
    st.caption("Digital Evidence Integrity & Chain of Custody")
    st.divider()
    page = st.radio("app", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("B.Tech research prototype · 2026")
    st.caption("Sample evidence only · No real case files")

if page == "Upload Evidence":
    intro("📤 Upload Evidence", "Upload a file. CloudForenX will generate a SHA-256 hash (file fingerprint) and store its details.")
    with st.form("evidence_intake", clear_on_submit=False, border=True):
        case_id = st.text_input("Case ID (example: CASE-101)", placeholder="CASE-101")
        evidence_name = st.text_input("Evidence Name (example: WhatsApp Chat Screenshot)", placeholder="Sample chat evidence")
        evidence_type = st.selectbox("Evidence Type", TYPES)
        collector = st.text_input("Collected By (your name)", placeholder="Research demo user")
        upload = st.file_uploader("Upload Evidence File", help="Synthetic files only; up to 12 MB")
        submit = st.form_submit_button("✅ Save Evidence", type="primary")
    if submit:
        if upload is None:
            st.error("Please select a sample file first.")
        else:
            try:
                record = save_evidence(root, case_id=case_id, evidence_name=evidence_name,
                                       evidence_type=evidence_type, collected_by=collector,
                                       filename=upload.name, data=upload.getvalue())
                st.session_state.latest_record_id = record["id"]
                st.success("✅ Evidence saved successfully!")
            except ValueError as exc:
                st.error(str(exc))
    current = st.session_state.get("latest_record_id")
    if current:
        item = get_record(root, current)
        if item:
            st.write(f"**Evidence ID:** {item['id']} · **File:** {item['original_filename']} · **Size:** {item['size_bytes']:,} bytes")
            st.markdown("**SHA-256 Hash:**")
            st.markdown(f'<div class="cf-digest">{item["sha256"]}</div>', unsafe_allow_html=True)
            st.info("The reference hash and evidence metadata are recorded in a demo SQLite database. The file is held in isolated temporary session storage.")

elif page == "Dashboard":
    intro("📋 Dashboard", "Search the records saved during this demo session.")
    st.subheader("🔎 Search / Filter")
    q = st.text_input("Search (Case ID / Evidence Name / Collected By)", placeholder="Search evidence records")
    records = get_records(root)
    if q.strip():
        needle = q.casefold().strip()
        records = [r for r in records if any(needle in str(r[k]).casefold() for k in ("case_id", "evidence_name", "collected_by", "evidence_type"))]
    st.subheader("📄 Evidence Records")
    cols = ["ID", "Case ID", "Evidence Name", "Type", "Collected By", "File Path (demo)", "SHA-256 Hash", "Integrity"]
    rows = [{"ID":r["id"], "Case ID":r["case_id"], "Evidence Name":r["evidence_name"],
             "Type":r["evidence_type"], "Collected By":r["collected_by"],
             "File Path (demo)": "uploads/"+r["stored_filename"], "SHA-256 Hash":r["sha256"],
             "Integrity":r["last_verified"]} for r in records]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download Evidence Table (CSV)", table_csv(rows, cols),
                           file_name="CloudForenX_Evidence_Records.csv", mime="text/csv")
        with st.expander("Inspect selected evidence"):
            rid = choose_record("Select saved record", "dash_item")
            if rid is not None:
                rec = get_record(root,rid)
                st.write(f"**Filename:** {rec['original_filename']}")
                st.write(f"**Stored at:** {rec['created_utc']} (UTC)")
                st.write(f"**Last integrity check:** {rec['last_verified']}")
                st.code(rec["sha256"], language="text")
                if st.download_button("Download original sample file", file_path(root, rec).read_bytes(),
                                      file_name=rec["original_filename"], mime="application/octet-stream"):
                    pass
    else:
        st.info("No matching evidence records yet. Start with Upload Evidence.")
    st.caption("Cloud-style repository simulation: SQLite and uploaded files are isolated per session. This is not real cloud evidence storage or access control.")

elif page == "Verify Integrity":
    intro("✅ Verify Integrity", "Re-upload a file and compare it with the stored SHA-256 hash to check whether its contents changed.")
    rid = choose_record("Select stored evidence record", "verify_rid")
    if rid is not None:
        rec = get_record(root,rid)
        st.markdown("**Stored SHA-256 Hash:**")
        st.markdown(f'<div class="cf-digest">{rec["sha256"]}</div>', unsafe_allow_html=True)
        candidate = st.file_uploader("Upload the file again to verify", key="verification_upload", help="Up to 12 MB")
        collector = st.text_input("Your name (for custody log)", value=rec["collected_by"], key="verifier_name")
        if st.button("🔎 Verify Now", type="primary"):
            if candidate is None:
                st.error("Choose a file to compare.")
            else:
                try:
                    matching, saved_hash, new_hash = verify_evidence(root, rid, candidate.getvalue(), collector)
                    st.session_state.verification_result = (rid, matching, saved_hash, new_hash)
                except ValueError as exc:
                    st.error(str(exc))
        result = st.session_state.get("verification_result")
        if result and result[0] == rid:
            st.write("**New SHA-256 Hash:**")
            st.code(result[3], language="text")
            if result[1]:
                st.success("✅ Integrity Verified: File is unchanged (hash matches).")
            else:
                st.error("❌ Not verified: SHA-256 mismatch. File contents differ from the saved reference.")
            st.caption("SHA-256 compares content; it does not establish who created or owned the file.")
    else:
        st.info("No stored evidence record. Upload a synthetic sample file first.")

elif page == "Chain of Custody":
    intro("📜 Chain of Custody", "View the time-stamped demonstration record of evidence upload and verification activities.")
    logs = get_custody(root)
    if logs:
        cols = ["Time (UTC)", "Evidence ID", "Case ID", "Collected By", "Action", "Status", "Hash", "Notes"]
        rows = [{"Time (UTC)":x["timestamp_utc"], "Evidence ID":x["evidence_id"],
                 "Case ID":x["case_id"], "Collected By":x["collector"],
                 "Action":x["action"], "Status":x["status"],
                 "Hash":x["hash_value"], "Notes":x["notes"]} for x in logs]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download Custody Logs (CSV)", table_csv(rows, cols),
                           "CloudForenX_Chain_of_Custody.csv", mime="text/csv")
        with st.expander("Record an additional handling action (demo)"):
            with st.form("manual_custody"):
                rid = choose_record("Evidence", "manual_log_evidence")
                actor = st.text_input("Handled By", placeholder="Name of person performing the action")
                action = st.selectbox("Action", ["Viewed record", "Examined working copy", "Simulated transfer", "Returned to storage"])
                notes = st.text_area("Notes", height=90)
                save = st.form_submit_button("Add custody log")
            if save:
                try:
                    add_custody_note(root, rid, actor, action, notes)
                    st.success("Demo log entry recorded. It will appear in the table after refresh.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    else:
        st.info("No custody history recorded. Upload sample evidence to create the first entry.")
    st.caption("The custody log is an editable demonstration log, not a tamper-proof or court-certified audit trail.")

elif page == "Guidance":
    intro("📘 Guidance", "Evidence-preservation practices, basic legal awareness and official Indian cyber help resources.")
    st.subheader("Essential digital-evidence handling practices")
    st.markdown("""
1. **Preserve the original** and create an authorised working copy before examination.
2. **Record the case ID, source, collector and acquisition time** for each item.
3. **Generate a SHA-256 reference hash** at acquisition, and verify again after handling or transfer.
4. **Document all transfers and examinations** with names, times and reasons.
5. **Restrict access and disclosure** and follow applicable institutional and legal procedures.
""")
    st.subheader("Indian legal awareness")
    st.write("The Information Technology Act, 2000 addresses relevant electronic-record and cyber-offence issues. The Bharatiya Sakshya Adhiniyam, 2023 addresses electronic and digital evidence. Specific admissibility depends on the case, applicable law and documented procedures.")
    st.subheader("Official reporting and support")
    st.markdown("""
- **National Cyber Crime Reporting Portal:** https://cybercrime.gov.in/
- **Cyber financial fraud helpline:** **1930** (India)
- **CERT-In:** https://www.cert-in.org.in/
- **India Code (official legislation):** https://www.indiacode.nic.in/
""")
    st.warning("Educational information, not legal advice. This app does not submit police reports or transmit evidence to these services.")

elif page == "Awareness Quiz":
    intro("🧠 Awareness Quiz", "A short knowledge check on SHA-256, evidence integrity and chain of custody.")
    with st.form("awareness_quiz"):
        answers = []
        for index,(question, options, correct) in enumerate(QUIZ,1):
            answers.append(st.radio(f"Q{index}. {question}", ["Choose an answer"]+options, key=f"quiz_{index}"))
        submitted = st.form_submit_button("Calculate Awareness Score", type="primary")
    if submitted:
        if "Choose an answer" in answers:
            st.error("Please answer all five questions.")
        else:
            score = sum(ans==QUIZ[idx][1][QUIZ[idx][2]] for idx,ans in enumerate(answers))
            st.session_state.awareness_result=(score, answers)
    if "awareness_result" in st.session_state:
        score, answers = st.session_state.awareness_result
        st.metric("Awareness assessment score", f"{score}/5")
        st.progress(score/5)
        for idx,(question,options,correct) in enumerate(QUIZ):
            st.write(("✅" if answers[idx]==options[correct] else "❌")+f" Q{idx+1}: {options[correct]}")
        st.caption("A five-question quiz measures responses to these questions, not real-life evidence-handling behaviour or improvement after training.")

st.divider()
st.caption("CloudForenX — Research demonstration based on: 'Bridging the awareness-practice gap in digital evidence handling: A survey and prototype-based study on integrity verification and chain of custody' · Parikshit Gulia · 2026.")
st.caption("Not secure case management: demo-only SQLite/file storage, no authentication, no immutable audit log, and no certified forensic preservation. Do not upload real, confidential or sensitive evidence.")
