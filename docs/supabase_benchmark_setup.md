# Benchmark arastirmasi: Supabase + ayri worker

## 1. Supabase

1. Supabase'de yeni bir proje olusturun. Veritabani sifresini saklayin.
2. Projenin **Connect > Session pooler** bolumundeki PostgreSQL URI'sini alin
   (5432 portu). `anon` veya `service_role` API anahtari kullanilmaz.
3. URI'deki parola alanini veritabani sifresiyle doldurun. Sifredeki ozel
   karakterleri URL-encode edin. URI'ye `?sslmode=require` ekleyin.
4. Baglanti adresini sohbete, kod deposuna veya ekran goruntusune koymayin.

Kaynak: https://supabase.com/docs/guides/database/connecting-to-postgres

## 2. Analist Streamlit uygulamasi

App settings > Secrets alanina kendi baglanti adresinizle ekleyin:

```toml
BENCHMARK_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/postgres?sslmode=require"
BENCHMARK_WORKER_MODE = "external"
```

Uygulama yeniden baslatildiginda tablolar `benchmark_private` semasinda olusur.
Bu semayi Supabase Data API icin exposed schemas listesine eklemeyin. Yalnizca
sunucu tarafindaki PostgreSQL baglantisi kullanilir. Analist uygulamasina erisimi
yetkili ekiple sinirlayin: bu surumde arastirmalar ortak ekip kutuphanesidir,
kullanici bazli ayirma veya executive yayinlama henuz yoktur.

## 3. Arastirma servisi

Depodaki `render.yaml` bir Render Background Worker tanimlar. Render'da repoyu
baglayip Blueprint ile worker olusturun. Hizmetin gosterdigi ucreti onaylamadan
kurulum baslamis sayilmaz. Gercek bir worker bu calisma sirasinda kurulmamisti.

Worker ortam degiskenleri:

- `BENCHMARK_DATABASE_URL`: Streamlit ile ayni URI.
- `ANTHROPIC_API_KEY`: AI ve web aramasi icin.
- `BENCHMARK_WORKER_MODE`: `external`.
- `MAX_LLM_ITEMS_PER_RUN`: `5` (iki serviste tutarli tutun).

Baslatma komutu: `python -m pipeline.benchmark_worker`.
Kaynak: https://render.com/docs/background-workers

Birden fazla worker ayni isi alamaz. Worker 30 saniyede bir yasam sinyali
gonderir. 180 saniye yenilenmeyen isler sonraki kuyruk kontrolunde `Kesildi`
olarak isaretlenir. Otomatik tekrar API ucreti olusturmaz; kullanici yeni surum
baslatabilir. Devam eden bir dis API cagrisi iptal sonrasi tamamlanabilir.

## 4. Yerel gecmisi aktarma

Worker'i baslatmadan once `.env` icine Supabase URI'sini ekleyin ve calistirin:

```sh
python3 -m pipeline.migrate_benchmark_jobs
```

Mevcut kimlikler ezilmez. Yerelde sirada/calisiyor kalan kayitlar tekrar
calistirilmak yerine `Kesildi` olarak aktarilir. Yerel dosyalar silinmez.

## 5. Kontrol

Taslak kaydedin, sayfayi yenileyin, taslagin kaldigini dogrulayin. Arastirmayi
baslatin: once `Sirada`, sonra `Arastiriliyor` gorunmeli. App kapaliyken worker
logunda is tamamlanabilmeli. Sonucu tekrar acip kaynaklari kontrol edin.

Yerel SQLite kuyruk ve eszamanlilik testleri mevcuttur. Supabase projesi ve
worker hesabi baglanmadan canli PostgreSQL/Cloud testi tamamlanmis sayilmaz.
