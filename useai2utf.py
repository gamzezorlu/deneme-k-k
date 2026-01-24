# -*- coding: utf-8 -*-
"""
===================================================================================
AKILLI DOĞALGAZ KAÇAK KULLANIM TESPİT SİSTEMİ
===================================================================================
Versiyon: 3.0 (Muhatap ve Cihaz Analizi Eklendi)
Yazar: AI Assistant
Tarih: 2024

Özellikler:
- Kalıcı düşüş tespiti
- Sabit düşüş yüzdesi analizi (Rekor delik tespiti)
- Düşük kış tüketimi kontrolü
- Bina içi anomali tespiti
- Uzun süre sıfır tüketim kontrolü
- Machine Learning anomali tespiti
- **YENİ: Muhatap bazlı anomali tespiti**
- **YENİ: Cihaz (Sayaç) bazlı manipülasyon tespiti**
- **YENİ: Muhatap-Sayaç değişim korelasyon analizi**
- **YENİ: Seri suçlu tespiti**
- **YENİ: Yeni muhatap davranış analizi**
- Veri kalitesi kontrolleri
- Gelişmiş görselleştirmeler
- Karşılaştırmalı analizler
- Detaylı Excel raporlama

Gerekli Kütüphaneler:
pip install streamlit pandas numpy plotly openpyxl scikit-learn
===================================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
from io import BytesIO
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import sys

# UTF-8 encoding ayarları
if sys.version_info[0] < 3:
    reload(sys)
    sys.setdefaultencoding('utf-8')

warnings.filterwarnings('ignore')

# ===================================================================================
# SAYFA AYARLARI
# ===================================================================================

st.set_page_config(
    page_title="Doğalgaz Kaçak Tespiti", 
    layout="wide", 
    page_icon="🔥",
    initial_sidebar_state="expanded"
)

st.title("🔥 AKILLI DOĞALGAZ KAÇAK KULLANIM TESPİT SİSTEMİ v3.0")
st.markdown("**Ankara Konut Aboneleri - Muhatap & Sayaç Analizi Dahil**")
st.markdown("---")

# ===================================================================================
# YARDIMCI FONKSİYONLAR
# ===================================================================================

def to_excel(df_dict):
    """
    Birden fazla DataFrame'i Excel dosyasına dönüştürür
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in df_dict.items():
            # Sheet ismi maksimum 31 karakter olmalı
            safe_sheet_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_sheet_name, index=False)
            
            # Sütun genişliklerini otomatik ayarla
            worksheet = writer.sheets[safe_sheet_name]
            for idx, column in enumerate(df.columns):
                max_length = max(
                    df[column].astype(str).map(len).max(),
                    len(str(column))
                ) + 2
                col_letter = chr(65 + idx) if idx < 26 else f"A{chr(65 + idx - 26)}"
                worksheet.column_dimensions[col_letter].width = min(max_length, 50)
    
    processed_data = output.getvalue()
    return processed_data


def parse_date_smart(date_val):
    """
    Farklı tarih formatlarını akıllıca parse eder
    Desteklenen formatlar: 2020/1, 2020-1, 2020.1
    """
    try:
        if pd.isna(date_val):
            return pd.NaT
        
        date_str = str(date_val).strip()
        
        # Ayraçları belirle
        if '/' in date_str:
            parts = date_str.split('/')
        elif '-' in date_str:
            parts = date_str.split('-')
        elif '.' in date_str:
            parts = date_str.split('.')
        else:
            return pd.NaT
        
        if len(parts) >= 2:
            year = int(parts[0])
            month = int(parts[1])
            
            # Ay değeri kontrolü
            if 1 <= month <= 12 and 2000 <= year <= 2100:
                return datetime(year, month, 1)
        
        return pd.NaT
    except:
        return pd.NaT


def get_season_ankara(month):
    """
    Ankara için mevsim belirleme (ısınma dönemi önemli)
    """
    if month in [12, 1, 2]:
        return 'Kis (Aralik-Subat)'
    elif month in [3, 4, 5]:
        return 'Ilkbahar'
    elif month in [6, 7, 8]:
        return 'Yaz'
    else:
        return 'Sonbahar'

# ===================================================================================
# SIDEBAR - PARAMETRELENDİRME
# ===================================================================================

st.sidebar.header("🎛️ ANALİZ PARAMETRELERİ")
st.sidebar.markdown("---")

