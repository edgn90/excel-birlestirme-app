import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Excel Akıllı Birleştirme", page_icon="📊", layout="wide")

# Virgülle birleştirilmesi istenen özel kolonlar
CONCAT_COLS = [
    'PERFORMANS DÖNEMİ', 'DaBT-İPA-Hib-Hep-B', 'HEP B', 'BCG', 'KKK', 
    'HEP A', 'KPA', 'OPA', 'SU ÇİÇEĞİ', 'DaBT-İPA', 'TD', 
    'İTİRAZ NEDENİ', 'ASM RET NEDENİ', 'İLÇE SAĞLIK RET NEDENİ'
]

def clean_tc(tc):
    if pd.isna(tc): return ""
    return str(tc).replace('.0', '').strip()

def clean_text(text):
    if pd.isna(text): return ""
    return str(text).strip().upper()

def smart_join(x):
    """Aynı hücredeki değerleri virgülle birleştirir, tekrarları siler."""
    parts = []
    for val in x:
        if pd.notna(val) and str(val).strip() != "" and str(val).lower() != "nan":
            parts.append(str(val).strip())
    # Benzersiz değerleri koruyarak birleştir
    return ", ".join(dict.fromkeys(parts))

def process_data(list_of_old_dfs, df_new):
    key_cols = ['İTİRAZ KONUSU KİŞİNİN ADI SOYADI', 'İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO', 'KONU']
    
    # 1. Eski dosyaları birleştir ve anahtar oluştur
    df_old_all = pd.concat(list_of_old_dfs, ignore_index=True)
    
    for df in [df_old_all, df_new]:
        df['TEMP_TC'] = df['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
        df['TEMP_AD'] = df['İTİRAZ KONUSU KİŞİNİN ADI SOYADI'].apply(clean_text)
        df['TEMP_KONU'] = df['KONU'].apply(clean_text)

    temp_keys = ['TEMP_TC', 'TEMP_AD', 'TEMP_KONU']

    # 2. Yeni dosyada olmayan ama eskide olanları ayır (Sadece ekleme olacaklar)
    # 3. Hem eskide hem yenide olanları bul (Güncelleme ve birleştirme yapılacaklar)
    
    # Yeni veri setini baz alarak birleştirme işlemi
    # Left join ile yeni verinin iskeletini koruyoruz
    merged = pd.merge(
        df_new, 
        df_old_all, 
        on=temp_keys, 
        how='left', 
        suffixes=('', '_old')
    )

    # İstatistikler için
    old_keys = set(zip(df_old_all['TEMP_TC'], df_old_all['TEMP_AD'], df_old_all['TEMP_KONU']))
    new_keys = set(zip(df_new['TEMP_TC'], df_new['TEMP_AD'], df_new['TEMP_KONU']))
    updated_keys_count = len(new_keys.intersection(old_keys))
    added_keys_count = len(new_keys - old_keys)

    # Birleştirme Mantığı Uygulaması
    final_rows = []
    
    # Tüm kolonları belirle (Yeni dosyandaki kolon sıralamasını korumak için)
    all_columns = df_new.columns.tolist()
    
    for _, row in merged.iterrows():
        new_row = row.copy()
        
        # Eğer bu kayıt eski dosyalarda da varsa (eşleşme olduysa)
        if pd.notna(row['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO_old']):
            for col in all_columns:
                if col in temp_keys: continue
                
                old_col_name = f"{col}_old"
                val_new = row[col]
                val_old = row[old_col_name] if old_col_name in row else None

                # Kural 1: Özel kolonlarda virgülle birleştir
                if col in CONCAT_COLS:
                    new_row[col] = smart_join([val_old, val_new])
                
                # Kural 2: Diğer kolonlarda yeni boşsa eskiyi al
                else:
                    if pd.isna(val_new) or str(val_new).strip() == "":
                        new_row[col] = val_old
        
        final_rows.append(new_row)

    df_final = pd.DataFrame(final_rows)[all_columns]

    # Eskide olup yenide hiç olmayan kayıtları da sonuna ekle (Veri kaybı olmaması için)
    df_only_old = df_old_all[~df_old_all.set_index(temp_keys).index.isin(df_new.set_index(temp_keys).index)]
    df_result = pd.concat([df_final, df_only_old[df_new.columns]], ignore_index=True)

    # Temizlik ve Hata Kontrolü
    df_result['TC_CHECK_TEMP'] = df_result['İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO'].apply(clean_tc)
    invalid_tc_df = df_result[~df_result['TC_CHECK_TEMP'].str.match(r'^\d{11}$')]
    df_result = df_result.drop(columns=['TC_CHECK_TEMP', 'TEMP_TC', 'TEMP_AD', 'TEMP_KONU'])

    return df_result, updated_keys_count, added_keys_count, invalid_tc_df

# UI Tasarımı
st.title("🚀 Gelişmiş Excel Birleştirme ve Veri Tamamlama")
st.info("Bu sistem, yeni Excel'deki boşlukları eski verilerle doldurur ve belirli kolonlardaki verileri virgülle birleştirir.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📂 Eski Veri Havuzu")
    old_files = st.file_uploader("Geçmiş aylara ait Excel dosyaları (Birden fazla)", type=['xlsx'], accept_multiple_files=True)

with col2:
    st.subheader("🆕 Yeni Güncel Veri")
    new_file = st.file_uploader("İşlenecek son ayın Excel dosyası (Tek)", type=['xlsx'])

if len(old_files) > 0 and new_file is not None:
    if st.button("🔄 Verileri Analiz Et ve Birleştir"):
        try:
            with st.spinner("Karmaşık veri eşleştirme işlemi yapılıyor..."):
                list_of_old_dfs = [pd.read_excel(f) for f in old_files]
                df_new = pd.read_excel(new_file)
                
                df_result, updated_cnt, added_cnt, invalid_tc_df = process_data(list_of_old_dfs, df_new)
                
                st.success("İşlem Tamamlandı!")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Güncellenen/Birleşen", updated_cnt)
                c2.metric("Sıfırdan Eklenen", added_cnt)
                c3.metric("Toplam Kayıt", len(df_result))

                if not invalid_tc_df.empty:
                    st.warning(f"⚠️ {len(invalid_tc_df)} kayıtta hatalı TC tespit edildi.")

                # Excel hazırlama
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_result.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 Birleştirilmiş Excel'i İndir",
                    data=output.getvalue(),
                    file_name="Birlestirilmis_Guncel_Veri.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.error(f"Hata oluştu: {e}")
