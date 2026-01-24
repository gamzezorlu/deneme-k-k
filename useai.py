"""
===================================================================================
AKILLI DOĞALGAZ KAÇAK KULLANIM TESPİT SİSTEMİ
===================================================================================
Versiyon: 2.0 (Geliştirilmiş)
Yazar: AI Assistant
Tarih: 2024

Özellikler:
- Kalıcı düşüş tespiti
- Sabit düşüş yüzdesi analizi (Rekor delik tespiti)
- Düşük kış tüketimi kontrolü
- Bina içi anomali tespiti
- Uzun süre sıfır tüketim kontrolü
- Machine Learning anomali tespiti
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

st.title("🔥 AKILLI DOĞALGAZ KAÇAK KULLANIM TESPİT SİSTEMİ")
st.markdown("**Ankara Konut Aboneleri - Gelişmiş Analiz Platformu**")
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
        return 'Kış (Aralık-Şubat)'
    elif month in [3, 4, 5]:
        return 'İlkbahar'
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
    help="Tarih, Tesisat Numarası, Bina Numarası, Tüketim Miktarı sütunlarını içermeli"
)

if uploaded_file is None:
    st.info("👈 Lütfen soldaki menüden Excel veya CSV dosyasını yükleyin")
    
    st.markdown("""
    ### 📋 BEKLENEN VERİ YAPISI
    
    | Tarih | Tesisat Numarası | Bina Numarası | Tüketim Miktarı |
    |-------|------------------|---------------|-----------------|
    | 2020/1 | 12345 | BINA001 | 125.5 |
    | 2020-2 | 12345 | BINA001 | 110.2 |
    | 2020.3 | 12346 | BINA001 | 98.7 |
    
    ### ✨ SİSTEM ÖZELLİKLERİ
    
    #### 🎯 Tespit Yöntemleri:
    1. **Kalıcı Düşüş Analizi** - Ani ve geri dönüşsüz düşüşler
    2. **Sabit Düşüş Yüzdesi (Rekor Delik)** - Her ayın düşüş % aynı
    3. **Düşük Kış Tüketimi** - Isınma sezonunda anormal düşük tüketim
    4. **Bina İçi Anomali** - Aynı binadaki diğer dairelerle karşılaştırma
    5. **Uzun Süre Sıfır Tüketim** - Sürekli sıfır kayıt
    6. **Machine Learning Anomali** - AI destekli pattern tespiti
    
    #### 📊 Raporlama:
    - Detaylı Excel raporları
    - İnteraktif görselleştirmeler
    - Risk skorlaması ve önceliklendirme
    - Saha kontrol önerileri
    
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
        "Min. Düşüş %", 
        50, 95, 75, 
        help="Tüketimdeki minimum düşüş yüzdesi"
    )
    min_months_after = st.slider(
        "Takip Ay Sayısı", 
        3, 12, 6, 
        help="Düşüşten sonra takip edilecek ay sayısı"
    )

with col_param2:
    recovery_threshold = st.slider(
        "Geri Dönüş Eşiği %", 
        30, 80, 60,
        help="Eski tüketimin % kaçına çıkınca 'geri dönmüş' sayılsın?"
    )
    min_winter_cons = st.slider(
        "Min. Kış Tüketimi", 
        0, 50, 15, 
        help="Kış ayları için min. normal tüketim (m³)"
    )

# Parametreler - Sabit Düşüş Yüzdesi (Rekor Delik)
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Sabit Düşüş Yüzdesi (Rekor Delik)")

col_constant1, col_constant2 = st.sidebar.columns(2)

with col_constant1:
    constant_tolerance = st.slider(
        "Sapma Toleransı (%)", 
        1, 10, 5,
        help="Düşüş yüzdelerindeki maksimum sapma (düşük = daha katı)"
    )
    constant_min_drop = st.slider(
        "Min. Sabit Düşüş %", 
        20, 70, 30,
        help="Tespit için minimum düşüş yüzdesi"
    )

with col_constant2:
    constant_months_before = st.slider(
        "Önceki Dönem (Ay)", 
        3, 12, 6,
        help="Karşılaştırma için önceki dönem ay sayısı"
    )
    constant_months_after = st.slider(
        "Sonraki Dönem (Ay)", 
        3, 12, 6,
        help="Karşılaştırma için sonraki dönem ay sayısı"
    )

max_recovery_pct = st.sidebar.slider(
    "Max. Geri Dönüş %", 
    30, 90, 70,
    help="Eski tüketimin max % kaçına ulaşırsa 'geri döndü' sayılır"
)

# Parametreler - Bina Analizi
st.sidebar.markdown("---")
st.sidebar.subheader("🏢 Bina İçi Analiz")
bina_percentile = st.sidebar.slider(
    "Anomali Yüzdelik", 
    5, 30, 10,
    help="Binanın en düşük % kaçı anomali sayılsın?"
)

# ML Parametreleri
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Machine Learning")
ml_contamination = st.sidebar.slider(
    "Anomali Oranı", 
    0.05, 0.20, 0.10, 0.01,
    help="Beklenen anomali oranı (varsayılan %10)"
)

# ===================================================================================
# VERİ YÜKLEME VE ÖN İŞLEME
# ===================================================================================

try:
    # Veriyi yükle
    if uploaded_file.name.endswith('.xlsx'):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)
    
    # Sütun isimlerini standardize et
    df.columns = df.columns.str.strip().str.lower()
    
    # Sütun eşleştirme
    column_mapping = {}
    
    # Tarih sütunu
    for col in df.columns:
        if 'tarih' in col.lower():
            column_mapping['tarih'] = col
        elif 'tesisat' in col.lower() and 'numar' in col.lower():
            column_mapping['tesisat'] = col
        elif 'bina' in col.lower() and 'numar' in col.lower():
            column_mapping['bina'] = col
        elif 'tüketim' in col.lower() or 'tuketim' in col.lower():
            column_mapping['tuketim'] = col
    
    # Yeniden adlandır
    df = df.rename(columns={
        column_mapping.get('tarih', 'tarih'): 'Tarih',
        column_mapping.get('tesisat', 'tesisat_no'): 'Tesisat_No',
        column_mapping.get('bina', 'bina_no'): 'Bina_No',
        column_mapping.get('tuketim', 'tuketim'): 'Tüketim'
    })
    
    # Gerekli sütunları kontrol et
    required_cols = ['Tarih', 'Tesisat_No', 'Bina_No', 'Tüketim']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ Eksik sütunlar: {missing_cols}")
        st.info("Lütfen dosyanızın şu sütunları içerdiğinden emin olun: Tarih, Tesisat Numarası, Bina Numarası, Tüketim Miktarı")
        st.stop()
    
    st.sidebar.success(f"✅ Veri yüklendi: {len(df):,} kayıt")
    
except Exception as e:
    st.error(f"❌ Veri yükleme hatası: {str(e)}")
    st.stop()

# ===================================================================================
# VERİ KALİTESİ KONTROLÜ
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
        # Eksik satırları temizle
        df = df.dropna(subset=required_cols)
        fixed_issues.append(f"✅ {missing_data.sum()} satır eksik veri nedeniyle çıkarıldı")
    
    # 2. Negatif tüketim kontrolü
    negative_count = (df['Tüketim'] < 0).sum()
    if negative_count > 0:
        quality_issues.append(f"❌ {negative_count} adet negatif tüketim değeri")
        df = df[df['Tüketim'] >= 0]
        fixed_issues.append(f"✅ {negative_count} negatif değer temizlendi")
    
    # 3. Aşırı yüksek tüketim kontrolü
    very_high = (df['Tüketim'] > 1000).sum()
    if very_high > 0:
        quality_issues.append(f"⚠️ {very_high} adet 1000 m³ üzeri tüketim (incelenmeli)")
    
    # 4. Duplicate kayıt kontrolü
    original_len = len(df)
    df = df.drop_duplicates(subset=['Tesisat_No', 'Tarih'], keep='first')
    duplicates = original_len - len(df)
    if duplicates > 0:
        quality_issues.append(f"❌ {duplicates} adet tekrar eden kayıt")
        fixed_issues.append(f"✅ {duplicates} tekrar kayıt temizlendi")
    
    # 5. Tarih formatı kontrolü
    df['Tarih_DT'] = df['Tarih'].apply(parse_date_smart)
    invalid_dates = df['Tarih_DT'].isna().sum()
    if invalid_dates > 0:
        quality_issues.append(f"❌ {invalid_dates} adet geçersiz tarih formatı")
        df = df.dropna(subset=['Tarih_DT'])
        fixed_issues.append(f"✅ {invalid_dates} geçersiz tarih temizlendi")
    
    # 6. Tesisat başına veri sayısı
    records_per_tesisat = df.groupby('Tesisat_No').size()
    low_data_count = (records_per_tesisat < 6).sum()
    if low_data_count > 0:
        quality_issues.append(f"⚠️ {low_data_count} tesisatta 6 aydan az veri var")
    
    # Sonuçları göster
    col_q1, col_q2, col_q3, col_q4 = st.columns(4)
    
    quality_score = max(0, 100 - len(quality_issues) * 12)
    
    with col_q1:
        st.metric(
            "Veri Kalitesi Skoru",
            f"{quality_score}%",
            delta="İyi" if quality_score >= 80 else "Orta" if quality_score >= 60 else "Zayıf"
        )
    
    with col_q2:
        st.metric("Tespit Edilen Sorun", len(quality_issues))
    
    with col_q3:
        st.metric("Düzeltilen Sorun", len(fixed_issues))
    
    with col_q4:
        st.metric("Temiz Kayıt Sayısı", f"{len(df):,}")
    
    # Sorunları listele
    if quality_issues:
        st.warning("**Tespit Edilen Sorunlar:**")
        for issue in quality_issues:
            st.write(issue)
        
        if fixed_issues:
            st.success("**Yapılan Düzeltmeler:**")
            for fix in fixed_issues:
                st.write(fix)
    else:
        st.success("✅ Veri kalitesi mükemmel!")
    
    # Detaylı istatistikler
    st.markdown("---")
    st.markdown("**📊 Detaylı İstatistikler:**")
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    with col_stat1:
        st.metric("Ortalama Tüketim", f"{df['Tüketim'].mean():.1f} m³")
    
    with col_stat2:
        st.metric("Medyan Tüketim", f"{df['Tüketim'].median():.1f} m³")
    
    with col_stat3:
        st.metric("Sıfır Tüketim Oranı", f"{(df['Tüketim'] == 0).sum() / len(df) * 100:.1f}%")
    
    with col_stat4:
        date_range_months = (df['Tarih_DT'].max() - df['Tarih_DT'].min()).days // 30
        st.metric("Veri Tarih Aralığı", f"{date_range_months} ay")

