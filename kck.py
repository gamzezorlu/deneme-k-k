import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import io

# Sayfa ayarı
st.set_page_config(
    page_title="Doğalgaz Kaçak Tespit Sistemi",
    page_icon="🔥",
    layout="wide"
)

# Başlık
st.title("🔥 Doğalgaz Kaçak Tespit Sistemi")
st.markdown("""
Bu uygulama, doğalgaz sayaçlarının **çıkış rekorunun delinmesi** sonucu oluşan 
manipülasyonları tespit etmek için geliştirilmiştir.
""")

# Sidebar
with st.sidebar:
    st.header("📁 Veri Yükleme")
    uploaded_file = st.file_uploader(
        "Excel dosyasını yükleyin", 
        type=['xlsx', 'xls'],
        help="Sütunlar: Tarih, TesisatNo, BinaNo, Tüketim"
    )
    
    st.header("⚙️ Analiz Parametreleri")
    drop_threshold = st.slider(
        "Minimum Düşüş Oranı (%)", 
        min_value=10, max_value=80, value=30, step=5
    ) / 100
    
    permanent_threshold = st.slider(
        "Kalıcı Düşüş Eşiği (%)",
        min_value=10, max_value=50, value=30, step=5
    ) / 100
    
    bina_diff_threshold = st.slider(
        "Bina Farkı Eşiği (%)",
        min_value=5, max_value=40, value=20, step=5
    ) / 100
    
    st.header("📊 Görselleştirme")
    show_charts = st.checkbox("Grafikleri göster", value=True)
    
    st.markdown("---")
    st.markdown("**Geliştirici:** Kaçak Tespit Sistemi v1.0")

