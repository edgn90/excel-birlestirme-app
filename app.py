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

def process_data(df_old, list_of_new_dfs):
    required_cols = ['İTİRAZ KONUSU KİŞİNİN ADI SOYADI', 'İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO']
    
    # Yüklenen tüm yeni Excel'leri tek bir veri setinde birleştir
    if not list_of_new_dfs:
        return None, 0, 0, None
        
    df_new = pd.concat(list_of_new_dfs, ignore_index=True)
    
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

    # Yeni yüklenen dosyaların içinde aynı kişi birden fazla kez geçiyorsa, sonuncuyu geçerli say (çakışmayı önlemek için)
    df_new = df_new.drop_duplicates(subset=['TEMP_TC', 'TEMP_AD'], keep='last')

    # İndeksleri bu anahtarlara göre kuruyoruz
    df_old_indexed = df_old.set_index(['TEMP_TC', 'TEMP_AD'])
    df_new_indexed = df_new.set_index(['TEMP_TC', 'TEMP_AD'])

    # İstatistikleri hesaplama
    old_keys = set(df_old_indexed.index)
    new_keys = set(df_new_indexed.index)
    
    updated_count = len(new_keys.intersection(old_keys))
    added_count = len(new_keys - old_keys)

    # MAGIC METHOD: combine_first
    # Yeni veri setini baz alır. Boş hücreleri eski veri setiyle doldurur.
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
st.markdown("""
- Yüklediğiniz dosyalar **sunucuya kaydedilmez**, işlem bittiğinde veya