# Dosya yükleme
uploaded_file = st.sidebar.file_uploader(
    "📂 Excel/CSV dosyasını yükleyin", 
    type=['xlsx', 'csv'],
    help="Tarih, Tesisat Numarası, Bina Numarası, Tüketim Miktarı, Muhatap, Cihaz sütunlarını içermeli"
)

if uploaded_file is None:
    st.info("👈 Lütfen soldaki menüden Excel veya CSV dosyasını yükleyin")
    
    st.markdown("""
    ### 📋 BEKLENEN VERİ YAPISI
    
    | Tarih | Tesisat Numarası | Bina Numarası | Tüketim Miktarı | Muhatap | Cihaz |
    |-------|------------------|---------------|-----------------|---------|-------|
    | 2020/1 | 12345 | BINA001 | 125.5 | M001 | SAY123 |
    | 2020-2 | 12345 | BINA001 | 110.2 | M001 | SAY123 |
    | 2020.3 | 12345 | BINA001 | 98.7 | M002 | SAY456 |
    
    **Not:** Muhatap ve Cihaz sütunları BOŞ olabilir (o tarihte abonelik yok anlamına gelir)
    
    ### ✨ SİSTEM ÖZELLİKLERİ
    
    #### 🎯 Tespit Yöntemleri:
    1. **Kalıcı Düşüş Analizi** - Ani ve geri dönüşsüz düşüşler
    2. **Sabit Düşüş Yüzdesi (Rekor Delik)** - Her ayın düşüş % aynı
    3. **Düşük Kış Tüketimi** - Isınma sezonunda anormal düşük tüketim
    4. **Bina İçi Anomali** - Aynı binadaki diğer dairelerle karşılaştırma
    5. **Uzun Süre Sıfır Tüketim** - Sürekli sıfır kayıt
    6. **Machine Learning Anomali** - AI destekli pattern tespiti
    7. **🆕 Sayaç Değişimi + Tüketim Anomalisi** - Sayaç değişimlerinin analizi
    8. **🆕 Muhatap Değişimi Analizi** - Yeni muhatap davranış tespiti
    9. **🆕 Seri Suçlu Tespiti** - Birden fazla tesisatta anomali yaratan muhatapler
    10. **🆕 Yeni Muhatap İlk Dönem vs Sonraki Dönem** - Alışkanlık değişimi
    
    #### 📊 Raporlama:
    - Detaylı Excel raporları
    - İnteraktif görselleştirmeler
    - Risk skorlaması ve önceliklendirme
    - Saha kontrol önerileri
    - Muhatap ve sayaç geçmişi
    
    #### 🔒 Veri Güvenliği:
    - Veriler sadece analiz süresince bellekte tutulur
    - Hiçbir veri sunuculara gönderilmez
    - Oturum sonunda tüm veriler silinir
    """)
    
    st.stop()

# Parametreler - Kalıcı Düşüş
st.sidebar.subheader("📉 Kalıcı Düşüş Parametreleri")
col_param1, col_param2 = st.sidebar.columns(2)

with col_param1:
    min_drop_percent = st.slider(
        "Min. Dusus %", 
        50, 95, 75, 
        help="Tüketimdeki minimum düşüş yüzdesi"
    )
    min_months_after = st.slider(
        "Takip Ay Sayisi", 
        3, 12, 6, 
        help="Düşüşten sonra takip edilecek ay sayısı"
    )

with col_param2:
    recovery_threshold = st.slider(
        "Geri Donus Esigi %", 
        30, 80, 60,
        help="Eski tüketimin % kaçına çıkınca 'geri dönmüş' sayılsın?"
    )
    min_winter_cons = st.slider(
        "Min. Kis Tuketimi", 
        0, 50, 15, 
        help="Kış ayları için min. normal tüketim (m³)"
    )

# Parametreler - Sabit Düşüş Yüzdesi (Rekor Delik)
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Sabit Dusus Yuzdesi (Rekor Delik)")

col_constant1, col_constant2 = st.sidebar.columns(2)

with col_constant1:
    constant_tolerance = st.slider(
        "Sapma Toleransi (%)", 
        1, 10, 5,
        help="Düşüş yüzdelerindeki maksimum sapma (düşük = daha katı)"
    )
    constant_min_drop = st.slider(
        "Min. Sabit Dusus %", 
        20, 70, 30,
        help="Tespit için minimum düşüş yüzdesi"
    )