# Ana içerik
if uploaded_file is not None:
    try:
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("Veri yükleniyor...")
        df = pd.read_excel(uploaded_file)
        progress_bar.progress(20)
        
        # Veri kontrolü
        required_columns = ['Tarih', 'TesisatNo', 'BinaNo', 'Tüketim']
        if not all(col in df.columns for col in required_columns):
            st.error(f"Excel dosyasında şu sütunlar olmalı: {required_columns}")
            st.stop()
        
        status_text.text("Tarih formatı dönüştürülüyor...")
        df['Tarih'] = pd.to_datetime(df['Tarih'], format='%Y-%m', errors='coerce')
        progress_bar.progress(30)
        
        # 1. Mevsimsel İndeks Hesaplama
        status_text.text("Mevsimsel indeks hesaplanıyor...")
        def calculate_seasonal_index(group):
            group = group.copy()
            yearly_avg = group.groupby(group['Tarih'].dt.year)['Tüketim'].transform('mean')
            group['Mevsimsel_İndeks'] = group['Tüketim'] / yearly_avg
            return group
        
        df = df.groupby('TesisatNo', group_keys=False).apply(calculate_seasonal_index)
        progress_bar.progress(40)
        
        # 2. Bina bazlı ortalama
        status_text.text("Bina ortalamaları hesaplanıyor...")
        df['Bina_Ay_Ortalama'] = df.groupby(['BinaNo', df['Tarih'].dt.month])['Mevsimsel_İndeks'].transform('mean')
        df['Bina_Fark'] = df['Mevsimsel_İndeks'] - df['Bina_Ay_Ortalama']
        progress_bar.progress(50)
        
        # 3. Rekor tarihleri
        status_text.text("Rekor tarihleri bulunuyor...")
        def find_record_date(group):
            if group.empty:
                return pd.NaT
            max_idx = group['Tüketim'].idxmax()
            return group.loc[max_idx, 'Tarih']
        
        record_dates = df.groupby('TesisatNo').apply(find_record_date).reset_index()
        record_dates.columns = ['TesisatNo', 'Rekor_Tarihi']
        df = df.merge(record_dates, on='TesisatNo', how='left')
        progress_bar.progress(60)
        
        # 4. Kalıcı düşüş kontrolü
        status_text.text("Kalıcı düşüş analizi yapılıyor...")
        def check_permanent_drop(group, drop_thresh, perm_thresh, bina_thresh):
            if pd.isna(group['Rekor_Tarihi'].iloc[0]):
                return pd.Series([False, None], index=['Süpheli', 'Açıklama'])
            
            rec_date = group['Rekor_Tarihi'].iloc[0]
            
            # Önceki ve sonraki dönemler
            before = group[group['Tarih'] < rec_date]
            after = group[group['Tarih'] > rec_date]
            
            if len(before) < 6 or len(after) < 12:
                return pd.Series([False, 'Yetersiz veri'], index=['Süpheli', 'Açıklama'])
            
            # Mevsimsel karşılaştırma
            before_monthly_avg = before.groupby(before['Tarih'].dt.month)['Mevsimsel_İndeks'].mean()
            after_monthly_avg = after.groupby(after['Tarih'].dt.month)['Mevsimsel_İndeks'].mean()
            
            common_months = set(before_monthly_avg.index) & set(after_monthly_avg.index)
            
            if not common_months:
                return pd.Series([False, 'Ortak ay yok'], index=['Süpheli', 'Açıklama'])
            
            drops = []
            for month in common_months:
                before_val = before_monthly_avg[month]
                after_val = after_monthly_avg[month]
                if before_val > 0:
                    drop_ratio = (before_val - after_val) / before_val
                    drops.append(drop_ratio)
            
            if not drops:
                return pd.Series([False, 'Düşüş hesaplanamadı'], index=['Süpheli', 'Açıklama'])
            
            avg_drop = np.mean(drops)
            
            if avg_drop < drop_thresh:
                return pd.Series([False, f'Düşüş yetersiz: %{avg_drop*100:.1f}'], 
                               index=['Süpheli', 'Açıklama'])
            
            # Kalıcılık kontrolü
            years_after = sorted(after['Tarih'].dt.year.unique())
            
            if len(years_after) >= 2:
                first_two_years = after[after['Tarih'].dt.year <= years_after[1]]
                first_two_years_avg = first_two_years['Mevsimsel_İndeks'].mean()
                before_avg = before['Mevsimsel_İndeks'].mean()
                
                if first_two_years_avg < before_avg * (1 - perm_thresh):
                    bina_fark_avg = after['Bina_Fark'].mean()
                    if bina_fark_avg < -bina_thresh:
                        return pd.Series([True, 
                                        f'Şüpheli - Düşüş: %{avg_drop*100:.1f}, Bina farkı: %{bina_fark_avg*100:.1f}'], 
                                       index=['Süpheli', 'Açıklama'])
            
            return pd.Series([False, f'Kalıcı düşüş yok: %{avg_drop*100:.1f}'], 
                           index=['Süpheli', 'Açıklama'])
        
        results = df.groupby('TesisatNo').apply(
            lambda x: check_permanent_drop(x, drop_threshold, permanent_threshold, bina_diff_threshold)
        ).reset_index()
        
        progress_bar.progress(80)
        
        # Sonuçları birleştir
        final_df = df.merge(results, on='TesisatNo', how='left')
        
        # Şüpheli aboneler
        suspicious = final_df[final_df['Süpheli'] == True]
        suspicious_list = suspicious[['TesisatNo', 'BinaNo', 'Rekor_Tarihi', 'Açıklama']].drop_duplicates()
        
        progress_bar.progress(100)
        status_text.text("Analiz tamamlandı!")
        
        # Sonuçlar
        st.success(f"✅ Analiz tamamlandı!")
        
        # Metrikler
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Toplam Abone", final_df['TesisatNo'].nunique())
        with col2:
            st.metric("Şüpheli Abone", len(suspicious_list))
        with col3:
            if final_df['TesisatNo'].nunique() > 0:
                percentage = (len(suspicious_list) / final_df['TesisatNo'].nunique()) * 100
                st.metric("Şüpheli Oranı", f"{percentage:.1f}%")
        
        # Şüpheli aboneler tablosu
        st.subheader("🔍 Şüpheli Aboneler")
        if len(suspicious_list) > 0:
            st.dataframe(
                suspicious_list.sort_values('Rekor_Tarihi', ascending=False),
                use_container_width=True
            )
            
            # Excel indirme butonu
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                suspicious_list.to_excel(writer, sheet_name='Şüpheli_Aboneler', index=False)
                final_df.to_excel(writer, sheet_name='Tüm_Veri', index=False)
            
            st.download_button(
                label="📥 Sonuçları Excel Olarak İndir",
                data=output.getvalue(),
                file_name="kacak_tespit_sonuclari.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("❌ Şüpheli abone bulunamadı.")
        
        # Grafikler
        if show_charts and len(suspicious_list) > 0:
            st.subheader("📈 Detaylı Analiz Grafikleri")
            
            # Şüpheli abone seçimi
            selected_tenant = st.selectbox(
                "Grafik görmek istediğiniz aboneyi seçin:",
                options=suspicious_list['TesisatNo'].unique()
            )
            
            if selected_tenant:
                tenant_data = final_df[final_df['TesisatNo'] == selected_tenant].sort_values('Tarih')
                rec_date = tenant_data['Rekor_Tarihi'].iloc[0]
                
                # Grafik oluştur
                fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12))
                
                # Tüketim grafiği
                ax1.plot(tenant_data['Tarih'], tenant_data['Tüketim'], 'b-', linewidth=2, label='Tüketim')
                ax1.axvline(rec_date, color='r', linestyle='--', linewidth=2, label='Rekor Tarihi')
                ax1.fill_between(tenant_data['Tarih'], 0, tenant_data['Tüketim'], alpha=0.3)
                ax1.set_title(f'Tesisat: {selected_tenant} - Tüketim Trendi', fontsize=14, fontweight='bold')
                ax1.set_ylabel('Tüketim (m³)')
                ax1.legend()
                ax1.grid(True, alpha=0.3)
                
                # Mevsimsel indeks grafiği
                ax2.plot(tenant_data['Tarih'], tenant_data['Mevsimsel_İndeks'], 'g-', linewidth=2, label='Mevsimsel İndeks')
                ax2.axhline(y=1, color='k', linestyle=':', alpha=0.5, label='Normal (1.0)')
                ax2.axvline(rec_date, color='r', linestyle='--', linewidth=2, label='Rekor Tarihi')
                ax2.set_title('Mevsimsel İndeks Trendi', fontsize=14, fontweight='bold')
                ax2.set_ylabel('İndeks')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
                
                # Bina farkı grafiği
                ax3.bar(tenant_data['Tarih'], tenant_data['Bina_Fark'], 
                       color=np.where(tenant_data['Bina_Fark'] < 0, 'red', 'green'), alpha=0.7)
                ax3.axhline(y=0, color='k', linestyle='-', alpha=0.5)
                ax3.axvline(rec_date, color='r', linestyle='--', linewidth=2, label='Rekor Tarihi')
                ax3.set_title('Bina Ortalamasından Fark', fontsize=14, fontweight='bold')
                ax3.set_ylabel('Fark')
                ax3.set_xlabel('Tarih')
                ax3.legend()
                ax3.grid(True, alpha=0.3)
                
                plt.tight_layout()
                st.pyplot(fig)
        
        # İstatistikler
        with st.expander("📊 Detaylı İstatistikler"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Tarih Aralığı:**")
                st.write(f"- Başlangıç: {final_df['Tarih'].min().strftime('%Y-%m')}")
                st.write(f"- Bitiş: {final_df['Tarih'].max().strftime('%Y-%m')}")
                
                st.write("**Bina Dağılımı:**")
                st.write(f"- Toplam bina: {final_df['BinaNo'].nunique()}")
            
            with col2:
                st.write("**Tüketim İstatistikleri:**")
                st.write(f"- Ortalama tüketim: {final_df['Tüketim'].mean():.2f} m³")
                st.write(f"- Maksimum tüketim: {final_df['Tüketim'].max():.2f} m³")
                st.write(f"- Minimum tüketim: {final_df['Tüketim'].min():.2f} m³")
        
    except Exception as e:
        st.error(f"Bir hata oluştu: {str(e)}")
        st.info("Lütfen Excel dosyasının formatını kontrol edin.")

else:
    # Dosya yüklenmemişse örnek veri göster
    st.info("👈 Lütfen sol taraftan bir Excel dosyası yükleyin.")
    
    with st.expander("📋 Örnek Excel Formatı"):
        sample_data = pd.DataFrame({
            'Tarih': ['2020/01', '2020/02', '2020/03', '2020/01', '2020/02'],
            'TesisatNo': [1001, 1001, 1001, 1002, 1002],
            'BinaNo': ['A1', 'A1', 'A1', 'A1', 'A1'],
            'Tüketim': [150.5, 180.2, 120.8, 90.3, 110.5]
        })
        st.dataframe(sample_data)
        
        st.download_button(
            label="📥 Örnek Excel Dosyasını İndir",
            data=sample_data.to_csv(index=False).encode('utf-8'),
            file_name="ornek_veri.csv",
            mime="text/csv"
        )
    
    with st.expander("ℹ️ Nasıl Kullanılır?"):
        st.markdown("""
        1. **Veri Hazırlığı**: Excel dosyanızda şu sütunlar olmalı:
           - `Tarih` (Örnek: 2020/01)
           - `TesisatNo` (Abone numarası)
           - `BinaNo` (Bina numarası/kodu)
           - `Tüketim` (m³ cinsinden)
        
        2. **Parametre Ayarları**: Sol taraftan analiz parametrelerini ayarlayın
        
        3. **Analiz**: Dosyayı yükleyip analiz butonuna tıklayın
        
        4. **Sonuçlar**: Şüpheli aboneler listelenecek ve detaylı grafikler gösterilecek
        """)

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center'>
        <p>Doğalgaz Kaçak Tespit Sistemi v1.0 | Geliştirici: Analiz Ekibi</p>
    </div>
    """,
    unsafe_allow_html=True
)
