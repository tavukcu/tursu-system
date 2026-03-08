from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import *
from datetime import datetime, date, timedelta
from functools import wraps
import uuid

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Lütfen giriş yapın.'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Kullanici, int(user_id))

# ===================== YARDIMCI FONKSİYONLAR =====================

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'admin':
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def generate_lot_no():
    return f"LOT-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

def generate_fis_no():
    return f"FIS-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

def generate_transfer_no():
    return f"TRN-{datetime.now().strftime('%Y%m%d%H%M%S')}"

def generate_fatura_no(tip):
    prefix = 'SF' if tip == 'satis' else 'AF'
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

def generate_irsaliye_no():
    return f"IRS-{datetime.now().strftime('%Y%m%d%H%M%S')}"

# ===================== AUTH =====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        kullanici = Kullanici.query.filter_by(kullanici_adi=request.form['kullanici_adi']).first()
        if kullanici and kullanici.check_sifre(request.form['sifre']) and kullanici.aktif:
            login_user(kullanici)
            return redirect(url_for('dashboard'))
        flash('Geçersiz kullanıcı adı veya şifre.', 'danger')
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ===================== DASHBOARD =====================

@app.route('/')
@login_required
def dashboard():
    bugun = date.today()
    bugun_baslangic = datetime.combine(bugun, datetime.min.time())

    # Bugünkü satışlar
    bugun_satislar = Satis.query.filter(
        Satis.tarih >= bugun_baslangic, Satis.iptal == False
    ).all()
    bugun_ciro = sum(s.net_tutar for s in bugun_satislar)
    bugun_satis_adet = len(bugun_satislar)

    # Lokasyon bazlı satışlar
    lokasyonlar = Lokasyon.query.filter_by(aktif=True).all()
    lokasyon_satirlar = []
    for lok in lokasyonlar:
        lok_satislar = [s for s in bugun_satislar if s.lokasyon_id == lok.id]
        lok_ciro = sum(s.net_tutar for s in lok_satislar)
        lokasyon_satirlar.append({'lokasyon': lok, 'ciro': lok_ciro, 'adet': len(lok_satislar)})

    # Aktif üretim emirleri
    aktif_uretimler = UretimEmri.query.filter(
        UretimEmri.durum.in_(['beklemede', 'uretimde'])
    ).count()

    # Kritik stok (hammadde)
    kritik_hammadde = db.session.query(Hammadde, HammaddeStok).join(
        HammaddeStok, Hammadde.id == HammaddeStok.hammadde_id
    ).filter(
        HammaddeStok.miktar <= Hammadde.min_stok, Hammadde.min_stok > 0
    ).all()

    # SKT yaklaşan ürünler (30 gün içinde)
    skt_yaklasan = UrunStok.query.filter(
        UrunStok.skt <= bugun + timedelta(days=30),
        UrunStok.skt >= bugun,
        UrunStok.miktar > 0
    ).all()

    # Son 7 gün satış grafiği
    satis_grafik = []
    for i in range(6, -1, -1):
        gun = bugun - timedelta(days=i)
        gun_bas = datetime.combine(gun, datetime.min.time())
        gun_son = datetime.combine(gun, datetime.max.time())
        gun_ciro = db.session.query(db.func.coalesce(db.func.sum(Satis.net_tutar), 0)).filter(
            Satis.tarih.between(gun_bas, gun_son), Satis.iptal == False
        ).scalar()
        satis_grafik.append({'gun': gun.strftime('%d/%m'), 'ciro': float(gun_ciro)})

    return render_template('dashboard.html',
        bugun_ciro=bugun_ciro,
        bugun_satis_adet=bugun_satis_adet,
        lokasyon_satirlar=lokasyon_satirlar,
        aktif_uretimler=aktif_uretimler,
        kritik_hammadde=kritik_hammadde,
        skt_yaklasan=skt_yaklasan,
        satis_grafik=satis_grafik
    )

# ===================== HAMMADDE =====================

@app.route('/hammadde')
@login_required
def hammadde_listesi():
    hammaddeler = Hammadde.query.filter_by(aktif=True).all()
    return render_template('hammadde/liste.html', hammaddeler=hammaddeler)

@app.route('/hammadde/ekle', methods=['GET', 'POST'])
@login_required
def hammadde_ekle():
    if request.method == 'POST':
        h = Hammadde(
            ad=request.form['ad'],
            birim=request.form['birim'],
            kategori=request.form['kategori'],
            min_stok=float(request.form.get('min_stok', 0))
        )
        db.session.add(h)
        db.session.commit()
        flash('Hammadde eklendi.', 'success')
        return redirect(url_for('hammadde_listesi'))
    return render_template('hammadde/ekle.html')

