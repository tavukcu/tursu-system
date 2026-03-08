from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ===================== KULLANICI & LOKASYON =====================

class Kullanici(UserMixin, db.Model):
    __tablename__ = 'kullanicilar'
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(50), unique=True, nullable=False)
    sifre_hash = db.Column(db.String(256), nullable=False)
    ad_soyad = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default='kasiyer')  # admin, mudur, kasiyer
    lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'), nullable=True)
    aktif = db.Column(db.Boolean, default=True)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    lokasyon = db.relationship('Lokasyon', backref='kullanicilar')

    def set_sifre(self, sifre):
        self.sifre_hash = generate_password_hash(sifre)

    def check_sifre(self, sifre):
        return check_password_hash(self.sifre_hash, sifre)


class Lokasyon(db.Model):
    __tablename__ = 'lokasyonlar'
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(100), nullable=False)
    tip = db.Column(db.String(20), nullable=False)  # fabrika, magaza
    adres = db.Column(db.Text)
    telefon = db.Column(db.String(20))
    aktif = db.Column(db.Boolean, default=True)


# ===================== TEDARİKÇİ (ÇİFTÇİ) =====================

class Tedarikci(db.Model):
    __tablename__ = 'tedarikciler'
    id = db.Column(db.Integer, primary_key=True)
    ad_soyad = db.Column(db.String(100), nullable=False)
    firma_adi = db.Column(db.String(100))
    telefon = db.Column(db.String(20))
    adres = db.Column(db.Text)
    vergi_no = db.Column(db.String(20))
    tc_no = db.Column(db.String(11))
    bakiye = db.Column(db.Float, default=0)  # pozitif=borcumuz, negatif=alacagimiz
    aktif = db.Column(db.Boolean, default=True)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    alimlar = db.relationship('HammaddeAlim', backref='tedarikci', lazy='dynamic')


# ===================== HAMMADDE =====================

class Hammadde(db.Model):
    __tablename__ = 'hammaddeler'
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(100), nullable=False)
    birim = db.Column(db.String(20), nullable=False, default='kg')  # kg, adet, litre
    kategori = db.Column(db.String(50))  # sebze, baharat, ambalaj, diger
    min_stok = db.Column(db.Float, default=0)
    aktif = db.Column(db.Boolean, default=True)


class HammaddeStok(db.Model):
    __tablename__ = 'hammadde_stok'
    id = db.Column(db.Integer, primary_key=True)
    hammadde_id = db.Column(db.Integer, db.ForeignKey('hammaddeler.id'), nullable=False)
    lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'), nullable=False)
    miktar = db.Column(db.Float, default=0)
    son_guncelleme = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hammadde = db.relationship('Hammadde', backref='stoklar')
    lokasyon = db.relationship('Lokasyon')

    __table_args__ = (db.UniqueConstraint('hammadde_id', 'lokasyon_id'),)


class HammaddeAlim(db.Model):
    __tablename__ = 'hammadde_alimlar'
    id = db.Column(db.Integer, primary_key=True)
    tedarikci_id = db.Column(db.Integer, db.ForeignKey('tedarikciler.id'), nullable=False)
    hammadde_id = db.Column(db.Integer, db.ForeignKey('hammaddeler.id'), nullable=False)
    lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'), nullable=False)
    miktar = db.Column(db.Float, nullable=False)
    birim_fiyat = db.Column(db.Float, nullable=False)
    toplam_tutar = db.Column(db.Float, nullable=False)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    aciklama = db.Column(db.Text)

    hammadde = db.relationship('Hammadde')
    lokasyon = db.relationship('Lokasyon')


# ===================== ÜRÜN (MAMÜL) =====================

class Urun(db.Model):
    __tablename__ = 'urunler'
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(100), nullable=False)
    barkod = db.Column(db.String(50), unique=True)
    kategori = db.Column(db.String(50))  # tursu, konserve, sos, diger
    birim = db.Column(db.String(20), default='adet')  # adet, kg
    ambalaj_tipi = db.Column(db.String(50))  # kavanoz_500g, kavanoz_1kg, kova_3kg, vs
    raf_omru_gun = db.Column(db.Integer, default=365)
    kdv_orani = db.Column(db.Float, default=10)
    aktif = db.Column(db.Boolean, default=True)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    fiyatlar = db.relationship('UrunFiyat', backref='urun', lazy='dynamic')
    recete = db.relationship('Recete', backref='urun', uselist=False)


