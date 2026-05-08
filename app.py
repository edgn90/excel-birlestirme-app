import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Excel Kayıt Birleştirme Aracı", page_icon="📊", layout="wide")

# Virgülle birleştirilmesi istenen özel kolonlar
CONCAT_COLS = [
    'PERFORMANS DÖNEMİ', 'DaBT-İPA-Hib-Hep-B', 'HEP B', 'BCG', 'KKK', 
    'HEP A', 'KPA', 'OPA', 'SU ÇİÇEĞİ', 'DaBT-İPA', 'TD', 
    'İTİRAZ NEDENİ', 'ASM RET NEDENİ', 'İLÇE SAĞLIK RET NEDENİ'
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
            # Önceden birleşmiş virgüllü veriler varsa (eski dosyalardan gelen), onları da ayırıp tekilleştir
            for sub_val in s_val.split(','):
                clean_sub = sub_val.strip()
                if clean_sub:
                    parts.append(clean_sub)
    # Aynı kelimeleri (Örn: "Göç, Göç") tekilleştirerek birleştir
    return ", ".join(dict.fromkeys(parts))

def consolidate_dataframe(df):
    """Aynı dosya içindeki veya eski dosyalardaki tekrar eden kayıtları virgülle birleştirerek tekilleştirir."""
    agg_funcs = {}
    for col in df.columns:
        if col in ['TEMP_TC', 'TEMP_AD', 'TEMP_KONU']:
            continue
        if col in CONCAT_COLS:
            # Özel alanları virgülle birleştir
            agg_funcs[col] = lambda x: smart_join(x.tolist())
        else:
            # Diğer alanlarda en son dolu (boş olmayan) veriyi al
            agg_funcs[col] = lambda x: x.dropna().iloc[-1] if not x.dropna().empty else None
            
    return df.groupby(['TEMP_TC', 'TEMP_AD', 'TEMP_KONU'], as_index=False).agg(agg_funcs)

def process_data(list_of_old_dfs, df_new):
    required_cols = ['İTİRAZ KONUSU KİŞİNİN ADI SOYADI', 'İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO', 'KONU']
    
    if not list_of_old_dfs or df_new is None or df_new.empty:
        return None, 0, 0, None, None
        
    df_old_all = pd.concat(list_of_old_dfs, ignore_index=True)
    
    # Kolon kontrolü
    for col in required_cols:
        if col not in df_old_all.columns or col not in df_new.columns:
            st.error(f"Kritik hata: '{col}' kolonu dosyalarda bulunamadı!")
            return None, None, None, None, None

    # Standartlaştırma (TC, Ad ve Konu)
    df_old_all['TEMP_TC'] = df_old_all['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    df_old_all['TEMP_AD'] = df_old_all['İTİRAZ KONUSU KİŞİNİN ADI SOYADI'].apply(clean_text)
    df_old_all['TEMP_KONU'] = df_old_all['KONU'].apply(clean_text)
    
    df_new['TEMP_TC'] = df_new['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    df_new['TEMP_AD'] = df_new['İTİRAZ KONUSU KİŞİNİN ADI SOYADI'].apply(clean_text)
    df_new['TEMP_KONU'] = df_new['KONU'].apply(clean_text)

    # 1. ADIM: Eski dosyaları ve yeni dosyayı kendi içinde virgülle birleştirerek tekilleştir
    df_old_all = consolidate_dataframe(df_old_all)
    df_new = consolidate_dataframe(df_new)

    # İndeksleri 3'lü anahtara göre kur (Orijinal kolonları kaybetmemek için drop=False yapıyoruz)
    df_old_indexed = df_old_all.set_index(['TEMP_TC', 'TEMP_AD', 'TEMP_KONU'], drop=False)
    df_new_indexed = df_new.set_index(['TEMP_TC', 'TEMP_AD', 'TEMP_KONU'], drop=False)

    old_keys = set(df_old_indexed.index)
    new_keys = set(df_new_indexed.index)
    
    updated_keys = new_keys.intersection(old_keys)
    old_only_keys = old_keys - new_keys
    
    updated_count = len(updated_keys)
    added_count = len(new_keys - old_keys)

    # UI'da göstermek için güncellenen kayıtları çekiyoruz
    if updated_count > 0:
        df_updated_records = df_new_indexed.loc[list(updated_keys)].reset_index(drop=True)
    else:
        df_updated_records = pd.DataFrame()

    # 2. ADIM: ESKİ VE YENİ DOSYALARI BİRLEŞTİRME VE TAMAMLAMA MANTIĞI
    final_rows = []
    all_cols = [col for col in df_new.columns if col not in ['TEMP_TC', 'TEMP_AD', 'TEMP_KONU']]

    # Yeni Dosyadaki Tüm Kayıtları İşle
    for key in new_keys:
        new_row = df_new_indexed.loc[key].copy()
        
        if key in old_keys:  # Eğer bu kayıt eskide de varsa
            old_row = df_old_indexed.loc[key]
            for col in all_cols:
                val_new = new_row[col]
                val_old = old_row[col] if col in old_row.index else pd.NA
                
                # Kural 1: Belirtilen kolonlarda verileri virgülle birleştir
                if col in CONCAT_COLS:
                    new_row[col] = smart_join([val_old, val_new])
                # Kural 2: Diğer kolonlarda yeni hücre boşsa eskisinden al
                else:
                    if pd.isna(val_new) or str(val_new).strip() == "":
                        new_row[col] = val_old
        
        final_rows.append(new_row[all_cols])

    df_final_new = pd.DataFrame(final_rows, columns=all_cols)

    # Sadece Eskide Olan Kayıtları Sonuna Ekle (Veri Kaybı Olmaması İçin)
    if old_only_keys:
        df_old_only = df_old_indexed.loc[list(old_only_keys), all_cols].copy()
        df_result = pd.concat([df_final_new, df_old_only], ignore_index=True)
    else:
        df_result = df_final_new

    # Hatalı/Eksik TC Kontrolü
    df_result['TC_CHECK_TEMP'] = df_result['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    invalid_tc_df = df_result[~df_result['TC_CHECK_TEMP'].str.match(r'^\d{11}$')]
    df_result = df_result.drop(columns=['TC_CHECK_TEMP'])

    return df_result, updated_count, added_count, invalid_tc_df, df_updated_records

# UI Tasarımı (Birebir Aynı)
st.title("📊 Excel Kayıt Birleştirme Aracı")
st.markdown("""
- Yüklediğiniz dosyalar **sunucuya kaydedilmez**, işlem bittiğinde veya sayfayı yenilediğinizde sistemden silinir.
- Eski aylara ait **birden fazla Excel dosyasını** sol taraftan seçip yükleyebilirsiniz.
- 💡 *Sistem kayıtları birleştirirken "TC Kimlik No", "Ad Soyad" ve "Konu" eşleşmesine bakar. Eğer yeni dosyada alan boşsa eski dosyadaki veriyle tamamlar. Belirli alanları ise hem eski dosyaların kendi arasında hem de yeni dosya ile birleştirirken virgülle birleştirir.*
""")

col1, col2 = st.columns(2)

with col1:
    old_files = st.file_uploader("📂 Eski Versiyon Excel'ler (Birden fazla seçilebilir)", type=['xlsx', 'xls'], accept_multiple_files=True)

with col2:
    new_file = st.file_uploader("🆕 Yeni Ay Excel Dosyası (Sadece Güncel Dosya)", type=['xlsx', 'xls'])

if len(old_files) > 0 and new_file is not None:
    if st.button("🚀 Verileri Birleştir"):
        with st.spinner("Excel dosyaları okunuyor ve birleştiriliyor..."):
            try:
                list_of_old_dfs = []
                for f in old_files:
                    list_of_old_dfs.append(pd.read_excel(f))
                
                df_new = pd.read_excel(new_file)
                
                df_merged, updated_count, added_count, invalid_tc_df, df_updated_records = process_data(list_of_old_dfs, df_new)
                
                if df_merged is not None:
                    st.success("İşlem başarıyla tamamlandı!")
                    
                    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                    mcol1.metric("İşlenen Eski Dosya", len(old_files))
                    mcol2.metric("Güncellenen Kayıt", updated_count)
                    mcol3.metric("Yeni Eklenen Kayıt", added_count)
                    mcol4.metric("Toplam Çıktı Kayıt", len(df_merged))
                    
                    if not df_updated_records.empty:
                        with st.expander(f"🔄 Güncellenen (Eski Veri ile Tamamlanan) {updated_count} Kaydı İncele"):
                            st.dataframe(df_updated_records[['İTİRAZ KONUSU KİŞİNİN ADI SOYADI', 'İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO', 'KONU']])
                    
                    if not invalid_tc_df.empty:
                        st.warning(f"⚠️ Dikkat: {len(invalid_tc_df)} kayıtta hatalı veya eksik TC Kimlik No tespit edildi (11 hane olmalı).")
                        with st.expander("Hatalı TC Numarasına Sahip Kayıtları İncele"):
                            st.dataframe(invalid_tc_df[['İTİRAZ KONUSU KİŞİNİN ADI SOYADI', 'İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO', 'KONU']])
                    else:
                        st.info("✅ Tüm kayıtların TC Kimlik Numarası formatı doğru (11 Hane).")

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_merged.to_excel(writer, index=False, sheet_name='Birleştirilmiş Veri')
                    processed_data = output.getvalue()

                    st.download_button(
                        label="📥 Birleştirilmiş Yeni Excel'i İndir",
                        data=processed_data,
                        file_name="Guncel_Birlestirilmis_Master.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except Exception as e:
                st.error(f"Beklenmeyen bir hata oluştu: {str(e)}")
