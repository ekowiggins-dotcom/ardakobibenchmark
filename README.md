# KOBİ Rekabet Gelişmeleri Radarı

Banka içi KOBİ strateji ve KOBİ iş geliştirme ekipleri için recent-development odaklı Streamlit MVP’si.

Platform; rakip banka ve fintech gelişmelerini tarar, Claude ile stratejik önemini değerlendirir, düşük değerli PR’ı ayıklar ve önemli gelişmeleri yönetici radarına taşır. Sabit benchmark modülleri V2 kapsamındadır ve dosyaları korunmuştur.

## Proje Yapısı

- `app.py`: Ana giriş sayfası ve Streamlit uygulama ayarları.
- `pages/`: Yönetici özeti, mevduat, gömülü finans, ödemeler, karşılaştırma, rakip kartları, kaynak takibi, haftalık radar ve analist onayı sayfaları.
- `pipeline/`: Kürate kaynak toplama, değişiklik tespiti, LLM taslak çıkarımı, onay kuyruğu güncelleme ve yayınlama scriptleri.
- `utils/`: Ortak veri yükleme, skorlama, grafik ve filtre yardımcıları.
- `data/`: CSV tabanlı örnek veri tabanı.

## Veri Dosyaları

- `institutions.csv`: Kurum ana verisi ve stratejik notlar.
- `benchmark_scores.csv`: Benchmark boyutlarında 1-5 arası skorlar.
- `deposit_products.csv`: KOBİ mevduat önerileri ve kampanya notları.
- `embedded_finance_features.csv`: Bağlama göre gömülü finans yetkinlikleri.
- `payments_features.csv`: Üye işyeri edinimi, POS ve ödeme kabul özellikleri.
- `digital_journey_features.csv`: KOBİ yolculuğu yetkinlikleri ve sürtünme sinyalleri.
- `sources.csv`: Güvenilirlik ve yaş bilgisi içeren eski/örnek araştırma kaynak takip dosyası.
- `battlecards.csv`: Kurum bazında tek sayfalık stratejik rakip kartı içeriği.
- `weekly_developments.csv`: Haftalık rakip gelişmeleri, etkiler ve önerilen aksiyonlar.
- `source_registry.csv`: Kürate Tier 1 ve Tier 2 kaynak envanteri. Yalnızca aktif onaylı kaynaklar toplamaya uygundur.
- `raw_documents_metadata.csv`: Toplanan dokümanlar için metadata, içerik hash’i, dosya yolları ve hata durumu.
- `llm_extractions.csv`: LLM destekli taslak gelişmeler. İncelenmeden yönetici kullanımına hazır değildir.
- `review_queue.csv`: Çıkarılan gelişmeler için analist onay kararları ve notları.
- `benchmark_facts.csv`: Stabil ürün, KOBİ, POS, fiyatlama ve API kaynaklarından çıkarılan yapılandırılmış benchmark bulguları.
- `benchmark_fact_review_queue.csv`: Benchmark bulgusu çıkarımı için analist onay kararları.
- `data/raw_documents/raw_html/`: Kürate statik kaynaklardan saklanan ham HTML.
- `data/raw_documents/cleaned_text/`: Analist doğrulaması için saklanan temizlenmiş kaynak metni.

## Benchmark Verisini Güncelleme

1. `data/institutions.csv` içinde kurumu ekleyin veya güncelleyin.
2. `data/benchmark_scores.csv` içinde her benchmark boyutu için bir satır ekleyin.
3. Mevduat, gömülü finans, ödemeler ve dijital yolculuk kanıtları için tematik dosyaları güncelleyin.
4. Erişim tarihi ve güvenilirlik seviyesiyle kaynak kayıtlarını ekleyin.
5. İlgili rakip kartını `data/battlecards.csv` içinde yenileyin.
6. Yönetici radarı için haftalık pazar gelişmelerini `data/weekly_developments.csv` içine ekleyin.

`institution_id` değerini tüm dosyalarda tutarlı kullanın. Uygulama dosyaları bu alanla birleştirir.

## Tier 1 ve Tier 2 Kaynak İzleme

Tier 1 kaynaklar, bankaların KOBİ sayfaları, POS sayfaları, kampanya sayfaları, basın bültenleri, ürün sayfaları ve geliştirici/API dokümanları gibi kuruma ait resmi sayfalardır. İçeriği kurum kontrol ettiği için bu kaynaklar daha yüksek güvenilirlik sağlar.

Tier 2 kaynaklar pazar, regülasyon, sektör birliği ve haber kaynaklarıdır. Regülasyon, ödemeler, fintek ve bankacılık sektörü gelişmeleri için daha geniş sinyal üretir. Regülatör veya resmi birlik kaynakları dışında Tier 2 çıktılar genellikle orta güvenle değerlendirilmelidir.