@app.route('/hammadde/alim', methods=['GET', 'POST'])
@login_required
def hammadde_alim():
    if request.method == 'POST':
        miktar = float(request.form['miktar'])
        birim_fiyat = float(request.form['birim_fiyat'])
        toplam = miktar * birim_fiyat
        tedarikci_id = int(request.form['tedarikci_id'])
        hammadde_id = int(request.form['hammadde_id'])
        lokasyon_id = int(request.form['lokasyon_id'])

        alim = HammaddeAlim(
            tedarikci_id=tedarikci_id,
            hammadde_id=hammadde_id,
            lokasyon_id=lokasyon_id,
            miktar=miktar,
            birim_fiyat=birim_fiyat,
            toplam_tutar=toplam,
            aciklama=request.form.get('aciklama', '')
        )
        db.session.add(alim)

        # Stok güncelle
        stok = HammaddeStok.query.filter_by(hammadde_id=hammadde_id, lokasyon_id=lokasyon_id).first()
        if stok:
            stok.miktar += miktar
        else:
            stok = HammaddeStok(hammadde_id=hammadde_id, lokasyon_id=lokasyon_id, miktar=miktar)
            db.session.add(stok)

        # Tedarikçi bakiye güncelle (borcumuz arttı)
        tedarikci = db.session.get(Tedarikci, tedarikci_id)
        tedarikci.bakiye += toplam

        # Cari hareket
        hareket = CariHareket(
            tedarikci_id=tedarikci_id,
            hareket_tipi='borc',
            tutar=toplam,
            aciklama=f"Hammadde alımı - {alim.hammadde.ad if alim.hammadde else ''}"
        )
        db.session.add(hareket)
        db.session.commit()
        flash(f'{miktar} {alim.hammadde.birim} hammadde alındı. Toplam: ₺{toplam:,.2f}', 'success')
        return redirect(url_for('hammadde_listesi'))

    tedarikciler = Tedarikci.query.filter_by(aktif=True).all()
    hammaddeler = Hammadde.query.filter_by(aktif=True).all()
    lokasyonlar = Lokasyon.query.filter_by(aktif=True, tip='fabrika').all()
    return render_template('hammadde/alim.html', tedarikciler=tedarikciler, hammaddeler=hammaddeler, lokasyonlar=lokasyonlar)

@app.route('/hammadde/stok')
@login_required
def hammadde_stok():
    stoklar = db.session.query(Hammadde, HammaddeStok, Lokasyon).join(
        HammaddeStok, Hammadde.id == HammaddeStok.hammadde_id
    ).join(
        Lokasyon, HammaddeStok.lokasyon_id == Lokasyon.id
    ).filter(Hammadde.aktif == True).all()
    return render_template('hammadde/stok.html', stoklar=stoklar)

# ===================== TEDARİKÇİ =====================

@app.route('/tedarikci')
@login_required
def tedarikci_listesi():
    tedarikciler = Tedarikci.query.filter_by(aktif=True).all()
    return render_template('cari/tedarikci_liste.html', tedarikciler=tedarikciler)

@app.route('/tedarikci/ekle', methods=['GET', 'POST'])
@login_required
def tedarikci_ekle():
    if request.method == 'POST':
        t = Tedarikci(
            ad_soyad=request.form['ad_soyad'],
            firma_adi=request.form.get('firma_adi', ''),
            telefon=request.form.get('telefon', ''),
            adres=request.form.get('adres', ''),
            vergi_no=request.form.get('vergi_no', ''),
            tc_no=request.form.get('tc_no', '')
        )
        db.session.add(t)
        db.session.commit()
        flash('Tedarikçi eklendi.', 'success')
        return redirect(url_for('tedarikci_listesi'))
    return render_template('cari/tedarikci_ekle.html')

@app.route('/tedarikci/<int:id>/odeme', methods=['POST'])
@login_required
def tedarikci_odeme(id):
    tedarikci = db.session.get(Tedarikci, id)
    tutar = float(request.form['tutar'])
    tedarikci.bakiye -= tutar
    hareket = CariHareket(
        tedarikci_id=id, hareket_tipi='odeme', tutar=tutar,
        aciklama=request.form.get('aciklama', 'Ödeme')
    )
    db.session.add(hareket)
    db.session.commit()
    flash(f'₺{tutar:,.2f} ödeme kaydedildi.', 'success')
    return redirect(url_for('tedarikci_listesi'))

# ===================== ÜRÜN =====================

@app.route('/urun')
@login_required
def urun_listesi():
    urunler = Urun.query.filter_by(aktif=True).all()
    return render_template('urun/liste.html', urunler=urunler)

@app.route('/urun/ekle', methods=['GET', 'POST'])
@login_required
def urun_ekle():
    if request.method == 'POST':
        u = Urun(
            ad=request.form['ad'],
            barkod=request.form.get('barkod', ''),
            kategori=request.form.get('kategori', ''),
            birim=request.form.get('birim', 'adet'),
            ambalaj_tipi=request.form.get('ambalaj_tipi', ''),
            raf_omru_gun=int(request.form.get('raf_omru_gun', 365)),
            kdv_orani=float(request.form.get('kdv_orani', 10))
        )
        db.session.add(u)
        db.session.flush()

        # Fiyatlar
        perakende = request.form.get('perakende_fiyat')
        if perakende:
            db.session.add(UrunFiyat(urun_id=u.id, fiyat_tipi='perakende', fiyat=float(perakende)))
        toptan = request.form.get('toptan_fiyat')
        if toptan:
            db.session.add(UrunFiyat(urun_id=u.id, fiyat_tipi='toptan', fiyat=float(toptan)))

        db.session.commit()
        flash('Ürün eklendi.', 'success')
        return redirect(url_for('urun_listesi'))
    return render_template('urun/ekle.html')

