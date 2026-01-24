import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
from io import BytesIO
warnings.filterwarnings('ignore')

# Sayfa ayarları
st.set_page_config(page_title="Doğalgaz Kaçak Tespiti", layout="wide", page_icon="🔥")
st.title("🔥 AKILLI DOĞALGAZ KAÇAK KULLANIM TESPİT SİSTEMİ")
st.markdown("**Ankara Konut Aboneleri - Kalıcı Düşüş Analizi**")

# Sidebar
st.sidebar.header("🎛️ ANALİZ PARAMETRELERİ")

# Excel yazma fonksiyonu
def to_excel(df_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in df_dict.items():
            # Sütun genişliklerini ayarla
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Sütun genişliklerini otomatik ayarla
            worksheet = writer.sheets[sheet_name]
            for column in df:
                column_length = max(df[column].astype(str).map(len).max(), len(column)) + 2
                col_idx = df.columns.get_loc(column)
                worksheet.column_dimensions[chr(65 + col_idx)].width = min(column_length, 50)
    
    processed_data = output.getvalue()
    return processed_data

# 1. VERİ YÜKLEME
uploaded_file = st.sidebar.file_uploader("📂 Excel/CSV dosyasını yükleyin", type=['xlsx', 'csv'])

if uploaded_file is not None:
    # Veriyi yükle
    try:
        if uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
        
        # Sütun isimlerini standardize et
        df.columns = df.columns.str.strip().str.lower()
        
        # Orijinal sütun isimlerini kontrol et
        column_mapping = {}
        for col in ['tarih', 'tesisat numarası', 'tesisat numarasi', 'bina numarası', 
                   'bina numarasi', 'tüketim miktarı', 'tüketim miktari']:
            for df_col in df.columns:
                if col in df_col.lower():
                    column_mapping[col.split()[0]] = df_col
        
        # Yeniden adlandır
        if 'tarih' in column_mapping:
            df = df.rename(columns={column_mapping['tarih']: 'Tarih'})
        if 'tesisat' in column_mapping:
            df = df.rename(columns={column_mapping['tesisat']: 'Tesisat_No'})
        if 'bina' in column_mapping:
            df = df.rename(columns={column_mapping['bina']: 'Bina_No'})
        if 'tüketim' in column_mapping:
            df = df.rename(columns={column_mapping['tüketim']: 'Tüketim'})
        
        # Gerekli sütunları kontrol et
        required_cols = ['Tarih', 'Tesisat_No', 'Bina_No', 'Tüketim']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"Eksik sütunlar: {missing_cols}")
            st.stop()
        
        st.sidebar.success(f"✅ Veri yüklendi: {len(df):,} kayıt, {df['Tesisat_No'].nunique():,} tesisat")
        
    except Exception as e:
        st.error(f"Veri yükleme hatası: {e}")
        st.stop()
    
    # 2. TARİH İŞLEME
    with st.expander("📊 VERİ ÖN İZLEME", expanded=False):
        st.dataframe(df.head(), use_container_width=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Toplam Kayıt", f"{len(df):,}")
        with col2:
            st.metric("Tesisat Sayısı", f"{df['Tesisat_No'].nunique():,}")
        with col3:
            st.metric("Bina Sayısı", f"{df['Bina_No'].nunique():,}")
    
    # Tarih formatını düzelt
    def parse_date_smart(date_val):
        try:
            if pd.isna(date_val):
                return pd.NaT
            
            date_str = str(date_val).strip()
            
            # Farklı formatları deneyelim
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
                if 1 <= month <= 12:
                    return datetime(year, month, 1)
            
            return pd.NaT
        except:
            return pd.NaT
    
    df['Tarih_DT'] = df['Tarih'].apply(parse_date_smart)
    df = df.dropna(subset=['Tarih_DT'])
    
    # Sırala ve ek sütunlar ekle
    df = df.sort_values(['Tesisat_No', 'Tarih_DT'])
    df['Yıl'] = df['Tarih_DT'].dt.year
    df['Ay'] = df['Tarih_DT'].dt.month
    df['Ay_Yıl'] = df['Tarih_DT'].dt.strftime('%Y-%m')
    
    # Mevsimleri belirle (Ankara için)
    def get_season_ankara(month):
        if month in [12, 1, 2]:
            return 'Kış (Aralık-Ocak-Şubat)'
        elif month in [3, 4, 5]:
            return 'İlkbahar'
        elif month in [6, 7, 8]:
            return 'Yaz'
        else:
            return 'Sonbahar'
    
    df['Mevsim'] = df['Ay'].apply(get_season_ankara)
    df['Kış_Mı'] = df['Ay'].isin([12, 1, 2, 3])
    
    # 3. PARAMETRELER
    st.sidebar.subheader("🎯 KALICI DÜŞÜŞ PARAMETRELERİ")
    
    col_param1, col_param2 = st.sidebar.columns(2)
    
    with col_param1:
        min_drop_percent = st.slider("Min. Düşüş %", 50, 95, 75, help="Tüketimdeki minimum düşüş yüzdesi")
        min_months_after = st.slider("Takip Ay Sayısı", 3, 12, 6, help="Düşüşten sonra takip edilecek ay sayısı")
    
    with col_param2:
        recovery_threshold = st.slider("Geri Dönüş Eşiği %", 30, 80, 60, 
                                     help="Eski tüketimin % kaçına çıkınca 'geri dönmüş' sayılsın?")
        min_winter_cons = st.slider("Min. Kış Tüketimi", 0, 50, 15, help="Kış ayları için min. normal tüketim (m³)")
    
    st.sidebar.subheader("🏢 BİNA ANALİZİ")
    bina_percentile = st.sidebar.slider("Anomali Yüzdelik", 5, 30, 10, 
                                      help="Binanın en düşük % kaçı anomali sayılsın?")
    
    # 4. EN ÖNEMLİ FONKSİYON: KALICI DÜŞÜŞ TESPİTİ (AÇIKLAMALI)
    def detect_permanent_drop_with_explanation(df, min_drop_pct=75, min_months_after=6, recovery_threshold_pct=60):
        """
        UZMAN KALICI DÜŞÜŞ TESPİT ALGORİTMASI - AÇIKLAMALI
        """
        
        results = []
        all_details = []
        
        tesisat_list = df['Tesisat_No'].unique()
        
        for tesisat in tesisat_list:
            tesisat_df = df[df['Tesisat_No'] == tesisat].sort_values('Tarih_DT')
            
            if len(tesisat_df) < 12:  # En az 1 yıl veri olsun
                continue
            
            tesisat_df = tesisat_df.reset_index(drop=True)
            
            # 1. POTANSİYEL DÜŞÜŞ NOKTALARINI BUL
            potential_drops = []
            
            for i in range(3, len(tesisat_df) - min_months_after):
                # Önceki 3 ayın ortalaması
                before_avg = tesisat_df.iloc[i-3:i]['Tüketim'].mean()
                
                # Sonraki N ayın ortalaması
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
            
            # 2. EN ANLAMLI DÜŞÜŞÜ SEÇ VE KALICILIK KONTROLÜ YAP
            if potential_drops:
                # En büyük düşüşü seç
                main_drop = max(potential_drops, key=lambda x: x['drop_pct'])
                drop_index = main_drop['index']
                drop_date = main_drop['date']
                
                # 3. KRİTİK KALICILIK KONTROLLERİ
                
                # a) Düşüşten SONRAKİ TÜM VERİYİ AL
                all_after = tesisat_df.iloc[drop_index:]
                
                # b) GERİ DÖNÜŞ KONTROLÜ - En önemli kontrol!
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
                
                # c) TREND ANALİZİ - Düşüşten sonra artış trendi var mı?
                if len(all_after) >= 3:
                    x = np.arange(len(all_after))
                    y = all_after['Tüketim'].values
                    trend_coef = np.polyfit(x, y, 1)[0]  # Lineer trend eğimi
                    
                    # Trend pozitifse ve anlamlıysa
                    trend_rising = (trend_coef > 0) and (abs(trend_coef) > (y.mean() * 0.05))
                else:
                    trend_rising = False
                
                # d) TUTARLILIK KONTROLÜ - Yüksek dalgalanma var mı?
                if len(all_after) >= 3:
                    cv_after = all_after['Tüketim'].std() / all_after['Tüketim'].mean() if all_after['Tüketim'].mean() > 0 else 0
                    high_volatility = cv_after > 0.5  # %50'den fazla dalgalanma
                else:
                    high_volatility = False
                
                # 4. KARAR: BU DÜŞÜŞ KALICI MI?
                is_permanent = False
                
                # Kalıcılık kriterleri
                if not recovery_occurred and not trend_rising:
                    is_permanent = True
                
                # 5. AÇIKLAMA OLUŞTUR
                explanation_parts = []
                
                if is_permanent:
                    explanation_parts.append(f"⏱️ {drop_date.strftime('%Y-%m')} tarihinde %{main_drop['drop_pct']:.1f} düşüş başladı")
                    
                    if not recovery_occurred:
                        explanation_parts.append(f"↗️ Düşüşten sonra eski tüketimin maksimum %{max_recovery_pct:.1f}'ine ulaştı (Eşik: %{recovery_threshold_pct})")
                    else:
                        explanation_parts.append(f"🔄 {recovery_month} ayında eski seviyenin %{recovery_threshold_pct} üzerine çıktı")
                    
                    if not trend_rising:
                        explanation_parts.append("📉 Düşüşten sonra artış trendi yok")
                    else:
                        explanation_parts.append("📈 Düşüşten sonra artış trendi var (dikkat!)")
                    
                    if high_volatility:
                        explanation_parts.append("⚡ Yüksek dalgalanma var")
                    else:
                        explanation_parts.append("📊 Tüketimde tutarlılık var")
                    
                    explanation = " | ".join(explanation_parts)
                    
                    # Risk skoru hesapla
                    risk_score = min(100, main_drop['drop_pct'])
                    
                    all_details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': tesisat_df['Bina_No'].iloc[0],
                        'DÜŞÜŞ_TARİHİ': drop_date.strftime('%Y-%m'),
                        'ÖNCEKİ_ORT (m³)': round(main_drop['before_avg'], 1),
                        'SONRAKİ_ORT (m³)': round(main_drop['after_avg'], 1),
                        'DÜŞÜŞ_%': round(main_drop['drop_pct'], 1),
                        'MAX_GERİ_DÖNÜŞ_%': round(max_recovery_pct, 1),
                        'GERİ_DÖNDÜ_MÜ?': 'EVET' if recovery_occurred else 'HAYIR',
                        'TREND_ARTIŞI': 'EVET' if trend_rising else 'HAYIR',
                        'RİSK_SKORU': round(risk_score, 0),
                        'KALICI_MI?': 'EVET' if is_permanent else 'HAYIR',
                        'AÇIKLAMA': explanation,
                        'TESPİT_NEDENİ': 'KALICI_DÜŞÜŞ' if is_permanent else 'GEÇİCİ_DÜŞÜŞ'
                    })
                    
                    if is_permanent:
                        results.append(tesisat)
        
        details_df = pd.DataFrame(all_details)
        if not details_df.empty:
            details_df = details_df.sort_values('RİSK_SKORU', ascending=False)
        
        return results, details_df
    
    # 5. DİĞER TESPİT FONKSİYONLARI (AÇIKLAMALI)
    def detect_low_winter_consumption_with_explanation(df, threshold=15):
        """Kış aylarında düşük tüketim tespiti - AÇIKLAMALI"""
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
                    
                    # Açıklama oluştur
                    explanation = f"❄️ Kış ayları ortalama tüketimi {avg_winter:.1f} m³ (Eşik: {threshold} m³)"
                    explanation += f" | Min: {min_winter:.1f} m³, Max: {max_winter:.1f} m³"
                    explanation += f" | Kış ay sayısı: {len(tesisat_winter)}"
                    
                    details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': tesisat_winter['Bina_No'].iloc[0],
                        'ORT_KIŞ_TÜKETİM (m³)': round(avg_winter, 1),
                        'MIN_KIŞ (m³)': round(min_winter, 1),
                        'MAX_KIŞ (m³)': round(max_winter, 1),
                        'KIŞ_AY_SAYISI': len(tesisat_winter),
                        'EŞİK (m³)': threshold,
                        'EŞİK_ALTINDA_MI?': 'EVET',
                        'AÇIKLAMA': explanation,
                        'TESPİT_NEDENİ': 'DÜŞÜK_KIŞ_TÜKETİMİ'
                    })
        
        return suspicious, pd.DataFrame(details)
    
    def detect_building_anomaly_with_explanation(df, percentile=10):
        """Bina içi karşılaştırma ile anomali tespiti - AÇIKLAMALI"""
        suspicious = []
        details = []
        
        for bina in df['Bina_No'].unique():
            bina_df = df[df['Bina_No'] == bina]
            tesisatlar = bina_df['Tesisat_No'].unique()
            
            if len(tesisatlar) > 2:  # Karşılaştırma için en az 3 tesisat
                tesisat_avgs = []
                
                for tesisat in tesisatlar:
                    tesisat_avg = bina_df[bina_df['Tesisat_No'] == tesisat]['Tüketim'].mean()
                    tesisat_avgs.append((tesisat, tesisat_avg))
                
                # Ortalamaya göre sırala
                tesisat_avgs.sort(key=lambda x: x[1])
                
                # En düşük %percentile'ı şüpheli olarak işaretle
                num_suspicious = max(1, int(len(tesisat_avgs) * percentile / 100))
                
                for i in range(num_suspicious):
                    tesisat, avg = tesisat_avgs[i]
                    suspicious.append(tesisat)
                    
                    # Bina ortalaması
                    bina_avg = np.mean([x[1] for x in tesisat_avgs])
                    
                    # Açıklama oluştur
                    explanation = f"🏢 {bina} binasında {i+1}. en düşük tüketim"
                    explanation += f" | Tesisat ort: {avg:.1f} m³, Bina ort: {bina_avg:.1f} m³"
                    explanation += f" | Fark: {bina_avg - avg:.1f} m³ (%{((bina_avg - avg) / bina_avg * 100):.1f})"
                    explanation += f" | Binadaki tesisat sayısı: {len(tesisat_avgs)}"
                    
                    details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': bina,
                        'TESİSAT_ORT (m³)': round(avg, 1),
                        'BİNA_ORT (m³)': round(bina_avg, 1),
                        'FARK (m³)': round(bina_avg - avg, 1),
                        'FARK_%': round(((bina_avg - avg) / bina_avg * 100), 1) if bina_avg > 0 else 0,
                        'SIRALAMA': f"{i+1}/{len(tesisat_avgs)}",
                        'BİNA_TESİSAT_SAYISI': len(tesisat_avgs),
                        'ANOMALİ': 'EVET',
                        'AÇIKLAMA': explanation,
                        'TESPİT_NEDENİ': 'BİNA_İÇİ_ANOMALİ'
                    })
        
        return suspicious, pd.DataFrame(details)
    
    def detect_zero_consumption_with_explanation(df, min_months=4):
        """Uzun süre sıfır tüketim tespiti - AÇIKLAMALI"""
        suspicious = []
        details = []
        
        for tesisat in df['Tesisat_No'].unique():
            tesisat_df = df[df['Tesisat_No'] == tesisat].sort_values('Tarih_DT')
            
            # Son N ayı kontrol et
            last_months = tesisat_df.tail(min_months)
            
            if len(last_months) >= min_months:
                if (last_months['Tüketim'] == 0).all():
                    suspicious.append(tesisat)
                    
                    # Önceki dönem tüketimi
                    if len(tesisat_df) > min_months:
                        before_zero = tesisat_df.iloc[-min_months-1]['Tüketim']
                    else:
                        before_zero = 0
                    
                    # Açıklama oluştur
                    explanation = f"🔴 {min_months} ay boyunca sürekli sıfır tüketim"
                    explanation += f" | Dönem: {last_months['Tarih_DT'].iloc[0].strftime('%Y-%m')} - {last_months['Tarih_DT'].iloc[-1].strftime('%Y-%m')}"
                    if before_zero > 0:
                        explanation += f" | Önceki ay tüketimi: {before_zero:.1f} m³"
                    
                    details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': tesisat_df['Bina_No'].iloc[0],
                        'SIFIR_AY_SAYISI': len(last_months),
                        'BAŞLANGIÇ_TARİH': last_months['Tarih_DT'].iloc[0].strftime('%Y-%m'),
                        'BİTİŞ_TARİH': last_months['Tarih_DT'].iloc[-1].strftime('%Y-%m'),
                        'ÖNCEKİ_TÜKETİM (m³)': round(before_zero, 1) if before_zero > 0 else 0,
                        'DURUM': 'SÜREKLİ_SIFIR',
                        'AÇIKLAMA': explanation,
                        'TESPİT_NEDENİ': 'UZUN_SÜRE_SIFIR_TÜKETİM'
                    })
        
        return suspicious, pd.DataFrame(details)
    
    # 6. ANALİZLERİ ÇALIŞTIR
    st.header("🔍 ANALİZ SONUÇLARI")
    
    with st.spinner("Analizler çalıştırılıyor... Lütfen bekleyin"):
        # Tüm analizleri AÇIKLAMALI olarak çalıştır
        suspicious_permanent, permanent_details = detect_permanent_drop_with_explanation(
            df, min_drop_pct=min_drop_percent, 
            min_months_after=min_months_after,
            recovery_threshold_pct=recovery_threshold
        )
        
        suspicious_winter, winter_details = detect_low_winter_consumption_with_explanation(
            df, threshold=min_winter_cons
        )
        
        suspicious_building, building_details = detect_building_anomaly_with_explanation(
            df, percentile=bina_percentile
        )
        
        suspicious_zero, zero_details = detect_zero_consumption_with_explanation(
            df, min_months=4
        )
        
        # Birleştirilmiş şüpheli listesi
        all_suspicious = list(set(
            suspicious_permanent + 
            suspicious_winter + 
            suspicious_building + 
            suspicious_zero
        ))
        
        # 7. TÜM ŞÜPHELİLERİN DETAYLI AÇIKLAMALI LİSTESİ
        all_suspicious_details = []
        
        for tesisat in all_suspicious:
            tesisat_data = df[df['Tesisat_No'] == tesisat]
            avg_consumption = tesisat_data['Tüketim'].mean()
            last_consumption = tesisat_data['Tüketim'].iloc[-1]
            consumption_std = tesisat_data['Tüketim'].std()
            total_months = len(tesisat_data)
            
            # Hangi kriterlere uyuyor? VE NEDENLERİ
            criteria_list = []
            explanations = []
            
            # Kalıcı düşüş kontrolü
            if tesisat in suspicious_permanent:
                perm_details = permanent_details[permanent_details['TESİSAT_NO'] == tesisat]
                if not perm_details.empty:
                    criteria_list.append('KALICI_DÜŞÜŞ')
                    explanations.append(f"📉 {perm_details.iloc[0]['AÇIKLAMA']}")
            
            # Düşük kış tüketimi
            if tesisat in suspicious_winter:
                winter_info = winter_details[winter_details['TESİSAT_NO'] == tesisat]
                if not winter_info.empty:
                    criteria_list.append('DÜŞÜK_KIŞ')
                    explanations.append(f"❄️ {winter_info.iloc[0]['AÇIKLAMA']}")
            
            # Bina anomalisi
            if tesisat in suspicious_building:
                bina_info = building_details[building_details['TESİSAT_NO'] == tesisat]
                if not bina_info.empty:
                    criteria_list.append('BİNA_ANOMALİ')
                    explanations.append(f"🏢 {bina_info.iloc[0]['AÇIKLAMA']}")
            
            # Sıfır tüketim
            if tesisat in suspicious_zero:
                zero_info = zero_details[zero_details['TESİSAT_NO'] == tesisat]
                if not zero_info.empty:
                    criteria_list.append('SIFIR_TÜKETİM')
                    explanations.append(f"🔴 {zero_info.iloc[0]['AÇIKLAMA']}")
            
            # Tüm açıklamaları birleştir
            full_explanation = " | ".join(explanations)
            
            # Risk skoru hesapla
            risk_score = 0
            if 'KALICI_DÜŞÜŞ' in criteria_list:
                risk_score += 40
            if 'SIFIR_TÜKETİM' in criteria_list:
                risk_score += 30
            if 'DÜŞÜK_KIŞ' in criteria_list:
                risk_score += 20
            if 'BİNA_ANOMALİ' in criteria_list:
                risk_score += 10
            
            # Öncelik belirle
            if risk_score >= 60:
                priority = 'YÜKSEK'
                priority_explanation = 'Çoklu kriter + yüksek risk'
            elif risk_score >= 30:
                priority = 'ORTA'
                priority_explanation = 'Birkaç kriter + orta risk'
            else:
                priority = 'DÜŞÜK'
                priority_explanation = 'Tek kriter + düşük risk'
            
            all_suspicious_details.append({
                'TESİSAT_NO': tesisat,
                'BİNA_NO': tesisat_data['Bina_No'].iloc[0],
                'ORTALAMA_TÜKETİM (m³)': round(avg_consumption, 1),
                'SON_TÜKETİM (m³)': round(last_consumption, 1),
                'MIN_TÜKETİM (m³)': round(tesisat_data['Tüketim'].min(), 1),
                'MAX_TÜKETİM (m³)': round(tesisat_data['Tüketim'].max(), 1),
                'STANDART_SAPMA': round(consumption_std, 1),
                'TOPLAM_AY_SAYISI': total_months,
                'UYDUĞU_KRİTERLER': ', '.join(criteria_list),
                'KRİTER_SAYISI': len(criteria_list),
                'RİSK_SKORU': risk_score,
                'ÖNCELİK': priority,
                'ÖNCELİK_AÇIKLAMASI': priority_explanation,
                'TESPİT_AÇIKLAMASI': full_explanation,
                'SAHA_KONTROL_ÖNERİSİ': f"{priority} öncelik - {'ACİL' if priority == 'YÜKSEK' else 'Planlı' if priority == 'ORTA' else 'Rutin'} kontrol önerilir"
            })
        
        all_suspicious_df = pd.DataFrame(all_suspicious_details)
        if not all_suspicious_df.empty:
            all_suspicious_df = all_suspicious_df.sort_values(['RİSK_SKORU', 'KRİTER_SAYISI'], ascending=[False, False])
    
    # 8. SONUÇ PANELİ
    st.subheader("📊 ÖZET RAPOR")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        suspicious_rate = len(all_suspicious)/df['Tesisat_No'].nunique()*100
        delta_color = "inverse" if suspicious_rate > 5 else "normal"
        st.metric("Toplam Şüpheli", len(all_suspicious), 
                 delta=f"{suspicious_rate:.1f}%", delta_color=delta_color)
    
    with col2:
        st.metric("Kalıcı Düşüş", len(suspicious_permanent),
                 delta_color="inverse")
    
    with col3:
        st.metric("Düşük Kış Tüketimi", len(suspicious_winter))
    
    with col4:
        st.metric("Bina İçi Anomali", len(suspicious_building))
    
    # 9. DETAYLI TABLOLAR
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🎯 TÜM ŞÜPHELİLER (AÇIKLAMALI)", 
        "📉 KALICI DÜŞÜŞ DETAY", 
        "❄️ DÜŞÜK KIŞ DETAY", 
        "🏢 BİNA ANOMALİ DETAY",
        "📈 GRAFİKLER",
        "🔍 TEKİL ANALİZ"
    ])
    
    with tab1:
        if not all_suspicious_df.empty:
            st.success(f"✅ **{len(all_suspicious)}** adet şüpheli tesisat tespit edildi")
            
            # Filtreleme
            col_filter1, col_filter2, col_filter3 = st.columns(3)
            with col_filter1:
                min_risk = st.slider("Min. Risk Skoru", 0, 100, 50, key="risk_filter_all")
            with col_filter2:
                priority_filter = st.selectbox("Öncelik Seviyesi", ["Tümü", "YÜKSEK", "ORTA", "DÜŞÜK"], key="priority_filter")
            with col_filter3:
                min_criteria = st.slider("Min. Kriter Sayısı", 1, 4, 1, key="criteria_filter")
            
            # Filtre uygula
            filtered_all = all_suspicious_df[all_suspicious_df['RİSK_SKORU'] >= min_risk]
            filtered_all = filtered_all[filtered_all['KRİTER_SAYISI'] >= min_criteria]
            
            if priority_filter != "Tümü":
                filtered_all = filtered_all[filtered_all['ÖNCELİK'] == priority_filter]
            
            st.info(f"**{len(filtered_all)}** tesisat filtrelere uyuyor")
            
            # Tabloyu göster
            st.dataframe(filtered_all, use_container_width=True, height=500)
            
            # Excel raporu oluştur
            if not filtered_all.empty:
                # Ayrıntılı Excel raporu
                excel_report_data = {
                    'ANALİZ_ÖZET': pd.DataFrame([{
                        'RAPOR_TARİHİ': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'TOPLAM_TESİSAT_SAYISI': df['Tesisat_No'].nunique(),
                        'TOPLAM_KAYIT_SAYISI': len(df),
                        'VERİ_ARALIĞI': f"{df['Tarih_DT'].min().strftime('%Y-%m')} - {df['Tarih_DT'].max().strftime('%Y-%m')}",
                        'ŞÜPHELİ_TESİSAT_SAYISI': len(all_suspicious),
                        'ŞÜPHELİ_ORANI_%': f"{len(all_suspicious)/df['Tesisat_No'].nunique()*100:.1f}",
                        'KALICI_DÜŞÜŞ_TESİSAT': len(suspicious_permanent),
                        'DÜŞÜK_KIŞ_TESİSAT': len(suspicious_winter),
                        'BİNA_ANOMALİ_TESİSAT': len(suspicious_building),
                        'SIFIR_TÜKETİM_TESİSAT': len(suspicious_zero),
                        'KULLANILAN_PARAMETRELER': f"Düşüş: {min_drop_percent}%, Takip: {min_months_after} ay, Geri Dönüş: {recovery_threshold}%, Kış Eşik: {min_winter_cons} m³, Bina %: {bina_percentile}"
                    }]),
                    'TÜM_ŞÜPHELİ_TESİSATLAR': filtered_all,
                    'KALICI_DÜŞÜŞ_AÇIKLAMALI': permanent_details if not permanent_details.empty else pd.DataFrame({'BİLGİ': ['Kalıcı düşüş tespit edilen tesisat bulunamadı']}),
                    'DÜŞÜK_KIŞ_AÇIKLAMALI': winter_details if not winter_details.empty else pd.DataFrame({'BİLGİ': ['Düşük kış tüketimi tespit edilen tesisat bulunamadı']}),
                    'BİNA_ANOMALİ_AÇIKLAMALI': building_details if not building_details.empty else pd.DataFrame({'BİLGİ': ['Bina içi anomali tespit edilen tesisat bulunamadı']}),
                    'SIFIR_TÜKETİM_AÇIKLAMALI': zero_details if not zero_details.empty else pd.DataFrame({'BİLGİ': ['Sıfır tüketim tespit edilen tesisat bulunamadı']}),
                    'PARAMETRELER_AÇIKLAMA': pd.DataFrame([{
                        'PARAMETRE': 'Minimum Düşüş Yüzdesi',
                        'DEĞER': f'{min_drop_percent}%',
                        'AÇIKLAMA': 'Tüketimdeki minimum azalma yüzdesi'
                    }, {
                        'PARAMETRE': 'Takip Ay Sayısı',
                        'DEĞER': f'{min_months_after} ay',
                        'AÇIKLAMA': 'Düşüşten sonraki takip süresi'
                    }, {
                        'PARAMETRE': 'Geri Dönüş Eşiği',
                        'DEĞER': f'{recovery_threshold}%',
                        'AÇIKLAMA': 'Eski tüketime ne kadar yaklaşınca geri dönmüş sayılır'
                    }, {
                        'PARAMETRE': 'Minimum Kış Tüketimi',
                        'DEĞER': f'{min_winter_cons} m³',
                        'AÇIKLAMA': 'Kış ayları için normal kabul edilen minimum tüketim'
                    }, {
                        'PARAMETRE': 'Bina Anomali Yüzdesi',
                        'DEĞER': f'{bina_percentile}%',
                        'AÇIKLAMA': 'Binadaki en düşük tüketime sahip tesisat yüzdesi'
                    }]),
                    'KRİTER_AÇIKLAMALARI': pd.DataFrame([{
                        'KRİTER_KODU': 'KALICI_DÜŞÜŞ',
                        'KRİTER_ADI': 'Kalıcı Tüketim Düşüşü',
                        'AÇIKLAMA': 'Tüketimde ani ve kalıcı düşüş (geri dönüş yok)',
                        'RİSK_PUANI': '40',
                        'KAÇAK_İLİŞKİSİ': 'YÜKSEK - Sayaç manipülasyonu ihtimali'
                    }, {
                        'KRİTER_KODU': 'DÜŞÜK_KIŞ',
                        'KRİTER_ADI': 'Düşük Kış Tüketimi',
                        'AÇIKLAMA': 'Kış aylarında beklenenden düşük tüketim',
                        'RİSK_PUANI': '20',
                        'KAÇAK_İLİŞKİSİ': 'ORTA - Isınma için kaçak kullanım ihtimali'
                    }, {
                        'KRİTER_KODU': 'BİNA_ANOMALİ',
                        'KRİTER_ADI': 'Bina İçi Anomali',
                        'AÇIKLAMA': 'Aynı binadaki diğer dairelere göre anormal düşük tüketim',
                        'RİSK_PUANI': '10',
                        'KAÇAK_İLİŞKİSİ': 'ORTA - Bina bazlı karşılaştırma'
                    }, {
                        'KRİTER_KODU': 'SIFIR_TÜKETİM',
                        'KRİTER_ADI': 'Uzun Süre Sıfır Tüketim',
                        'AÇIKLAMA': '4+ ay boyunca sürekli sıfır tüketim',
                        'RİSK_PUANI': '30',
                        'KAÇAK_İLİŞKİSİ': 'YÜKSEK - Sayaç tamamen durdurulmuş olabilir'
                    }]),
                    'SAHA_KONTROL_ÖNERİLERİ': pd.DataFrame([{
                        'ÖNCELİK_SEVİYESİ': 'YÜKSEK',
                        'RİSK_SKORU_ARALIĞI': '60-100',
                        'KONTROL_ZAMANI': 'ACİL (1 hafta içinde)',
                        'ÖNERİLEN_AKSIYON': 'Öncelikli saha kontrolü, sayaç incelemesi',
                        'DOKÜMANTASYON': 'Detaylı rapor + fotoğraf'
                    }, {
                        'ÖNCELİK_SEVİYESİ': 'ORTA',
                        'RİSK_SKORU_ARALIĞI': '30-59',
                        'KONTROL_ZAMANI': 'Planlı (1 ay içinde)',
                        'ÖNERİLEN_AKSIYON': 'Rutin kontrol, tüketim takibi',
                        'DOKÜMANTASYON': 'Standart rapor'
                    }, {
                        'ÖNCELİK_SEVİYESİ': 'DÜŞÜK',
                        'RİSK_SKORU_ARALIĞI': '0-29',
                        'KONTROL_ZAMANI': 'Rutin (3 ay içinde)',
                        'ÖNERİLEN_AKSIYON': 'Gözlem, sonraki dönem takibi',
                        'DOKÜMANTASYON': 'Not kaydı'
                    }])
                }
                
                # Excel oluştur
                excel_data = to_excel(excel_report_data)
                
                # İndirme butonları
                col_download1, col_download2 = st.columns(2)
                
                with col_download1:
                    st.download_button(
                        label="📊 TAM RAPORU EXCEL İNDİR",
                        data=excel_data,
                        file_name=f"kacak_tespit_tam_rapor_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Tüm analizleri, açıklamaları ve önerileri içeren kapsamlı Excel raporu"
                    )
                
                with col_download2:
                    # Sadece şüpheli listesini indir
                    simple_excel = to_excel({'ŞÜPHELİ_TESİSATLAR': filtered_all})
                    st.download_button(
                        label="📋 SADECE ŞÜPHELİ LİSTESİ",
                        data=simple_excel,
                        file_name=f"kacak_supheli_liste_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Sadece şüpheli tesisatların listesi"
                    )
                
                # Örnek açıklama gösterimi
                st.subheader("📝 ÖRNEK TESPİT AÇIKLAMASI")
                sample_row = filtered_all.iloc[0]
                st.info(f"""
                **Tesisat:** {sample_row['TESİSAT_NO']} | **Bina:** {sample_row['BİNA_NO']} | **Risk Skoru:** {sample_row['RİSK_SKORU']} | **Öncelik:** {sample_row['ÖNCELİK']}
                
                **Açıklama:** {sample_row['TESPİT_AÇIKLAMASI']}
                
                **Saha Kontrol Önerisi:** {sample_row['SAHA_KONTROL_ÖNERİSİ']}
                """)
        else:
            st.success("✅ Şüpheli tesisat bulunamadı")
    
    with tab2:
        if not permanent_details.empty:
            st.dataframe(permanent_details, use_container_width=True, height=400)
            
            # Kalıcı düşüş örnek açıklama
            if not permanent_details.empty:
                sample_perm = permanent_details.iloc[0]
                st.info(f"""
                **Örnek Kalıcı Düşüş Açıklaması:**
                
                {sample_perm['AÇIKLAMA']}
                
                **Risk Değerlendirmesi:** {sample_perm['RİSK_SKORU']} puan - {'Yüksek risk' if sample_perm['RİSK_SKORU'] >= 70 else 'Orta risk' if sample_perm['RİSK_SKORU'] >= 40 else 'Düşük risk'}
                """)
        else:
            st.info("Kalıcı düşüş tespit edilemedi")
    
    with tab3:
        if not winter_details.empty:
            st.dataframe(winter_details, use_container_width=True)
        else:
            st.info("Düşük kış tüketimi tespit edilemedi")
    
    with tab4:
        if not building_details.empty:
            st.dataframe(building_details, use_container_width=True)
        else:
            st.info("Bina içi anomali tespit edilemedi")
    
    # Diğer tablar aynı kalacak...
    with tab5:
        # Grafikler
        fig1 = px.histogram(df, x='Tüketim', nbins=50, title="Tüketim Dağılımı")
        st.plotly_chart(fig1, use_container_width=True)
    
    with tab6:
        # Tekil analiz
        st.subheader("🔍 Tekil Tesisat Analizi")
        selected_tesisat = st.selectbox(
            "Analiz etmek istediğiniz tesisatı seçin:",
            options=df['Tesisat_No'].unique()[:200],
            index=0
        )
        
        if selected_tesisat:
            tesisat_data = df[df['Tesisat_No'] == selected_tesisat].sort_values('Tarih_DT')
            
            # Grafik çiz
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=tesisat_data['Tarih_DT'], y=tesisat_data['Tüketim'],
                mode='lines+markers', name='Tüketim'
            ))
            st.plotly_chart(fig, use_container_width=True)
    
    # 10. ÖZET VE ÖNERİLER PANELİ
    st.header("🎯 ÖZET VE SAHA KONTROL ÖNERİLERİ")
    
    if not all_suspicious_df.empty:
        # Öncelik dağılımı
        priority_counts = all_suspicious_df['ÖNCELİK'].value_counts()
        
        col_sum1, col_sum2, col_sum3 = st.columns(3)
        
        with col_sum1:
            st.metric("Yüksek Öncelikli", priority_counts.get('YÜKSEK', 0))
        
        with col_sum2:
            st.metric("Orta Öncelikli", priority_counts.get('ORTA', 0))
        
        with col_sum3:
            st.metric("Düşük Öncelikli", priority_counts.get('DÜŞÜK', 0))
        
        # Kontrol planı önerisi
        st.subheader("📋 ÖNERİLEN SAHA KONTROL PLANI")
        
        if priority_counts.get('YÜKSEK', 0) > 0:
            high_risk_tesisatlar = all_suspicious_df[all_suspicious_df['ÖNCELİK'] == 'YÜKSEK']
            st.warning(f"""
            **ACİL KONTROL GEREKTİREN {priority_counts.get('YÜKSEK', 0)} TESİSAT:**
            
            1. **Öncelik:** Bu tesisatlar en yüksek kaçak kullanım riskine sahip
            2. **Zamanlama:** 1 hafta içinde kontrol edilmeli
            3. **Aksiyon:** Sayaç fiziksel kontrolü + tüketim kayıtları incelenmeli
            4. **Dokümantasyon:** Detaylı rapor + fotoğraf çekilmeli
            
            **Örnek Yüksek Riskli Tesisatlar:**
            {', '.join(high_risk_tesisatlar['TESİSAT_NO'].head(5).tolist())}
            """)
        
        # Excel raporu indirme butonu (tekrar)
        st.markdown("---")
        st.subheader("📄 RAPORLAMA")
        
        report_col1, report_col2 = st.columns(2)
        
        with report_col1:
            # Hızlı rapor (sadece şüpheliler)
            quick_report = all_suspicious_df[['TESİSAT_NO', 'BİNA_NO', 'RİSK_SKORU', 'ÖNCELİK', 'TESPİT_AÇIKLAMASI']]
            quick_excel = to_excel({'HIZLI_RAPOR': quick_report})
            
            st.download_button(
                label="🚀 HIZLI RAPOR İNDİR",
                data=quick_excel,
                file_name="kacak_hizli_rapor.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Sadece temel bilgileri içeren hızlı rapor"
            )
        
        with report_col2:
            # Detaylı rapor
            st.download_button(
                label="📋 DETAYLI RAPOR İNDİR",
                data=excel_data,
                file_name="kacak_detayli_rapor.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Tüm detayları içeren kapsamlı rapor"
            )
    else:
        st.success("✅ Hiç şüpheli tesisat bulunamadı - Temiz rapor!")