`data/source_registry.csv` kontrol katmanıdır. Kaynak seviyesi, kurum, kaynak tipi, URL, toplama yöntemi, güncelleme sıklığı, güvenilirlik, stratejik temalar ve aktiflik bilgisini içerir. Toplayıcı yalnızca `active == TRUE` ve `collection_method == static_scrape` olan satırları okur.

Bu yapı özellikle kontrolsüz bir scraper değildir. Kaynak envanterindeki `extraction_mode`, her kaynağın nasıl yorumlanacağını belirler:

- `benchmark_fact`: Stabil ürün, KOBİ, POS, fiyatlama ve API sayfaları. Haftalık haber değil, yeniden kullanılabilir benchmark bulgusu üretir.
- `weekly_development`: Basın bültenleri, kampanyalar, regülatör duyuruları, birlik/dernek duyuruları ve haber kaynakları. Haftalık Gelişmeler Radarı’nı besler.
- `both`: Hem stabil benchmark kanıtı hem de pazar gelişmesi üretebilen kaynaklar.
- `ignore`: Kürate edilmiş ama şu anda çıkarıma alınmayan kaynaklar.

Ürün sayfaları ilk kez toplandı diye otomatik olarak haftalık gelişmeye dönüşmez. İlk toplama çoğunlukla platformun bir benchmark kaynağını yakaladığı anlamına gelir; rakibin yeni bir ürün çıkardığı anlamına gelmez.

Kontrollü akış:

1. Kürate edilmiş onaylı kaynaklar
2. Statik toplama ve ham metni saklama
3. İçerik hash değişim tespiti
4. `extraction_mode` ile doğru akışa yönlendirme
5. Sadece yeni/değişen kaynaklar için LLM veya dry-run taslak çıkarımı
6. Analist onay kuyruğu
7. Onaylı haftalık gelişmelerin Haftalık Gelişmeler Radarı’na yayınlanması

LLM çıktıları ve dry-run çıktıları yönetime gitmeden önce mutlaka analist tarafından incelenmelidir.

## Yarı Otomasyon Komutları

Bağımlılıkları yükleme:

```bash
pip install -r requirements.txt
```

Dashboard’u çalıştırma:

```bash
streamlit run app.py
```

Kaynak izleme pipeline’ını çalıştırma:

```bash
python pipeline/collect_static_pages.py
python pipeline/detect_changes.py
python pipeline/run_llm_extraction.py
python pipeline/run_benchmark_fact_extraction.py
python pipeline/update_review_queue.py
python pipeline/publish_weekly_developments.py
```

## MVP Recent-Development Komutları

Garanti BBVA:

```bash
python3 pipeline/run_bank_recent_flow.py --institution "Garanti BBVA"
```

İş Bankası:

```bash
python3 pipeline/run_bank_recent_flow.py --institution "İş Bankası"
```

Yapı Kredi:

```bash
python3 pipeline/run_bank_recent_flow.py --institution "Yapı Kredi"
```

QNB Finansbank:

```bash
python3 pipeline/run_bank_recent_flow.py --institution "QNB Finansbank"
```

Onaylı recent item gelişmelerini yönetici radarına yayınlama:

```bash
python3 pipeline/publish_recent_items_to_weekly_developments.py
```

## Streamlit Analyst -> Executive Veri Senkronu

Streamlit Community Cloud üzerinde analyst ve executive app ayrı runtime dosya sistemlerinde çalışır. Bu yüzden analyst app içinde onaylanan bir kayıt, sadece lokal CSV'ye yazılırsa executive app tarafından otomatik görülmez. Analyst app onay sonrası değişen CSV'leri GitHub'a commit edebilir; executive app aynı repo'dan beslendiği için güncel yönetici özetini alır.

Analyst app secrets içine şu değerleri ekleyin:

```toml
GITHUB_SYNC_TOKEN = "github_pat_..."
GITHUB_SYNC_REPOSITORY = "ekowiggins-dotcom/ardakobibenchmark"
GITHUB_SYNC_BRANCH = "main"
```

`GITHUB_SYNC_TOKEN` repo içeriğine yazma yetkisi olan bir GitHub personal access token olmalıdır. Bu değer `.env`, CSV veya koda yazılmamalıdır.

`run_llm_extraction.py` haftalık gelişme çıkarım akışıdır. Yalnızca `extraction_mode` değeri `weekly_development` veya `both` olan kaynakları işler; sadece benchmark amaçlı ürün sayfalarını haftalık radar taslağına almaz.