@app.route('/urun/<int:id>/duzenle', methods=['GET', 'POST'])
@login_required
def urun_duzenle(id):
    urun = db.session.get(Urun, id)
    if request.method == 'POST':
        urun.ad = request.form['ad']
        urun.barkod = request.form.get('barkod', '')
        urun.kategori = request.form.get('kategori', '')
        urun.birim = request.form.get('birim', 'adet')
        urun.ambalaj_tipi = request.form.get('ambalaj_tipi', '')
        urun.raf_omru_gun = int(request.form.get('raf_omru_gun', 365))
        urun.kdv_orani = float(request.form.get('kdv_orani', 10))

        # Fiyat güncelle
        for fiyat_tipi in ['perakende', 'toptan']:
            fiyat_val = request.form.get(f'{fiyat_tipi}_fiyat')
            if fiyat_val:
                fiyat = UrunFiyat.query.filter_by(urun_id=id, fiyat_tipi=fiyat_tipi).first()
                if fiyat:
                    fiyat.fiyat = float(fiyat_val)
                else:
                    db.session.add(UrunFiyat(urun_id=id, fiyat_tipi=fiyat_tipi, fiyat=float(fiyat_val)))

        db.session.commit()
        flash('Ürün güncellendi.', 'success')
        return redirect(url_for('urun_listesi'))

    perakende_fiyat = UrunFiyat.query.filter_by(urun_id=id, fiyat_tipi='perakende').first()
    toptan_fiyat = UrunFiyat.query.filter_by(urun_id=id, fiyat_tipi='toptan').first()
    return render_template('urun/duzenle.html', urun=urun,
        perakende_fiyat=perakende_fiyat.fiyat if perakende_fiyat else '',
        toptan_fiyat=toptan_fiyat.fiyat if toptan_fiyat else '')

# ===================== REÇETE =====================

@app.route('/urun/<int:urun_id>/recete', methods=['GET', 'POST'])
@login_required
def recete_yonet(urun_id):
    urun = db.session.get(Urun, urun_id)
    if request.method == 'POST':
        recete = Recete.query.filter_by(urun_id=urun_id).first()
        if not recete:
            recete = Recete(urun_id=urun_id, ad=f"{urun.ad} Reçetesi")
            db.session.add(recete)
            db.session.flush()
        else:
            ReceteKalem.query.filter_by(recete_id=recete.id).delete()

        recete.uretim_suresi_dk = int(request.form.get('uretim_suresi_dk', 0))
        recete.aciklama = request.form.get('aciklama', '')

        hammadde_ids = request.form.getlist('hammadde_id[]')
        miktarlar = request.form.getlist('miktar[]')
        for h_id, mik in zip(hammadde_ids, miktarlar):
            if h_id and mik:
                kalem = ReceteKalem(recete_id=recete.id, hammadde_id=int(h_id), miktar=float(mik))
                db.session.add(kalem)

        db.session.commit()
        flash('Reçete kaydedildi.', 'success')
        return redirect(url_for('urun_listesi'))

    recete = Recete.query.filter_by(urun_id=urun_id).first()
    hammaddeler = Hammadde.query.filter_by(aktif=True).all()
    return render_template('urun/recete.html', urun=urun, recete=recete, hammaddeler=hammaddeler)

# ===================== ÜRETİM =====================

@app.route('/uretim')
@login_required
def uretim_listesi():
    emirler = UretimEmri.query.order_by(UretimEmri.olusturma_tarihi.desc()).limit(50).all()
    return render_template('uretim/liste.html', emirler=emirler)

@app.route('/uretim/yeni', methods=['GET', 'POST'])
@login_required
def uretim_yeni():
    if request.method == 'POST':
        urun_id = int(request.form['urun_id'])
        hedef_miktar = float(request.form['hedef_miktar'])
        urun = db.session.get(Urun, urun_id)
        lokasyon_id = int(request.form['lokasyon_id'])

        lot_no = generate_lot_no()
        skt = date.today() + timedelta(days=urun.raf_omru_gun)

        emir = UretimEmri(
            urun_id=urun_id, lokasyon_id=lokasyon_id, hedef_miktar=hedef_miktar,
            lot_no=lot_no, skt=skt, olusturan_id=current_user.id,
            aciklama=request.form.get('aciklama', '')
        )
        db.session.add(emir)
        db.session.flush()

        # Reçeteden girdileri hesapla
        recete = Recete.query.filter_by(urun_id=urun_id).first()
        if recete:
            for kalem in recete.kalemleri:
                girdi = UretimGirdi(
                    uretim_emri_id=emir.id,
                    hammadde_id=kalem.hammadde_id,
                    planlanan_miktar=kalem.miktar * hedef_miktar
                )
                db.session.add(girdi)

        db.session.commit()
        flash(f'Üretim emri oluşturuldu. Lot No: {lot_no}', 'success')
        return redirect(url_for('uretim_detay', id=emir.id))

    urunler = Urun.query.filter_by(aktif=True).all()
    lokasyonlar = Lokasyon.query.filter_by(aktif=True, tip='fabrika').all()
    return render_template('uretim/yeni.html', urunler=urunler, lokasyonlar=lokasyonlar)

