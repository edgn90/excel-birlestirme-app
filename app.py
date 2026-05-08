import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Excel Kayıt Birleştirme Aracı", page_icon="📊", layout="wide")

def clean_tc(tc):
    """TC Kimlik numarasını temizler ve string'e çevirir."""
    if pd.isna(tc):
        return ""
    return str(tc).replace('.0', '').strip()

def clean_text(text):
    """Metinleri (Ad Soyad, Konu) standartlaştırmak ve eşleştirmek için temizler."""
    if pd.isna(text):
        return ""
    return str(text).strip().upper()

def process_data(df_old, list_of_new_dfs):
    # Eşleştirme için gereken zorunlu kolonlara 'KONU' da eklendi
    required_cols = ['İTİRAZ KONUSU KİŞİNİN ADI SOYADI', 'İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO', 'KONU']
    
    if not list_of_new_dfs:
        return None, 0, 0, None, None
        
    df_new = pd.concat(list_of_new_dfs, ignore_index=True)
    
    for col in required_cols:
        if col not in df_old.columns or col not in df_new.columns:
            st.error(f"Kritik hata: '{col}' kolonu dosyalarda bulunamadı!")
            return None, None, None, None, None

    # Standartlaştırma (TC, Ad ve Konu)
    df_old['TEMP_TC'] = df_old['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    df_old['TEMP_AD'] = df_old['İTİRAZ KONUSU KİŞİNİN ADI SOYADI'].apply(clean_text)
    df_old['TEMP_KONU'] = df_old['KONU'].apply(clean_text)
    
    df_new['TEMP_TC'] = df_new['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    df_new['TEMP_AD'] = df_new['İTİRAZ KONUSU KİŞİNİN ADI SOYADI'].apply(clean_text)
    df_new['TEMP_KONU'] = df_new['KONU'].apply(clean_text)

    # Yeni dosyalarda Ad, TC ve Konu tamamen aynı olanlar varsa sonuncuyu geçerli say
    df_new = df_new.drop_duplicates(subset=['TEMP_TC', 'TEMP_AD', 'TEMP_KONU'], keep='last')

    # İndeksleri 3'lü anahtara göre kuruyoruz
    df_old_indexed = df_old.set_index(['TEMP_TC', 'TEMP_AD', 'TEMP_KONU'])
    df_new_indexed = df_new.set_index(['TEMP_TC', 'TEMP_AD', 'TEMP_KONU'])

    old_keys = set(df_old_indexed.index)
    new_keys = set(df_new_indexed.index)
    
    updated_keys = new_keys.intersection(old_keys)
    
    updated_count = len(updated_keys)
    added_count = len(new_keys - old_keys)

    if updated_count > 0:
        df_updated_records = df_new_indexed.loc[list(updated_keys)].reset_index()
    else:
        df_updated_records = pd.DataFrame()

    df_merged_indexed = df_new_indexed.combine_first(df_old_indexed)
    df_merged = df_merged_indexed.reset_index(drop=True)

    df_merged['TC_CHECK_TEMP'] = df_merged['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    invalid_tc_df = df_merged[~df_merged['TC_CHECK_TEMP'].str.match(r'^\d{11}$')]
    df_merged = df_merged.drop(columns=['TC_CHECK_TEMP'])

    return df_merged, updated_count, added_count, invalid_tc_df, df_updated_records

# UI Tasarımı
st.title("📊 Excel Kayıt Birleştirme Aracı")
st.markdown("""
- Yüklediğiniz dosyalar **sunucuya kaydedilmez**, işlem bittiğinde veya sayfayı yenilediğinizde sistemden silinir.
- Yeni ay için **birden fazla Excel dosyasını** aynı anda seçip yükleyebilirsiniz. Sistem onları otomatik olarak birleştirecektir.
- 💡 *Sistem kayıtları birleştirirken "TC Kimlik No", "Ad Soyad" ve "Konu" eşleşmesine bakar. Aynı kişinin farklı konulardaki itirazları ayrı kayıtlar olarak korunur.*
""")

col1, col2 = st.columns(2)

with col1:
    old_file = st.file_uploader("📂 Eski Versiyon Excel (Master Dosya)", type=['xlsx', 'xls'])

with col2:
    new_files = st.file_uploader("🆕 Yeni Excel Dosyaları (Birden fazla seçilebilir)", type=['xlsx', 'xls'], accept_multiple_files=True)

if old_file is not None and len(new_files) > 0:
    if st.button("🚀 Verileri Birleştir"):
        with st.spinner("Excel dosyaları okunuyor ve birleştiriliyor..."):
            try:
                df_old = pd.read_excel(old_file)
                
                list_of_new_dfs = []
                for file in new_files:
                    list_of_new_dfs.append(pd.read_excel(file))
                
                df_merged, updated_count, added_count, invalid_tc_df, df_updated_records = process_data(df_old, list_of_new_dfs)
                
                if df_merged is not None:
                    st.success("İşlem başarıyla tamamlandı!")
                    
                    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                    mcol1.metric("İşlenen Yeni Dosya", len(new_files))
                    mcol2.metric("Güncellenen Kayıt", updated_count)
                    mcol3.metric("Yeni Eklenen Kayıt", added_count)
                    mcol4.metric("Toplam Çıktı Kayıt", len(df_merged))
                    
                    if not df_updated_records.empty:
                        with st.expander(f"🔄 Güncellenen (Üzerine Yazılan) {updated_count} Kaydı İncele"):
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