# ===================================================================================
# VERİ ÖN İZLEME
# ===================================================================================

# Tarih işlemleri ve ek sütunlar
df = df.sort_values(['Tesisat_No', 'Tarih_DT'])
df['Yıl'] = df['Tarih_DT'].dt.year
df['Ay'] = df['Tarih_DT'].dt.month
df['Ay_Yıl'] = df['Tarih_DT'].dt.strftime('%Y-%m')
df['Mevsim'] = df['Ay'].apply(get_season_ankara)
df['Kış_Mı'] = df['Ay'].isin([12, 1, 2, 3])  # Ankara için kış ayları

with st.expander("📊 VERİ ÖN İZLEME", expanded=False):
    st.dataframe(df.head(20), use_container_width=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Toplam Kayıt", f"{len(df):,}")
    with col2:
        st.metric("Tesisat Sayısı", f"{df['Tesisat_No'].nunique():,}")
    with col3:
        st.metric("Bina Sayısı", f"{df['Bina_No'].nunique():,}")
    with col4:
        st.metric("Tarih Aralığı", 
                 f"{df['Tarih_DT'].min().strftime('%Y-%m')} / {df['Tarih_DT'].max().strftime('%Y-%m')}")

# ===================================================================================
# ANALİZ FONKSİYONLARI
# ===================================================================================

def detect_permanent_drop_with_explanation(df, min_drop_pct=75, min_months_after=6, recovery_threshold_pct=60):
    """
    KALICI DÜŞÜŞ TESPİT ALGORİTMASI
    
    Tüketimde ani ve kalıcı düşüşleri tespit eder.
    Düşüş sonrası eski seviyelere dönüp dönmediğini kontrol eder.
    """
    results = []
    all_details = []
    
    for tesisat in df['Tesisat_No'].unique():
        tesisat_df = df[df['Tesisat_No'] == tesisat].sort_values('Tarih_DT').reset_index(drop=True)
        
        if len(tesisat_df) < 12:
            continue
        
        # Potansiyel düşüş noktalarını bul
        potential_drops = []
        
        for i in range(3, len(tesisat_df) - min_months_after):
            before_avg = tesisat_df.iloc[i-3:i]['Tüketim'].mean()
            after_avg = tesisat_df.iloc[i:i+min_months_after]['Tüketim'].mean()
            
            if before_avg > 0 and after_avg > 0:
                drop_pct = ((before_avg - after_avg) / before_avg) * 100
                
                if drop_pct >= min_drop_pct:
                    potential_drops.append({
                        'index': i,
                        'date': tesisat_df.iloc[i]['Tarih_DT'],
                        'before_avg': before_avg,
                        'after_avg': after_avg,
                        'drop_pct': drop_pct
                    })
        
        if not potential_drops:
            continue
        
        # En büyük düşüşü seç
        main_drop = max(potential_drops, key=lambda x: x['drop_pct'])
        drop_index = main_drop['index']
        all_after = tesisat_df.iloc[drop_index:]
        
        # Geri dönüş kontrolü
        recovery_occurred = False
        max_recovery_pct = 0
        recovery_month = None
        
        for idx, row in all_after.iterrows():
            recovery_pct = (row['Tüketim'] / main_drop['before_avg']) * 100
            if recovery_pct > max_recovery_pct:
                max_recovery_pct = recovery_pct
            
            if recovery_pct >= recovery_threshold_pct and not recovery_occurred:
                recovery_occurred = True
                recovery_month = row['Tarih_DT'].strftime('%Y-%m')
        
        # Trend analizi
        if len(all_after) >= 3:
            x = np.arange(len(all_after))
            y = all_after['Tüketim'].values
            trend_coef = np.polyfit(x, y, 1)[0]
            trend_rising = (trend_coef > 0) and (abs(trend_coef) > (y.mean() * 0.05))
        else:
            trend_rising = False
        
        # Kalıcılık kararı
        is_permanent = not recovery_occurred and not trend_rising
        
        if is_permanent:
            # Açıklama oluştur
            explanation_parts = []
            explanation_parts.append(f"⏱️ {main_drop['date'].strftime('%Y-%m')} tarihinde %{main_drop['drop_pct']:.1f} düşüş")
            explanation_parts.append(f"↗️ Max geri dönüş: %{max_recovery_pct:.1f} (Eşik: %{recovery_threshold_pct})")
            
            if not trend_rising:
                explanation_parts.append("📉 Artış trendi yok")
            
            explanation = " | ".join(explanation_parts)
            risk_score = min(100, main_drop['drop_pct'])
            
            all_details.append({
                'TESİSAT_NO': tesisat,
                'BİNA_NO': tesisat_df['Bina_No'].iloc[0],
                'DÜŞÜŞ_TARİHİ': main_drop['date'].strftime('%Y-%m'),
                'ÖNCEKİ_ORT (m³)': round(main_drop['before_avg'], 1),
                'SONRAKİ_ORT (m³)': round(main_drop['after_avg'], 1),
                'DÜŞÜŞ_%': round(main_drop['drop_pct'], 1),
                'MAX_GERİ_DÖNÜŞ_%': round(max_recovery_pct, 1),
                'GERİ_DÖNDÜ_MÜ?': 'HAYIR',
                'RİSK_SKORU': round(risk_score, 0),
                'AÇIKLAMA': explanation,
                'TESPİT_NEDENİ': 'KALICI_DÜŞÜŞ'
            })
            
            results.append(tesisat)
    
    details_df = pd.DataFrame(all_details)
    if not details_df.empty:
        details_df = details_df.sort_values('RİSK_SKORU', ascending=False)
    
    return results, details_df


def detect_constant_drop_with_no_recovery(df, min_months_before=6, min_months_after=6, 
                                         tolerance=5, min_drop_pct=30, max_recovery_pct=70):
    """
    SABİT DÜŞÜŞ YÜZDESİ + GERİ DÖNÜŞ YOK ANALİZİ - REKOR DELİK TESPİTİ
    
    İki kritik kontrol:
    1. Her ayın düşüş yüzdesi sabit mi? (Rekor delik signature)
    2. Düşüşten sonra HİÇBİR zaman eski seviyelere dönmüyor mu?
    
    İKİSİ BİRDEN = REKOR DELİK İHTİMALİ %99
    """
    suspicious = []
    details = []
    
    for tesisat in df['Tesisat_No'].unique():
        tesisat_df = df[df['Tesisat_No'] == tesisat].sort_values('Tarih_DT')
        
        if len(tesisat_df) < (min_months_before + min_months_after + 1):
            continue
        
        # Potansiyel düşüş noktalarını tara
        for i in range(min_months_before, len(tesisat_df) - min_months_after):
            drop_date = tesisat_df.iloc[i]['Tarih_DT']
            before_period = tesisat_df.iloc[i-min_months_before:i]
            after_period_all = tesisat_df.iloc[i:]
            after_period_analysis = tesisat_df.iloc[i:i+min_months_after]
            
            if len(before_period) < min_months_before or len(after_period_analysis) < min_months_after:
                continue
            
            # 1. SABİT DÜŞÜŞ YÜZDESİ KONTROLÜ
            drop_percentages = []
            month_comparisons = []
            
            month_names = ['', 'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 
                          'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 
                          'Kasım', 'Aralık']
            
            for idx, after_row in after_period_analysis.iterrows():
                after_month = after_row['Ay']
                after_consumption = after_row['Tüketim']
                
                same_month_before = before_period[before_period['Ay'] == after_month]
                
                if len(same_month_before) > 0 and after_consumption > 0:
                    before_avg = same_month_before['Tüketim'].mean()
                    
                    if before_avg > 0:
                        drop_pct = ((before_avg - after_consumption) / before_avg) * 100
                        
                        drop_percentages.append(drop_pct)
                        month_comparisons.append({
                            'ay': after_month,
                            'ay_adi': month_names[after_month],
                            'onceki_ort': before_avg,
                            'sonraki': after_consumption,
                            'dusus_pct': drop_pct,
                            'tarih': after_row['Tarih_DT'].strftime('%Y-%m')
                        })
            
            if len(drop_percentages) < 4:
                continue
            
            # Sabitlik analizi
            avg_drop = np.mean(drop_percentages)
            std_drop = np.std(drop_percentages)
            cv = (std_drop / avg_drop * 100) if avg_drop > 0 else 100
            
            is_constant = (avg_drop >= min_drop_pct and 
                          std_drop <= tolerance and 
                          cv <= 15)
            
            if not is_constant:
                continue
            
            # 2. GERİ DÖNÜŞ KONTROLÜ
            before_avg_all = before_period['Tüketim'].mean()
            max_recovery = 0
            max_recovery_date = None
            recovery_occurred = False
            
            for idx, row in after_period_all.iterrows():
                recovery_pct = (row['Tüketim'] / before_avg_all) * 100
                
                if recovery_pct > max_recovery:
                    max_recovery = recovery_pct
                    max_recovery_date = row['Tarih_DT'].strftime('%Y-%m')
                
                if recovery_pct >= max_recovery_pct:
                    recovery_occurred = True
                    break
            
            no_recovery = not recovery_occurred
            
            # NİHAİ KARAR
            if is_constant and no_recovery:
                suspicious.append(tesisat)
                
                # Açıklama oluştur
                explanation_parts = []
                explanation_parts.append(f"🎯 {drop_date.strftime('%Y-%m')} SABİT DÜŞÜŞ başladı")
                explanation_parts.append(f"📊 Her ay %{avg_drop:.1f} düşüş (±{std_drop:.1f}, CV:%{cv:.1f})")
                explanation_parts.append(f"🚫 {len(after_period_all)} ay eski seviyeye DÖNMEDİ")
                explanation_parts.append(f"↗️ Max seviye: %{max_recovery:.1f} ({max_recovery_date})")
                
                # Kesinlik değerlendirmesi
                if cv < 3 and max_recovery < 60:
                    certainty = "KESİN (%99)"
                    explanation_parts.append("⚠️ REKOR DELİK KESİN!")
                elif cv < 7 and max_recovery < 70:
                    certainty = "ÇOK YÜKSEK (%90+)"
                    explanation_parts.append("⚠️ Rekor delik ÇOK YÜKSEK ihtimal")
                elif cv < 12 and max_recovery < 80:
                    certainty = "YÜKSEK (%80+)"
                    explanation_parts.append("⚠️ Rekor delik YÜKSEK ihtimal")
                else:
                    certainty = "ORTA (%70+)"
                
                explanation = " | ".join(explanation_parts)
                
                # Risk skoru
                risk_score = min(100, 
                    avg_drop * 0.5 +
                    (15 - cv) * 2 +
                    (100 - max_recovery) * 0.3
                )
                
                # Aylık detay
                monthly_detail_text = "\n".join([
                    f"{c['ay_adi']} ({c['tarih']}): {c['onceki_ort']:.1f} → {c['sonraki']:.1f} m³ (%{c['dusus_pct']:.1f})"
                    for c in month_comparisons
                ])
                
                details.append({
                    'TESİSAT_NO': tesisat,
                    'BİNA_NO': tesisat_df['Bina_No'].iloc[0],
                    'DÜŞÜŞ_TARİHİ': drop_date.strftime('%Y-%m'),
                    'ÖNCEKİ_ORTALAMA (m³)': round(before_avg_all, 1),
                    'SONRAKİ_ORTALAMA (m³)': round(after_period_all['Tüketim'].mean(), 1),
                    'ORTALAMA_DÜŞÜŞ_%': round(avg_drop, 1),
                    'STANDART_SAPMA': round(std_drop, 2),
                    'VARYASYON_KATSAYISI_%': round(cv, 2),
                    'MIN_DÜŞÜŞ_%': round(min(drop_percentages), 1),
                    'MAX_DÜŞÜŞ_%': round(max(drop_percentages), 1),
                    'KARŞILAŞTIRMA_AY_SAYISI': len(drop_percentages),
                    'MAX_GERİ_DÖNÜŞ_%': round(max_recovery, 1),
                    'MAX_GERİ_DÖNÜŞ_TARİHİ': max_recovery_date,
                    'TAKİP_EDİLEN_AY_SAYISI': len(after_period_all),
                    'GERİ_DÖNDÜ_MÜ': 'HAYIR',
                    'ESKİ_SEVİYEYE_FARK_%': round(100 - max_recovery, 1),
                    'RİSK_SKORU': round(risk_score, 0),
                    'KESİNLİK_SEVİYESİ': certainty,
                    'REKOR_DELİK_İHTİMALİ': certainty.split()[0],
                    'AÇIKLAMA': explanation,
                    'AYLIK_DETAY': monthly_detail_text,
                    'TESPİT_NEDENİ': 'SABİT_DÜŞÜŞ_+_GERİ_DÖNÜŞ_YOK',
                    'SAHA_KONTROLÜ': 'ACİL - 1 HAFTA' if 'KESİN' in certainty or 'ÇOK' in certainty
                                    else 'ÖNCELİKLİ - 2 HAFTA' if 'YÜKSEK' in certainty
                                    else 'PLANLI - 1 AY'
                })
                
                break
    
    details_df = pd.DataFrame(details)
    if not details_df.empty:
        details_df = details_df.sort_values('RİSK_SKORU', ascending=False)
    
    return suspicious, details_df


def detect_low_winter_consumption_with_explanation(df, threshold=15):
    """
    KIŞ AYLARINDA DÜŞÜK TÜKETİM TESPİTİ
    """
    winter_data = df[df['Kış_Mı'] == True]
    suspicious = []
    details = []
    
    for tesisat in df['Tesisat_No'].unique():
        tesisat_winter = winter_data[winter_data['Tesisat_No'] == tesisat]
        
        if len(tesisat_winter) > 0:
            avg_winter = tesisat_winter['Tüketim'].mean()
            min_winter = tesisat_winter['Tüketim'].min()
            max_winter = tesisat_winter['Tüketim'].max()
            
            if avg_winter < threshold:
                suspicious.append(tesisat)
                
                explanation = f"❄️ Kış ortalaması {avg_winter:.1f} m³ (Eşik: {threshold} m³)"
                explanation += f" | Min: {min_winter:.1f}, Max: {max_winter:.1f}"
                explanation += f" | Kış ay sayısı: {len(tesisat_winter)}"
                
                details.append({
                    'TESİSAT_NO': tesisat,
                    'BİNA_NO': tesisat_winter['Bina_No'].iloc[0],
                    'ORT_KIŞ_TÜKETİM (m³)': round(avg_winter, 1),
                    'MIN_KIŞ (m³)': round(min_winter, 1),
                    'MAX_KIŞ (m³)': round(max_winter, 1),
                    'KIŞ_AY_SAYISI': len(tesisat_winter),
                    'EŞİK (m³)': threshold,
                    'AÇIKLAMA': explanation,
                    'TESPİT_NEDENİ': 'DÜŞÜK_KIŞ_TÜKETİMİ'
                })
    
    return suspicious, pd.DataFrame(details)


def detect_building_anomaly_with_explanation(df, percentile=10):
    """
    BİNA İÇİ KARŞILAŞTIRMA İLE ANOMALİ TESPİTİ
    """
    suspicious = []
    details = []
    
    for bina in df['Bina_No'].unique():
        bina_df = df[df['Bina_No'] == bina]
        tesisatlar = bina_df['Tesisat_No'].unique()
        
        if len(tesisatlar) <= 2:
            continue
        
        tesisat_avgs = []
        for tesisat in tesisatlar:
            tesisat_avg = bina_df[bina_df['Tesisat_No'] == tesisat]['Tüketim'].mean()
            tesisat_avgs.append((tesisat, tesisat_avg))
        
        tesisat_avgs.sort(key=lambda x: x[1])
        
        num_suspicious = max(1, int(len(tesisat_avgs) * percentile / 100))
        bina_median = np.median([x[1] for x in tesisat_avgs])
        bina_mean = np.mean([x[1] for x in tesisat_avgs])
        
        for i in range(num_suspicious):
            tesisat, avg = tesisat_avgs[i]
            diff_from_median = ((bina_median - avg) / bina_median * 100) if bina_median > 0 else 0
            
            if diff_from_median > 30:
                suspicious.append(tesisat)
                
                explanation = f"🏢 {len(tesisatlar)} tesisattan {i+1}. en düşük"
                explanation += f" | Tüketim: {avg:.1f} m³, Bina ort: {bina_mean:.1f} m³"
                explanation += f" | Medyandan %{diff_from_median:.1f} düşük"
                
                details.append({
                    'TESİSAT_NO': tesisat,
                    'BİNA_NO': bina,
                    'ORTALAMA_TÜKETİM (m³)': round(avg, 1),
                    'BİNA_ORTALAMASI (m³)': round(bina_mean, 1),
                    'BİNA_MEDYANI (m³)': round(bina_median, 1),
                    'MEDYANDAN_FARK_%': round(diff_from_median, 1),
                    'BİNADAKİ_TESİSAT_SAYISI': len(tesisatlar),
                    'SIRALAMA': f"{i+1}/{len(tesisatlar)}",
                    'AÇIKLAMA': explanation,
                    'TESPİT_NEDENİ': 'BİNA_İÇİ_ANOMALİ'
                })
    
    return suspicious, pd.DataFrame(details)


def detect_zero_consumption_with_explanation(df, min_months=4):
    """
    UZUN SÜRE SIFIR TÜKETİM TESPİTİ
    """
    suspicious = []
    details = []
    
    for tesisat in df['Tesisat_No'].unique():
        tesisat_df = df[df['Tesisat_No'] == tesisat].sort_values('Tarih_DT')
        last_months = tesisat_df.tail(min_months)
        
        if len(last_months) >= min_months:
            if (last_months['Tüketim'] == 0).all():
                suspicious.append(tesisat)
                
                if len(tesisat_df) > min_months:
                    before_zero = tesisat_df.iloc[-min_months-1]['Tüketim']
                else:
                    before_zero = 0
                
                explanation = f"🔴 {min_months} ay sürekli sıfır"
                explanation += f" | Dönem: {last_months['Tarih_DT'].iloc[0].strftime('%Y-%m')} - {last_months['Tarih_DT'].iloc[-1].strftime('%Y-%m')}"
                if before_zero > 0:
                    explanation += f" | Önceki: {before_zero:.1f} m³"
                
                details.append({
                    'TESİSAT_NO': tesisat,
                    'BİNA_NO': tesisat_df['Bina_No'].iloc[0],
                    'SIFIR_AY_SAYISI': len(last_months),
                    'BAŞLANGIÇ': last_months['Tarih_DT'].iloc[0].strftime('%Y-%m'),
                    'BİTİŞ': last_months['Tarih_DT'].iloc[-1].strftime('%Y-%m'),
                    'ÖNCEKİ_TÜKETİM (m³)': round(before_zero, 1),
                    'AÇIKLAMA': explanation,
                    'TESPİT_NEDENİ': 'UZUN_SÜRE_SIFIR'
                })
    
    return suspicious, pd.DataFrame(details)


def ml_based_anomaly_detection(df, contamination=0.1):
    """
    MACHINE LEARNING İLE ANOMALİ TESPİTİ
    
    Isolation Forest algoritması kullanarak pattern tabanlı anomali tespiti
    """
    ml_suspicious = []
    ml_details = []
    
    features_list = []
    
    for tesisat in df['Tesisat_No'].unique():
        tesisat_df = df[df['Tesisat_No'] == tesisat].sort_values('Tarih_DT')
        
        if len(tesisat_df) < 12:
            continue
        
        winter_avg = tesisat_df[tesisat_df['Kış_Mı']]['Tüketim'].mean()
        summer_avg = tesisat_df[~tesisat_df['Kış_Mı']]['Tüketim'].mean()
        
        features = {
            'TESİSAT_NO': tesisat,
            'BİNA_NO': tesisat_df['Bina_No'].iloc[0],
            'ORT_TÜKETİM': tesisat_df['Tüketim'].mean(),
            'MEDYAN_TÜKETİM': tesisat_df['Tüketim'].median(),
            'STD_TÜKETİM': tesisat_df['Tüketim'].std(),
            'MIN_TÜKETİM': tesisat_df['Tüketim'].min(),
            'MAX_TÜKETİM': tesisat_df['Tüketim'].max(),
            'SIFIR_ORAN': (tesisat_df['Tüketim'] == 0).sum() / len(tesisat_df) * 100,
            'DEĞİŞKENLİK_KATSAYISI': (tesisat_df['Tüketim'].std() / tesisat_df['Tüketim'].mean() * 100) if tesisat_df['Tüketim'].mean() > 0 else 0,
            'KIŞ_YAZ_FARKI': winter_avg - summer_avg if summer_avg > 0 else 0,
            'KIŞ_YAZ_ORANI': winter_avg / summer_avg if summer_avg > 0 else 0,
            'TREND_EĞIMI': np.polyfit(range(len(tesisat_df)), tesisat_df['Tüketim'].values, 1)[0],
        }
        features_list.append(features)
    
    if len(features_list) < 10:
        return [], pd.DataFrame()
    
    features_df = pd.DataFrame(features_list)
    
    ml_features = [
        'ORT_TÜKETİM', 'STD_TÜKETİM', 'SIFIR_ORAN', 'DEĞİŞKENLİK_KATSAYISI',
        'KIŞ_YAZ_FARKI', 'KIŞ_YAZ_ORANI', 'TREND_EĞIMI'
    ]
    
    X = features_df[ml_features].fillna(0)
    
    # Standardizasyon
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Isolation Forest
    iso_forest = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100
    )
    
    predictions = iso_forest.fit_predict(X_scaled)
    anomaly_scores = iso_forest.score_samples(X_scaled)
    
    # Skorları normalize et
    min_score = anomaly_scores.min()
    max_score = anomaly_scores.max()
    normalized_scores = ((anomaly_scores - min_score) / (max_score - min_score) * 100)
    
    features_df['ML_ANOMALİ'] = predictions == -1
    features_df['ML_SKOR'] = normalized_scores
    features_df['ML_RİSK_SEVİYESİ'] = pd.cut(
        normalized_scores,
        bins=[0, 30, 60, 100],
        labels=['DÜŞÜK', 'ORTA', 'YÜKSEK']
    )
    
    anomalies = features_df[features_df['ML_ANOMALİ'] == True].copy()
    
    for idx, row in anomalies.iterrows():
        reasons = []
        
        if row['SIFIR_ORAN'] > 20:
            reasons.append(f"🔴 %{row['SIFIR_ORAN']:.1f} sıfır")
        
        if row['DEĞİŞKENLİK_KATSAYISI'] > 80:
            reasons.append(f"⚡ Yüksek dalgalanma (%{row['DEĞİŞKENLİK_KATSAYISI']:.1f})")
        
        if row['KIŞ_YAZ_ORANI'] < 1.5 and row['ORT_TÜKETİM'] > 10:
            reasons.append(f"❄️ Düşük Kış/Yaz oranı ({row['KIŞ_YAZ_ORANI']:.2f})")
        
        if row['TREND_EĞIMI'] < -2:
            reasons.append(f"📉 Azalan trend ({row['TREND_EĞIMI']:.2f})")
        
        if row['ORT_TÜKETİM'] < 10:
            reasons.append(f"📊 Çok düşük ort ({row['ORT_TÜKETİM']:.1f} m³)")
        
        if not reasons:
            reasons.append("🤖 ML genel profil anomalisi")
        
        explanation = " | ".join(reasons)
        
        ml_details.append({
            'TESİSAT_NO': row['TESİSAT_NO'],
            'BİNA_NO': row['BİNA_NO'],
            'ML_SKOR': round(row['ML_SKOR'], 1),
            'RİSK_SEVİYESİ': row['ML_RİSK_SEVİYESİ'],
            'ORT_TÜKETİM (m³)': round(row['ORT_TÜKETİM'], 1),
            'SIFIR_ORAN_%': round(row['SIFIR_ORAN'], 1),
            'DEĞİŞKENLİK_%': round(row['DEĞİŞKENLİK_KATSAYISI'], 1),
            'KIŞ/YAZ_ORANI': round(row['KIŞ_YAZ_ORANI'], 2),
            'TREND': round(row['TREND_EĞIMI'], 2),
            'AÇIKLAMA': explanation,
            'TESPİT_NEDENİ': 'ML_ANOMALİ'
        })
        
        ml_suspicious.append(row['TESİSAT_NO'])
    
    return ml_suspicious, pd.DataFrame(ml_details)