@app.route('/uretim/<int:id>')
@login_required
def uretim_detay(id):
    emir = db.session.get(UretimEmri, id)
    return render_template('uretim/detay.html', emir=emir)

@app.route('/uretim/<int:id>/baslat', methods=['POST'])
@login_required
def uretim_baslat(id):
    emir = db.session.get(UretimEmri, id)

    # Hammadde stok kontrolü
    yeterli = True
    for girdi in emir.girdiler:
        stok = HammaddeStok.query.filter_by(
            hammadde_id=girdi.hammadde_id, lokasyon_id=emir.lokasyon_id
        ).first()
        if not stok or stok.miktar < girdi.planlanan_miktar:
            yeterli = False
            flash(f'{girdi.hammadde.ad} stoku yetersiz!', 'danger')

    if yeterli:
        emir.durum = 'uretimde'
        emir.baslama_zamani = datetime.utcnow()

        # Hammadde düş
        for girdi in emir.girdiler:
            stok = HammaddeStok.query.filter_by(
                hammadde_id=girdi.hammadde_id, lokasyon_id=emir.lokasyon_id
            ).first()
            stok.miktar -= girdi.planlanan_miktar
            girdi.kullanilan_miktar = girdi.planlanan_miktar

        db.session.commit()
        flash('Üretim başlatıldı, hammaddeler stoktan düşüldü.', 'success')

    return redirect(url_for('uretim_detay', id=id))

@app.route('/uretim/<int:id>/tamamla', methods=['POST'])
@login_required
def uretim_tamamla(id):
    emir = db.session.get(UretimEmri, id)
    uretilen = float(request.form.get('uretilen_miktar', emir.hedef_miktar))

    emir.durum = 'tamamlandi'
    emir.uretilen_miktar = uretilen
    emir.bitis_zamani = datetime.utcnow()

    # Mamül stoka ekle
    stok = UrunStok.query.filter_by(
        urun_id=emir.urun_id, lokasyon_id=emir.lokasyon_id, lot_no=emir.lot_no
    ).first()
    if stok:
        stok.miktar += uretilen
    else:
        stok = UrunStok(
            urun_id=emir.urun_id, lokasyon_id=emir.lokasyon_id,
            miktar=uretilen, lot_no=emir.lot_no, skt=emir.skt
        )
        db.session.add(stok)

    db.session.commit()
    flash(f'Üretim tamamlandı. {uretilen} adet stoka eklendi.', 'success')
    return redirect(url_for('uretim_detay', id=id))

@app.route('/uretim/<int:id>/kalite', methods=['POST'])
@login_required
def kalite_kontrol_ekle(id):
    kk = KaliteKontrol(
        uretim_emri_id=id,
        kontrol_eden=request.form.get('kontrol_eden', current_user.ad_soyad),
        ph_degeri=float(request.form['ph_degeri']) if request.form.get('ph_degeri') else None,
        tuz_orani=float(request.form['tuz_orani']) if request.form.get('tuz_orani') else None,
        gorunum=request.form.get('gorunum', ''),
        tat=request.form.get('tat', ''),
        sonuc=request.form.get('sonuc', 'beklemede'),
        notlar=request.form.get('notlar', '')
    )
    db.session.add(kk)
    db.session.commit()
    flash('Kalite kontrol kaydı eklendi.', 'success')
    return redirect(url_for('uretim_detay', id=id))

# ===================== STOK & TRANSFER =====================

@app.route('/stok')
@login_required
def stok_listesi():
    stoklar = db.session.query(Urun, UrunStok, Lokasyon).join(
        UrunStok, Urun.id == UrunStok.urun_id
    ).join(
        Lokasyon, UrunStok.lokasyon_id == Lokasyon.id
    ).filter(UrunStok.miktar > 0).order_by(Urun.ad).all()
    return render_template('stok/liste.html', stoklar=stoklar)