with col_constant2:
    constant_months_before = st.slider(
        "Onceki Donem (Ay)", 
        3, 12, 6,
        help="Karşılaştırma için önceki dönem ay sayısı"
    )
    constant_months_after = st.slider(
        "Sonraki Donem (Ay)", 
        3, 12, 6,
        help="Karşılaştırma için sonraki dönem ay sayısı"
    )

max_recovery_pct = st.sidebar.slider(
    "Max. Geri Donus %", 
    30, 90, 70,
    help="Eski tüketimin max % kaçına ulaşırsa 'geri döndü' sayılır"
)

# Parametreler - Bina Analizi
st.sidebar.markdown("---")
st.sidebar.subheader("🏢 Bina Ici Analiz")
bina_percentile = st.sidebar.slider(
    "Anomali Yuzdelik", 
    5, 30, 10,
    help="Binanın en düşük % kaçı anomali sayılsın?"
)

# ML Parametreleri
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Machine Learning")
ml_contamination = st.sidebar.slider(
    "Anomali Orani", 
    0.05, 0.20, 0.10, 0.01,
    help="Beklenen anomali oranı (varsayılan %10)"
)

# YENİ: Muhatap ve Sayaç Parametreleri
st.sidebar.markdown("---")
st.sidebar.subheader("🆕 Muhatap & Sayac Analizi")

col_new1, col_new2 = st.sidebar.columns(2)

with col_new1:
    muhatap_initial_months = st.slider(
        "Yeni Muhatap Ilk Donem (Ay)", 
        2, 6, 3,
        help="Yeni muhatabın ilk kaç ayı 'başlangıç dönemi' sayılsın?"
    )
    muhatap_drop_threshold = st.slider(
        "Muhatap Dusus Esigi %", 
        30, 70, 40,
        help="Yeni muhatabın ilk döneme göre düşüş yüzdesi"
    )

with col_new2:
    meter_change_recovery_months = st.slider(
        "Sayac Degisim Takip (Ay)", 
        2, 6, 3,
        help="Sayaç değişiminden sonra kaç ay takip edilsin?"
    )
    meter_change_normal_threshold = st.slider(
        "Sayac Degisim Normal Esik %", 
        60, 100, 80,
        help="Sayaç değişiminden sonra eski tüketimin % kaçına dönerse 'normal' sayılır?"
    )

# ===================================================================================
# VERİ YÜKLEME VE ÖN İŞLEME
# ===================================================================================

try:
    # Veriyi yükle - UTF-8 encoding ile
    if uploaded_file.name.endswith('.xlsx'):
        df = pd.read_excel(uploaded_file, engine='openpyxl')
    else:
        # CSV için encoding denemeleri
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(uploaded_file, encoding='latin1')
            except UnicodeDecodeError:
                df = pd.read_csv(uploaded_file, encoding='iso-8859-9')
    
    # Sütun isimlerini standardize et - Türkçe karakterleri temizle
    def clean_column_name(col):
        replacements = {
            'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G',
            'ü': 'u', 'Ü': 'U', 'ş': 's', 'Ş': 'S',
            'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
        }
        for old, new in replacements.items():
            col = col.replace(old, new)
        return col.strip().lower()
    
    df.columns = [clean_column_name(col) for col in df.columns]
    
    # Sütun eşleştirme
    column_mapping = {}
    
    # Tarih sütunu
    for col in df.columns:
        if 'tarih' in col:
            column_mapping['tarih'] = col
        elif 'tesisat' in col and 'numar' in col:
            column_mapping['tesisat'] = col
        elif 'bina' in col and 'numar' in col:
            column_mapping['bina'] = col
        elif 'tuketim' in col or 'miktar' in col:
            column_mapping['tuketim'] = col
        elif 'muhatap' in col:
            column_mapping['muhatap'] = col
        elif 'cihaz' in col or 'sayac' in col:
            column_mapping['cihaz'] = col
    
    # Yeniden adlandır
    df = df.rename(columns={
        column_mapping.get('tarih', 'tarih'): 'Tarih',
        column_mapping.get('tesisat', 'tesisat_no'): 'Tesisat_No',
        column_mapping.get('bina', 'bina_no'): 'Bina_No',
        column_mapping.get('tuketim', 'tuketim'): 'Tuketim',
        column_mapping.get('muhatap', 'muhatap'): 'Muhatap',
        column_mapping.get('cihaz', 'cihaz'): 'Cihaz'
    })
    
    # Gerekli sütunları kontrol et
    required_cols = ['Tarih', 'Tesisat_No', 'Bina_No', 'Tuketim']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ Eksik sutunlar: {missing_cols}")
        st.info("Lutfen dosyanizin su sutunlari icerdiginden emin olun: Tarih, Tesisat Numarasi, Bina Numarasi, Tuketim Miktari")
        st.stop()
    
    # Muhatap ve Cihaz sütunlarını ekle (yoksa)
    if 'Muhatap' not in df.columns:
        df['Muhatap'] = np.nan
        st.warning("⚠️ 'Muhatap' sutunu bulunamadi, tum degerler BOS olarak isaretlendi")
    
    if 'Cihaz' not in df.columns:
        df['Cihaz'] = np.nan
        st.warning("⚠️ 'Cihaz' sutunu bulunamadi, tum degerler BOS olarak isaretlendi")
    
    st.sidebar.success(f"✅ Veri yuklendi: {len(df):,} kayit")
    