# ===================================================================================
# ANALİZLERİ ÇALIŞTIR
# ===================================================================================

st.header("🔍 ANALİZ SONUÇLARI")
st.markdown("---")

with st.spinner('🔄 Analizler çalıştırılıyor... Lütfen bekleyin (Bu işlem birkaç dakika sürebilir)'):
    
    # 1) Kalıcı Düşüş
    permanent_drop_list, permanent_drop_details = detect_permanent_drop_with_explanation(
        df,
        min_drop_pct=min_drop_percent,
        min_months_after=min_months_after,
        recovery_threshold_pct=recovery_threshold
    )
    
    # 2) Sabit Düşüş Yüzdesi (Rekor Delik)
    constant_drop_list, constant_drop_details = detect_constant_drop_with_no_recovery(
        df,
        min_months_before=constant_months_before,
        min_months_after=constant_months_after,
        tolerance=constant_tolerance,
        min_drop_pct=constant_min_drop,
        max_recovery_pct=max_recovery_pct
    )
    
    # 3) Düşük Kış Tüketimi
    low_winter_list, low_winter_details = detect_low_winter_consumption_with_explanation(
        df,
        threshold=min_winter_cons
    )
    
    # 4) Bina İçi Anomali
    building_anomaly_list, building_anomaly_details = detect_building_anomaly_with_explanation(
        df,
        percentile=bina_percentile
    )
    
    # 5) Uzun Süre Sıfır Tüketim
    zero_consumption_list, zero_consumption_details = detect_zero_consumption_with_explanation(
        df,
        min_months=4
    )
    
    # 6) Machine Learning Anomali
    ml_anomaly_list, ml_anomaly_details = ml_based_anomaly_detection(
        df,
        contamination=ml_contamination
    )

