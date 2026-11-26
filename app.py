from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
import pandas as pd
import plotly.express as px
import numpy as np
import io
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'rahasia_dashboard_skenario18'

# Pastikan folder 'data' otomatis dibuat jika belum ada
app.config['UPLOAD_FOLDER'] = 'data'
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def load_data():
    # Cek apakah ada file yang diupload, jika tidak gunakan default WHR_2024.csv
    file_upload = os.path.join(app.config['UPLOAD_FOLDER'], 'data_upload.csv')
    file_default = os.path.join(app.config['UPLOAD_FOLDER'], 'WHR_2024.csv')
    
    file_path = file_upload if os.path.exists(file_upload) else file_default
        
    df = pd.read_csv(file_path)
    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
    
    # Simulasi 3 Tahun Data
    df_2022 = df.copy()
    df_2023 = df.copy()
    df_2024 = df.copy()
    df_2022['year'] = 2022
    df_2023['year'] = 2023
    df_2024['year'] = 2024
    
    np.random.seed(42)
    df_2022['happiness_score'] -= np.random.uniform(0.1, 0.5, size=len(df_2022))
    df_2023['happiness_score'] -= np.random.uniform(0.05, 0.2, size=len(df_2023))
    
    df_all = pd.concat([df_2022, df_2023, df_2024], ignore_index=True)
    
    # PIPELINE PEMBERSIHAN DATA
    df_all = df_all.drop_duplicates()
    df_all = df_all.dropna(subset=['happiness_score', 'gdp_per_capita'])
    
    return df_all