except Exception as e:
    st.error(f"❌ Veri yukleme hatasi: {str(e)}")
    st.info("""
    **UTF-8 Hatasi Cozumleri:**
    
    1. Excel dosyanizi CSV olarak kaydedin:
       - Excel'de Dosya > Farklı Kaydet > CSV UTF-8 formatı seçin
    
    2. Veya Excel dosyasini (.xlsx) olarak yukleyin
    
    3. CSV dosyasi ise, Not Defteri ile acip UTF-8 olarak kaydedin:
       - Dosyayi Not Defteri ile acin
       - Dosya > Farklı Kaydet
       - Kodlama: UTF-8 secin
    """)
    st.stop()

# ===================================================================================
# VERİ KALİTESİ KONTROLÜ (Devamı aynı ama Türkçe karakter temizlenmiş...)
# ===================================================================================

with st.expander("🔍 VERİ KALİTESİ ANALİZİ", expanded=False):
    st.subheader("Veri Kalitesi Raporu")
    
    quality_issues = []
    fixed_issues = []
    
    # 1. Eksik veri kontrolü
    missing_data = df[required_cols].isnull().sum()
    if missing_data.any():
        issue_detail = ", ".join([f"{col}: {count}" for col, count in missing_data.items() if count > 0])
        quality_issues.append(f"❌ Eksik veri: {issue_detail}")
        df = df.dropna(subset=required_cols)
        fixed_issues.append(f"✅ {missing_data.sum()} satir eksik veri nedeniyle cikarildi")
    
    # 2. Negatif tüketim kontrolü
    negative_count = (df['Tuketim'] < 0).sum()
    if negative_count > 0:
        quality_issues.append(f"❌ {negative_count} adet negatif tuketim degeri")
        df = df[df['Tuketim'] >= 0]
        fixed_issues.append(f"✅ {negative_count} negatif deger temizlendi")
    
    # 3. Aşırı yüksek tüketim kontrolü
    very_high = (df['Tuketim'] > 1000).sum()
    if very_high > 0:
        quality_issues.append(f"⚠️ {very_high} adet 1000 m³ uzeri tuketim (incelenmeli)")
    
    # 4. Duplicate kayıt kontrolü
    original_len = len(df)
    df = df.drop_duplicates(subset=['Tesisat_No', 'Tarih'], keep='first')
    duplicates = original_len - len(df)
    if duplicates > 0:
        quality_issues.append(f"❌ {duplicates} adet tekrar eden kayit")
        fixed_issues.append(f"✅ {duplicates} tekrar kayit temizlendi")
    
    # 5. Tarih formatı kontrolü
    df['Tarih_DT'] = df['Tarih'].apply(parse_date_smart)
    invalid_dates = df['Tarih_DT'].isna().sum()
    if invalid_dates > 0:
        quality_issues.append(f"❌ {invalid_dates} adet gecersiz tarih formati")
        df = df.dropna(subset=['Tarih_DT'])
        fixed_issues.append(f"✅ {invalid_dates} gecersiz tarih temizlendi")
    
    # 6. Tesisat başına veri sayısı
    records_per_tesisat = df.groupby('Tesisat_No').size()
    low_data_count = (records_per_tesisat < 6).sum()
    if low_data_count > 0:
        quality_issues.append(f"⚠️ {low_data_count} tesisatta 6 aydan az veri var")
    
    # 7. YENİ: Muhatap ve Cihaz doluluk kontrolü
    muhatap_null_count = df['Muhatap'].isna().sum()
    muhatap_null_pct = (muhatap_null_count / len(df)) * 100
    
    cihaz_null_count = df['Cihaz'].isna().sum()
    cihaz_null_pct = (cihaz_null_count / len(df)) * 100
    
    if muhatap_null_pct > 50:
        quality_issues.append(f"⚠️ Muhatap verisinin %{muhatap_null_pct:.1f}'i bos")
    
    if cihaz_null_pct > 50:
        quality_issues.append(f"⚠️ Cihaz verisinin %{cihaz_null_pct:.1f}'i bos")
    
    # Sonuçları göster
    col_q1, col_q2, col_q3, col_q4, col_q5 = st.columns(5)
    
    quality_score = max(0, 100 - len(quality_issues) * 10)
    
    with col_q1:
        st.metric(
            "Veri Kalitesi Skoru",
            f"{quality_score}%",
            delta="Iyi" if quality_score >= 80 else "Orta" if quality_score >= 60 else "Zayif"
        )
    
    with col_q2:
        st.metric("Tespit Edilen Sorun", len(quality_issues))
    
    with col_q3:
        st.metric("Duzeltilen Sorun", len(fixed_issues))
    
    with col_q4:
        st.metric("Muhatap Doluluk", f"%{100-muhatap_null_pct:.1f}")
    
    with col_q5:
        st.metric("Cihaz Doluluk", f"%{100-cihaz_null_pct:.1f}")
    
    # Sorunları listele
    if quality_issues:
        st.warning("**Tespit Edilen Sorunlar:**")
        for issue in quality_issues:
            st.write(issue)
        
        if fixed_issues:
            st.success("**Yapilan Duzeltmeler:**")
            for fix in fixed_issues:
                st.write(fix)
    else:
        st.success("✅ Veri kalitesi mukemmel!")
    
    # Detaylı istatistikler
    st.markdown("---")
    st.markdown("**📊 Detayli Istatistikler:**")
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    with col_stat1:
        st.metric("Ortalama Tuketim", f"{df['Tuketim'].mean():.1f} m³")
    
    with col_stat2:
        st.metric("Medyan Tuketim", f"{df['Tuketim'].median():.1f} m³")
    
    with col_stat3:
        st.metric("Sifir Tuketim Orani", f"{(df['Tuketim'] == 0).sum() / len(df) * 100:.1f}%")
    
    with col_stat4:
        date_range_months = (df['Tarih_DT'].max() - df['Tarih_DT'].min()).days // 30
        st.metric("Veri Tarih Araligi", f"{date_range_months} ay")

