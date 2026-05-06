import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Excel Kayıt Birleştirme Aracı", page_icon="📊", layout="wide")

def clean_tc(tc):
    """TC Kimlik numarasını temizler ve string'e çevirir."""
    if pd.isna(tc):
        return ""
    return str(tc).replace('.0', '').strip()

def clean_name(name):
    """Ad Soyad bilgisini standartlaştırmak için temizler."""
    if pd.isna(name):
        return ""
    return str(name).strip().upper()

def process_data(df_old, df_new):
    required_cols = ['İTİRAZ KONUSU KİŞİNİN ADI SOYADI', 'İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO']
    
    # Kolon kontrolü
    for col in required_cols:
        if col not in df_old.columns or col not in df_new.columns:
            st.error(f"Kritik hata: '{col}' kolonu dosyalarda bulunamadı!")
            return None, None, None, None

    # Eşleştirme yapabilmek için geçici (standartlaştırılmış) anahtar kolonlar ekliyoruz
    df_old['TEMP_TC'] = df_old['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    df_old['TEMP_AD'] = df_old['İTİRAZ KONUSU KİŞİNİN ADI SOYADI'].apply(clean_name)
    
    df_new['TEMP_TC'] = df_new['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    df_new['TEMP_AD'] = df_new['İTİRAZ KONUSU KİŞİNİN ADI SOYADI'].apply(clean_name)

    # İndeksleri bu anahtarlara göre kuruyoruz
    df_old_indexed = df_old.set_index(['TEMP_TC', 'TEMP_AD'])
    df_new_indexed = df_new.set_index(['TEMP_TC', 'TEMP_AD'])

    # İstatistikleri hesaplama
    old_keys = set(df_old_indexed.index)
    new_keys = set(df_new_indexed.index)
    
    updated_count = len(new_keys.intersection(old_keys))
    added_count = len(new_keys - old_keys)

    # MAGIC METHOD: combine_first
    # Yeni veri setini baz alır. Eğer yeni veri setinde bir hücre boşsa, 
    # o hücreyi eski veri setindeki eşleşen kayıtla doldurur. 
    # Ayrıca eski veya yeni veri setinde olup diğerinde olmayan satırları da birleştirir.
    df_merged_indexed = df_new_indexed.combine_first(df_old_indexed)

    # Geçici indeksleri kaldırıp veriyi normalleştiriyoruz
    df_merged = df_merged_indexed.reset_index(drop=True)

    # Hatalı/Eksik TC kontrolü (11 karakter ve sadece rakam olmalı)
    df_merged['TC_CHECK_TEMP'] = df_merged['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    invalid_tc_df = df_merged[~df_merged['TC_CHECK_TEMP'].str.match(r'^\d{11}$')]
    df_merged = df_merged.drop(columns=['TC_CHECK_TEMP'])

    return df_merged, updated_count, added_count, invalid_tc_df

# UI Tasarımı
st.title("📊 Excel Kayıt Birleştirme Aracı")
st.markdown("Eski ana Excel dosyanızı ve bu ayın yeni Excel dosyasını yükleyin. Sistem eşleşen kayıtları güncelleyerek eksik verileri tamamlayacaktır.")

col1, col2 = st.columns(2)

with col1:
    old_file = st.file_uploader("📂 Eski Versiyon Excel (Master Dosya)", type=['xlsx', 'xls'])

with col2:
    new_file = st.file_uploader("🆕 Yeni Ay Excel Dosyası (Güncel Dosya)", type=['xlsx', 'xls'])

if old_file is not None and new_file is not None:
    if st.button("🚀 Verileri Birleştir"):
        with st.spinner("Excel dosyaları okunuyor ve birleştiriliyor..."):
            try:
                df_old = pd.read_excel(old_file)
                df_new = pd.read_excel(new_file)
                
                df_merged, updated_count, added_count, invalid_tc_df = process_data(df_old, df_new)
                
                if df_merged is not None:
                    st.success("İşlem başarıyla tamamlandı!")
                    
                    # Metrikler
                    mcol1, mcol2, mcol3 = st.columns(3)
                    mcol1.metric("Güncellenen (Eşleşen) Kayıt", updated_count)
                    mcol2.metric("Yeni Eklenen Kayıt", added_count)
                    mcol3.metric("Toplam Çıktı Kayıt Sayısı", len(df_merged))
                    
                    # Hatalı TC Uyarıları
                    if not invalid_tc_df.empty:
                        st.warning(f"⚠️ Dikkat: {len(invalid_tc_df)} kayıtta hatalı veya eksik TC Kimlik No tespit edildi (11 hane olmalı).")
                        with st.expander("Hatalı TC Numarasına Sahip Kayıtları İncele"):
                            st.dataframe(invalid_tc_df[['İTİRAZ KONUSU KİŞİNİN ADI SOYADI', 'İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO']])
                    else:
                        st.info("✅ Tüm kayıtların TC Kimlik Numarası formatı doğru (11 Hane).")

                    # Excel Çıktısını Hazırlama
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
