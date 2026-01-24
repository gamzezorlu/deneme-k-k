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
        
        # Sütun isimlerini kontrol et ve küçük harfe çevir
        df.columns = df.columns.str.strip().str.lower()
        
        # Beklenen sütun isimleri
        expected_columns = {
            'tarih': 'tarih',
            'tesisat_no': 'tesisat_no',
            'bina_no': 'bina_no',
            'tuketim': 'tuketim'
        }
        
        # Sütun isimlerini kontrol et
        missing_cols = []
        for col in expected_columns.keys():
            if col not in df.columns:
                missing_cols.append(col)
        
        if missing_cols:
            st.error(f"Eksik sütunlar: {missing_cols}")
            st.error(f"Mevcut sütunlar: {list(df.columns)}")
            st.stop()
        
        # Sütun isimlerini standartlaştır
        df = df.rename(columns={
            'tarih': 'tarih',
            'tesisat_no': 'tesisat_no',
            'bina_no': 'bina_no',
            'tuketim': 'tuketim'
        })
        
        st.sidebar.success(f"✅ Veri yüklendi: {len(df):,} kayıt, {df['tesisat_no'].nunique():,} tesisat")
        
    except Exception as e:
        st.error(f"Veri yükleme hatası: {e}")
        st.stop()
    
    # 2. VERİ ÖN İZLEME
    with st.expander("📊 VERİ ÖN İZLEME", expanded=False):
        st.dataframe(df.head(), use_container_width=True)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Toplam Kayıt", f"{len(df):,}")
        with col2:
            st.metric("Tesisat Sayısı", f"{df['tesisat_no'].nunique():,}")
        with col3:
            st.metric("Bina Sayısı", f"{df['bina_no'].nunique():,}")
        with col4:
            st.metric("Ort. Tüketim", f"{df['tuketim'].mean():.1f} m³")
    
    # 3. TARİH İŞLEME
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
    
    df['tarih_dt'] = df['tarih'].apply(parse_date_smart)
    df = df.dropna(subset=['tarih_dt'])
    
    # Sırala ve ek sütunlar ekle
    df = df.sort_values(['tesisat_no', 'tarih_dt'])
    df['yil'] = df['tarih_dt'].dt.year
    df['ay'] = df['tarih_dt'].dt.month
    df['ay_yil'] = df['tarih_dt'].dt.strftime('%Y-%m')
    
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
    
    df['mevsim'] = df['ay'].apply(get_season_ankara)
    df['kis_mi'] = df['ay'].isin([12, 1, 2, 3])
    
    # 4. PARAMETRELER
    st.sidebar.subheader("🎯 KALICI DÜŞÜŞ PARAMETRELERİ")
    
    col_param1, col_param2 = st.sidebar.columns(2)
    
    with col_param1:
        min_drop_percent = st.slider("Min. Düşüş %", 50, 95, 75, 
                                   help="Tüketimdeki minimum düşüş yüzdesi")
        min_months_after = st.slider("Takip Ay Sayısı", 3, 12, 6, 
                                   help="Düşüşten sonra takip edilecek ay sayısı")
    
    with col_param2:
        recovery_threshold = st.slider("Geri Dönüş Eşiği %", 30, 80, 60, 
                                     help="Eski tüketimin % kaçına çıkınca 'geri dönmüş' sayılsın?")
        min_winter_cons = st.slider("Min. Kış Tüketimi", 0, 50, 15, 
                                  help="Kış ayları için min. normal tüketim (m³)")
    
    st.sidebar.subheader("🏢 BİNA ANALİZİ")
    bina_percentile = st.slider("Anomali Yüzdelik", 5, 30, 10, 
                              help="Binanın en düşük % kaçı anomali sayılsın?")
    
    st.sidebar.subheader("📊 DİĞER AYARLAR")
    min_data_months = st.slider("Min. Veri Ay Sayısı", 6, 24, 12,
                              help="Analiz için minimum ay sayısı")
    
    # 5. KALICI DÜŞÜŞ TESPİTİ (AÇIKLAMALI)
    def detect_permanent_drop(df, min_drop_pct=75, min_months_after=6, recovery_threshold_pct=60, min_data=12):
        results = []
        details = []
        
        for tesisat in df['tesisat_no'].unique():
            tesisat_df = df[df['tesisat_no'] == tesisat].sort_values('tarih_dt')
            
            if len(tesisat_df) < min_data:
                continue
            
            tesisat_df = tesisat_df.reset_index(drop=True)
            
            # Potansiyel düşüş noktalarını bul
            potential_drops = []
            
            for i in range(3, len(tesisat_df) - min_months_after):
                before_avg = tesisat_df.iloc[i-3:i]['tuketim'].mean()
                after_avg = tesisat_df.iloc[i:i+min_months_after]['tuketim'].mean()
                
                if before_avg > 0 and after_avg > 0:
                    drop_pct = ((before_avg - after_avg) / before_avg) * 100
                    
                    if drop_pct >= min_drop_pct:
                        potential_drops.append({
                            'index': i,
                            'date': tesisat_df.iloc[i]['tarih_dt'],
                            'before_avg': before_avg,
                            'after_avg': after_avg,
                            'drop_pct': drop_pct
                        })
            
            if potential_drops:
                main_drop = max(potential_drops, key=lambda x: x['drop_pct'])
                drop_index = main_drop['index']
                drop_date = main_drop['date']
                
                # Kalıcılık kontrolleri
                all_after = tesisat_df.iloc[drop_index:]
                
                # Geri dönüş kontrolü
                recovery_occurred = False
                max_recovery_pct = 0
                recovery_month = None
                
                for _, row in all_after.iterrows():
                    recovery_pct = (row['tuketim'] / main_drop['before_avg']) * 100
                    if recovery_pct > max_recovery_pct:
                        max_recovery_pct = recovery_pct
                    
                    if recovery_pct >= recovery_threshold_pct and not recovery_occurred:
                        recovery_occurred = True
                        recovery_month = row['tarih_dt'].strftime('%Y-%m')
                
                # Trend analizi
                if len(all_after) >= 3:
                    x = np.arange(len(all_after))
                    y = all_after['tuketim'].values
                    trend_coef = np.polyfit(x, y, 1)[0]
                    trend_rising = (trend_coef > 0) and (abs(trend_coef) > (y.mean() * 0.05))
                else:
                    trend_rising = False
                
                # Kalıcılık kararı
                is_permanent = not recovery_occurred and not trend_rising
                
                if is_permanent:
                    # Açıklama oluştur
                    explanation_parts = []
                    explanation_parts.append(f"📅 {drop_date.strftime('%Y-%m')} tarihinde %{main_drop['drop_pct']:.1f} düşüş başladı")
                    
                    if not recovery_occurred:
                        explanation_parts.append(f"↗️ Maksimum %{max_recovery_pct:.1f}'e ulaştı (Eşik: %{recovery_threshold_pct})")
                    else:
                        explanation_parts.append(f"🔄 {recovery_month}'de %{recovery_threshold_pct} eşiğini aştı")
                    
                    if not trend_rising:
                        explanation_parts.append("📉 Artış trendi yok")
                    else:
                        explanation_parts.append("📈 Artış trendi var")
                    
                    explanation = " | ".join(explanation_parts)
                    
                    # Risk skoru
                    risk_score = min(100, main_drop['drop_pct'])
                    
                    details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': tesisat_df['bina_no'].iloc[0],
                        'DÜŞÜŞ_TARİHİ': drop_date.strftime('%Y-%m'),
                        'ÖNCEKİ_ORT (m³)': round(main_drop['before_avg'], 1),
                        'SONRAKİ_ORT (m³)': round(main_drop['after_avg'], 1),
                        'DÜŞÜŞ_%': round(main_drop['drop_pct'], 1),
                        'MAX_GERİ_DÖNÜŞ_%': round(max_recovery_pct, 1),
                        'GERİ_DÖNDÜ_MÜ?': 'EVET' if recovery_occurred else 'HAYIR',
                        'RİSK_SKORU': risk_score,
                        'AÇIKLAMA': explanation,
                        'TESPİT_NEDENİ': 'KALICI_DÜŞÜŞ'
                    })
                    results.append(tesisat)
        
        details_df = pd.DataFrame(details)
        if not details_df.empty:
            details_df = details_df.sort_values('RİSK_SKORU', ascending=False)
        
        return results, details_df
    
    # 6. DÜŞÜK KIŞ TÜKETİMİ TESPİTİ
    def detect_low_winter(df, threshold=15):
        kis_data = df[df['kis_mi'] == True]
        results = []
        details = []
        
        for tesisat in df['tesisat_no'].unique():
            tesisat_kis = kis_data[kis_data['tesisat_no'] == tesisat]
            
            if len(tesisat_kis) > 0:
                avg_kis = tesisat_kis['tuketim'].mean()
                min_kis = tesisat_kis['tuketim'].min()
                max_kis = tesisat_kis['tuketim'].max()
                
                if avg_kis < threshold:
                    explanation = f"❄️ Kış ortalaması: {avg_kis:.1f} m³ (Eşik: {threshold} m³)"
                    explanation += f" | Min: {min_kis:.1f} m³, Max: {max_kis:.1f} m³"
                    explanation += f" | Kış ay sayısı: {len(tesisat_kis)}"
                    
                    details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': tesisat_kis['bina_no'].iloc[0],
                        'ORT_KIŞ (m³)': round(avg_kis, 1),
                        'MIN_KIŞ (m³)': round(min_kis, 1),
                        'MAX_KIŞ (m³)': round(max_kis, 1),
                        'KIŞ_AY_SAYISI': len(tesisat_kis),
                        'EŞİK (m³)': threshold,
                        'AÇIKLAMA': explanation,
                        'TESPİT_NEDENİ': 'DÜŞÜK_KIŞ'
                    })
                    results.append(tesisat)
        
        return results, pd.DataFrame(details)
    
    # 7. BİNA İÇİ ANOMALİ TESPİTİ
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
                    bina_avg = np.mean([x[1] for x in tesisat_avgs])
                    
                    explanation = f"🏢 {bina} binasında {i+1}. en düşük"
                    explanation += f" | Tesisat: {avg:.1f} m³, Bina ort: {bina_avg:.1f} m³"
                    explanation += f" | Fark: {bina_avg - avg:.1f} m³ (%{((bina_avg - avg)/bina_avg*100):.1f})"
                    explanation += f" | Toplam tesisat: {len(tesisat_avgs)}"
                    
                    details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': bina,
                        'TESİSAT_ORT (m³)': round(avg, 1),
                        'BİNA_ORT (m³)': round(bina_avg, 1),
                        'FARK (m³)': round(bina_avg - avg, 1),
                        'FARK_%': round(((bina_avg - avg) / bina_avg * 100), 1) if bina_avg > 0 else 0,
                        'SIRALAMA': f"{i+1}/{len(tesisat_avgs)}",
                        'AÇIKLAMA': explanation,
                        'TESPİT_NEDENİ': 'BİNA_ANOMALİ'
                    })
                    results.append(tesisat)
        
        return results, pd.DataFrame(details)
    
    # 8. SIFIR TÜKETİM TESPİTİ
    def detect_zero_consumption(df, min_months=4):
        results = []
        details = []
        
        for tesisat in df['tesisat_no'].unique():
            tesisat_df = df[df['tesisat_no'] == tesisat].sort_values('tarih_dt')
            last_months = tesisat_df.tail(min_months)
            
            if len(last_months) >= min_months:
                if (last_months['tuketim'] == 0).all():
                    # Önceki tüketimi bul
                    if len(tesisat_df) > min_months:
                        before_zero = tesisat_df.iloc[-min_months-1]['tuketim']
                    else:
                        before_zero = 0
                    
                    explanation = f"🔴 {min_months} ay sürekli sıfır"
                    explanation += f" | Dönem: {last_months['tarih_dt'].iloc[0].strftime('%Y-%m')} - {last_months['tarih_dt'].iloc[-1].strftime('%Y-%m')}"
                    if before_zero > 0:
                        explanation += f" | Önceki tüketim: {before_zero:.1f} m³"
                    
                    details.append({
                        'TESİSAT_NO': tesisat,
                        'BİNA_NO': tesisat_df['bina_no'].iloc[0],
                        'SIFIR_AY_SAYISI': len(last_months),
                        'BAŞLANGIÇ_TARİH': last_months['tarih_dt'].iloc[0].strftime('%Y-%m'),
                        'BİTİŞ_TARİH': last_months['tarih_dt'].iloc[-1].strftime('%Y-%m'),
                        'ÖNCEKİ_TÜKETİM (m³)': round(before_zero, 1) if before_zero > 0 else 0,
                        'AÇIKLAMA': explanation,
                        'TESPİT_NEDENİ': 'SIFIR_TÜKETİM'
                    })
                    results.append(tesisat)
        
        return results, pd.DataFrame(details)
    
    # 9. ANALİZLERİ ÇALIŞTIR
    st.header("🔍 ANALİZ SONUÇLARI")
    
    with st.spinner("Analizler çalıştırılıyor... Lütfen bekleyin"):
        sus_permanent, perm_details = detect_permanent_drop(
            df, min_drop_pct=min_drop_percent,
            min_months_after=min_months_after,
            recovery_threshold_pct=recovery_threshold,
            min_data=min_data_months
        )
        
        sus_winter, winter_details = detect_low_winter(df, threshold=min_winter_cons)
        sus_building, building_details = detect_building_anomaly(df, percentile=bina_percentile)
        sus_zero, zero_details = detect_zero_consumption(df, min_months=4)
        
        # Tüm şüpheliler
        all_sus = list(set(sus_permanent + sus_winter + sus_building + sus_zero))
        
        # Detaylı liste oluştur
        all_details = []
        
        for tesisat in all_sus:
            tesisat_data = df[df['tesisat_no'] == tesisat]
            avg_cons = tesisat_data['tuketim'].mean()
            last_cons = tesisat_data['tuketim'].iloc[-1]
            min_cons = tesisat_data['tuketim'].min()
            max_cons = tesisat_data['tuketim'].max()
            
            # Kriterler ve açıklamalar
            criteria = []
            explanations = []
            
            if tesisat in sus_permanent:
                perm_info = perm_details[perm_details['TESİSAT_NO'] == tesisat]
                if not perm_info.empty:
                    criteria.append('KALICI_DÜŞÜŞ')
                    explanations.append(perm_info.iloc[0]['AÇIKLAMA'])
            
            if tesisat in sus_winter:
                winter_info = winter_details[winter_details['TESİSAT_NO'] == tesisat]
                if not winter_info.empty:
                    criteria.append('DÜŞÜK_KIŞ')
                    explanations.append(winter_info.iloc[0]['AÇIKLAMA'])
            
            if tesisat in sus_building:
                bina_info = building_details[building_details['TESİSAT_NO'] == tesisat]
                if not bina_info.empty:
                    criteria.append('BİNA_ANOMALİ')
                    explanations.append(bina_info.iloc[0]['AÇIKLAMA'])
            
            if tesisat in sus_zero:
                zero_info = zero_details[zero_details['TESİSAT_NO'] == tesisat]
                if not zero_info.empty:
                    criteria.append('SIFIR_TÜKETİM')
                    explanations.append(zero_info.iloc[0]['AÇIKLAMA'])
            
            # Risk skoru
            risk_score = 0
            if 'KALICI_DÜŞÜŞ' in criteria:
                risk_score += 40
            if 'SIFIR_TÜKETİM' in criteria:
                risk_score += 30
            if 'DÜŞÜK_KIŞ' in criteria:
                risk_score += 20
            if 'BİNA_ANOMALİ' in criteria:
                risk_score += 10
            
            # Öncelik
            if risk_score >= 60:
                priority = 'YÜKSEK'
                priority_exp = 'Çoklu kriter + yüksek risk'
            elif risk_score >= 30:
                priority = 'ORTA'
                priority_exp = 'Birkaç kriter + orta risk'
            else:
                priority = 'DÜŞÜK'
                priority_exp = 'Tek kriter + düşük risk'
            
            # Tüm açıklamaları birleştir
            full_exp = " | ".join(explanations)
            
            all_details.append({
                'TESİSAT_NO': tesisat,
                'BİNA_NO': tesisat_data['bina_no'].iloc[0],
                'ORT_TÜKETİM (m³)': round(avg_cons, 1),
                'SON_TÜKETİM (m³)': round(last_cons, 1),
                'MIN_TÜKETİM (m³)': round(min_cons, 1),
                'MAX_TÜKETİM (m³)': round(max_cons, 1),
                'AY_SAYISI': len(tesisat_data),
                'KRİTERLER': ', '.join(criteria),
                'KRİTER_SAYISI': len(criteria),
                'RİSK_SKORU': risk_score,
                'ÖNCELİK': priority,
                'ÖNCELİK_AÇIKLAMA': priority_exp,
                'TESPİT_AÇIKLAMASI': full_exp,
                'SAHA_KONTROL_ÖNERİSİ': f"{priority} - {'ACİL' if priority == 'YÜKSEK' else 'Planlı' if priority == 'ORTA' else 'Rutin'} kontrol"
            })
        
        all_sus_df = pd.DataFrame(all_details)
        if not all_sus_df.empty:
            all_sus_df = all_sus_df.sort_values(['RİSK_SKORU', 'KRİTER_SAYISI'], ascending=[False, False])
    
    # 10. SONUÇ PANELİ
    st.subheader("📊 ÖZET RAPOR")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        sus_rate = len(all_sus)/df['tesisat_no'].nunique()*100
        st.metric("Toplam Şüpheli", len(all_sus), delta=f"{sus_rate:.1f}%")
    
    with col2:
        st.metric("Kalıcı Düşüş", len(sus_permanent), delta_color="inverse")
    
    with col3:
        st.metric("Düşük Kış", len(sus_winter))
    
    with col4:
        st.metric("Bina Anomalisi", len(sus_building))
    
    # 11. DETAYLI TABLOLAR
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎯 TÜM ŞÜPHELİLER", 
        "📉 KALICI DÜŞÜŞ", 
        "❄️ DÜŞÜK KIŞ", 
        "🏢 BİNA ANOMALİ",
        "📈 GRAFİKLER"
    ])
    
    with tab1:
        if not all_sus_df.empty:
            st.success(f"**{len(all_sus)}** adet şüpheli tesisat tespit edildi")
            
            # Filtreleme
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                min_risk = st.slider("Min. Risk", 0, 100, 50, key="risk_slider")
            with col_f2:
                priority_sel = st.selectbox("Öncelik", ["Tümü", "YÜKSEK", "ORTA", "DÜŞÜK"])
            
            # Filtre uygula
            filtered = all_sus_df[all_sus_df['RİSK_SKORU'] >= min_risk]
            if priority_sel != "Tümü":
                filtered = filtered[filtered['ÖNCELİK'] == priority_sel]
            
            st.dataframe(filtered, use_container_width=True, height=500)
            
            # Excel raporu
            excel_data = to_excel({
                'ANALİZ_ÖZET': pd.DataFrame([{
                    'Tarih': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'Toplam_Tesisat': df['tesisat_no'].nunique(),
                    'Şüpheli_Tesisat': len(all_sus),
                    'Şüpheli_Oranı_%': f"{sus_rate:.1f}",
                    'Kalıcı_Düşüş': len(sus_permanent),
                    'Düşük_Kış': len(sus_winter),
                    'Bina_Anomalisi': len(sus_building),
                    'Sıfır_Tüketim': len(sus_zero),
                    'Parametreler': f"Düşüş: {min_drop_percent}%, Geri Dönüş: {recovery_threshold}%, Kış Eşik: {min_winter_cons}m³"
                }]),
                'TÜM_ŞÜPHELİLER': filtered,
                'KALICI_DÜŞÜŞ_DETAY': perm_details if not perm_details.empty else pd.DataFrame({'BİLGİ': ['Bulunamadı']}),
                'DÜŞÜK_KIŞ_DETAY': winter_details if not winter_details.empty else pd.DataFrame({'BİLGİ': ['Bulunamadı']}),
                'BİNA_ANOMALİ_DETAY': building_details if not building_details.empty else pd.DataFrame({'BİLGİ': ['Bulunamadı']}),
                'SIFIR_TÜKETİM_DETAY': zero_details if not zero_details.empty else pd.DataFrame({'BİLGİ': ['Bulunamadı']})
            })
            
            # İndirme butonu
            st.download_button(
                label="📊 EXCEL RAPORU İNDİR",
                data=excel_data,
                file_name=f"dogalgaz_kacak_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Örnek açıklama
            if not filtered.empty:
                sample = filtered.iloc[0]
                st.info(f"""
                **Örnek Tesisat:** {sample['TESİSAT_NO']} | **Risk:** {sample['RİSK_SKORU']} | **Öncelik:** {sample['ÖNCELİK']}
                
                **Açıklama:** {sample['TESPİT_AÇIKLAMASI']}
                
                **Öneri:** {sample['SAHA_KONTROL_ÖNERİSİ']}
                """)
        else:
            st.success("✅ Şüpheli tesisat bulunamadı")
    
    with tab2:
        if not perm_details.empty:
            st.dataframe(perm_details, use_container_width=True)
        else:
            st.info("Kalıcı düşüş bulunamadı")
    
    with tab3:
        if not winter_details.empty:
            st.dataframe(winter_details, use_container_width=True)
        else:
            st.info("Düşük kış tüketimi bulunamadı")
    
    with tab4:
        if not building_details.empty:
            st.dataframe(building_details, use_container_width=True)
        else:
            st.info("Bina anomalisi bulunamadı")
    
    with tab5:
        # Tüketim dağılımı
        fig1 = px.histogram(df, x='tuketim', nbins=50, 
                          title="Tüketim Dağılımı (m³)")
        st.plotly_chart(fig1, use_container_width=True)
        
        # Mevsimsel analiz
        seasonal = df.groupby('mevsim')['tuketim'].mean().reset_index()
        fig2 = px.bar(seasonal, x='mevsim', y='tuketim',
                     title="Mevsimlere Göre Ortalama Tüketim")
        st.plotly_chart(fig2, use_container_width=True)
        
        # Yıllık trend
        yearly = df.groupby('yil')['tuketim'].mean().reset_index()
        fig3 = px.line(yearly, x='yil', y='tuketim',
                      title="Yıllara Göre Tüketim Trendi")
        st.plotly_chart(fig3, use_container_width=True)
    
    # 12. TEKİL TESİSAT ANALİZİ
    st.header("🔍 TEKİL TESİSAT ANALİZİ")
    
    selected_tesisat = st.selectbox(
        "Tesisat seçin:",
        options=df['tesisat_no'].unique()[:100]
    )
    
    if selected_tesisat:
        tesisat_data = df[df['tesisat_no'] == selected_tesisat].sort_values('tarih_dt')
        
        col_graph, col_info = st.columns([2, 1])
        
        with col_graph:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=tesisat_data['tarih_dt'], y=tesisat_data['tuketim'],
                mode='lines+markers', name='Tüketim',
                line=dict(color='blue', width=2)
            ))
            
            # Ortalama çizgisi
            avg_line = tesisat_data['tuketim'].mean()
            fig.add_hline(y=avg_line, line_dash="dash", line_color="red",
                         annotation_text=f"Ortalama: {avg_line:.1f}")
            
            fig.update_layout(
                title=f"Tesisat {selected_tesisat} Tüketim Geçmişi",
                xaxis_title="Tarih",
                yaxis_title="Tüketim (m³)"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col_info:
            st.subheader("📊 İstatistikler")
            
            stats = {
                "Ortalama": f"{tesisat_data['tuketim'].mean():.1f} m³",
                "Maksimum": f"{tesisat_data['tuketim'].max():.1f} m³",
                "Minimum": f"{tesisat_data['tuketim'].min():.1f} m³",
                "Son Tüketim": f"{tesisat_data['tuketim'].iloc[-1]:.1f} m³",
                "Veri Ay Sayısı": len(tesisat_data),
                "İlk Kayıt": tesisat_data['tarih_dt'].min().strftime('%Y-%m'),
                "Son Kayıt": tesisat_data['tarih_dt'].max().strftime('%Y-%m')
            }
            
            for key, value in stats.items():
                st.metric(key, value)
            
            # Uyarılar
            if selected_tesisat in all_sus:
                st.error("⚠️ ŞÜPHELİ TESİSAT")
                sus_info = all_sus_df[all_sus_df['TESİSAT_NO'] == selected_tesisat]
                if not sus_info.empty:
                    st.warning(f"**Risk:** {sus_info.iloc[0]['RİSK_SKORU']}")
                    st.warning(f"**Öncelik:** {sus_info.iloc[0]['ÖNCELİK']}")
                    st.info(f"**Neden:** {sus_info.iloc[0]['TESPİT_AÇIKLAMASI'][:100]}...")
            else:
                st.success("✅ NORMAL TESİSAT")
    
    # 13. SAHA KONTROL PLANI
    st.header("📋 SAHA KONTROL PLANI")
    
    if not all_sus_df.empty:
        high_risk = all_sus_df[all_sus_df['ÖNCELİK'] == 'YÜKSEK']
        med_risk = all_sus_df[all_sus_df['ÖNCELİK'] == 'ORTA']
        low_risk = all_sus_df[all_sus_df['ÖNCELİK'] == 'DÜŞÜK']
        
        col_high, col_med, col_low = st.columns(3)
        
        with col_high:
            st.subheader("🔴 YÜKSEK RİSK")
            st.metric("Sayı", len(high_risk))
            if len(high_risk) > 0:
                st.caption("Öneri: 1 hafta içinde kontrol")
                for tesisat in high_risk['TESİSAT_NO'].head(3):
                    st.code(f"{tesisat}")
        
        with col_med:
            st.subheader("🟡 ORTA RİSK")
            st.metric("Sayı", len(med_risk))
            if len(med_risk) > 0:
                st.caption("Öneri: 1 ay içinde kontrol")
        
        with col_low:
            st.subheader("🟢 DÜŞÜK RİSK")
            st.metric("Sayı", len(low_risk))
            if len(low_risk) > 0:
                st.caption("Öneri: 3 ay içinde kontrol")

else:
    st.info("👈 Lütfen Excel veya CSV dosyasını yükleyin")
    
    st.markdown("""
    ### 📋 BEKLENEN VERİ YAPISI:
    
    | tarih | tesisat_no | bina_no | tuketim |
    |-------|------------|---------|---------|
    | 2020/1 | 12345 | BINA001 | 125.5 |
    | 2020-2 | 12345 | BINA001 | 110.2 |
    | 2020.3 | 12346 | BINA001 | 98.7 |
    
    ### 🚀 ÖZELLİKLER:
    
    1. **Kalıcı Düşüş Tespiti** - Geri dönmeyen ani düşüşler
    2. **Düşük Kış Tüketimi** - Kış aylarında anormal düşük tüketim
    3. **Bina İçi Karşılaştırma** - Aynı binadaki anomaliler
    4. **Sıfır Tüketim** - Uzun süre sıfır tüketim
    5. **Açıklamalı Rapor** - Her tespitin nedeni açıklanır
    6. **Excel İndirme** - Detaylı Excel raporu
    7. **Önceliklendirme** - Risk skoruna göre öncelik
    8. **Grafikler** - Görsel analizler
    """)