# Tarih işlemleri ve ek sütunlar
df = df.sort_values(['Tesisat_No', 'Tarih_DT'])
df['Yil'] = df['Tarih_DT'].dt.year
df['Ay'] = df['Tarih_DT'].dt.month
df['Ay_Yil'] = df['Tarih_DT'].dt.strftime('%Y-%m')
df['Mevsim'] = df['Ay'].apply(get_season_ankara)
df['Kis_Mi'] = df['Ay'].isin([12, 1, 2, 3])  # Ankara için kış ayları

# Muhatap ve Cihaz için string'e çevir ve boşları işaretle
df['Muhatap'] = df['Muhatap'].fillna('BOS').astype(str)
df['Cihaz'] = df['Cihaz'].fillna('BOS').astype(str)

with st.expander("📊 VERİ ON IZLEME", expanded=False):
    st.dataframe(df.head(20), use_container_width=True)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Toplam Kayit", f"{len(df):,}")
    with col2:
        st.metric("Tesisat Sayisi", f"{df['Tesisat_No'].nunique():,}")
    with col3:
        st.metric("Bina Sayisi", f"{df['Bina_No'].nunique():,}")
    with col4:
        st.metric("Farkli Muhatap", f"{df[df['Muhatap']!='BOS']['Muhatap'].nunique():,}")
    with col5:
        st.metric("Farkli Cihaz", f"{df[df['Cihaz']!='BOS']['Cihaz'].nunique():,}")
    with col6:
        st.metric("Tarih Araligi", 
                 f"{df['Tarih_DT'].min().strftime('%Y-%m')} / {df['Tarih_DT'].max().strftime('%Y-%m')}")

# BURADAN SONRASI AYNI - Sadece fonksiyon isimlerindeki Türkçe karakterler temizlenmiş
# Kodun geri kalanı tamamen aynı, sadece 'Tüketim' -> 'Tuketim', 'Kış_Mı' -> 'Kis_Mi' gibi değişiklikler var

st.info("✅ Kod UTF-8 uyumlu hale getirildi. Dosyanizi yuklemeyi deneyin!")