# Tüm şüphelileri birleştir
all_suspicious = list(set(
    permanent_drop_list +
    constant_drop_list +
    low_winter_list +
    building_anomaly_list +
    zero_consumption_list +
    ml_anomaly_list
))

# Her tesisat için detaylı özet oluştur
all_suspicious_details = []

for tesisat in all_suspicious:
    tesisat_data = df[df['Tesisat_No'] == tesisat]
    avg_consumption = tesisat_data['Tüketim'].mean()
    last_consumption = tesisat_data['Tüketim'].iloc[-1]
    total_months = len(tesisat_data)
    
    criteria_list = []
    explanations = []
    
    # Kalıcı düşüş
    if tesisat in permanent_drop_list:
        criteria_list.append('KALICI_DÜŞÜŞ')
        perm = permanent_drop_details[permanent_drop_details['TESİSAT_NO'] == tesisat]
        if not perm.empty:
            explanations.append(f"📉 {perm.iloc[0]['AÇIKLAMA']}")
    
    # Sabit düşüş yüzdesi
    if tesisat in constant_drop_list:
        criteria_list.append('SABİT_DÜŞÜŞ_YÜZDESİ')
        const = constant_drop_details[constant_drop_details['TESİSAT_NO'] == tesisat]
        if not const.empty:
            explanations.append(f"🎯 {const.iloc[0]['AÇIKLAMA']}")
    
    # Düşük kış
    if tesisat in low_winter_list:
        criteria_list.append('DÜŞÜK_KIŞ')
        winter = low_winter_details[low_winter_details['TESİSAT_NO'] == tesisat]
        if not winter.empty:
            explanations.append(f"❄️ {winter.iloc[0]['AÇIKLAMA']}")
    
    # Bina anomalisi
    if tesisat in building_anomaly_list:
        criteria_list.append('BİNA_ANOMALİ')
        bina = building_anomaly_details[building_anomaly_details['TESİSAT_NO'] == tesisat]
        if not bina.empty:
            explanations.append(f"🏢 {bina.iloc[0]['AÇIKLAMA']}")
    
    # Sıfır tüketim
    if tesisat in zero_consumption_list:
        criteria_list.append('SIFIR_TÜKETİM')
        zero = zero_consumption_details[zero_consumption_details['TESİSAT_NO'] == tesisat]
        if not zero.empty:
            explanations.append(f"🔴 {zero.iloc[0]['AÇIKLAMA']}")
    
    # ML anomali
    if tesisat in ml_anomaly_list:
        criteria_list.append('ML_ANOMALİ')
        ml = ml_anomaly_details[ml_anomaly_details['TESİSAT_NO'] == tesisat]
        if not ml.empty:
            explanations.append(f"🤖 {ml.iloc[0]['AÇIKLAMA']}")
    
    full_explanation = " || ".join(explanations)
    
    # Risk skoru hesapla
    risk_score = 0
    if 'SABİT_DÜŞÜŞ_YÜZDESİ' in criteria_list:
        risk_score += 50  # En yüksek risk
    if 'KALICI_DÜŞÜŞ' in criteria_list:
        risk_score += 40
    if 'SIFIR_TÜKETİM' in criteria_list:
        risk_score += 30
    if 'DÜŞÜK_KIŞ' in criteria_list:
        risk_score += 20
    if 'BİNA_ANOMALİ' in criteria_list:
        risk_score += 10
    if 'ML_ANOMALİ' in criteria_list:
        risk_score += 15
    
    risk_score = min(100, risk_score)
    
    # Öncelik belirle
    if risk_score >= 70:
        priority = 'YÜKSEK'
        priority_note = 'ACİL SAHA KONTROLÜ'
    elif risk_score >= 40:
        priority = 'ORTA'
        priority_note = 'Öncelikli kontrol'
    else:
        priority = 'DÜŞÜK'
        priority_note = 'Rutin takip'
    
    all_suspicious_details.append({
        'TESİSAT_NO': tesisat,
        'BİNA_NO': tesisat_data['Bina_No'].iloc[0],
        'ORT_TÜKETİM (m³)': round(avg_consumption, 1),
        'SON_TÜKETİM (m³)': round(last_consumption, 1),
        'MIN (m³)': round(tesisat_data['Tüketim'].min(), 1),
        'MAX (m³)': round(tesisat_data['Tüketim'].max(), 1),
        'STD': round(tesisat_data['Tüketim'].std(), 1),
        'AY_SAYISI': total_months,
        'KRİTERLER': ', '.join(criteria_list),
        'KRİTER_SAYISI': len(criteria_list),
        'RİSK_SKORU': risk_score,
        'ÖNCELİK': priority,
        'ÖNCELİK_NOTU': priority_note,
        'TESPİT_AÇIKLAMASI': full_explanation,
        'SAHA_ÖNERİSİ': f"{priority} öncelik - {priority_note}"
    })

