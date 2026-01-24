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

# 1. VERİ YÜKLEME
uploaded_file = st.sidebar.file_uploader("📂 Excel/CSV dosyasını yükleyin", type=['xlsx', 'csv'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
        
        # Sütun isimlerini standardize et
        df.columns = df.columns.str.strip().str.lower()
        
        # Beklenen sütunlar
        expected_columns = ['tarih', 'tesisat_no', 'bina_no', 'tuketim']
        
        # Opsiyonel sütunlar
        optional_columns = ['muhatap', 'cihaz_no']
        
        # Sütunları kontrol et
        missing_mandatory = [col for col in expected_columns if col not in df.columns]
        if missing_mandatory:
            st.error(f"❌ Zorunlu sütunlar eksik: {missing_mandatory}")
            st.stop()
        
        # Opsiyonel sütunları kontrol et
        has_muhatap = 'muhatap' in df.columns
        has_cihaz = 'cihaz_no' in df.columns
        
        if not has_muhatap:
            st.warning("⚠️ Muhatap sütunu bulunamadı. Muhatap analizleri devre dışı.")
        if not has_cihaz:
            st.warning("⚠️ Cihaz_no sütunu bulunamadı. Cihaz analizleri devre dışı.")
        
        # Sütun isimlerini düzenle
        rename_dict = {}
        for col in df.columns:
            if 'tarih' in col:
                rename_dict[col] = 'tarih'
            elif 'tesisat' in col:
                rename_dict[col] = 'tesisat_no'
            elif 'bina' in col:
                rename_dict[col] = 'bina_no'
            elif 'tuketim' in col or 'tüketim' in col:
                rename_dict[col] = 'tuketim'
            elif 'muhatap' in col:
                rename_dict[col] = 'muhatap'
            elif 'cihaz' in col:
                rename_dict[col] = 'cihaz_no'
        
        df = df.rename(columns=rename_dict)
        
        st.sidebar.success(f"✅ Veri yüklendi: {len(df):,} kayıt")
        
    except Exception as e:
        st.error(f"❌ Veri yükleme hatası: {e}")
        st.stop()
    
    # 2. TARİH İŞLEME
    def parse_date_smart(date_val):
        try:
            if pd.isna(date_val):
                return pd.NaT
            
            date_str = str(date_val).strip()
            
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
                if 1 <= month <= 12 and 2000 <= year <= 2100:
                    return datetime(year, month, 1)
            
            return pd.NaT
        except:
            return pd.NaT
    
    df['tarih_dt'] = df['tarih'].apply(parse_date_smart)
    df = df.dropna(subset=['tarih_dt'])
    df = df.sort_values(['tesisat_no', 'tarih_dt'])
    
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
    
    # 3. PARAMETRELER
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
    
    # 4. TEMEL ANALİZ FONKSİYONLARI (Önceki koddan)
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
    
    # 5. AKILLI KALICI DÜŞÜŞ TESPİTİ (MUHATAP VE CIHAZ KONTROLLÜ)
    def detect_smart_permanent_drop(df, min_drop_pct=75, min_months_after=6, recovery_threshold_pct=60):
        """
        AKILLI KALICI DÜŞÜŞ TESPİTİ
        
        Kritik Mantık:
        1. Cihaz değişmedi ama düşüş var → ŞÜPHELİ (rekor delik)
        2. Cihaz değişti, düşüş var → Normal (yanlış pozitif elemek için)
        3. Yeni muhatap, ilk ay yüksek sonra düşük → ŞÜPHELİ (kaçak başladı)
        """
        
        results = []
        all_details = []
        
        for tesisat in df['tesisat_no'].unique():
            tesisat_df = df[df['tesisat_no'] == tesisat].sort_values('tarih_dt')
            
            if len(tesisat_df) < 12:
                continue
            
            # Cihaz değişimlerini kontrol et
            cihaz_degisim_var = False
            cihaz_degisim_tarihi = None
            if 'cihaz_no' in tesisat_df.columns:
                cihazlar = tesisat_df['cihaz_no'].dropna().unique()
                if len(cihazlar) > 1:
                    # Cihaz değişim tarihini bul
                    for i in range(1, len(tesisat_df)):
                        if tesisat_df.iloc[i]['cihaz_no'] != tesisat_df.iloc[i-1]['cihaz_no']:
                            cihaz_degisim_var = True
                            cihaz_degisim_tarihi = tesisat_df.iloc[i]['tarih_dt']
                            break
            
            # Muhatap değişimlerini kontrol et
            muhatap_degisim_var = False
            muhatap_degisim_tarihi = None
            yeni_muhatap = None
            if 'muhatap' in tesisat_df.columns:
                muhataplar = tesisat_df['muhatap'].dropna().unique()
                if len(muhataplar) > 1:
                    for i in range(1, len(tesisat_df)):
                        if tesisat_df.iloc[i]['muhatap'] != tesisat_df.iloc[i-1]['muhatap']:
                            muhatap_degisim_var = True
                            muhatap_degisim_tarihi = tesisat_df.iloc[i]['tarih_dt']
                            yeni_muhatap = tesisat_df.iloc[i]['muhatap']
                            break
            
            # Potansiyel düşüş noktalarını bul
            potential_drops = []
            
            for i in range(3, len(tesisat_df) - min_months_after):
                before_avg = tesisat_df.iloc[i-3:i]['tuketim'].mean()
                after_avg = tesisat_df.iloc[i:i+min_months_after]['tuketim'].mean()
                
                if before_avg > 0 and after_avg > 0:
                    drop_pct = ((before_avg - after_avg) / before_avg) * 100
                    
                    if drop_pct >= min_drop_pct:
                        drop_date = tesisat_df.iloc[i]['tarih_dt']
                        potential_drops.append({
                            'index': i,
                            'date': drop_date,
                            'before_avg': before_avg,
                            'after_avg': after_avg,
                            'drop_pct': drop_pct
                        })
            
            if not potential_drops:
                continue
            
            # En büyük düşüşü seç
            main_drop = max(potential_drops, key=lambda x: x['drop_pct'])
            drop_index = main_drop['index']
            drop_date = main_drop['date']
            all_after = tesisat_df.iloc[drop_index:]
            
            # Geri dönüş kontrolü
            recovery_occurred = False
            max_recovery_pct = 0
            
            for _, row in all_after.iterrows():
                recovery_pct = (row['tuketim'] / main_drop['before_avg']) * 100
                max_recovery_pct = max(max_recovery_pct, recovery_pct)
                
                if recovery_pct >= recovery_threshold_pct:
                    recovery_occurred = True
                    break
            
            # Trend kontrolü
            if len(all_after) >= 3:
                x = np.arange(len(all_after))
                y = all_after['tuketim'].values
                trend_coef = np.polyfit(x, y, 1)[0]
                trend_rising = (trend_coef > 0) and (abs(trend_coef) > (y.mean() * 0.05))
            else:
                trend_rising = False
            
            # Yeni muhatap ilk ay kontrolü (Senaryo: İlk ay yüksek, sonra düşük)
            new_muhatap_suspicious = False
            if muhatap_degisim_var and muhatap_degisim_tarihi:
                # Muhatap değişiminden sonraki ilk 3 ay
                after_change_idx = tesisat_df[tesisat_df['tarih_dt'] >= muhatap_degisim_tarihi].index
                if len(after_change_idx) >= 6:
                    first_3_months = tesisat_df.loc[after_change_idx[0]:after_change_idx[2]]
                    next_3_months = tesisat_df.loc[after_change_idx[3]:after_change_idx[5]]
                    
                    if len(first_3_months) >= 3 and len(next_3_months) >= 3:
                        first_avg = first_3_months['tuketim'].mean()
                        next_avg = next_3_months['tuketim'].mean()
                        
                        if first_avg > 0 and next_avg > 0:
                            drop_after_change = ((first_avg - next_avg) / first_avg) * 100
                            if drop_after_change > 50:  # İlk 3 aydan sonra %50+ düşüş
                                new_muhatap_suspicious = True
            
            # KRİTİK KARAR ALGORİTMASI
            is_suspicious = False
            explanation_parts = []
            risk_score = min(100, main_drop['drop_pct'])
            
            # SENARYO 1: Cihaz DEĞİŞMEDİ, düşüş var → EN RİSKLİ
            if not cihaz_degisim_var and not recovery_occurred and not trend_rising:
                explanation_parts.append("🚨 **CIHAZ DEĞİŞMEDİ** ama düşüş var (Rekor delik şüphesi)")
                risk_score += 30
                is_suspicious = True
            
            # SENARYO 2: Cihaz değişti → GENELLİKLE NORMAL
            elif cihaz_degisim_var:
                explanation_parts.append(f"🔧 Cihaz değişimi var ({cihaz_degisim_tarihi.strftime('%Y-%m')})")
                risk_score -= 40  # Risk azalt
                # Sadece çok yüksek düşüşse şüpheli
                if main_drop['drop_pct'] > 90 and not recovery_occurred:
                    explanation_parts.append("⚠️ Cihaz değişti ama %90+ düşüş var")
                    risk_score += 20
                    is_suspicious = True
                else:
                    is_suspicious = False
            
            # SENARYO 3: Yeni muhatap, ilk ay yüksek sonra düşük → ŞÜPHELİ
            elif new_muhatap_suspicious:
                explanation_parts.append(f"👤 **YENİ MUHATAP ŞÜPHELİ**: {yeni_muhatap} - İlk ay yüksek, sonra düşük")
                risk_score += 40
                is_suspicious = True
            
            # SENARYO 4: Normal kalıcı düşüş
            elif not recovery_occurred and not trend_rising:
                explanation_parts.append(f"📉 Kalıcı düşüş tespit edildi")
                is_suspicious = True
            
            # SON KARAR
            if is_suspicious:
                results.append(tesisat)
                explanation = " | ".join(explanation_parts)
                
                # Öncelik belirle
                if risk_score >= 80:
                    oncelik = 'YÜKSEK'
                    saha_onerisi = 'ACİL KONTROL (1 hafta içinde)'
                elif risk_score >= 60:
                    oncelik = 'ORTA'
                    saha_onerisi = 'ÖNCELİKLİ KONTROL (1 ay içinde)'
                else:
                    oncelik = 'DÜŞÜK'
                    saha_onerisi = 'RUTİN TAKİP (3 ay içinde)'
                
                all_details.append({
                    'TESİSAT_NO': tesisat,
                    'BİNA_NO': tesisat_df['bina_no'].iloc[0],
                    'MUHATAP': tesisat_df['muhatap'].iloc[-1] if 'muhatap' in tesisat_df.columns else 'Bilgi Yok',
                    'CIHAZ_NO': tesisat_df['cihaz_no'].iloc[-1] if 'cihaz_no' in tesisat_df.columns else 'Bilgi Yok',
                    'DÜŞÜŞ_TARİHİ': drop_date.strftime('%Y-%m'),
                    'ÖNCEKİ_ORT (m³)': round(main_drop['before_avg'], 1),
                    'SONRAKİ_ORT (m³)': round(main_drop['after_avg'], 1),
                    'DÜŞÜŞ_%': round(main_drop['drop_pct'], 1),
                    'MAX_GERİ_DÖNÜŞ_%': round(max_recovery_pct, 1),
                    'CIHAZ_DEĞİŞİMİ': 'EVET' if cihaz_degisim_var else 'HAYIR',
                    'MUHATAP_DEĞİŞİMİ': 'EVET' if muhatap_degisim_var else 'HAYIR',
                    'YENİ_MUHATAP': yeni_muhatap if yeni_muhatap else '',
                    'RİSK_SKORU': round(risk_score, 0),
                    'ÖNCELİK': oncelik,
                    'AÇIKLAMA': explanation,
                    'SAHA_KONTROL_ÖNERİSİ': saha_onerisi,
                    'TESPİT_NEDENİ': 'AKILLI_KALICI_DÜŞÜŞ'
                })
        
        details_df = pd.DataFrame(all_details)
        if not details_df.empty:
            details_df = details_df.sort_values('RİSK_SKORU', ascending=False)
        
        return results, details_df
    
    # 6. MUHATAP DEĞİŞİM RAPORU (Basit)
    def get_muhatap_changes(df):
        """Basit muhatap değişim raporu"""
        if 'muhatap' not in df.columns:
            return pd.DataFrame()
        
        changes = []
        for tesisat in df['tesisat_no'].unique():
            tesisat_df = df[df['tesisat_no'] == tesisat].sort_values('tarih_dt')
            muhataplar = tesisat_df['muhatap'].dropna().unique()
            
            if len(muhataplar) > 1:
                changes.append({
                    'TESİSAT_NO': tesisat,
                    'BİNA_NO': tesisat_df['bina_no'].iloc[0],
                    'MUHATAP_SAYISI': len(muhataplar),
                    'MUHATAPLAR': ' → '.join([str(m) for m in muhataplar]),
                    'İLK_MUHATAP': muhataplar[0],
                    'SON_MUHATAP': muhataplar[-1]
                })
        
        return pd.DataFrame(changes)
    
    # 7. ANALİZLERİ ÇALIŞTIR
    st.header("🔍 AKILLI ANALİZ SONUÇLARI")
    
    with st.spinner("Analizler çalıştırılıyor..."):
        # 1. Akıllı Kalıcı Düşüş
        smart_drop_list, smart_drop_details = detect_smart_permanent_drop(
            df,
            min_drop_pct=min_drop_percent,
            min_months_after=min_months_after,
            recovery_threshold_pct=recovery_threshold
        )
        
        # 2. Diğer analizler
        winter_list, winter_details = detect_low_winter_consumption(df, threshold=min_winter_cons)
        bina_list, bina_details = detect_building_anomaly(df, percentile=bina_percentile)
        zero_list, zero_details = detect_zero_consumption(df, min_months=4)
        
        # 3. Muhatap değişim raporu
        muhatap_changes_df = get_muhatap_changes(df)
        
        # Tüm şüphelileri birleştir
        all_sus = list(set(smart_drop_list + winter_list + bina_list + zero_list))
        
        # Detaylı liste oluştur
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
            
            # Risk skoru (akıllı düşüş varsa onun skorunu al)
            risk_score = 0
            if tesisat in smart_drop_list:
                smart_info = smart_drop_details[smart_drop_details['TESİSAT_NO'] == tesisat]
                if not smart_info.empty:
                    risk_score = smart_info.iloc[0]['RİSK_SKORU']
                else:
                    # Diğer kriterlere göre
                    risk_score = len(criteria) * 20
            else:
                risk_score = len(criteria) * 20
            
            all_details_list.append({
                'TESİSAT_NO': tesisat,
                'BİNA_NO': tesisat_data['bina_no'].iloc[0],
                'MUHATAP': tesisat_data['muhatap'].iloc[-1] if 'muhatap' in tesisat_data.columns else 'Bilgi Yok',
                'KRİTERLER': ', '.join(criteria),
                'RİSK_SKORU': risk_score,
                'ÖNCELİK': 'YÜKSEK' if risk_score >= 70 else 'ORTA' if risk_score >= 40 else 'DÜŞÜK'
            })
        
        all_sus_df = pd.DataFrame(all_details_list)
        if not all_sus_df.empty:
            all_sus_df = all_sus_df.sort_values('RİSK_SKORU', ascending=False)
    
    # 8. SONUÇ PANELİ
    st.subheader("📊 ÖZET RAPOR")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Toplam Şüpheli", len(all_sus))
    with col2:
        st.metric("Akıllı Düşüş", len(smart_drop_list), delta_color="inverse")
    with col3:
        st.metric("Muhatap Değişimi", f"{len(muhatap_changes_df)} tesisat" if not muhatap_changes_df.empty else "Yok")
    with col4:
        high_risk = len([x for x in all_details_list if x['RİSK_SKORU'] >= 70])
        st.metric("Yüksek Risk", high_risk, delta_color="inverse")
    
    # 9. TABLAR
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🎯 TÜM ŞÜPHELİLER",
        "🚨 AKILLI DÜŞÜŞ ANALİZİ",
        "👤 MUHATAP DEĞİŞİMLERİ",
        "❄️ DÜŞÜK KIŞ",
        "🏢 BİNA ANOMALİSİ",
        "🔍 TEKİL ANALİZ"
    ])
    
    with tab1:
        if not all_sus_df.empty:
            st.dataframe(all_sus_df, use_container_width=True)
        else:
            st.success("✅ Şüpheli tesisat bulunamadı")
    
    with tab2:
        if not smart_drop_details.empty:
            # Filtreleme
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                min_risk = st.slider("Min. Risk", 0, 100, 60, key="smart_risk")
            with col_f2:
                cihaz_filter = st.selectbox("Cihaz Değişimi", ["Tümü", "EVET", "HAYIR"], key="cihaz_filter")
            
            filtered = smart_drop_details[smart_drop_details['RİSK_SKORU'] >= min_risk]
            if cihaz_filter != "Tümü":
                filtered = filtered[filtered['CIHAZ_DEĞİŞİMİ'] == cihaz_filter]
            
            st.dataframe(filtered, use_container_width=True)
            
            # Grafik: Cihaz değişimine göre risk dağılımı
            if not filtered.empty:
                fig = px.box(filtered, x='CIHAZ_DEĞİŞİMİ', y='RİSK_SKORU',
                           title='Cihaz Değişimine Göre Risk Skorları',
                           color='CIHAZ_DEĞİŞİMİ')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Akıllı düşüş tespit edilmedi")
    
    with tab3:
        if not muhatap_changes_df.empty:
            st.dataframe(muhatap_changes_df, use_container_width=True)
        else:
            st.info("Muhatap değişimi bulunamadı")
    
    with tab4:
        if not winter_details.empty:
            st.dataframe(winter_details, use_container_width=True)
    
    with tab5:
        if not bina_details.empty:
            st.dataframe(bina_details, use_container_width=True)
    
    with tab6:
        st.subheader("🔍 Tekil Tesisat Analizi")
        selected_tesisat = st.selectbox("Tesisat seçin:", df['tesisat_no'].unique()[:100])
        
        if selected_tesisat:
            tesisat_data = df[df['tesisat_no'] == selected_tesisat].sort_values('tarih_dt')
            
            # Bilgiler
            col_i1, col_i2, col_i3 = st.columns(3)
            with col_i1:
                st.metric("Tesisat", selected_tesisat)
                if 'muhatap' in tesisat_data.columns:
                    st.metric("Muhatap", tesisat_data['muhatap'].iloc[-1])
            
            with col_i2:
                st.metric("Ortalama", f"{tesisat_data['tuketim'].mean():.1f} m³")
                if 'cihaz_no' in tesisat_data.columns:
                    st.metric("Cihaz", tesisat_data['cihaz_no'].iloc[-1])
            
            with col_i3:
                st.metric("Veri Sayısı", len(tesisat_data))
                st.metric("Son Tüketim", f"{tesisat_data['tuketim'].iloc[-1]:.1f} m³")
            
            # Muhatap değişim bilgisi
            if 'muhatap' in tesisat_data.columns:
                unique_muhataplar = tesisat_data['muhatap'].dropna().unique()
                if len(unique_muhataplar) > 1:
                    st.warning(f"👤 Muhatap değişimi: {' → '.join([str(m) for m in unique_muhataplar])}")
            
            # Cihaz değişim bilgisi
            if 'cihaz_no' in tesisat_data.columns:
                unique_cihazlar = tesisat_data['cihaz_no'].dropna().unique()
                if len(unique_cihazlar) > 1:
                    st.info(f"🔧 Cihaz değişimi: {' → '.join([str(c) for c in unique_cihazlar])}")
            
            # Grafik
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
            
            # Muhatap değişim çizgileri
            if 'muhatap' in tesisat_data.columns:
                for i in range(1, len(tesisat_data)):
                    if tesisat_data.iloc[i]['muhatap'] != tesisat_data.iloc[i-1]['muhatap']:
                        fig.add_vline(x=tesisat_data.iloc[i]['tarih_dt'], 
                                    line_dash="dot", line_color="green",
                                    annotation_text="Muhatap değişimi")
            
            fig.update_layout(title=f"Tesisat {selected_tesisat} Tüketim Geçmişi",
                            xaxis_title="Tarih", yaxis_title="Tüketim (m³)")
            st.plotly_chart(fig, use_container_width=True)
    
    # 10. EXCEL RAPORU
    st.markdown("---")
    st.header("📄 EXCEL RAPORU")
    
    if not all_sus_df.empty:
        excel_data = to_excel({
            'ANALİZ_ÖZET': pd.DataFrame([{
                'Tarih': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'Toplam_Tesisat': df['tesisat_no'].nunique(),
                'Şüpheli_Tesisat': len(all_sus),
                'Akıllı_Düşüş': len(smart_drop_list),
                'Düşük_Kış': len(winter_list),
                'Bina_Anomalisi': len(bina_list),
                'Sıfır_Tüketim': len(zero_list)
            }]),
            'TÜM_ŞÜPHELİLER': all_sus_df,
            'AKILLI_DÜŞÜŞ_ANALİZİ': smart_drop_details if not smart_drop_details.empty else pd.DataFrame({'BİLGİ': ['Bulunamadı']}),
            'MUHATAP_DEĞİŞİMLERİ': muhatap_changes_df if not muhatap_changes_df.empty else pd.DataFrame({'BİLGİ': ['Bulunamadı']}),
            'DÜŞÜK_KIŞ': winter_details if not winter_details.empty else pd.DataFrame({'BİLGİ': ['Bulunamadı']}),
            'BİNA_ANOMALİSİ': bina_details if not bina_details.empty else pd.DataFrame({'BİLGİ': ['Bulunamadı']})
        })
        
        st.download_button(
            label="📊 EXCEL RAPORU İNDİR",
            data=excel_data,
            file_name=f"akilli_kacak_tespit_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("👈 Lütfen Excel veya CSV dosyasını yükleyin")
    st.markdown("""
    ### 📋 BEKLENEN VERİ YAPISI:
    
    | tarih | tesisat_no | bina_no | tuketim | muhatap | cihaz_no |
    |-------|------------|---------|---------|---------|----------|
    | 2023/1 | 12345 | BINA001 | 150.5 | Ahmet Yılmaz | SAYAC001 |
    | 2023/2 | 12345 | BINA001 | 145.2 | Ahmet Yılmaz | SAYAC001 |
    | 2023/3 | 12345 | BINA001 | 25.3 | Mehmet Demir | SAYAC001 |
    | 2023/4 | 12345 | BINA001 | 24.8 | Mehmet Demir | SAYAC002 |
    
    ### 🎯 AKILLI ANALİZ SENARYOLARI:
    
    1. **CIHAZ DEĞİŞMEDİ + DÜŞÜŞ VAR**: 🚨 **REKOR DELİK ŞÜPHESİ** (En riskli)
    2. **CIHAZ DEĞİŞTİ + DÜŞÜŞ VAR**: 🔧 **Normal** (Yanlış pozitif elemek için)
    3. **YENİ MUHATAP + İLK AY YÜKSEK + SONRA DÜŞÜK**: 🚨 **KAÇAK BAŞLADI**
    
    ### ✨ SADECE FAYDALI ÖZELLİKLER:
    
    - **Akıllı Filtreleme**: Gereksiz kontrollerden kurtarır
    - **Yanlış Pozitif Azaltma**: Cihaz değişimini otomatik ele
    - **Odaklanmış Kontrol**: Sadece gerçek şüphelilere git
    - **Pratik Rapor**: Saha ekibi için net öneriler
    """)
