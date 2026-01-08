import matplotlib.pyplot as plt

# Şüpheli bir aboneyi görselleştir
def plot_suspicious_tenant(tenant_id):
    tenant_data = final_df[final_df['TesisatNo'] == tenant_id].sort_values('Tarih')
    rec_date = tenant_data['Rekor_Tarihi'].iloc[0]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Tüketim grafiği
    ax1.plot(tenant_data['Tarih'], tenant_data['Tüketim'], 'b-', label='Tüketim')
    ax1.axvline(rec_date, color='r', linestyle='--', label='Rekor Tarihi')
    ax1.set_title(f'Tesisat: {tenant_id} - Tüketim Trendi')
    ax1.set_ylabel('Tüketim')
    ax1.legend()
    ax1.grid(True)
    
    # Mevsimsel indeks grafiği
    ax2.plot(tenant_data['Tarih'], tenant_data['Mevsimsel_İndeks'], 'g-', label='Mevsimsel İndeks')
    ax2.axhline(y=1, color='k', linestyle=':', label='Normal (1.0)')
    ax2.axvline(rec_date, color='r', linestyle='--', label='Rekor Tarihi')
    ax2.set_title('Mevsimsel İndeks Trendi')
    ax2.set_ylabel('İndeks')
    ax2.set_xlabel('Tarih')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.show()

# İlk 3 şüpheli aboneyi görselleştir
for tenant in suspicious_list['TesisatNo'].head(3).values:
    plot_suspicious_tenant(tenant)
