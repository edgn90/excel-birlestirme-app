import streamlit as st
import pandas as pd
import io
from datetime import datetime

st.set_page_config(page_title="Excel Kayıt Birleştirme Aracı", page_icon="📊", layout="wide")

# Virgülle birleştirilmesi istenen özel kolonlar
# Not: Eğer Konu bir eşleşme kriteri değilse, onu da virgülle birleştirilecekler listesine dahil ediyoruz.
DEFAULT_CONCAT_COLS = [
    'PERFORMANS DÖNEMİ', 'DaBT-İPA-Hib-Hep-B', 'HEP B', 'BCG', 'KKK', 
    'HEP A', 'KPA', 'OPA', 'SU ÇİÇEĞİ', 'DaBT-İPA', 'TD', 
    'İTİRAZ NEDENİ', 'ASM RET NEDENİ', 'İLÇE SAĞLIK RET NEDENİ',
    'GEBE İZLEM', 'LOHUSA İZLEM', 'BEBEK İZLEM', 'ÇOCUK İZLEM'
]

def clean_tc(tc):
    """TC Kimlik numarasını temizler ve string'e çevirir."""
    if pd.isna(tc): return ""
    return str(tc).replace('.0', '').strip()

def clean_text(text):
    """Metinleri standartlaştırmak için temizler."""
    if pd.isna(text): return ""
    return str(text).strip().upper()

def smart_join(vals):
    """Aynı hücredeki değerleri virgülle birleştirir, tekrarları siler."""
    parts = []
    for val in vals:
        if pd.notna(val) and str(val).strip() != "" and str(val).lower() != "nan":
            s_val = str(val).strip()
            if s_val.endswith('.0'):
                s_val = s_val[:-2]
            for sub_val in s_val.split(','):
                clean_sub = sub_val.strip()
                if clean_sub:
                    parts.append(clean_sub)
    return ", ".join(dict.fromkeys(parts))

def consolidate_dataframe(df, merge_keys, concat_cols):
    """Belirlenen kriterlere (TC veya TC+KONU) göre kayıtları birleştirir."""
    agg_funcs = {}
    for col in df.columns:
        if col in merge_keys:
            continue
        if col in concat_cols:
            agg_funcs[col] = lambda x: smart_join(x.tolist())
        else:
            # Diğer alanlarda en son dolu veriyi al
            agg_funcs[col] = lambda x: x.dropna().iloc[-1] if not x.dropna().empty else None
            
    return df.groupby(merge_keys, as_index=False).agg(agg_funcs)