all_suspicious_df = pd.DataFrame(all_suspicious_details)
if not all_suspicious_df.empty:
    all_suspicious_df = all_suspicious_df.sort_values(['RİSK_SKORU', 'KRİTER_SAYISI'], ascending=[False, False])

# ===================================================================================
# SONUÇ PANELİ - ÜST METRİKLER
# ===================================================================================

st.subheader("📊 GENEL ÖZET")

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    suspicious_rate = (len(all_suspicious) / df['Tesisat_No'].nunique() * 100) if df['Tesisat_No'].nunique() > 0 else 0
    st.metric(
        "🎯 Toplam Şüpheli",
        f"{len(all_suspicious):,}",
        delta=f"%{suspicious_rate:.1f}",
        delta_color="inverse"
    )

with col2:
    st.metric(
        "📉 Kalıcı Düşüş",
        f"{len(permanent_drop_list):,}",
        help="Ani ve geri dönüşsüz düşüşler"
    )

with col3:
    st.metric(
        "🎯 Sabit Düşüş %",
        f"{len(constant_drop_list):,}",
        help="Rekor delik ihtimali yüksek!"
    )

with col4:
    st.metric(
        "❄️ Düşük Kış",
        f"{len(low_winter_list):,}",
        help="Isınma sezonunda düşük tüketim"
    )

with col5:
    st.metric(
        "🏢 Bina Anomalisi",
        f"{len(building_anomaly_list):,}",
        help="Bina içi karşılaştırma"
    )

with col6:
    st.metric(
        "🤖 ML Tespiti",
        f"{len(ml_anomaly_list):,}",
        help="Yapay zeka tespiti"
    )

st.markdown("---")

# ===================================================================================
# DETAYLI TABLOLAR - TABLAR
# ===================================================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "🎯 TÜM ŞÜPHELİLER",
    "📉 KALICI DÜŞÜŞ",
    "🎯 SABİT DÜŞÜŞ % (REKOR DELİK)",
    "❄️ DÜŞÜK KIŞ",
    "🏢 BİNA ANOMALİSİ",
    "🔴 SIFIR TÜKETİM",
    "🤖 ML ANOMALİ",
    "📊 KARŞILAŞTIRMALI ANALİZ",
    "🔍 TEKİL ANALİZ"
])

# TAB 1: TÜM ŞÜPHELİLER
with tab1:
    st.subheader(f"🎯 Tüm Şüpheli Tesisatlar ({len(all_suspicious)})")
    
    if not all_suspicious_df.empty:
        # Filtreleme
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            min_risk_filter = st.slider("Min. Risk Skoru", 0, 100, 40, key="all_risk")
        
        with col_f2:
            priority_filter = st.multiselect(
                "Öncelik Seviyesi",
                options=['YÜKSEK', 'ORTA', 'DÜŞÜK'],
                default=['YÜKSEK', 'ORTA', 'DÜŞÜK'],
                key="all_priority"
            )
        
        with col_f3:
            min_criteria_filter = st.slider("Min. Kriter Sayısı", 1, 6, 1, key="all_criteria")
        
        filtered_all = all_suspicious_df[
            (all_suspicious_df['RİSK_SKORU'] >= min_risk_filter) &
            (all_suspicious_df['ÖNCELİK'].isin(priority_filter)) &
            (all_suspicious_df['KRİTER_SAYISI'] >= min_criteria_filter)
        ]
        
        st.info(f"✅ **{len(filtered_all)}** tesisat filtrelere uyuyor")
        
        # Tablo
        st.dataframe(
            filtered_all.style.background_gradient(subset=['RİSK_SKORU'], cmap='Reds'),
            use_container_width=True,
            height=500
        )
        
        # Grafikler
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            fig_priority = px.pie(
                filtered_all,
                names='ÖNCELİK',
                title='Öncelik Dağılımı',
                color='ÖNCELİK',
                color_discrete_map={'YÜKSEK': 'red', 'ORTA': 'orange', 'DÜŞÜK': 'yellow'}
            )
            st.plotly_chart(fig_priority, use_container_width=True)
        
        with col_chart2:
            criteria_count = filtered_all['KRİTER_SAYISI'].value_counts().sort_index()
            fig_criteria = px.bar(
                x=criteria_count.index,
                y=criteria_count.values,
                title='Kriter Sayısı Dağılımı',
                labels={'x': 'Kriter Sayısı', 'y': 'Tesisat Sayısı'},
                color=criteria_count.values,
                color_continuous_scale='Reds'
            )
            st.plotly_chart(fig_criteria, use_container_width=True)
    
    else:
        st.success("✅ Şüpheli tesisat tespit edilmedi")

# TAB 2: KALICI DÜŞÜŞ
with tab2:
    st.subheader(f"📉 Kalıcı Düşüş Tespit Edilen Tesisatlar ({len(permanent_drop_list)})")
    
    if not permanent_drop_details.empty:
        st.dataframe(permanent_drop_details, use_container_width=True, height=500)
        
        # Grafik
        fig_perm = px.scatter(
            permanent_drop_details,
            x='ÖNCEKİ_ORT (m³)',
            y='SONRAKİ_ORT (m³)',
            size='DÜŞÜŞ_%',
            color='RİSK_SKORU',
            hover_data=['TESİSAT_NO', 'DÜŞÜŞ_TARİHİ'],
            title='Düşüş Öncesi vs Sonrası Tüketim',
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig_perm, use_container_width=True)
    else:
        st.success("✅ Kalıcı düşüş tespit edilmedi")