`run_benchmark_fact_extraction.py` benchmark bulgusu çıkarım akışıdır. KOBİ sayfaları, POS sayfaları, resmi ürün sayfaları, fiyatlama sayfaları ve geliştirici/API dokümanları gibi `benchmark_fact` veya `both` kaynakları işler.

Her iki script de ortamdan veya `.env` dosyasından `LEGACY_LLM_API_KEY` okur. Anahtar yoksa dry-run modunda analist tarafından incelenebilir taslak satırlar üretir. Doğrudan yönetici sayfalarına yayın yapmaz.

Recent item akışında `summarize_recent_items.py`, Claude/Anthropic yapılandırması varsa tekil gelişme adaylarını gerçek LLM özetiyle sınıflandırır. `ANTHROPIC_API_KEY` yoksa dry-run modunda güvenli placeholder satırları üretir.

Streamlit’te `pages/9_Analist_Onay_Kuyrugu.py` ile taslakları onaylayabilir, reddedebilir veya ek araştırma gerekli olarak işaretleyebilirsiniz. `publish_weekly_developments.py` yalnızca onaylı maddeleri ekler ve çıkarım/doküman kimlikleriyle mükerrerliği engeller.

Benchmark görünümlerinde veya rakip kartlarında kanıt olarak kullanmadan önce `pages/10_Benchmark_Bulgulari_Onay_Kuyrugu.py` üzerinden benchmark bulgularını onaylayın, reddedin veya ek araştırma gerekli olarak işaretleyin.

## Claude API Kurulumu

1. Lokal `.env` dosyasını `.env.example` üzerinden oluşturun.
2. Anahtarınızı sadece lokal `.env` içine ekleyin:

```bash
ANTHROPIC_API_KEY=your_key_here
```

3. `.env` dosyasını asla commit etmeyin. `.gitignore` bu dosyayı dışarıda bırakır.
4. Garanti BBVA pilot özetleme akışını çalıştırın:

```bash
python3 pipeline/summarize_recent_items.py --institution "Garanti BBVA" --limit 3
```

5. Anahtar yoksa script otomatik olarak dry-run modunu kullanır ve analist onay kuyruğuna düşük güvenli placeholder özetler gönderir.

## Türkçe Operasyon Notu

Uygulama Akbank KOBİ strateji, KOBİ iş geliştirme ve KOBİ liderlik kullanıcıları için Türkçe öncelikli tasarlanmıştır. `data/source_registry.csv` otomatik izleme için kanonik kaynak envanteridir; `data/sources.csv` eski/mock destek dosyası olarak değerlendirilmelidir.

`extraction_mode` iki farklı kullanım senaryosunu ayırır:

- `benchmark_fact`: KOBİ sayfaları, POS sayfaları, ürün sayfaları, fiyatlama sayfaları ve API dokümanları gibi stabil kaynaklardan benchmark bulguları çıkarır.
- `weekly_development`: Basın bültenleri, kampanyalar, regülatör duyuruları, birlik/dernek duyuruları ve haber kaynaklarından haftalık gelişme taslakları çıkarır.
- `both`: Her iki akış için de kullanılabilecek kaynaklar.
- `ignore`: İzlenen ama çıkarıma alınmayan kaynaklar.

Normal bir ürün sayfasının ilk kez toplanması haftalık gelişme anlamına gelmez. Bu yalnızca benchmark kanıtı üretir. Haftalık Gelişmeler Radarı’na gidecek maddeler önce LLM/dry-run taslağı olarak oluşur, ardından analist onay kuyruğunda insan onayı alır.

İlgili sayfalar:

- `Kaynak Takibi`: Kanonik kaynak envanteri, son kontrol durumu ve hata/stale kaynak takibi.
- `Haftalık Gelişmeler Radarı`: Varsayılan olarak sadece onaylı gelişmeleri gösterir.
- `Analist Onay Kuyruğu`: Haftalık gelişme taslaklarını onaylama/reddetme alanı.
- `Benchmark Bulguları Onay Kuyruğu`: Benchmark bulgularını onaylama/reddetme alanı.

## Lokal Çalıştırma

Bağımlılıkları yükleme:

```bash
pip install -r requirements.txt
```

Uygulamayı başlatma:

```bash
streamlit run app.py
```

## Notlar

Tüm veriler prototip gösterimi için oluşturulmuş örnek verilerdir. Skorlar analist tarzı tahminlerdir; doğrulanmış banka araştırması değildir. V2 sürümü kaynak toplama, iş akışı onayları, CRM veya BD istihbarat entegrasyonları ve otomatik rapor üretimi ekleyebilir.