class UrunFiyat(db.Model):
    __tablename__ = 'urun_fiyatlari'
    id = db.Column(db.Integer, primary_key=True)
    urun_id = db.Column(db.Integer, db.ForeignKey('urunler.id'), nullable=False)
    fiyat_tipi = db.Column(db.String(20), nullable=False)  # perakende, toptan
    fiyat = db.Column(db.Float, nullable=False)
    gecerlilik_tarihi = db.Column(db.Date, default=date.today)


# ===================== REÇETE =====================

class Recete(db.Model):
    __tablename__ = 'receteler'
    id = db.Column(db.Integer, primary_key=True)
    urun_id = db.Column(db.Integer, db.ForeignKey('urunler.id'), nullable=False, unique=True)
    ad = db.Column(db.String(100))
    aciklama = db.Column(db.Text)
    uretim_suresi_dk = db.Column(db.Integer)  # dakika

    kalemleri = db.relationship('ReceteKalem', backref='recete', cascade='all, delete-orphan')


class ReceteKalem(db.Model):
    __tablename__ = 'recete_kalemleri'
    id = db.Column(db.Integer, primary_key=True)
    recete_id = db.Column(db.Integer, db.ForeignKey('receteler.id'), nullable=False)
    hammadde_id = db.Column(db.Integer, db.ForeignKey('hammaddeler.id'), nullable=False)
    miktar = db.Column(db.Float, nullable=False)  # birim urun basina miktar

    hammadde = db.relationship('Hammadde')


# ===================== ÜRETİM =====================

class UretimEmri(db.Model):
    __tablename__ = 'uretim_emirleri'
    id = db.Column(db.Integer, primary_key=True)
    urun_id = db.Column(db.Integer, db.ForeignKey('urunler.id'), nullable=False)
    lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'), nullable=False)
    hedef_miktar = db.Column(db.Float, nullable=False)
    uretilen_miktar = db.Column(db.Float, default=0)
    durum = db.Column(db.String(20), default='beklemede')  # beklemede, uretimde, tamamlandi, iptal
    lot_no = db.Column(db.String(50), unique=True)
    uretim_tarihi = db.Column(db.Date, default=date.today)
    skt = db.Column(db.Date)  # son kullanma tarihi
    baslama_zamani = db.Column(db.DateTime)
    bitis_zamani = db.Column(db.DateTime)
    olusturan_id = db.Column(db.Integer, db.ForeignKey('kullanicilar.id'))
    aciklama = db.Column(db.Text)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    urun = db.relationship('Urun', backref='uretim_emirleri')
    lokasyon = db.relationship('Lokasyon')
    olusturan = db.relationship('Kullanici')
    girdiler = db.relationship('UretimGirdi', backref='uretim_emri', cascade='all, delete-orphan')
    kalite_kontroller = db.relationship('KaliteKontrol', backref='uretim_emri', cascade='all, delete-orphan')


class UretimGirdi(db.Model):
    __tablename__ = 'uretim_girdileri'
    id = db.Column(db.Integer, primary_key=True)
    uretim_emri_id = db.Column(db.Integer, db.ForeignKey('uretim_emirleri.id'), nullable=False)
    hammadde_id = db.Column(db.Integer, db.ForeignKey('hammaddeler.id'), nullable=False)
    planlanan_miktar = db.Column(db.Float, nullable=False)
    kullanilan_miktar = db.Column(db.Float, default=0)

    hammadde = db.relationship('Hammadde')


class KaliteKontrol(db.Model):
    __tablename__ = 'kalite_kontroller'
    id = db.Column(db.Integer, primary_key=True)
    uretim_emri_id = db.Column(db.Integer, db.ForeignKey('uretim_emirleri.id'), nullable=False)
    kontrol_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    kontrol_eden = db.Column(db.String(100))
    ph_degeri = db.Column(db.Float)
    tuz_orani = db.Column(db.Float)
    gorunum = db.Column(db.String(20))  # iyi, orta, kotu
    tat = db.Column(db.String(20))  # iyi, orta, kotu
    sonuc = db.Column(db.String(20), default='beklemede')  # gecti, kaldi, beklemede
    notlar = db.Column(db.Text)


# ===================== MAMÜL STOK =====================

class UrunStok(db.Model):
    __tablename__ = 'urun_stok'
    id = db.Column(db.Integer, primary_key=True)
    urun_id = db.Column(db.Integer, db.ForeignKey('urunler.id'), nullable=False)
    lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'), nullable=False)
    miktar = db.Column(db.Float, default=0)
    lot_no = db.Column(db.String(50))
    skt = db.Column(db.Date)
    son_guncelleme = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    urun = db.relationship('Urun', backref='stoklar')
    lokasyon = db.relationship('Lokasyon')

    __table_args__ = (db.UniqueConstraint('urun_id', 'lokasyon_id', 'lot_no'),)