@app.route('/stok/transfer', methods=['GET', 'POST'])
@login_required
def stok_transfer():
    if request.method == 'POST':
        transfer = StokTransfer(
            kaynak_lokasyon_id=int(request.form['kaynak_id']),
            hedef_lokasyon_id=int(request.form['hedef_id']),
            transfer_no=generate_transfer_no(),
            olusturan_id=current_user.id,
            aciklama=request.form.get('aciklama', '')
        )
        db.session.add(transfer)
        db.session.flush()

        urun_ids = request.form.getlist('urun_id[]')
        miktarlar = request.form.getlist('miktar[]')
        lot_nolar = request.form.getlist('lot_no[]')

        for u_id, mik, lot in zip(urun_ids, miktarlar, lot_nolar):
            if u_id and mik:
                kalem = StokTransferKalem(
                    transfer_id=transfer.id, urun_id=int(u_id),
                    miktar=float(mik), lot_no=lot
                )
                db.session.add(kalem)

        db.session.commit()
        flash(f'Transfer oluşturuldu: {transfer.transfer_no}', 'success')
        return redirect(url_for('stok_transfer_listesi'))

    lokasyonlar = Lokasyon.query.filter_by(aktif=True).all()
    urunler = Urun.query.filter_by(aktif=True).all()
    return render_template('stok/transfer.html', lokasyonlar=lokasyonlar, urunler=urunler)

@app.route('/stok/transferler')
@login_required
def stok_transfer_listesi():
    transferler = StokTransfer.query.order_by(StokTransfer.tarih.desc()).limit(50).all()
    return render_template('stok/transfer_liste.html', transferler=transferler)

@app.route('/stok/transfer/<int:id>/onayla', methods=['POST'])
@login_required
def stok_transfer_onayla(id):
    transfer = db.session.get(StokTransfer, id)
    hata = False

    for kalem in transfer.kalemler:
        # Kaynaktan düş
        kaynak_stok = UrunStok.query.filter_by(
            urun_id=kalem.urun_id, lokasyon_id=transfer.kaynak_lokasyon_id, lot_no=kalem.lot_no
        ).first()
        if not kaynak_stok or kaynak_stok.miktar < kalem.miktar:
            flash(f'{kalem.urun.ad} kaynakta yetersiz stok!', 'danger')
            hata = True
            continue

        kaynak_stok.miktar -= kalem.miktar

        # Hedefe ekle
        hedef_stok = UrunStok.query.filter_by(
            urun_id=kalem.urun_id, lokasyon_id=transfer.hedef_lokasyon_id, lot_no=kalem.lot_no
        ).first()
        if hedef_stok:
            hedef_stok.miktar += kalem.miktar
        else:
            skt = kaynak_stok.skt if kaynak_stok else None
            hedef_stok = UrunStok(
                urun_id=kalem.urun_id, lokasyon_id=transfer.hedef_lokasyon_id,
                miktar=kalem.miktar, lot_no=kalem.lot_no, skt=skt
            )
            db.session.add(hedef_stok)

    if not hata:
        transfer.durum = 'teslim_edildi'
        transfer.teslim_tarihi = datetime.utcnow()
        db.session.commit()
        flash('Transfer onaylandı, stoklar güncellendi.', 'success')

    return redirect(url_for('stok_transfer_listesi'))

# ===================== MÜŞTERİ =====================

@app.route('/musteri')
@login_required
def musteri_listesi():
    musteriler = Musteri.query.filter_by(aktif=True).all()
    return render_template('cari/musteri_liste.html', musteriler=musteriler)

@app.route('/musteri/ekle', methods=['GET', 'POST'])
@login_required
def musteri_ekle():
    if request.method == 'POST':
        m = Musteri(
            ad_soyad=request.form['ad_soyad'],
            firma_adi=request.form.get('firma_adi', ''),
            tip=request.form.get('tip', 'perakende'),
            telefon=request.form.get('telefon', ''),
            adres=request.form.get('adres', ''),
            vergi_no=request.form.get('vergi_no', ''),
            tc_no=request.form.get('tc_no', '')
        )
        db.session.add(m)
        db.session.commit()
        flash('Müşteri eklendi.', 'success')
        return redirect(url_for('musteri_listesi'))
    return render_template('cari/musteri_ekle.html')

# ===================== SATIŞ (POS) =====================

@app.route('/satis')
@login_required
def satis_ekrani():
    lokasyon_id = current_user.lokasyon_id or request.args.get('lokasyon_id')
    urunler = Urun.query.filter_by(aktif=True).all()
    urun_fiyatlar = {}
    for u in urunler:
        fiyat = UrunFiyat.query.filter_by(urun_id=u.id, fiyat_tipi='perakende').first()
        urun_fiyatlar[u.id] = fiyat.fiyat if fiyat else 0
    musteriler = Musteri.query.filter_by(aktif=True).all()
    return render_template('satis/pos.html', urunler=urunler, urun_fiyatlar=urun_fiyatlar,
                         musteriler=musteriler, lokasyon_id=lokasyon_id)

