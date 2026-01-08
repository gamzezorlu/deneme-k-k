import pandas as pd
import numpy as np
from datetime import datetime

# Veriyi yükle (örnek yapı: Tarih, TesisatNo, BinaNo, Tüketim)
df = pd.read_excel('veri.xlsx')

# Tarihi datetime'a çevir
df['Tarih'] = pd.to_datetime(df['Tarih'], format='%Y/%m')

# 1. Mevsimsel İndeks Hesaplama
def calculate_seasonal_index(group):
    group = group.copy()
    # Yıllık ortalama tüketim
    yearly_avg = group.groupby(group['Tarih'].dt.year)['Tüketim'].transform('mean')
    group['Mevsimsel_İndeks'] = group['Tüketim'] / yearly_avg
    return group

df = df.groupby('TesisatNo', group_keys=False).apply(calculate_seasonal_index)

# 2. Bina bazlı ortalama hesaplama (mevsimsel indeks bazında)
df['Bina_Ay_Ortalama'] = df.groupby(['BinaNo', df['Tarih'].dt.month])['Mevsimsel_İndeks'].transform('mean')
df['Bina_Fark'] = df['Mevsimsel_İndeks'] - df['Bina_Ay_Ortalama']

# 3. Her abone için rekor tarihini bul
def find_record_date(group):
    if group.empty:
        return pd.NaT
    max_idx = group['Tüketim'].idxmax()
    return group.loc[max_idx, 'Tarih']

record_dates = df.groupby('TesisatNo').apply(find_record_date).reset_index()
record_dates.columns = ['TesisatNo', 'Rekor_Tarihi']

# Ana veriye rekor tarihini ekle
df = df.merge(record_dates, on='TesisatNo', how='left')

# 4. Kalıcı düşüş kontrolü
def check_permanent_drop(group):
    if pd.isna(group['Rekor_Tarihi'].iloc[0]):
        return pd.Series([False, None], index=['Süpheli', 'Açıklama'])
    
    rec_date = group['Rekor_Tarihi'].iloc[0]
    
    # Önceki dönem (rekor öncesi 1 yıl)
    before = group[group['Tarih'] < rec_date]
    
    # Sonraki dönem (rekor sonrası en az 2 yıl)
    after = group[group['Tarih'] > rec_date]
    
    if len(before) < 6 or len(after) < 12:  # Yeterli veri yok
        return pd.Series([False, 'Yetersiz veri'], index=['Süpheli', 'Açıklama'])
    
    # Aynı ayları karşılaştır (mevsimsellik için)
    before_monthly_avg = before.groupby(before['Tarih'].dt.month)['Mevsimsel_İndeks'].mean()
    after_monthly_avg = after.groupby(after['Tarih'].dt.month)['Mevsimsel_İndeks'].mean()
    
    # Ortak ayları bul
    common_months = set(before_monthly_avg.index) & set(after_monthly_avg.index)
    
    if not common_months:
        return pd.Series([False, 'Ortak ay yok'], index=['Süpheli', 'Açıklama'])
    
    # Her ortak ay için düşüş oranı hesapla
    drops = []
    for month in common_months:
        before_val = before_monthly_avg[month]
        after_val = after_monthly_avg[month]
        if before_val > 0:
            drop_ratio = (before_val - after_val) / before_val
            drops.append(drop_ratio)
    
    if not drops:
        return pd.Series([False, 'Düşüş hesaplanamadı'], index=['Süpheli', 'Açıklama'])
    
    # Ortalama düşüş %30'dan fazla mı?
    avg_drop = np.mean(drops)
    
    if avg_drop < 0.3:
        return pd.Series([False, f'Düşüş yetersiz: %{avg_drop*100:.1f}'], index=['Süpheli', 'Açıklama'])
    
    # Kalıcılık kontrolü: Sonraki 2 yıl boyunca düşük mü?
    years_after = sorted(after['Tarih'].dt.year.unique())
    
    if len(years_after) >= 2:
        first_two_years = after[after['Tarih'].dt.year <= years_after[1]]
        first_two_years_avg = first_two_years['Mevsimsel_İndeks'].mean()
        before_avg = before['Mevsimsel_İndeks'].mean()
        
        if first_two_years_avg < before_avg * 0.7:  # %30'tan fazla düşük
            # Bina bazlı doğrulama: Binadan da düşük mü?
            bina_fark_avg = after['Bina_Fark'].mean()
            if bina_fark_avg < -0.2:  # Binadan %20 daha düşük
                return pd.Series([True, f'Şüpheli - Düşüş: %{avg_drop*100:.1f}, Bina farkı: %{bina_fark_avg*100:.1f}'], 
                               index=['Süpheli', 'Açıklama'])
    
    return pd.Series([False, f'Kalıcı düşüş yok: %{avg_drop*100:.1f}'], index=['Süpheli', 'Açıklama'])

# 5. Her abone için analiz yap
results = df.groupby('TesisatNo').apply(check_permanent_drop).reset_index()

# Sonuçları birleştir
final_df = df.merge(results, on='TesisatNo', how='left')

# Şüpheli aboneleri filtrele
suspicious = final_df[final_df['Süpheli'] == True]
suspicious_list = suspicious[['TesisatNo', 'BinaNo', 'Rekor_Tarihi', 'Açıklama']].drop_duplicates()

print(f"Toplam abone sayısı: {final_df['TesisatNo'].nunique()}")
print(f"Şüpheli abone sayısı: {len(suspicious_list)}")
print("\nŞüpheli aboneler:")
print(suspicious_list.head(20))