# ===================== STOK TRANSFER =====================

class StokTransfer(db.Model):
    __tablename__ = 'stok_transferler'
    id = db.Column(db.Integer, primary_key=True)
    kaynak_lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'), nullable=False)
    hedef_lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'), nullable=False)
    transfer_no = db.Column(db.String(50), unique=True)
    durum = db.Column(db.String(20), default='hazirlaniyor')  # hazirlaniyor, yolda, teslim_edildi
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    teslim_tarihi = db.Column(db.DateTime)
    olusturan_id = db.Column(db.Integer, db.ForeignKey('kullanicilar.id'))
    aciklama = db.Column(db.Text)

    kaynak = db.relationship('Lokasyon', foreign_keys=[kaynak_lokasyon_id])
    hedef = db.relationship('Lokasyon', foreign_keys=[hedef_lokasyon_id])
    olusturan = db.relationship('Kullanici')
    kalemler = db.relationship('StokTransferKalem', backref='transfer', cascade='all, delete-orphan')


class StokTransferKalem(db.Model):
    __tablename__ = 'stok_transfer_kalemleri'
    id = db.Column(db.Integer, primary_key=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey('stok_transferler.id'), nullable=False)
    urun_id = db.Column(db.Integer, db.ForeignKey('urunler.id'), nullable=False)
    miktar = db.Column(db.Float, nullable=False)
    lot_no = db.Column(db.String(50))

    urun = db.relationship('Urun')


# ===================== MÜŞTERİ =====================

class Musteri(db.Model):
    __tablename__ = 'musteriler'
    id = db.Column(db.Integer, primary_key=True)
    ad_soyad = db.Column(db.String(100), nullable=False)
    firma_adi = db.Column(db.String(100))
    tip = db.Column(db.String(20), default='perakende')  # perakende, toptan
    telefon = db.Column(db.String(20))
    adres = db.Column(db.Text)
    vergi_no = db.Column(db.String(20))
    tc_no = db.Column(db.String(11))
    bakiye = db.Column(db.Float, default=0)
    aktif = db.Column(db.Boolean, default=True)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)


# ===================== SATIŞ =====================

class Satis(db.Model):
    __tablename__ = 'satislar'
    id = db.Column(db.Integer, primary_key=True)
    fis_no = db.Column(db.String(50), unique=True)
    musteri_id = db.Column(db.Integer, db.ForeignKey('musteriler.id'), nullable=True)
    lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'), nullable=False)
    kasiyer_id = db.Column(db.Integer, db.ForeignKey('kullanicilar.id'), nullable=False)
    satis_tipi = db.Column(db.String(20), default='perakende')  # perakende, toptan
    toplam_tutar = db.Column(db.Float, default=0)
    iskonto_tutar = db.Column(db.Float, default=0)
    kdv_tutar = db.Column(db.Float, default=0)
    net_tutar = db.Column(db.Float, default=0)
    odeme_tipi = db.Column(db.String(20), default='nakit')  # nakit, kart, havale, veresiye
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    iptal = db.Column(db.Boolean, default=False)

    musteri = db.relationship('Musteri', backref='satislar')
    lokasyon = db.relationship('Lokasyon')
    kasiyer = db.relationship('Kullanici')
    kalemler = db.relationship('SatisKalem', backref='satis', cascade='all, delete-orphan')


class SatisKalem(db.Model):
    __tablename__ = 'satis_kalemleri'
    id = db.Column(db.Integer, primary_key=True)
    satis_id = db.Column(db.Integer, db.ForeignKey('satislar.id'), nullable=False)
    urun_id = db.Column(db.Integer, db.ForeignKey('urunler.id'), nullable=False)
    miktar = db.Column(db.Float, nullable=False)
    birim_fiyat = db.Column(db.Float, nullable=False)
    iskonto = db.Column(db.Float, default=0)
    kdv_orani = db.Column(db.Float, default=10)
    toplam = db.Column(db.Float, nullable=False)
    lot_no = db.Column(db.String(50))

    urun = db.relationship('Urun')


# ===================== FATURA & İRSALİYE =====================