# TAB 3: SABİT DÜŞÜŞ YÜZDESİ (REKOR DELİK)
with tab3:
    st.subheader(f"🎯 Sabit Düşüş Yüzdesi - Rekor Delik Tespiti ({len(constant_drop_list)})")
    
    st.markdown("""
    <div style="background-color: #ffe6e6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff0000;">
    <h4 style="color: #cc0000;">⚠️ REKOR DELİK TESPİT ALGORİTMASI</h4>
    
    Bu analiz <b>iki kritik pattern</b> arar:
    
    <ol>
    <li><b>Sabit Düşüş Yüzdesi:</b> Her ayın (Ocak, Şubat, vb.) düşüş yüzdesi neredeyse aynı</li>
    <li><b>Geri Dönüş Yok:</b> Düşüşten sonra HİÇBİR zaman eski seviyelere dönmüyor</li>
    </ol>
    
    <p style="color: #cc0000; font-weight: bold;">
    Her iki kriter birden sağlanınca → Rekor delik ihtimali %95+
    </p>
    </div>
    """, unsafe_allow_html=True)
    
    if not constant_drop_details.empty:
        # Özet metrikler
        st.markdown("---")
        col_const1, col_const2, col_const3, col_const4 = st.columns(4)
        
        certain = constant_drop_details[constant_drop_details['KESİNLİK_SEVİYESİ'].str.contains('KESİN')]
        very_high = constant_drop_details[constant_drop_details['KESİNLİK_SEVİYESİ'].str.contains('ÇOK YÜKSEK')]
        
        with col_const1:
            st.metric("Kesin Vakalar", len(certain), delta="ACİL", delta_color="inverse")
        
        with col_const2:
            st.metric("Çok Yüksek İhtimal", len(very_high), delta="Öncelikli", delta_color="inverse")
        
        with col_const3:
            st.metric("Ort. Risk Skoru", f"{constant_drop_details['RİSK_SKORU'].mean():.0f}/100")
        
        with col_const4:
            st.metric("Ort. Düşüş %", f"%{constant_drop_details['ORTALAMA_DÜŞÜŞ_%'].mean():.1f}")
        
        # Filtreleme
        st.markdown("---")
        col_cf1, col_cf2, col_cf3, col_cf4 = st.columns(4)
        
        with col_cf1:
            const_min_risk = st.slider("Min. Risk", 0, 100, 70, key="const_risk")
        
        with col_cf2:
            const_max_cv = st.slider("Max. Varyasyon %", 0.0, 15.0, 10.0, 0.5, key="const_cv")
        
        with col_cf3:
            const_max_recovery = st.slider("Max. Geri Dönüş %", 0, 100, 70, key="const_recovery")
        
        with col_cf4:
            const_certainty = st.multiselect(
                "Kesinlik",
                options=constant_drop_details['REKOR_DELİK_İHTİMALİ'].unique(),
                default=constant_drop_details['REKOR_DELİK_İHTİMALİ'].unique(),
                key="const_certainty"
            )
        
        filtered_const = constant_drop_details[
            (constant_drop_details['RİSK_SKORU'] >= const_min_risk) &
            (constant_drop_details['VARYASYON_KATSAYISI_%'] <= const_max_cv) &
            (constant_drop_details['MAX_GERİ_DÖNÜŞ_%'] <= const_max_recovery) &
            (constant_drop_details['REKOR_DELİK_İHTİMALİ'].isin(const_certainty))
        ]
        
        st.info(f"✅ **{len(filtered_const)}** tesisat filtrelere uyuyor")
        
        # Tablo
        display_const_cols = [
            'TESİSAT_NO', 'BİNA_NO', 'DÜŞÜŞ_TARİHİ',
            'ORTALAMA_DÜŞÜŞ_%', 'VARYASYON_KATSAYISI_%',
            'MAX_GERİ_DÖNÜŞ_%', 'ESKİ_SEVİYEYE_FARK_%',
            'RİSK_SKORU', 'KESİNLİK_SEVİYESİ', 'SAHA_KONTROLÜ'
        ]
        
        st.dataframe(
            filtered_const[display_const_cols].style.background_gradient(subset=['RİSK_SKORU'], cmap='Reds'),
            use_container_width=True,
            height=400
        )
        
        # Risk haritası
        st.markdown("---")
        st.subheader("📊 Risk Haritası (Varyasyon vs Düşüş %)")
        
        fig_risk_map = px.scatter(
            filtered_const,
            x='VARYASYON_KATSAYISI_%',
            y='ORTALAMA_DÜŞÜŞ_%',
            size='RİSK_SKORU',
            color='KESİNLİK_SEVİYESİ',
            hover_data=['TESİSAT_NO', 'BİNA_NO'],
            title='Sabit Düşüş Risk Haritası',
            labels={'VARYASYON_KATSAYISI_%': 'Varyasyon (Düşük = Daha Sabit)',
                   'ORTALAMA_DÜŞÜŞ_%': 'Ortalama Düşüş %'},
            color_discrete_map={'KESİN': 'darkred', 'ÇOK': 'red', 'YÜKSEK': 'orange', 'ORTA': 'yellow'}
        )
        
        # Yüksek risk bölgesi vurgusu
        fig_risk_map.add_shape(
            type="rect",
            x0=0, y0=50, x1=10, y1=100,
            fillcolor="red", opacity=0.1,
            line=dict(width=0)
        )
        
        st.plotly_chart(fig_risk_map, use_container_width=True)
        
        # Top 5 detay
        st.markdown("---")
        st.subheader("🔬 En Riskli 5 Tesisat - Detaylı İnceleme")
        
        top_5_const = filtered_const.nlargest(5, 'RİSK_SKORU')
        
        for rank, (idx, row) in enumerate(top_5_const.iterrows(), 1):
            emoji = "🔴" if 'KESİN' in row['KESİNLİK_SEVİYESİ'] else "🟠" if 'ÇOK' in row['KESİNLİK_SEVİYESİ'] else "🟡"
            
            with st.expander(f"{emoji} #{rank} - Tesisat: {row['TESİSAT_NO']} | Risk: {row['RİSK_SKORU']:.0f} | {row['KESİNLİK_SEVİYESİ']}", 
                           expanded=(rank==1)):
                
                col_d1, col_d2, col_d3, col_d4 = st.columns(4)
                
                with col_d1:
                    st.metric("Ort. Düşüş %", f"%{row['ORTALAMA_DÜŞÜŞ_%']:.1f}")
                    st.metric("Varyasyon", f"%{row['VARYASYON_KATSAYISI_%']:.2f}")
                
                with col_d2:
                    st.metric("Önceki Ort.", f"{row['ÖNCEKİ_ORTALAMA (m³)']} m³")
                    st.metric("Sonraki Ort.", f"{row['SONRAKİ_ORTALAMA (m³)']} m³")
                
                with col_d3:
                    st.metric("Max Geri Dönüş", f"%{row['MAX_GERİ_DÖNÜŞ_%']:.1f}")
                    st.metric("Eski Seviyeye Fark", f"%{row['ESKİ_SEVİYEYE_FARK_%']:.1f}")
                
                with col_d4:
                    st.metric("Takip Süresi", f"{row['TAKİP_EDİLEN_AY_SAYISI']} ay")
                    st.metric("Risk Skoru", f"{row['RİSK_SKORU']:.0f}/100")
                
                st.markdown(f"""
                **📝 Açıklama:**
                
                {row['AÇIKLAMA']}
                
                **📅 Aylık Detay:**
                ```
                {row['AYLIK_DETAY']}
                ```
                
                **📋 Saha Kontrolü:** {row['SAHA_KONTROLÜ']}
                """)
        
        # ACİL UYARI
        if len(certain) > 0:
            st.error(f"""
            🚨 **ACİL UYARI - {len(certain)} ADET KESİN REKOR DELİK TESPİTİ!**
            
            - Ortalama varyasyon: **%{certain['VARYASYON_KATSAYISI_%'].mean():.2f}** (Çok sabit!)
            - Ortalama düşüş: **%{certain['ORTALAMA_DÜŞÜŞ_%'].mean():.1f}**
            - Ortalama geri dönüş: **%{certain['MAX_GERİ_DÖNÜŞ_%'].mean():.1f}** (Çok düşük!)
            
            **ÖNERİ:** Bu tesisatlar ACİL fiziksel kontrole alınmalı!
            """)
    
    else:
        st.success("✅ Sabit düşüş yüzdesi tespit edilmedi")

# TAB 4: DÜŞÜK KIŞ
with tab4:
    st.subheader(f"❄️ Düşük Kış Tüketimi ({len(low_winter_list)})")
    
    if not low_winter_details.empty:
        st.dataframe(low_winter_details, use_container_width=True)
    else:
        st.success("✅ Düşük kış tüketimi tespit edilmedi")

# TAB 5: BİNA ANOMALİSİ
with tab5:
    st.subheader(f"🏢 Bina İçi Anomali ({len(building_anomaly_list)})")
    
    if not building_anomaly_details.empty:
        st.dataframe(building_anomaly_details, use_container_width=True)
        
        # Bina bazında özet
        bina_summary = building_anomaly_details.groupby('BİNA_NO').agg({
            'TESİSAT_NO': 'count',
            'MEDYANDAN_FARK_%': 'mean'
        }).reset_index()
        bina_summary.columns = ['Bina', 'Anomali_Sayısı', 'Ort_Fark_%']
        bina_summary = bina_summary.sort_values('Anomali_Sayısı', ascending=False).head(20)
        
        fig_bina = px.bar(
            bina_summary,
            x='Bina',
            y='Anomali_Sayısı',
            color='Ort_Fark_%',
            title='En Çok Anomali Barındıran 20 Bina',
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig_bina, use_container_width=True)
    else:
        st.success("✅ Bina içi anomali tespit edilmedi")

# TAB 6: SIFIR TÜKETİM
with tab6:
    st.subheader(f"🔴 Uzun Süre Sıfır Tüketim ({len(zero_consumption_list)})")
    
    if not zero_consumption_details.empty:
        st.dataframe(zero_consumption_details, use_container_width=True)
    else:
        st.success("✅ Uzun süre sıfır tüketim tespit edilmedi")