else:
    st.info("👈 Lütfen Excel veya CSV dosyasını yükleyin")
    
    # Örnek veri yapısı
    st.markdown("""
    ### 📋 BEKLENEN VERİ YAPISI:
    
    | Tarih | Tesisat Numarası | Bina Numarası | Tüketim Miktarı |
    |-------|------------------|---------------|-----------------|
    | 2020/1 | 12345 | BINA001 | 125.5 |
    | 2020-2 | 12345 | BINA001 | 110.2 |
    | 2020.3 | 12346 | BINA001 | 98.7 |
    
    ### 📝 RAPOR İÇERİĞİ:
    
    Excel raporu aşağıdaki sayfaları içerecek:
    
    1. **ANALİZ_ÖZET** - Genel istatistikler
    2. **TÜM_ŞÜPHELİ_TESİSATLAR** - Tüm şüpheliler detaylı açıklamalı
    3. **KALICI_DÜŞÜŞ_AÇIKLAMALI** - Kalıcı düşüş tespit edilenler
    4. **DÜŞÜK_KIŞ_AÇIKLAMALI** - Düşük kış tüketimi olanlar
    5. **BİNA_ANOMALİ_AÇIKLAMALI** - Bina içi anomali tespit edilenler
    6. **SIFIR_TÜKETİM_AÇIKLAMALI** - Uzun süre sıfır tüketim olanlar
    7. **PARAMETRELER_AÇIKLAMA** - Kullanılan parametrelerin açıklaması
    8. **KRİTER_AÇIKLAMALARI** - Tespit kriterlerinin detayları
    9. **SAHA_KONTROL_ÖNERİLERİ** - Önceliklendirme ve kontrol önerileri
    """)