@app.route('/api/barkod/<barkod>')
@login_required
def barkod_sorgula(barkod):
    urun = Urun.query.filter_by(barkod=barkod, aktif=True).first()
    if not urun:
        return jsonify({'error': 'Ürün bulunamadı'}), 404
    fiyat = UrunFiyat.query.filter_by(urun_id=urun.id, fiyat_tipi='perakende').first()
    return jsonify({
        'id': urun.id, 'ad': urun.ad, 'barkod': urun.barkod,
        'fiyat': fiyat.fiyat if fiyat else 0, 'kdv_orani': urun.kdv_orani,
        'birim': urun.birim
    })

@app.route('/api/satis', methods=['POST'])
@login_required
def satis_kaydet():
    data = request.get_json()
    lokasyon_id = data.get('lokasyon_id') or current_user.lokasyon_id
    if not lokasyon_id:
        return jsonify({'error': 'Lokasyon seçiniz'}), 400

    fis_no = generate_fis_no()
    satis = Satis(
        fis_no=fis_no,
        musteri_id=data.get('musteri_id'),
        lokasyon_id=lokasyon_id,
        kasiyer_id=current_user.id,
        satis_tipi=data.get('satis_tipi', 'perakende'),
        odeme_tipi=data.get('odeme_tipi', 'nakit'),
        toplam_tutar=0, kdv_tutar=0, net_tutar=0,
        iskonto_tutar=float(data.get('iskonto', 0))
    )
    db.session.add(satis)
    db.session.flush()

    toplam = 0
    kdv_toplam = 0
    for item in data.get('kalemler', []):
        miktar = float(item['miktar'])
        birim_fiyat = float(item['birim_fiyat'])
        kdv_orani = float(item.get('kdv_orani', 10))
        kalem_toplam = miktar * birim_fiyat
        kalem_kdv = kalem_toplam * kdv_orani / (100 + kdv_orani)

        kalem = SatisKalem(
            satis_id=satis.id, urun_id=int(item['urun_id']),
            miktar=miktar, birim_fiyat=birim_fiyat,
            kdv_orani=kdv_orani, toplam=kalem_toplam
        )
        db.session.add(kalem)

        # Stoktan düş
        stok = UrunStok.query.filter(
            UrunStok.urun_id == int(item['urun_id']),
            UrunStok.lokasyon_id == lokasyon_id,
            UrunStok.miktar > 0
        ).first()
        if stok:
            stok.miktar = max(0, stok.miktar - miktar)

        toplam += kalem_toplam
        kdv_toplam += kalem_kdv

    satis.toplam_tutar = toplam
    satis.kdv_tutar = kdv_toplam
    satis.net_tutar = toplam - satis.iskonto_tutar

    # Veresiye ise cari hareket
    if satis.odeme_tipi == 'veresiye' and satis.musteri_id:
        musteri = db.session.get(Musteri, satis.musteri_id)
        musteri.bakiye += satis.net_tutar
        hareket = CariHareket(
            musteri_id=satis.musteri_id, hareket_tipi='borc',
            tutar=satis.net_tutar, belge_no=fis_no, aciklama='Veresiye satış'
        )
        db.session.add(hareket)

    db.session.commit()
    return jsonify({'success': True, 'fis_no': fis_no, 'toplam': satis.net_tutar})

@app.route('/satis/gecmis')
@login_required
def satis_gecmis():
    satislar = Satis.query.order_by(Satis.tarih.desc()).limit(100).all()
    return render_template('satis/gecmis.html', satislar=satislar)

# ===================== FATURA =====================

@app.route('/fatura')
@login_required
def fatura_listesi():
    faturalar = Fatura.query.order_by(Fatura.tarih.desc()).limit(50).all()
    return render_template('fatura/liste.html', faturalar=faturalar)

@app.route('/fatura/yeni', methods=['GET', 'POST'])
@login_required
def fatura_yeni():
    if request.method == 'POST':
        fatura_tipi = request.form['fatura_tipi']
        fatura = Fatura(
            fatura_no=generate_fatura_no(fatura_tipi),
            fatura_tipi=fatura_tipi,
            musteri_id=int(request.form['musteri_id']) if request.form.get('musteri_id') else None,
            tedarikci_id=int(request.form['tedarikci_id']) if request.form.get('tedarikci_id') else None,
            lokasyon_id=int(request.form.get('lokasyon_id')) if request.form.get('lokasyon_id') else None,
            vade_tarihi=datetime.strptime(request.form['vade_tarihi'], '%Y-%m-%d').date() if request.form.get('vade_tarihi') else None,
            aciklama=request.form.get('aciklama', '')
        )
        db.session.add(fatura)
        db.session.flush()

        urun_ids = request.form.getlist('urun_id[]')
        miktarlar = request.form.getlist('miktar[]')
        fiyatlar = request.form.getlist('birim_fiyat[]')
        kdv_oranlari = request.form.getlist('kdv_orani[]')

        ara_toplam = 0
        kdv_toplam = 0
        for u_id, mik, fiy, kdv in zip(urun_ids, miktarlar, fiyatlar, kdv_oranlari):
            if u_id and mik and fiy:
                kalem_toplam = float(mik) * float(fiy)
                kalem_kdv = kalem_toplam * float(kdv) / 100
                kalem = FaturaKalem(
                    fatura_id=fatura.id, urun_id=int(u_id),
                    miktar=float(mik), birim_fiyat=float(fiy),
                    kdv_orani=float(kdv), toplam=kalem_toplam + kalem_kdv
                )
                db.session.add(kalem)
                ara_toplam += kalem_toplam
                kdv_toplam += kalem_kdv

        fatura.ara_toplam = ara_toplam
        fatura.kdv_toplam = kdv_toplam
        fatura.toplam_tutar = ara_toplam + kdv_toplam

        db.session.commit()
        flash(f'Fatura oluşturuldu: {fatura.fatura_no}', 'success')
        return redirect(url_for('fatura_listesi'))

    musteriler = Musteri.query.filter_by(aktif=True).all()
    tedarikciler = Tedarikci.query.filter_by(aktif=True).all()
    urunler = Urun.query.filter_by(aktif=True).all()
    lokasyonlar = Lokasyon.query.filter_by(aktif=True).all()
    return render_template('fatura/yeni.html', musteriler=musteriler,
        tedarikciler=tedarikciler, urunler=urunler, lokasyonlar=lokasyonlar)