def process_data(list_of_old_dfs, df_new, use_subject_as_key):
    # Anahtar sütunları belirle
    merge_keys = ['TEMP_TC']
    if use_subject_as_key:
        merge_keys.append('TEMP_KONU')
    
    # Eğer Konu anahtar değilse, verilerin kaybolmaması için onu virgülle birleştirilecekler listesine ekle
    current_concat_cols = DEFAULT_CONCAT_COLS.copy()
    if not use_subject_as_key:
        current_concat_cols.append('KONU')

    if not list_of_old_dfs or df_new is None or df_new.empty:
        return None, 0, 0, None, None
        
    df_old_all = pd.concat(list_of_old_dfs, ignore_index=True)
    
    # Standartlaştırma
    df_old_all['TEMP_TC'] = df_old_all['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    df_old_all['TEMP_KONU'] = df_old_all['KONU'].apply(clean_text)
    
    df_new['TEMP_TC'] = df_new['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    df_new['TEMP_KONU'] = df_new['KONU'].apply(clean_text)

    # 1. ADIM: Kendi içlerinde seçilen kriterlere göre tekilleştir
    df_old_all = consolidate_dataframe(df_old_all, merge_keys, current_concat_cols)
    df_new = consolidate_dataframe(df_new, merge_keys, current_concat_cols)

    df_old_indexed = df_old_all.set_index(merge_keys, drop=False)
    df_new_indexed = df_new.set_index(merge_keys, drop=False)

    old_keys = set(df_old_indexed.index)
    new_keys = set(df_new_indexed.index)
    
    updated_keys = new_keys.intersection(old_keys)
    old_only_keys = old_keys - new_keys
    
    updated_count = len(updated_keys)
    added_count = len(new_keys - old_keys)

    # 2. ADIM: BİRLEŞTİRME MANTIĞI
    final_rows = []
    all_cols = [col for col in df_new.columns if col not in merge_keys]

    for key in new_keys:
        new_row = df_new_indexed.loc[key].copy()
        
        if key in old_keys:
            old_row = df_old_indexed.loc[key]
            for col in all_cols:
                val_new = new_row[col]
                val_old = old_row[col] if col in old_row.index else pd.NA
                
                if col in current_concat_cols:
                    new_row[col] = smart_join([val_old, val_new])
                else:
                    if pd.isna(val_new) or str(val_new).strip() == "":
                        new_row[col] = val_old
        
        final_rows.append(new_row[all_cols])

    df_final_new = pd.DataFrame(final_rows, columns=all_cols)

    if old_only_keys:
        df_old_only = df_old_indexed.loc[list(old_only_keys), all_cols].copy()
        df_result = pd.concat([df_final_new, df_old_only], ignore_index=True)
    else:
        df_result = df_final_new

    # Hata Kontrolü
    df_result['TC_CHECK_TEMP'] = df_result['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    invalid_tc_df = df_result[~df_result['TC_CHECK_TEMP'].str.match(r'^\d{11}$')]
    df_result = df_result.drop(columns=['TC_CHECK_TEMP'])

    # Tablo gösterimi için güncellenen kayıtlar
    if updated_count > 0:
        df_updated_records = df_new_indexed.loc[list(updated_keys)].reset_index(drop=True)
    else:
        df_updated_records = pd.DataFrame()

    return df_result, updated_count, added_count, invalid_tc_df, df_updated_records

# UI Tasarımı
st.title("📊 Excel Kayıt Birleştirme Aracı")
st.markdown("""
- Yüklediğiniz dosyalar **sunucuya kaydedilmez**, sayfa yenilendiğinde silinir.
- 💡 *İzlem alanları ve özel kolonlar eşleşen kayıtlarda otomatik olarak virgülle birleştirilir.*
""")

# --- KRİTER SEÇİM PANELİ ---
st.sidebar.header("🛠️ Birleştirme Ayarları")
selected_criteria = st.sidebar.multiselect(
    "Eşleştirme Kriterleri",
    options=["TC Kimlik No", "Konu"],
    default=["TC Kimlik No", "Konu"],
    help="Hangi alanlar aynıysa kayıtlar 'aynı kişi' kabul edilsin? (TC Kimlik No zorunludur)"
)

# TC her zaman zorunlu olsun
use_subject_as_key = "Konu" in selected_criteria
if "TC Kimlik No" not in selected_criteria:
    st.sidebar.warning("TC Kimlik No ana kriterdir, seçim dışı bırakılamaz.")

col1, col2 = st.columns(2)

with col1:
    old_files = st.file_uploader("📂 Eski Versiyon Excel'ler (Birden fazla)", type=['xlsx', 'xls'], accept_multiple_files=True)

with col2:
    new_file = st.file_uploader("🆕 Yeni Ay Excel Dosyası (Güncel)", type=['xlsx', 'xls'])

if len(old_files) > 0 and new_file is not None:
    if st.button("🚀 Verileri Birleştir ve Analiz Et"):
        with st.spinner("Veriler eşleştiriliyor..."):
            try:
                list_of_old_dfs = [pd.read_excel(f) for f in old_files]
                df_new = pd.read_excel(new_file)
                
                df_result, updated_count, added_count, invalid_tc_df, df_updated_records = process_data(list_of_old_dfs, df_new, use_subject_as_key)
                
                if df_result is not None:
                    st.success(f"Birleştirme tamamlandı! (Kriter: {'TC + Konu' if use_subject_as_key else 'Sadece TC'})")
                    
                    # --- FİLTRELEME BÖLÜMÜ ---
                    st.divider()
                    available_subjects = sorted(df_result['KONU'].dropna().unique().tolist())
                    selected_subjects = st.multiselect(
                        "🔍 Sonucu Konuya Göre Filtrele (İndirmeden önce):", 
                        options=available_subjects
                    )
                    
                    df_to_download = df_result[df_result['KONU'].isin(selected_subjects)] if selected_subjects else df_result

                    # Metrikler
                    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                    mcol1.metric("İşlenen Eski Dosya", len(old_files))
                    mcol2.metric("Güncellenen Kayıt", updated_count)
                    mcol3.metric("Yeni Eklenen Kayıt", added_count)
                    mcol4.metric("İndirilecek Kayıt", len(df_to_download))
                    
                    # Tablolar
                    if not df_updated_records.empty:
                        with st.expander("🔄 Güncellenen Kayıtları Listele"):
                            cols_to_show = [c for c in ['İTİRAZ KONUSU KİŞİNİN ADI SOYADI', 'İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO', 'KONU'] if c in df_updated_records.columns]
                            st.dataframe(df_updated_records[cols_to_show])
                    
                    if not invalid_tc_df.empty:
                        with st.expander("⚠️ Hatalı TC Tespit Edilen Kayıtlar"):
                            st.dataframe(invalid_tc_df)

                    # Dinamik Dosya İsmi
                    current_time = datetime.now().strftime("%d-%m-%Y_%H-%M")
                    file_name_dynamic = f"Birlestirilmis_Master_{current_time}.xlsx"

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_to_download.to_excel(writer, index=False, sheet_name='Birleştirilmiş Veri')
                    
                    st.download_button(
                        label=f"📥 {file_name_dynamic} Dosyasını İndir",
                        data=output.getvalue(),
                        file_name=file_name_dynamic,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Hata: {str(e)}")