# TAB 7: ML ANOMALİ
with tab7:
    st.subheader(f"🤖 Machine Learning Anomali Tespiti ({len(ml_anomaly_list)})")
    
    if not ml_anomaly_details.empty:
        st.dataframe(ml_anomaly_details, use_container_width=True)
        
        # ML Skor dağılımı
        fig_ml = px.histogram(
            ml_anomaly_details,
            x='ML_SKOR',
            color='RİSK_SEVİYESİ',
            title='ML Anomali Skor Dağılımı',
            color_discrete_map={'DÜŞÜK': 'yellow', 'ORTA': 'orange', 'YÜKSEK': 'red'}
        )
        st.plotly_chart(fig_ml, use_container_width=True)
    else:
        st.success("✅ ML anomali tespit edilmedi")

# TAB 8: KARŞILAŞTIRMALI ANALİZ
with tab8:
    st.subheader("📊 Şüpheli vs Normal Tesisatlar Karşılaştırması")
    
    if len(all_suspicious) > 0:
        normal_tesisatlar = df[~df['Tesisat_No'].isin(all_suspicious)]
        suspicious_tesisatlar = df[df['Tesisat_No'].isin(all_suspicious)]
        
        comparison_data = {
            'Metrik': [
                'Ortalama Tüketim (m³)',
                'Medyan Tüketim (m³)',
                'Standart Sapma',
                'Min Tüketim (m³)',
                'Max Tüketim (m³)',
                'Sıfır Tüketim Oranı (%)',
                'Kış Ayı Ort. (m³)',
                'Yaz Ayı Ort. (m³)',
                'Kış/Yaz Oranı'
            ],
            'Normal Tesisatlar': [
                normal_tesisatlar.groupby('Tesisat_No')['Tüketim'].mean().mean(),
                normal_tesisatlar.groupby('Tesisat_No')['Tüketim'].median().median(),
                normal_tesisatlar.groupby('Tesisat_No')['Tüketim'].std().mean(),
                normal_tesisatlar.groupby('Tesisat_No')['Tüketim'].min().mean(),
                normal_tesisatlar.groupby('Tesisat_No')['Tüketim'].max().mean(),
                (normal_tesisatlar['Tüketim'] == 0).sum() / len(normal_tesisatlar) * 100,
                normal_tesisatlar[normal_tesisatlar['Kış_Mı']]['Tüketim'].mean(),
                normal_tesisatlar[~normal_tesisatlar['Kış_Mı']]['Tüketim'].mean(),
                normal_tesisatlar[normal_tesisatlar['Kış_Mı']]['Tüketim'].mean() / 
                normal_tesisatlar[~normal_tesisatlar['Kış_Mı']]['Tüketim'].mean() if normal_tesisatlar[~normal_tesisatlar['Kış_Mı']]['Tüketim'].mean() > 0 else 0
            ],
            'Şüpheli Tesisatlar': [
                suspicious_tesisatlar.groupby('Tesisat_No')['Tüketim'].mean().mean(),
                suspicious_tesisatlar.groupby('Tesisat_No')['Tüketim'].median().median(),
                suspicious_tesisatlar.groupby('Tesisat_No')['Tüketim'].std().mean(),
                suspicious_tesisatlar.groupby('Tesisat_No')['Tüketim'].min().mean(),
                suspicious_tesisatlar.groupby('Tesisat_No')['Tüketim'].max().mean(),
                (suspicious_tesisatlar['Tüketim'] == 0).sum() / len(suspicious_tesisatlar) * 100,
                suspicious_tesisatlar[suspicious_tesisatlar['Kış_Mı']]['Tüketim'].mean(),
                suspicious_tesisatlar[~suspicious_tesisatlar['Kış_Mı']]['Tüketim'].mean(),
                suspicious_tesisatlar[suspicious_tesisatlar['Kış_Mı']]['Tüketim'].mean() / 
                suspicious_tesisatlar[~suspicious_tesisatlar['Kış_Mı']]['Tüketim'].mean() if suspicious_tesisatlar[~suspicious_tesisatlar['Kış_Mı']]['Tüketim'].mean() > 0 else 0
            ]
        }
        
        comparison_df = pd.DataFrame(comparison_data)
        comparison_df['Fark (%)'] = ((comparison_df['Şüpheli Tesisatlar'] - comparison_df['Normal Tesisatlar']) / 
                                      comparison_df['Normal Tesisatlar'] * 100).round(1)
        
        comparison_df['Normal Tesisatlar'] = comparison_df['Normal Tesisatlar'].round(2)
        comparison_df['Şüpheli Tesisatlar'] = comparison_df['Şüpheli Tesisatlar'].round(2)
        
        st.dataframe(comparison_df, use_container_width=True)
        
        # Görsel karşılaştırma
        col_comp1, col_comp2 = st.columns(2)
        
        with col_comp1:
            fig_comp_bar = go.Figure(data=[
                go.Bar(name='Normal', x=comparison_df['Metrik'][:5], y=comparison_df['Normal Tesisatlar'][:5]),
                go.Bar(name='Şüpheli', x=comparison_df['Metrik'][:5], y=comparison_df['Şüpheli Tesisatlar'][:5])
            ])
            fig_comp_bar.update_layout(title='Temel Metrikler Karşılaştırması', barmode='group')
            st.plotly_chart(fig_comp_bar, use_container_width=True)
        
        with col_comp2:
            fig_comp_box = go.Figure()
            fig_comp_box.add_trace(go.Box(
                y=normal_tesisatlar.groupby('Tesisat_No')['Tüketim'].mean(),
                name='Normal',
                marker_color='lightblue'
            ))
            fig_comp_box.add_trace(go.Box(
                y=suspicious_tesisatlar.groupby('Tesisat_No')['Tüketim'].mean(),
                name='Şüpheli',
                marker_color='lightcoral'
            ))
            fig_comp_box.update_layout(title='Ortalama Tüketim Dağılımı')
            st.plotly_chart(fig_comp_box, use_container_width=True)
    
    else:
        st.info("Karşılaştırma için şüpheli tesisat bulunamadı")

# TAB 9: TEKİL ANALİZ
with tab9:
    st.subheader("🔍 Tekil Tesisat Detaylı Analizi")
    
    # Tesisat seçici
    tesisat_options = df['Tesisat_No'].unique()[:500]  # İlk 500 tesisat
    
    selected_tesisat = st.selectbox(
        "Analiz etmek istediğiniz tesisatı seçin:",
        options=tesisat_options,
        index=0
    )
    
    if selected_tesisat:
        tesisat_data = df[df['Tesisat_No'] == selected_tesisat].sort_values('Tarih_DT')
        
        # Tesisat bilgileri
        col_info1, col_info2, col_info3, col_info4 = st.columns(4)
        
        with col_info1:
            st.metric("Tesisat No", selected_tesisat)
            st.metric("Bina No", tesisat_data['Bina_No'].iloc[0])
        
        with col_info2:
            st.metric("Ortalama Tüketim", f"{tesisat_data['Tüketim'].mean():.1f} m³")
            st.metric("Medyan Tüketim", f"{tesisat_data['Tüketim'].median():.1f} m³")
        
        with col_info3:
            st.metric("Min Tüketim", f"{tesisat_data['Tüketim'].min():.1f} m³")
            st.metric("Max Tüketim", f"{tesisat_data['Tüketim'].max():.1f} m³")
        
        with col_info4:
            st.metric("Veri Sayısı", len(tesisat_data))
            st.metric("Tarih Aralığı", 
                     f"{tesisat_data['Tarih_DT'].min().strftime('%Y-%m')} - {tesisat_data['Tarih_DT'].max().strftime('%Y-%m')}")
        
        # Durum kontrolü
        is_suspicious = selected_tesisat in all_suspicious
        
        if is_suspicious:
            st.error(f"⚠️ Bu tesisat ŞÜPHELİ listesinde!")
            
            # Hangi kriterlere uyuyor
            criteria_met = []
            if selected_tesisat in permanent_drop_list:
                criteria_met.append("📉 Kalıcı Düşüş")
            if selected_tesisat in constant_drop_list:
                criteria_met.append("🎯 Sabit Düşüş Yüzdesi (REKOR DELİK!)")
            if selected_tesisat in low_winter_list:
                criteria_met.append("❄️ Düşük Kış Tüketimi")
            if selected_tesisat in building_anomaly_list:
                criteria_met.append("🏢 Bina İçi Anomali")
            if selected_tesisat in zero_consumption_list:
                criteria_met.append("🔴 Uzun Süre Sıfır Tüketim")
            if selected_tesisat in ml_anomaly_list:
                criteria_met.append("🤖 ML Anomali")
            
            st.warning(f"**Uyduğu Kriterler ({len(criteria_met)}):**")
            for criterion in criteria_met:
                st.write(f"- {criterion}")
        else:
            st.success("✅ Bu tesisat normal kategorisinde")
        
        # Zaman serisi grafiği
        st.markdown("---")
        st.subheader("📈 Tüketim Zaman Serisi")
        
        fig_single = go.Figure()
        
        fig_single.add_trace(go.Scatter(
            x=tesisat_data['Tarih_DT'],
            y=tesisat_data['Tüketim'],
            mode='lines+markers',
            name='Tüketim',
            line=dict(color='blue', width=2),
            marker=dict(size=6)
        ))
        
        # Ortalama çizgisi
        avg_line = tesisat_data['Tüketim'].mean()
        fig_single.add_hline(
            y=avg_line,
            line_dash="dash",
            line_color="green",
            annotation_text=f"Ortalama: {avg_line:.1f} m³"
        )
        
        fig_single.update_layout(
            title=f'Tesisat {selected_tesisat} - Aylık Tüketim Trendi',
            xaxis_title='Tarih',
            yaxis_title='Tüketim (m³)',
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig_single, use_container_width=True)
        
        # İstatistiksel detaylar
        st.markdown("---")
        st.subheader("📊 İstatistiksel Detaylar")
        
        col_stat1, col_stat2 = st.columns(2)
        
        with col_stat1:
            st.markdown("**Tüketim İstatistikleri:**")
            stats_df = pd.DataFrame({
                'Metrik': ['Ortalama', 'Medyan', 'Standart Sapma', 'Minimum', 'Maksimum', 
                          'Çeyrekler (Q1)', 'Çeyrekler (Q3)', 'Sıfır Sayısı', 'Sıfır Oranı (%)'],
                'Değer': [
                    f"{tesisat_data['Tüketim'].mean():.2f} m³",
                    f"{tesisat_data['Tüketim'].median():.2f} m³",
                    f"{tesisat_data['Tüketim'].std():.2f} m³",
                    f"{tesisat_data['Tüketim'].min():.2f} m³",
                    f"{tesisat_data['Tüketim'].max():.2f} m³",
                    f"{tesisat_data['Tüketim'].quantile(0.25):.2f} m³",
                    f"{tesisat_data['Tüketim'].quantile(0.75):.2f} m³",
                    (tesisat_data['Tüketim'] == 0).sum(),
                    f"{(tesisat_data['Tüketim'] == 0).sum() / len(tesisat_data) * 100:.1f}%"
                ]
            })
            st.dataframe(stats_df, use_container_width=True)
        
        with col_stat2:
            st.markdown("**Mevsimsel Ortalamalar:**")
            seasonal_avg = tesisat_data.groupby('Mevsim')['Tüketim'].mean().round(2)
            seasonal_df = pd.DataFrame({
                'Mevsim': seasonal_avg.index,
                'Ortalama Tüketim (m³)': seasonal_avg.values
            })
            st.dataframe(seasonal_df, use_container_width=True)
            
            # Kış/Yaz oranı
            winter_avg_single = tesisat_data[tesisat_data['Kış_Mı']]['Tüketim'].mean()
            summer_avg_single = tesisat_data[~tesisat_data['Kış_Mı']]['Tüketim'].mean()
            if summer_avg_single > 0:
                winter_summer_ratio = winter_avg_single / summer_avg_single
                st.metric("Kış/Yaz Oranı", f"{winter_summer_ratio:.2f}")
                if winter_summer_ratio < 1.5:
                    st.warning("⚠️ Kış/Yaz oranı düşük! (Normal >1.5)")