@app.route('/fatura/<int:id>/onayla', methods=['POST'])
@login_required
def fatura_onayla(id):
    fatura = db.session.get(Fatura, id)
    fatura.durum = 'onaylandi'

    # Cari hareket oluştur
    if fatura.fatura_tipi == 'satis' and fatura.musteri_id:
        musteri = db.session.get(Musteri, fatura.musteri_id)
        musteri.bakiye += fatura.toplam_tutar
        hareket = CariHareket(
            musteri_id=fatura.musteri_id, hareket_tipi='borc',
            tutar=fatura.toplam_tutar, belge_no=fatura.fatura_no, aciklama='Satış faturası'
        )
        db.session.add(hareket)

    db.session.commit()
    flash('Fatura onaylandı.', 'success')
    return redirect(url_for('fatura_listesi'))

# ===================== İRSALİYE =====================

@app.route('/irsaliye')
@login_required
def irsaliye_listesi():
    irsaliyeler = Irsaliye.query.order_by(Irsaliye.tarih.desc()).limit(50).all()
    return render_template('fatura/irsaliye_liste.html', irsaliyeler=irsaliyeler)

@app.route('/irsaliye/yeni', methods=['GET', 'POST'])
@login_required
def irsaliye_yeni():
    if request.method == 'POST':
        irsaliye = Irsaliye(
            irsaliye_no=generate_irsaliye_no(),
            irsaliye_tipi=request.form['irsaliye_tipi'],
            musteri_id=int(request.form['musteri_id']) if request.form.get('musteri_id') else None,
            kaynak_lokasyon_id=int(request.form['kaynak_id']),
            hedef_lokasyon_id=int(request.form['hedef_id']) if request.form.get('hedef_id') else None,
            plaka=request.form.get('plaka', ''),
            surucu=request.form.get('surucu', ''),
            aciklama=request.form.get('aciklama', '')
        )
        db.session.add(irsaliye)
        db.session.flush()

        urun_ids = request.form.getlist('urun_id[]')
        miktarlar = request.form.getlist('miktar[]')
        lot_nolar = request.form.getlist('lot_no[]')

        for u_id, mik, lot in zip(urun_ids, miktarlar, lot_nolar):
            if u_id and mik:
                kalem = IrsaliyeKalem(
                    irsaliye_id=irsaliye.id, urun_id=int(u_id),
                    miktar=float(mik), lot_no=lot
                )
                db.session.add(kalem)

        db.session.commit()
        flash(f'İrsaliye oluşturuldu: {irsaliye.irsaliye_no}', 'success')
        return redirect(url_for('irsaliye_listesi'))

    musteriler = Musteri.query.filter_by(aktif=True).all()
    lokasyonlar = Lokasyon.query.filter_by(aktif=True).all()
    urunler = Urun.query.filter_by(aktif=True).all()
    return render_template('fatura/irsaliye_yeni.html', musteriler=musteriler,
        lokasyonlar=lokasyonlar, urunler=urunler)

# ===================== RAPORLAR =====================

@app.route('/rapor')
@login_required
def rapor_ana():
    return render_template('rapor/ana.html')

@app.route('/rapor/satis')
@login_required
def rapor_satis():
    baslangic = request.args.get('baslangic', (date.today() - timedelta(days=30)).isoformat())
    bitis = request.args.get('bitis', date.today().isoformat())
    lokasyon_id = request.args.get('lokasyon_id')

    query = Satis.query.filter(
        Satis.tarih >= baslangic, Satis.tarih <= bitis + ' 23:59:59', Satis.iptal == False
    )
    if lokasyon_id:
        query = query.filter(Satis.lokasyon_id == int(lokasyon_id))

    satislar = query.order_by(Satis.tarih.desc()).all()
    toplam_ciro = sum(s.net_tutar for s in satislar)
    toplam_kdv = sum(s.kdv_tutar for s in satislar)

    lokasyonlar = Lokasyon.query.filter_by(aktif=True).all()
    return render_template('rapor/satis.html', satislar=satislar, toplam_ciro=toplam_ciro,
        toplam_kdv=toplam_kdv, lokasyonlar=lokasyonlar, baslangic=baslangic, bitis=bitis)

