import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
from io import BytesIO
import tempfile
import os

warnings.filterwarnings('ignore')

# Sayfa ayarları
st.set_page_config(page_title="Doğalgaz Kaçak Tespiti", layout="wide", page_icon="🔥")
st.title("🔥 AKILLI DOĞALGAZ KAÇAK KULLANIM TESPİT SİSTEMİ")
st.markdown("**Muhatap ve Cihaz Değişim Analizi ile**")

# Sidebar
st.sidebar.header("🎛️ ANALİZ PARAMETRELERİ")

# Excel yazma fonksiyonu
def to_excel(df_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in df_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    processed_data = output.getvalue()
    return processed_data

# DOSYA OKUMA FONKSİYONU - TÜRKÇE FORMATLAR İÇİN
def read_file_with_turkish_support(uploaded_file):
    """Türkçe formatları destekleyen dosya okuma"""
    
    # Geçici dosya oluştur
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, uploaded_file.name)
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Dosya türü
    file_type = 'xlsx' if uploaded_file.name.lower().endswith('.xlsx') else 'csv'
    
    try:
        if file_type == 'xlsx':
            # Excel dosyası
            df = pd.read_excel(file_path, engine='openpyxl', dtype=str)
        else:
            # CSV dosyası - Türkçe formatlar için
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-9', 
                              'windows-1254', 'cp1254', 'cp1252']
            
            for encoding in encodings_to_try:
                try:
                    # Türkçe ondalık ayracı (virgül) için decimal parametresi
                    df = pd.read_csv(file_path, encoding=encoding, 
                                    sep=None, engine='python',  # Otomatik ayraç tespiti
                                    dtype=str,
                                    decimal=',')  # Türkçe ondalık ayracı
                    st.sidebar.info(f"✅ Kodlama: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    # Diğer hatalar için devam et
                    continue
            else:
                # Son çare
                df = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip', 
                               sep=None, engine='python', dtype=str, decimal=',')
        
        # Temizlik
        os.remove(file_path)
        os.rmdir(temp_dir)
        
        return df
    
    except Exception as e:
        # Temizlik
        try:
            os.remove(file_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        st.error(f"❌ Dosya okuma hatası: {str(e)[:200]}")
        return None

# TÜRKÇE ONDALIK DÖNÜŞÜMÜ
def turkish_to_float(value):
    """Türkçe ondalık formatını float'a çevir"""
    if pd.isna(value) or str(value).strip() == '':
        return np.nan
    
    try:
        # String'e çevir
        str_val = str(value).strip()
        
        # Binlik ayracı nokta, ondalık ayracı virgül olan Türkçe format
        if ',' in str_val and '.' in str_val:
            # 1.234,56 formatı -> binlik nokta, ondalık virgül
            str_val = str_val.replace('.', '').replace(',', '.')
        elif ',' in str_val:
            # 1234,56 formatı -> ondalık virgül
            str_val = str_val.replace(',', '.')
        
        return float(str_val)
    except:
        return np.nan

# TARİH DÖNÜŞÜMÜ - TÜRKÇE FORMATLAR İÇİN
def parse_turkish_date(date_val):
    """Türkçe tarih formatlarını parse et"""
    if pd.isna(date_val) or str(date_val).strip() == '':
        return pd.NaT
    
    date_str = str(date_val).strip()
    
    # Farklı formatları dene
    formats_to_try = [
        '%d.%m.%Y',    # 1.06.2016
        '%d/%m/%Y',    # 1/06/2016
        '%d-%m-%Y',    # 1-06-2016
        '%Y.%m.%d',    # 2016.06.01
        '%Y/%m/%d',    # 2016/06/01
        '%Y-%m-%d',    # 2016-06-01
        '%m.%Y',       # 06.2016
        '%m/%Y',       # 06/2016
        '%m-%Y',       # 06-2016
        '%Y.%m',       # 2016.06
        '%Y/%m',       # 2016/06
        '%Y-%m',       # 2016-06
        '%Y%m',        # 201606
    ]
    
    for fmt in formats_to_try:
        try:
            if fmt in ['%m.%Y', '%m/%Y', '%m-%Y', '%Y.%m', '%Y/%m', '%Y-%m', '%Y%m']:
                # Sadece ay-yıl formatı
                dt = datetime.strptime(date_str, fmt)
                return datetime(dt.year, dt.month, 1)
            else:
                # Tam tarih formatı
                dt = datetime.strptime(date_str, fmt)
                return dt
        except:
            continue
    
    return pd.NaT

# 1. VERİ YÜKLEME
uploaded_file = st.sidebar.file_uploader("📂 Excel/CSV dosyasını yükleyin", type=['xlsx', 'csv'])

if uploaded_file is not None:
    try:
        # Dosyayı oku (Türkçe destekli)
        df = read_file_with_turkish_support(uploaded_file)
        
        if df is None or df.empty:
            st.error("❌ Dosya boş veya okunamadı!")
            st.stop()
        
        # Sütun isimlerini standardize et (Türkçe karakterleri koru)
        df.columns = df.columns.astype(str).str.strip()
        
        # Tüm sütunları temizle
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()
        
        # Sütun eşleştirme (Türkçe sütun isimleri için)
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            
            # Tarih sütunları
            if any(word in col_lower for word in ['tarikh', 'tarih', 'date', 'tarih']):
                column_mapping[col] = 'tarih'
            
            # Cihaz sütunları
            elif any(word in col_lower for word in ['cihaz', 'device', 'sayaç', 'sayac']):
                column_mapping[col] = 'cihaz_no'
            
            # Muhatap sütunları
            elif any(word in col_lower for word in ['muhatap', 'abone', 'müşteri', 'musteri', 'customer']):
                column_mapping[col] = 'muhatap_no'
            
            # Tesisat sütunları
            elif any(word in col_lower for word in ['tesisat', 'installation', 'tesisat numarası']):
                column_mapping[col] = 'tesisat_no'
            
            # Bina sütunları
            elif any(word in col_lower for word in ['bina', 'building', 'bina numarası']):
                column_mapping[col] = 'bina_no'
            
            # Tüketim sütunları
            elif any(word in col_lower for word in ['tüketim', 'tuketim', 'consumption', 'tüketim miktarı', 'miktar']):
                column_mapping[col] = 'tuketim'
        
        # Eşleşen sütunları yeniden adlandır
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        # Eksik sütunları kontrol et
        expected_columns = ['tarih', 'tesisat_no', 'bina_no', 'tuketim']
        missing_columns = []
        
        for col in expected_columns:
            if col not in df.columns:
                missing_columns.append(col)
        
        if missing_columns:
            st.error(f"❌ Eksik sütunlar: {missing_columns}")
            st.info(f"📋 Mevcut sütunlar: {list(df.columns)}")
            
            # Manuel sütun seçimi
            st.subheader("📝 Sütun Eşleştirmesi")
            
            col_tarih = st.selectbox("Tarih sütununu seçin:", df.columns, index=0)
            col_tesisat = st.selectbox("Tesisat No sütununu seçin:", df.columns, index=1 if len(df.columns) > 1 else 0)
            col_bina = st.selectbox("Bina No sütununu seçin:", df.columns, index=2 if len(df.columns) > 2 else 0)
            col_tuketim = st.selectbox("Tüketim sütununu seçin:", df.columns, index=3 if len(df.columns) > 3 else 0)
            
            if st.button("✅ Sütunları Eşleştir"):
                df = df.rename(columns={
                    col_tarih: 'tarih',
                    col_tesisat: 'tesisat_no',
                    col_bina: 'bina_no',
                    col_tuketim: 'tuketim'
                })
                st.success("Sütunlar başarıyla eşleştirildi!")
            else:
                st.stop()
        
        # Opsiyonel sütunları kontrol et
        if 'muhatap_no' not in df.columns:
            # Muhatap sütunu yoksa, varsa ekle
            for col in df.columns:
                if 'muhatap' in col.lower():
                    df = df.rename(columns={col: 'muhatap_no'})
                    break
        
        if 'cihaz_no' not in df.columns:
            # Cihaz sütunu yoksa, varsa ekle
            for col in df.columns:
                if 'cihaz' in col.lower():
                    df = df.rename(columns={col: 'cihaz_no'})
                    break
        
        # Veri dönüşümleri
        st.info("🔄 Veriler dönüştürülüyor...")
        
        # 1. Tüketimi Türkçe formatına göre dönüştür
        df['tuketim'] = df['tuketim'].apply(turkish_to_float)
        
        # NaN tüketimleri kontrol et
        nan_count = df['tuketim'].isna().sum()
        if nan_count > 0:
            st.warning(f"⚠️ {nan_count} kayıtın tüketim değeri hatalı/boş. Bu kayıtlar kaldırılıyor.")
            df = df.dropna(subset=['tuketim'])
        
        # 2. Tarihleri dönüştür
        df['tarih_dt'] = df['tarih'].apply(parse_turkish_date)
        
        # Geçersiz tarihleri kontrol et
        invalid_dates = df['tarih_dt'].isna().sum()
        if invalid_dates > 0:
            st.warning(f"⚠️ {invalid_dates} kayıt için tarih parse edilemedi")
            df = df.dropna(subset=['tarih_dt'])
        
        # 3. Muhatap ve Cihaz numaralarını temizle
        if 'muhatap_no' in df.columns:
            df['muhatap_no'] = df['muhatap_no'].fillna('Bilinmiyor').astype(str)
        
        if 'cihaz_no' in df.columns:
            df['cihaz_no'] = df['cihaz_no'].fillna('Bilinmiyor').astype(str)
        
        # Tesisat ve Bina numaralarını temizle
        df['tesisat_no'] = df['tesisat_no'].fillna('').astype(str)
        df['bina_no'] = df['bina_no'].fillna('').astype(str)
        
        # Sırala
        df = df.sort_values(['tesisat_no', 'tarih_dt'])
        
        st.sidebar.success(f"✅ Veri yüklendi: {len(df):,} kayıt, {df['tesisat_no'].nunique():,} tesisat")
        
        # Veri önizleme
        with st.expander("📊 Veri Önizleme (İlk 10 satır)"):
            st.dataframe(df.head(10), use_container_width=True)
        
        # Veri kalitesi raporu
        with st.expander("📈 Veri Kalitesi Raporu"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Toplam Kayıt", len(df))
                st.metric("Tesisat Sayısı", df['tesisat_no'].nunique())
            with col2:
                st.metric("Başlangıç Tarihi", df['tarih_dt'].min().strftime('%Y-%m'))
                st.metric("Bitiş Tarihi", df['tarih_dt'].max().strftime('%Y-%m'))
            with col3:
                st.metric("Ort. Tüketim", f"{df['tuketim'].mean():.1f} m³")
                st.metric("Top. Tüketim", f"{df['tuketim'].sum():,.0f} m³")
        
    except Exception as e:
        st.error(f"❌ Veri yükleme hatası: {str(e)}")
        st.info("""
        🔧 **Türkçe Formatlar İçin İpuçları:**
        
        1. **CSV olarak kaydedin**: Excel'de "Farklı Kaydet" > "CSV UTF-8 (Virgülle Ayrılmış)"
        2. **Ondalık ayracı**: 30,75 şeklinde kalabilir (virgül)
        3. **Tarih formatı**: 1.06.2016 şeklinde kalabilir (nokta ile)
        4. **Sütun isimleri**: Türkçe karakterler sorun değil
        
        **Alternatif**: Excel dosyası olarak yükleyin (.xlsx)
        """)
        st.stop()
    
    # Mevsim tanımları
    def get_season(month):
        if month in [12, 1, 2]:
            return 'Kış'
        elif month in [6, 7, 8]:
            return 'Yaz'
        else:
            return 'Diğer'
    
    df['mevsim'] = df['tarih_dt'].dt.month.apply(get_season)
    df['kis_mi'] = df['tarih_dt'].dt.month.isin([12, 1, 2, 3])
    
    # 2. PARAMETRELER
    st.sidebar.subheader("🎯 KALICI DÜŞÜŞ PARAMETRELERİ")
    col_param1, col_param2 = st.sidebar.columns(2)
    
    with col_param1:
        min_drop_percent = st.slider("Min. Düşüş %", 50, 95, 75)
        min_months_after = st.slider("Takip Ay Sayısı", 3, 12, 6)
    
    with col_param2:
        recovery_threshold = st.slider("Geri Dönüş Eşiği %", 30, 80, 60)
        min_winter_cons = st.slider("Min. Kış Tüketimi", 0, 50, 15)
    
    st.sidebar.subheader("🏢 BİNA ANALİZİ")
    bina_percentile = st.slider("Anomali Yüzdelik", 5, 30, 10)
    
    # 3. ANALİZ FONKSİYONLARI
    def detect_low_winter_consumption(df, threshold=15):
        kis_data = df[df['kis_mi'] == True]
        results = []
        details = []
        
        for tesisat in df['tesisat_no'].unique():
            tesisat_kis = kis_data[kis_data['tesisat_no'] == tesisat]
            
            if len(tesisat_kis) > 0:
                avg_kis = tesisat_kis['tuketim'].mean()
                
                if avg_kis < threshold:
                    results.append(tesisat)
                    details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': tesisat_kis['bina_no'].iloc[0],
                        'ORT_KIŞ (m³)': round(avg_kis, 1),
                        'EŞİK (m³)': threshold
                    })
        
        return results, pd.DataFrame(details)
    
    def detect_building_anomaly(df, percentile=10):
        results = []
        details = []
        
        for bina in df['bina_no'].unique():
            bina_df = df[df['bina_no'] == bina]
            tesisatlar = bina_df['tesisat_no'].unique()
            
            if len(tesisatlar) > 2:
                tesisat_avgs = []
                
                for tesisat in tesisatlar:
                    tesisat_avg = bina_df[bina_df['tesisat_no'] == tesisat]['tuketim'].mean()
                    tesisat_avgs.append((tesisat, tesisat_avg))
                
                tesisat_avgs.sort(key=lambda x: x[1])
                num_suspicious = max(1, int(len(tesisat_avgs) * percentile / 100))
                
                for i in range(num_suspicious):
                    tesisat, avg = tesisat_avgs[i]
                    results.append(tesisat)
                    details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': bina,
                        'TESİSAT_ORT (m³)': round(avg, 1),
                        'SIRALAMA': f"{i+1}/{len(tesisat_avgs)}"
                    })
        
        return results, pd.DataFrame(details)
    
    def detect_zero_consumption(df, min_months=4):
        results = []
        details = []
        
        for tesisat in df['tesisat_no'].unique():
            tesisat_df = df[df['tesisat_no'] == tesisat].sort_values('tarih_dt')
            last_months = tesisat_df.tail(min_months)
            
            if len(last_months) >= min_months:
                if (last_months['tuketim'] == 0).all():
                    results.append(tesisat)
                    details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': tesisat_df['bina_no'].iloc[0],
                        'SIFIR_AY_SAYISI': len(last_months),
                        'BAŞLANGIÇ': last_months['tarih_dt'].iloc[0].strftime('%Y-%m'),
                        'BİTİŞ': last_months['tarih_dt'].iloc[-1].strftime('%Y-%m')
                    })
        
        return results, pd.DataFrame(details)
    
    def detect_smart_permanent_drop(df, min_drop_pct=75, min_months_after=6, recovery_threshold_pct=60):
        """Akıllı kalıcı düşüş tespiti"""
        
        results = []
        all_details = []
        
        for tesisat in df['tesisat_no'].unique():
            tesisat_df = df[df['tesisat_no'] == tesisat].sort_values('tarih_dt')
            
            if len(tesisat_df) < 12:
                continue
            
            # Cihaz değişimi kontrolü
            cihaz_degisim_var = False
            if 'cihaz_no' in tesisat_df.columns:
                valid_cihazlar = tesisat_df[tesisat_df['cihaz_no'] != 'Bilinmiyor']['cihaz_no'].unique()
                if len(valid_cihazlar) > 1:
                    cihaz_degisim_var = True
            
            # Muhatap değişimi kontrolü
            muhatap_degisim_var = False
            if 'muhatap_no' in tesisat_df.columns:
                valid_muhataplar = tesisat_df[tesisat_df['muhatap_no'] != 'Bilinmiyor']['muhatap_no'].unique()
                if len(valid_muhataplar) > 1:
                    muhatap_degisim_var = True
            
            # Düşüş analizi
            if len(tesisat_df) >= min_months_after + 3:
                for i in range(3, len(tesisat_df) - min_months_after):
                    before_avg = tesisat_df.iloc[i-3:i]['tuketim'].mean()
                    after_avg = tesisat_df.iloc[i:i+min_months_after]['tuketim'].mean()
                    
                    if before_avg > 0 and after_avg > 0:
                        drop_pct = ((before_avg - after_avg) / before_avg) * 100
                        
                        if drop_pct >= min_drop_pct:
                            # Geri dönüş kontrolü
                            recovery_occurred = False
                            for _, row in tesisat_df.iloc[i:].iterrows():
                                if (row['tuketim'] / before_avg) * 100 >= recovery_threshold_pct:
                                    recovery_occurred = True
                                    break
                            
                            if not recovery_occurred:
                                results.append(tesisat)
                                
                                # Risk skoru hesapla
                                risk_score = drop_pct
                                if not cihaz_degisim_var:
                                    risk_score += 30  # Cihaz değişmediyse risk artar
                                
                                if muhatap_degisim_var:
                                    risk_score += 20  # Muhatap değiştiyse risk artar
                                
                                risk_score = min(100, risk_score)
                                
                                # Öncelik belirle
                                if risk_score >= 80:
                                    oncelik = 'YÜKSEK'
                                elif risk_score >= 60:
                                    oncelik = 'ORTA'
                                else:
                                    oncelik = 'DÜŞÜK'
                                
                                all_details.append({
                                    'TESİSAT_NO': tesisat,
                                    'BİNA_NO': tesisat_df['bina_no'].iloc[0],
                                    'MUHATAP_NO': tesisat_df['muhatap_no'].iloc[-1] if 'muhatap_no' in tesisat_df.columns else 'Bilgi Yok',
                                    'CIHAZ_NO': tesisat_df['cihaz_no'].iloc[-1] if 'cihaz_no' in tesisat_df.columns else 'Bilgi Yok',
                                    'DÜŞÜŞ_%': round(drop_pct, 1),
                                    'CIHAZ_DEĞİŞİMİ': 'EVET' if cihaz_degisim_var else 'HAYIR',
                                    'MUHATAP_DEĞİŞİMİ': 'EVET' if muhatap_degisim_var else 'HAYIR',
                                    'RİSK_SKORU': round(risk_score, 0),
                                    'ÖNCELİK': oncelik,
                                    'ÖNCE_ORT (m³)': round(before_avg, 1),
                                    'SONRA_ORT (m³)': round(after_avg, 1)
                                })
                            break
        
        details_df = pd.DataFrame(all_details)
        if not details_df.empty:
            details_df = details_df.sort_values('RİSK_SKORU', ascending=False)
        
        return results, details_df
    
    # 4. ANALİZLERİ ÇALIŞTIR
    st.header("🔍 AKILLI ANALİZ SONUÇLARI")
    
    with st.spinner("Analizler çalıştırılıyor..."):
        # Akıllı düşüş analizi
        smart_drop_list, smart_drop_details = detect_smart_permanent_drop(
            df, min_drop_pct=min_drop_percent,
            min_months_after=min_months_after,
            recovery_threshold_pct=recovery_threshold
        )
        
        # Diğer analizler
        winter_list, winter_details = detect_low_winter_consumption(df, threshold=min_winter_cons)
        bina_list, bina_details = detect_building_anomaly(df, percentile=bina_percentile)
        zero_list, zero_details = detect_zero_consumption(df, min_months=4)
        
        # Tüm şüpheliler
        all_sus = list(set(smart_drop_list + winter_list + bina_list + zero_list))
        
        # Detaylı liste
        all_details_list = []
        for tesisat in all_sus:
            tesisat_data = df[df['tesisat_no'] == tesisat]
            
            criteria = []
            if tesisat in smart_drop_list:
                criteria.append('AKILLI_DÜŞÜŞ')
            if tesisat in winter_list:
                criteria.append('DÜŞÜK_KIŞ')
            if tesisat in bina_list:
                criteria.append('BİNA_ANOMALİ')
            if tesisat in zero_list:
                criteria.append('SIFIR_TÜKETİM')
            
            risk_score = len(criteria) * 25
            if tesisat in smart_drop_list:
                smart_info = smart_drop_details[smart_drop_details['TESİSAT_NO'] == tesisat]
                if not smart_info.empty:
                    risk_score = smart_info.iloc[0]['RİSK_SKORU']
            
            all_details_list.append({
                'TESİSAT_NO': tesisat,
                'BİNA_NO': tesisat_data['bina_no'].iloc[0],
                'MUHATAP_NO': tesisat_data['muhatap_no'].iloc[-1] if 'muhatap_no' in tesisat_data.columns else 'Bilgi Yok',
                'KRİTERLER': ', '.join(criteria),
                'RİSK_SKORU': risk_score,
                'ÖNCELİK': 'YÜKSEK' if risk_score >= 70 else 'ORTA' if risk_score >= 40 else 'DÜŞÜK'
            })
        
        all_sus_df = pd.DataFrame(all_details_list)
        if not all_sus_df.empty:
            all_sus_df = all_sus_df.sort_values('RİSK_SKORU', ascending=False)
    
    # 5. SONUÇLARI GÖSTER
    st.subheader("📊 ÖZET RAPOR")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Toplam Şüpheli", len(all_sus))
    with col2:
        st.metric("Akıllı Düşüş", len(smart_drop_list))
    with col3:
        st.metric("Düşük Kış", len(winter_list))
    with col4:
        high_risk = len([x for x in all_details_list if x['RİSK_SKORU'] >= 70])
        st.metric("Yüksek Risk", high_risk)
    
    # Tablar
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 TÜM ŞÜPHELİLER", 
        "🚨 AKILLI DÜŞÜŞ",
        "❄️ DÜŞÜK KIŞ",
        "🔍 TEKİL ANALİZ"
    ])
    
    with tab1:
        if not all_sus_df.empty:
            st.dataframe(all_sus_df, use_container_width=True)
        else:
            st.success("✅ Şüpheli tesisat bulunamadı")
    
    with tab2:
        if not smart_drop_details.empty:
            st.dataframe(smart_drop_details, use_container_width=True)
        else:
            st.info("Akıllı düşüş tespit edilmedi")
    
    with tab3:
        if not winter_details.empty:
            st.dataframe(winter_details, use_container_width=True)
    
    with tab4:
        st.subheader("Tekil Tesisat Analizi")
        selected_tesisat = st.selectbox("Tesisat seçin:", df['tesisat_no'].unique()[:50])
        
        if selected_tesisat:
            tesisat_data = df[df['tesisat_no'] == selected_tesisat].sort_values('tarih_dt')
            
            # Grafik
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=tesisat_data['tarih_dt'], y=tesisat_data['tuketim'],
                mode='lines+markers', name='Tüketim'
            ))
            
            fig.update_layout(
                title=f"Tesisat {selected_tesisat} Tüketim Geçmişi",
                xaxis_title="Tarih",
                yaxis_title="Tüketim (m³)"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # 6. EXCEL RAPORU
    st.markdown("---")
    st.header("📄 EXCEL RAPORU")
    
    if not all_sus_df.empty:
        excel_data = to_excel({
            'ANALİZ_ÖZET': pd.DataFrame([{
                'Tarih': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'Toplam_Tesisat': df['tesisat_no'].nunique(),
                'Şüpheli_Tesisat': len(all_sus),
                'Akıllı_Düşüş': len(smart_drop_list),
                'Düşük_Kış': len(winter_list)
            }]),
            'TÜM_ŞÜPHELİLER': all_sus_df,
            'AKILLI_DÜŞÜŞ': smart_drop_details
        })
        
        st.download_button(
            label="📊 EXCEL RAPORU İNDİR",
            data=excel_data,
            file_name=f"kacak_tespit_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("👈 Lütfen Excel veya CSV dosyasını yükleyin")
    st.markdown("""
    ### 📋 TÜRKÇE VERİ FORMATI DESTEĞİ:
    
    Bu uygulama aşağıdaki Türkçe formatları destekler:
    
    **1. ONDALIK SAYILAR:**
    - 30,75  (virgül ondalık ayracı)
    - 1.234,56  (binlik nokta, ondalık virgül)
    - 1234.56  (nokta ondalık ayracı - uluslararası)
    
    **2. TARİH FORMATLARI:**
    - 1.06.2016  (gün.ay.yıl)
    - 01/06/2016  (gün/ay/yıl)
    - 2016-06-01  (yıl-ay-gün)
    - 06.2016  (ay.yıl)
    
    **3. SÜTUN İSİMLERİ:**
    - Tarikh, Tarih, Date
    - Cihaz, Sayaç, Device
    - Muhatap, Abone, Müşteri
    - Tesisat Numarası, Installation No
    - Bina Numarası, Building No
    - Tüketim Miktarı, Consumption
    
    **4. DOSYA TİPLERİ:**
    - CSV (UTF-8, Windows-1254, ISO-8859-9)
    - Excel (.xlsx)
    
    ### 🎯 **VERİNİZİ HAZIRLARKEN:**
    
    1. **CSV için**: Excel'de "Farklı Kaydet" > "CSV UTF-8 (Virgülle Ayrılmış)"
    2. **Ondalık ayraç**: Türkçe formatı koruyabilirsiniz (virgül)
    3. **Tarih formatı**: Mevcut formatınızda kalabilir
    4. **Sütun isimleri**: Türkçe karakterler sorun değil
    """)