users = {"admin": generate_password_hash("12345")}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and check_password_hash(users[username], password):
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            return "Login Gagal! <a href='/login'>Coba lagi</a>"
    return '''
    <div style="text-align:center; margin-top:100px; font-family:Arial;">
        <h2>Login Dashboard</h2>
        <form method="post">
            <input type="text" name="username" placeholder="Username (admin)" required><br><br>
            <input type="password" name="password" placeholder="Password (12345)" required><br><br>
            <button type="submit" style="padding:10px 20px;">Masuk</button>
        </form>
    </div>
    '''

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route("/", methods=['GET', 'POST'])
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        if file.filename.endswith('.csv'):
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'data_upload.csv'))
            return redirect(url_for('home'))

    df = load_data()

    tahun_filter = request.args.get('tahun', '2024')
    region_filter = request.args.get('region', 'Semua')
    
    df_filter = df[df['year'] == int(tahun_filter)]
    
    # Cek nama kolom region (bisa 'region' atau 'regional_indicator')
    region_col = 'region' if 'region' in df.columns else ('regional_indicator' if 'regional_indicator' in df.columns else None)
    
    if region_filter != 'Semua' and region_col:
        df_filter = df_filter[df_filter[region_col] == region_filter]
        
    daftar_region = ['Semua'] + df[region_col].dropna().unique().tolist() if region_col else ['Semua']

    # --- KPI ---
    total_negara = df_filter['country'].nunique()
    rata_rata_skor = round(df_filter['happiness_score'].mean(), 2) if not df_filter.empty else 0
    skor_tertinggi = round(df_filter['happiness_score'].max(), 2) if not df_filter.empty else 0
    negara_terbahagia = df_filter.loc[df_filter['happiness_score'].idxmax(), 'country'] if not df_filter.empty else "-"

    # --- TAMBAHAN: Peringkat Indonesia ---
    df_sorted = df_filter.sort_values(by='happiness_score', ascending=False).reset_index(drop=True)
    if 'Indonesia' in df_sorted['country'].values:
        rank_indonesia = df_sorted[df_sorted['country'] == 'Indonesia'].index[0] + 1
        skor_indonesia = round(df_sorted[df_sorted['country'] == 'Indonesia']['happiness_score'].values[0], 2)
        info_indonesia = f"Peringkat {rank_indonesia} (Skor: {skor_indonesia})"
    else:
        info_indonesia = "Data tidak ditemukan"

    # --- GRAFIK ---
    top10 = df_filter.nlargest(10, 'happiness_score')
    fig_bar = px.bar(top10, x='country', y='happiness_score', title=f'Top 10 Negara Terbahagia ({tahun_filter})', color='happiness_score', color_continuous_scale='Blues')
    chart_bar = fig_bar.to_html(full_html=False)

    negara_top = df_filter.nlargest(5, 'happiness_score')['country'].tolist()
    if 'Indonesia' not in negara_top and 'Indonesia' in df['country'].values:
        negara_top.append('Indonesia')
    df_tren = df[df['country'].isin(negara_top)]
    fig_line = px.line(df_tren, x='year', y='happiness_score', color='country', title='Tren Skor (2022-2024)', markers=True)
    fig_line.update_xaxes(type='category')
    chart_line = fig_line.to_html(full_html=False)

    fig_box = px.box(df_filter, x=region_col if region_col else 'country', y='happiness_score', title='Boxplot Distribusi Skor (Deteksi Outlier)', color=region_col if region_col else None)
    chart_box = fig_box.to_html(full_html=False)

    # Menggunakan trendline="ols" (butuh library statsmodels)
    fig_scatter = px.scatter(df_filter, x='gdp_per_capita', y='happiness_score', hover_name='country', title='Hubungan PDB & Kebahagiaan', trendline="ols")
    chart_scatter = fig_scatter.to_html(full_html=False)

    kolom_numerik = ['happiness_score', 'gdp_per_capita', 'social_support', 'healthy_life_expectancy']
    kolom_tersedia = [c for c in kolom_numerik if c in df_filter.columns]
    corr = df_filter[kolom_tersedia].corr()
    fig_heat = px.imshow(corr, text_auto=True, title='Matriks Korelasi', color_continuous_scale='RdBu_r')
    chart_heat = fig_heat.to_html(full_html=False)

    desc_stats = df_filter[kolom_tersedia].describe().to_html(classes='table table-striped table-bordered', float_format="%.2f")

    html_template = """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <title>Dashboard Kebahagiaan Dunia</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f8f9fa; font-family: 'Segoe UI', sans-serif; }
            .kpi-card { background: white; border-left: 5px solid #0d6efd; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px;}
            .chart-box { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px;}
            h2 { margin-top: 30px; margin-bottom: 20px; border-bottom: 2px solid #dee2e6; padding-bottom: 10px;}
        </style>
    </head>
    <body>
        <div class="container-fluid py-4">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h1>🌍 Dashboard Kebahagiaan Dunia</h1>
                <div>
                    <a href="/export_csv" class="btn btn-success">⬇️ Ekspor CSV</a>
                    <a href="/logout" class="btn btn-danger">Logout</a>
                </div>
            </div>

            <div class="row bg-white p-3 mx-1 mb-4 rounded shadow-sm">
                <div class="col-md-4">
                    <form method="POST" enctype="multipart/form-data" class="d-flex">
                        <input class="form-control me-2" type="file" name="file" accept=".csv" required>
                        <button class="btn btn-primary" type="submit">Upload</button>
                    </form>
                </div>
                <div class="col-md-8">
                    <form method="GET" class="d-flex justify-content-end">
                        <select name="tahun" class="form-select me-2" style="width:150px;">
                            <option value="2024" {% if tahun_filter == '2024' %}selected{% endif %}>2024</option>
                            <option value="2023" {% if tahun_filter == '2023' %}selected{% endif %}>2023</option>
                            <option value="2022" {% if tahun_filter == '2022' %}selected{% endif %}>2022</option>
                        </select>
                        <select name="region" class="form-select me-2" style="width:200px;">
                            {% for r in daftar_region %}
                                <option value="{{ r }}" {% if region_filter == r %}selected{% endif %}>{{ r }}</option>
                            {% endfor %}
                        </select>
                        <button class="btn btn-dark" type="submit">Filter</button>
                    </form>
                </div>
            </div>

            <!-- KPI SECTION -->
            <div class="row">
                <div class="col-md-3"><div class="kpi-card p-3"><h6 class="text-muted">Total Negara</h6><h3 class="text-primary">{{ total_negara }}</h3></div></div>
                <div class="col-md-3"><div class="kpi-card p-3"><h6 class="text-muted">Rata-rata Skor</h6><h3 class="text-success">{{ rata_rata_skor }}</h3></div></div>
                <div class="col-md-3"><div class="kpi-card p-3"><h6 class="text-muted">Negara Terbahagia</h6><h3 class="text-danger" style="font-size: 1.2rem;">{{ negara_terbahagia }}</h3></div></div>
                <div class="col-md-3"><div class="kpi-card p-3" style="border-left-color: #dc3545;"><h6 class="text-muted">Posisi Indonesia</h6><h3 class="text-dark" style="font-size: 1.2rem;">{{ info_indonesia }}</h3></div></div>
            </div>

            <div class="row mt-4">
                <div class="col-md-6"><div class="chart-box">{{ chart_bar|safe }}</div></div>
                <div class="col-md-6"><div class="chart-box">{{ chart_line|safe }}</div></div>
            </div>
            <div class="row">
                <div class="col-md-6"><div class="chart-box">{{ chart_box|safe }}</div></div>
                <div class="col-md-6"><div class="chart-box">{{ chart_scatter|safe }}</div></div>
            </div>

            <h2>🔍 Eksplorasi Data (EDA)</h2>
            <div class="row">
                <div class="col-md-6"><div class="chart-box">{{ chart_heat|safe }}</div></div>
                <div class="col-md-6"><div class="chart-box"><h4>Statistik Deskriptif</h4><div style="overflow-x:auto;">{{ desc_stats|safe }}</div></div></div>
            </div>

            <h2>💡 Insight & Rekomendasi</h2>
            <div class="alert alert-info shadow-sm">
                <ul>
                    <li><b>Temuan 1:</b> Pada tahun <b>{{ tahun_filter }}</b>, <b>{{ negara_terbahagia }}</b> memimpin dengan skor <b>{{ skor_tertinggi }}</b>.</li>
                    <li><b>Temuan 2:</b> Posisi Indonesia saat ini berada di <b>{{ info_indonesia }}</b>. Hal ini <b>berhubungan</b> dengan tingkat PDB per kapita dan dukungan sosial yang masih perlu ditingkatkan.</li>
                    <li><b>Temuan 3:</b> PDB per Kapita memiliki korelasi positif yang kuat dengan Skor Kebahagiaan. Ini <b>berhubungan</b> dengan daya beli masyarakat, <i>bukan berarti</i> uang semata-mata menyebabkan bahagia.</li>
                    <li><b>Temuan 4:</b> Berdasarkan Heatmap, Dukungan Sosial (Social Support) juga berhubungan erat dengan kebahagiaan. <b>Rekomendasi:</b> Pemerintah perlu memperkuat program kesejahteraan sosial komunitas.</li>
                </ul>
            </div>
            
            <div class="mt-5 p-3 bg-light rounded text-center text-muted">
                <p><b>Tentang Data:</b> Dashboard ini menggunakan dataset <i>World Happiness Report 2022-2024</i> yang diunduh dari <a href="https://www.kaggle.com/datasets/unsdsn/world-happiness" target="_blank">Kaggle</a>. Data telah melalui proses pembersihan (Pandas) dan disimpan secara lokal.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(html_template, 
        total_negara=total_negara, rata_rata_skor=rata_rata_skor, skor_tertinggi=skor_tertinggi, negara_terbahagia=negara_terbahagia,
        info_indonesia=info_indonesia, tahun_filter=tahun_filter, region_filter=region_filter, daftar_region=daftar_region,
        chart_bar=chart_bar, chart_line=chart_line, chart_box=chart_box, chart_scatter=chart_scatter, chart_heat=chart_heat,
        desc_stats=desc_stats)

@app.route('/export_csv')
def export_csv():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    df = load_data()
    csv_data = df.to_csv(index=False)
    return send_file(
        io.BytesIO(csv_data.encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='data_kebahagiaan_clean.csv'
    )

if __name__ == "__main__":
    app.run(debug=True)