@app.route('/rapor/uretim')
@login_required
def rapor_uretim():
    baslangic = request.args.get('baslangic', (date.today() - timedelta(days=30)).isoformat())
    bitis = request.args.get('bitis', date.today().isoformat())

    emirler = UretimEmri.query.filter(
        UretimEmri.uretim_tarihi >= baslangic, UretimEmri.uretim_tarihi <= bitis
    ).order_by(UretimEmri.uretim_tarihi.desc()).all()

    return render_template('rapor/uretim.html', emirler=emirler, baslangic=baslangic, bitis=bitis)

@app.route('/rapor/stok')
@login_required
def rapor_stok():
    lokasyon_id = request.args.get('lokasyon_id')
    query = db.session.query(Urun, UrunStok, Lokasyon).join(
        UrunStok, Urun.id == UrunStok.urun_id
    ).join(Lokasyon, UrunStok.lokasyon_id == Lokasyon.id)
    if lokasyon_id:
        query = query.filter(UrunStok.lokasyon_id == int(lokasyon_id))
    stoklar = query.order_by(Urun.ad).all()
    lokasyonlar = Lokasyon.query.filter_by(aktif=True).all()
    return render_template('rapor/stok.html', stoklar=stoklar, lokasyonlar=lokasyonlar)

@app.route('/rapor/cari')
@login_required
def rapor_cari():
    musteriler = Musteri.query.filter(Musteri.bakiye != 0).all()
    tedarikciler = Tedarikci.query.filter(Tedarikci.bakiye != 0).all()
    return render_template('rapor/cari.html', musteriler=musteriler, tedarikciler=tedarikciler)

# ===================== KULLANICI YÖNETİMİ =====================

@app.route('/kullanici')
@login_required
@admin_required
def kullanici_listesi():
    kullanicilar = Kullanici.query.all()
    return render_template('auth/kullanici_liste.html', kullanicilar=kullanicilar)

@app.route('/kullanici/ekle', methods=['GET', 'POST'])
@login_required
@admin_required
def kullanici_ekle():
    if request.method == 'POST':
        k = Kullanici(
            kullanici_adi=request.form['kullanici_adi'],
            ad_soyad=request.form['ad_soyad'],
            rol=request.form['rol'],
            lokasyon_id=int(request.form['lokasyon_id']) if request.form.get('lokasyon_id') else None
        )
        k.set_sifre(request.form['sifre'])
        db.session.add(k)
        db.session.commit()
        flash('Kullanıcı eklendi.', 'success')
        return redirect(url_for('kullanici_listesi'))
    lokasyonlar = Lokasyon.query.filter_by(aktif=True).all()
    return render_template('auth/kullanici_ekle.html', lokasyonlar=lokasyonlar)

# ===================== LOKASYON YÖNETİMİ =====================

@app.route('/lokasyon')
@login_required
@admin_required
def lokasyon_listesi():
    lokasyonlar = Lokasyon.query.all()
    return render_template('auth/lokasyon_liste.html', lokasyonlar=lokasyonlar)

@app.route('/lokasyon/ekle', methods=['GET', 'POST'])
@login_required
@admin_required
def lokasyon_ekle():
    if request.method == 'POST':
        l = Lokasyon(
            ad=request.form['ad'],
            tip=request.form['tip'],
            adres=request.form.get('adres', ''),
            telefon=request.form.get('telefon', '')
        )
        db.session.add(l)
        db.session.commit()
        flash('Lokasyon eklendi.', 'success')
        return redirect(url_for('lokasyon_listesi'))
    return render_template('auth/lokasyon_ekle.html')

# ===================== INIT DB =====================

@app.route('/init-db')
def init_db():
    db.create_all()
    # Varsayılan admin kontrolü
    admin = Kullanici.query.filter_by(kullanici_adi='admin').first()
    if not admin:
        admin = Kullanici(kullanici_adi='admin', ad_soyad='Sistem Yöneticisi', rol='admin')
        admin.set_sifre('admin123')
        db.session.add(admin)

        # Varsayılan lokasyonlar
        fabrika = Lokasyon(ad='Turşu Fabrikası', tip='fabrika', adres='Fabrika Adresi')
        magaza1 = Lokasyon(ad='Mağaza 1', tip='magaza', adres='Mağaza 1 Adresi')
        magaza2 = Lokasyon(ad='Mağaza 2', tip='magaza', adres='Mağaza 2 Adresi')
        db.session.add_all([fabrika, magaza1, magaza2])
        db.session.commit()

    return jsonify({'status': 'ok', 'message': 'Veritabanı oluşturuldu.'})

# ===================== RUN =====================

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
