# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
from pathlib import Path

st.set_page_config(page_title="Okulistik Takip Paneli", page_icon="📚", layout="wide")

STORAGE_FILE = Path("progress.json")

@st.cache_data
def load_dataframe(file):
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file, encoding="utf-8")
    else:
        df = pd.read_excel(file)
    # Eski/ham CSV’lerde kolon isimleri farklı olabilir; normalize edelim
    cols = {c.lower(): c for c in df.columns}
    # Beklenen: GradeURL, Subject, Topic, TopicURL, ItemTitle, ItemURL
    # Bazı dosyalarda ItemTitle yok olabilir → üretelim
    if "itemtitle" not in cols:
        df["ItemTitle"] = ""
    if "itemurl" not in cols:
        # ham çıktıysa “ItemURL” yerine “ItemURL” zaten vardır; yoksa boş geç
        df["ItemURL"] = df.get("ItemURL", "")
    # Güvenli kolon seti:
    base_cols = ["GradeURL","Subject","Topic","TopicURL","ItemTitle","ItemURL"]
    for c in base_cols:
        if c not in df.columns:
            df[c] = ""
    # Temizlik
    df["Subject"] = df["Subject"].fillna("").astype(str).str.strip()
    df["Topic"] = df["Topic"].fillna("").astype(str).str.strip()
    df["ItemTitle"] = df["ItemTitle"].fillna("").astype(str).str.strip()
    df["ItemURL"] = df["ItemURL"].fillna("").astype(str).str.strip()
    # Boş URL’leri at
    df = df[df["ItemURL"] != ""].copy()
    df.reset_index(drop=True, inplace=True)
    return df

def load_progress():
    if STORAGE_FILE.exists():
        try:
            return json.loads(STORAGE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_progress(data: dict):
    STORAGE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def calc_progress(df, completed_set):
    total = len(df)
    done = df["ItemURL"].isin(completed_set).sum()
    pct = (done / total) if total else 0
    return done, total, pct

st.title("📚 Okulistik 6. Sınıf Takip Paneli")
st.caption("Ders → Konu → İçerik akışıyla gezin; tamamlananları işaretle, ilerlemeni takip et.")

with st.sidebar:
    st.header("⚙️ Veri Yükle")
    uploaded = st.file_uploader("CSV/XLSX dosyanı seç", type=["csv","xlsx"])
    st.markdown("**İpucu:** `study_links_all.csv` veya düzenlenmiş Excel’i seç.")
    st.divider()
    st.header("💾 İlerleme")
    if st.button("İlerlemeyi sıfırla", type="primary"):
        save_progress({})
        st.success("İlerleme sıfırlandı. Sayfayı yenileyin (R).")

if not uploaded:
    st.info("Soldan bir CSV/XLSX dosyası yükleyin.")
    st.stop()

df = load_dataframe(uploaded)
if df.empty:
    st.warning("Tablonuz boş görünüyor. CSV/XLSX içeriğini kontrol edin.")
    st.stop()

progress = load_progress()
completed = set(progress.get("completed_urls", []))

# Üst seviye özet
done, total, pct = calc_progress(df, completed)
st.metric("Genel İlerleme", f"{int(pct*100)}%", f"{done}/{total}")
st.progress(pct)

# Filtreler
left, right = st.columns([2,3])
with left:
    ders = st.selectbox("Ders seç:", ["(Tümü)"] + sorted(df["Subject"].unique()))
    alt = df if ders == "(Tümü)" else df[df["Subject"] == ders]
    konu = st.selectbox("Konu seç:", ["(Tümü)"] + sorted(alt["Topic"].unique()))
    alt = alt if konu == "(Tümü)" else alt[alt["Topic"] == konu]
with right:
    q = st.text_input("Ara (başlık/URL)")

if q:
    mask = alt["ItemTitle"].str.contains(q, case=False, na=False) | alt["ItemURL"].str.contains(q, case=False, na=False)
    alt = alt[mask]

# Ders/Konu bazlı özet
grp_cols = ["Subject","Topic"]
grouped = alt.groupby(grp_cols, dropna=False).size().reset_index(name="Count")

st.subheader("🔎 Konu Listesi")
for _, row in grouped.iterrows():
    s, t, count = row["Subject"], row["Topic"], int(row["Count"])
    sub_df = alt[(alt["Subject"] == s) & (alt["Topic"] == t)].copy()
    d, tt, p = calc_progress(sub_df, completed)

    with st.expander(f"{s} → {t}  |  {d}/{tt} tamamlandı  ({int(p*100)}%)", expanded=False):
        st.progress(p)
        # İçerik tablosu
        for ix, r in sub_df.reset_index(drop=True).iterrows():
            col1, col2, col3 = st.columns([6, 2, 2])
            title = r["ItemTitle"] or "İçerik"
            url = r["ItemURL"]
            with col1:
                st.markdown(f"**{ix+1}. {title}**  \n<small>{url}</small>", unsafe_allow_html=True)
            with col2:
                if st.button("Aç", key=f"open-{s}-{t}-{ix}"):
                    st.markdown(f"[Bağımsız sekmede açmak için tıkla]({url})")
            with col3:
                key = f"chk-{s}-{t}-{ix}"
                checked = url in completed
                new_state = st.checkbox("Tamamlandı", value=checked, key=key)
                if new_state and not checked:
                    completed.add(url)
                    progress["completed_urls"] = list(completed)
                    save_progress(progress)
                elif (not new_state) and checked:
                    completed.discard(url)
                    progress["completed_urls"] = list(completed)
                    save_progress(progress)

st.success("Hazır! Soldan yeni dosya seçebilir, ilerlemeyi kaydedebilir veya sıfırlayabilirsin.")