class Fatura(db.Model):
    __tablename__ = 'faturalar'
    id = db.Column(db.Integer, primary_key=True)
    fatura_no = db.Column(db.String(50), unique=True, nullable=False)
    fatura_tipi = db.Column(db.String(20), nullable=False)  # satis, alis
    musteri_id = db.Column(db.Integer, db.ForeignKey('musteriler.id'), nullable=True)
    tedarikci_id = db.Column(db.Integer, db.ForeignKey('tedarikciler.id'), nullable=True)
    lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'))
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    vade_tarihi = db.Column(db.Date)
    ara_toplam = db.Column(db.Float, default=0)
    kdv_toplam = db.Column(db.Float, default=0)
    toplam_tutar = db.Column(db.Float, default=0)
    durum = db.Column(db.String(20), default='taslak')  # taslak, onaylandi, iptal
    efatura_durum = db.Column(db.String(20))  # gonderildi, kabul, red
    aciklama = db.Column(db.Text)

    musteri = db.relationship('Musteri', backref='faturalar')
    tedarikci = db.relationship('Tedarikci', backref='faturalar')
    lokasyon = db.relationship('Lokasyon')
    kalemler = db.relationship('FaturaKalem', backref='fatura', cascade='all, delete-orphan')


class FaturaKalem(db.Model):
    __tablename__ = 'fatura_kalemleri'
    id = db.Column(db.Integer, primary_key=True)
    fatura_id = db.Column(db.Integer, db.ForeignKey('faturalar.id'), nullable=False)
    urun_id = db.Column(db.Integer, db.ForeignKey('urunler.id'), nullable=True)
    hammadde_id = db.Column(db.Integer, db.ForeignKey('hammaddeler.id'), nullable=True)
    aciklama = db.Column(db.String(200))
    miktar = db.Column(db.Float, nullable=False)
    birim_fiyat = db.Column(db.Float, nullable=False)
    kdv_orani = db.Column(db.Float, default=10)
    toplam = db.Column(db.Float, nullable=False)

    urun = db.relationship('Urun')
    hammadde = db.relationship('Hammadde')


class Irsaliye(db.Model):
    __tablename__ = 'irsaliyeler'
    id = db.Column(db.Integer, primary_key=True)
    irsaliye_no = db.Column(db.String(50), unique=True, nullable=False)
    irsaliye_tipi = db.Column(db.String(20), nullable=False)  # sevk, iade
    musteri_id = db.Column(db.Integer, db.ForeignKey('musteriler.id'), nullable=True)
    kaynak_lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'))
    hedef_lokasyon_id = db.Column(db.Integer, db.ForeignKey('lokasyonlar.id'), nullable=True)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    durum = db.Column(db.String(20), default='hazirlaniyor')  # hazirlaniyor, sevk_edildi, teslim_edildi
    plaka = db.Column(db.String(20))
    surucu = db.Column(db.String(100))
    aciklama = db.Column(db.Text)

    musteri = db.relationship('Musteri')
    kaynak = db.relationship('Lokasyon', foreign_keys=[kaynak_lokasyon_id])
    hedef = db.relationship('Lokasyon', foreign_keys=[hedef_lokasyon_id])
    kalemler = db.relationship('IrsaliyeKalem', backref='irsaliye', cascade='all, delete-orphan')


class IrsaliyeKalem(db.Model):
    __tablename__ = 'irsaliye_kalemleri'
    id = db.Column(db.Integer, primary_key=True)
    irsaliye_id = db.Column(db.Integer, db.ForeignKey('irsaliyeler.id'), nullable=False)
    urun_id = db.Column(db.Integer, db.ForeignKey('urunler.id'), nullable=False)
    miktar = db.Column(db.Float, nullable=False)
    lot_no = db.Column(db.String(50))

    urun = db.relationship('Urun')


# ===================== CARİ HESAP HAREKETLERİ =====================

class CariHareket(db.Model):
    __tablename__ = 'cari_hareketler'
    id = db.Column(db.Integer, primary_key=True)
    musteri_id = db.Column(db.Integer, db.ForeignKey('musteriler.id'), nullable=True)
    tedarikci_id = db.Column(db.Integer, db.ForeignKey('tedarikciler.id'), nullable=True)
    hareket_tipi = db.Column(db.String(20), nullable=False)  # borc, alacak, odeme, tahsilat
    tutar = db.Column(db.Float, nullable=False)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    aciklama = db.Column(db.Text)
    belge_no = db.Column(db.String(50))  # fatura no, fis no vs

    musteri = db.relationship('Musteri')
    tedarikci = db.relationship('Tedarikci')