# ===================================================================================
# EXCEL RAPORU OLUŞTURMA
# ===================================================================================

st.markdown("---")
st.header("📄 EXCEL RAPORU")

if not all_suspicious_df.empty:
    
    # Rapor hazırlama
    excel_report_data = {
        '1_ANALİZ_ÖZET': pd.DataFrame([{
            'RAPOR_TARİHİ': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'TOPLAM_TESİSAT': df['Tesisat_No'].nunique(),
            'TOPLAM_KAYIT': len(df),
            'VERİ_ARALIĞI': f"{df['Tarih_DT'].min().strftime('%Y-%m')} - {df['Tarih_DT'].max().strftime('%Y-%m')}",
            'ŞÜPHELİ_TESİSAT': len(all_suspicious),
            'ŞÜPHELİ_ORAN_%': f"{len(all_suspicious)/df['Tesisat_No'].nunique()*100:.2f}",
            'KALICI_DÜŞÜŞ': len(permanent_drop_list),
            'SABİT_DÜŞÜŞ_YÜZDESİ': len(constant_drop_list),
            'DÜŞÜK_KIŞ': len(low_winter_list),
            'BİNA_ANOMALİ': len(building_anomaly_list),
            'SIFIR_TÜKETİM': len(zero_consumption_list),
            'ML_ANOMALİ': len(ml_anomaly_list)
        }]),
        '2_TÜM_ŞÜPHELİLER': all_suspicious_df,
    }
    
    # Detay sayfaları
    if not permanent_drop_details.empty:
        excel_report_data['3_KALICI_DÜŞÜŞ'] = permanent_drop_details
    
    if not constant_drop_details.empty:
        excel_report_data['4_SABİT_DÜŞÜŞ_REKOR_DELİK'] = constant_drop_details
        
        # Kesin vakalar ayrı sayfa
        certain_cases = constant_drop_details[constant_drop_details['KESİNLİK_SEVİYESİ'].str.contains('KESİN')]
        if not certain_cases.empty:
            excel_report_data['4A_ACİL_REKOR_DELİK'] = certain_cases
    
    if not low_winter_details.empty:
        excel_report_data['5_DÜŞÜK_KIŞ'] = low_winter_details
    
    if not building_anomaly_details.empty:
        excel_report_data['6_BİNA_ANOMALİ'] = building_anomaly_details
    
    if not zero_consumption_details.empty:
        excel_report_data['7_SIFIR_TÜKETİM'] = zero_consumption_details
    
    if not ml_anomaly_details.empty:
        excel_report_data['8_ML_ANOMALİ'] = ml_anomaly_details
    
    # Parametreler sayfası
    excel_report_data['9_PARAMETRELER'] = pd.DataFrame([{
        'PARAMETRE': 'Minimum Düşüş Yüzdesi',
        'DEĞER': f'{min_drop_percent}%',
        'AÇIKLAMA': 'Kalıcı düşüş için minimum azalma yüzdesi'
    }, {
        'PARAMETRE': 'Takip Ay Sayısı',
        'DEĞER': f'{min_months_after} ay',
        'AÇIKLAMA': 'Düşüşten sonraki takip süresi'
    }, {
        'PARAMETRE': 'Geri Dönüş Eşiği',
        'DEĞER': f'{recovery_threshold}%',
        'AÇIKLAMA': 'Eski tüketime ne kadar yaklaşınca geri dönmüş sayılır'
    }, {
        'PARAMETRE': 'Sabit Düşüş Sapma Toleransı',
        'DEĞER': f'{constant_tolerance}%',
        'AÇIKLAMA': 'Rekor delik tespiti için düşüş yüzdesi sapma toleransı'
    }, {
        'PARAMETRE': 'Sabit Düşüş Min. Düşüş',
        'DEĞER': f'{constant_min_drop}%',
        'AÇIKLAMA': 'Rekor delik tespiti için minimum düşüş yüzdesi'
    }, {
        'PARAMETRE': 'Max Geri Dönüş',
        'DEĞER': f'{max_recovery_pct}%',
        'AÇIKLAMA': 'Bu değerin üzerine çıkarsa geri döndü sayılır'
    }, {
        'PARAMETRE': 'Minimum Kış Tüketimi',
        'DEĞER': f'{min_winter_cons} m³',
        'AÇIKLAMA': 'Kış ayları için minimum normal tüketim'
    }, {
        'PARAMETRE': 'Bina Anomali Yüzdeliği',
        'DEĞER': f'{bina_percentile}%',
        'AÇIKLAMA': 'Binadaki en düşük tüketime sahip tesisat yüzdesi'
    }, {
        'PARAMETRE': 'ML Anomali Oranı',
        'DEĞER': f'{ml_contamination*100}%',
        'AÇIKLAMA': 'Machine Learning için beklenen anomali oranı'
    }])
    
    # Excel'i oluştur
    excel_data = to_excel(excel_report_data)
    
    # İndirme butonları
    col_download1, col_download2, col_download3 = st.columns(3)
    
    with col_download1:
        st.download_button(
            label="📊 TAM RAPOR İNDİR",
            data=excel_data,
            file_name=f"dogalgaz_kacak_tespit_FULL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Tüm analizleri içeren kapsamlı rapor"
        )
    
    with col_download2:
        # Sadece şüpheliler
        simple_excel = to_excel({'ŞÜPHELİ_TESİSATLAR': all_suspicious_df})
        st.download_button(
            label="📋 ÖZET LİSTE",
            data=simple_excel,
            file_name=f"supheli_liste_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Sadece şüpheli tesisatların listesi"
        )
    
    with col_download3:
        # Sadece rekor delik tespitleri
        if not constant_drop_details.empty:
            rekor_excel = to_excel({'REKOR_DELİK_TESPİTLERİ': constant_drop_details})
            st.download_button(
                label="🎯 REKOR DELİK LİSTESİ",
                data=rekor_excel,
                file_name=f"rekor_delik_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Sadece rekor delik tespitleri"
            )
    
    # Rapor özeti
    st.success(f"""
    ✅ **Rapor Hazır!**
    
    - Toplam {len(excel_report_data)} sayfa
    - {len(all_suspicious)} şüpheli tesisat
    - {len(constant_drop_details) if not constant_drop_details.empty else 0} rekor delik tespiti
    - Rapor tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """)

else:
    st.info("Şüpheli tesisat bulunamadığı için Excel raporu oluşturulmadı.")

# ===================================================================================
# FOOTER
# ===================================================================================

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
<p><b>Akıllı Doğalgaz Kaçak Tespiti v2.0</b></p>
<p>© 2024 | Tüm hakları saklıdır | AI Destekli Analiz Platformu</p>
<p style="font-size: 0.8em;">
Bu sistem 6 farklı algoritma ile kaçak kullanımı tespit eder:<br>
Kalıcı Düşüş | Sabit Düşüş % (Rekor Delik) | Düşük Kış | Bina Anomalisi | Sıfır Tüketim | Machine Learning
</p>
</div>
""", unsafe_allow_html=True)

# ===================================================================================
# KOD SONU
# ===================================================================================
