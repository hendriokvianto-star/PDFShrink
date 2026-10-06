# PRD — PDF Compressor Offline (Windows Desktop)

**Versi dokumen:** 1.0
**Status:** Siap dieksekusi oleh AI coding agent (Claude Code / Codex / Antigravity)
**Nama produk (kerja):** PDF Shrink

---

## 1. Ringkasan

Aplikasi desktop Windows yang berjalan **100% offline** untuk mengompresi file PDF ke **rentang ukuran target** yang ditentukan pengguna dalam satuan KB (ukuran minimum dan maksimum). Antarmuka dibuat minimalis: satu jendela, satu alur kerja, tanpa menu bertingkat.

Kasus pakai utama: pengguna harus mengunggah dokumen ke sistem/portal yang mensyaratkan ukuran file dalam rentang tertentu (mis. "PDF maksimal 300 KB, minimal 100 KB"), sementara data dokumen bersifat sensitif sehingga **tidak boleh diunggah ke layanan kompresi online**.

---

## 2. Tujuan & Non-Tujuan

### 2.1 Tujuan
- G1 — Mengompresi PDF hingga ukuran akhir masuk ke dalam rentang `[min_kb, max_kb]` yang diminta pengguna.
- G2 — Berjalan tanpa koneksi internet sama sekali. Tidak ada telemetri, tidak ada panggilan jaringan.
- G3 — Distribusi berupa satu file `.exe` portabel, tanpa instalasi Python/Ghostscript oleh pengguna.
- G4 — GUI minimalis yang bisa dipakai tanpa pelatihan: pilih file → isi min/max → tekan Kompres.
- G5 — Menjaga dokumen tetap terbaca (teks tetap teks, bukan gambar buram tanpa dasar).

### 2.2 Non-Tujuan (di luar cakupan v1.0)
- Tidak melakukan OCR.
- Tidak mengedit, menggabung, memisah, atau memberi watermark PDF.
- Tidak mendukung macOS/Linux (kode boleh cross-platform, tetapi hanya Windows yang diuji dan dirilis).
- Tidak ada akun, lisensi daring, atau auto-update.
- Tidak menjamin ukuran akhir mencapai `min_kb` jika PDF sumber sendiri sudah lebih kecil dari `min_kb` (lihat §6.4).

---

## 3. Pengguna & Skenario

**Persona:** staf administrasi perkantoran, keterampilan teknis dasar, memakai Windows 10/11, sering menangani berkas scan.

**Skenario utama:**
1. Pengguna membuka aplikasi.
2. Pengguna menyeret satu atau beberapa file PDF ke area drop, atau menekan tombol "Pilih File".
3. Pengguna mengisi ukuran minimum (mis. `100`) dan maksimum (mis. `300`) dalam KB.
4. Pengguna menekan "Kompres".
5. Progress bar berjalan; hasil ditampilkan: ukuran awal → ukuran akhir, status berhasil/gagal.
6. Pengguna menekan "Buka Folder Hasil".

---

## 4. Tumpukan Teknologi (wajib diikuti)

| Komponen | Pilihan | Alasan |
|---|---|---|
| Bahasa | Python 3.11 | Ekosistem PDF matang, packaging mudah |
| GUI | **CustomTkinter** (≥5.2) | Ringan, modern, tidak menambah beban besar ke `.exe` |
| Mesin PDF | **pikepdf** (MPL-2.0, wrapper QPDF) | Rewrite struktur, kompresi stream, linearisasi |
| Gambar | **Pillow** | Downsample + rekompresi JPEG pada gambar di dalam PDF |
| Packaging | **PyInstaller** (`--onefile --windowed`) | Menghasilkan satu `.exe` portabel |
| Testing | `pytest` | Uji unit untuk logika kompresi |

**Batasan lisensi — penting:**
- **DILARANG** membundel Ghostscript atau PyMuPDF/`fitz` di rilis default. Keduanya AGPL dan memaksa kewajiban lisensi pada distribusi. Gunakan pikepdf + Pillow.
- Jika agent merasa target ukuran tidak tercapai tanpa Ghostscript, jangan diam-diam menambahkannya — catat sebagai keterbatasan di `LIMITATIONS.md`.

**Larangan jaringan:** tidak boleh ada `requests`, `urllib`, `httpx`, atau soket apa pun di dalam kode aplikasi. Ini diuji lewat tes statis (§10.4).

---

## 5. Spesifikasi Antarmuka (GUI)

### 5.1 Tata letak
Satu jendela, ukuran tetap **520 × 560 px**, tidak resizable, judul `PDF Shrink`.

```
┌──────────────────────────────────────────────┐
│  PDF Shrink                             — ✕  │
├──────────────────────────────────────────────┤
│                                              │
│   ┌────────────────────────────────────┐     │
│   │                                    │     │
│   │   Tarik file PDF ke sini           │     │
│   │   atau [ Pilih File ]              │     │
│   │                                    │     │
│   └────────────────────────────────────┘     │
│                                              │
│   Daftar file (maks. 20):                    │
│   • laporan.pdf              1.842 KB   ✕    │
│   • sk-mutasi.pdf              976 KB   ✕    │
│                                              │
│   Ukuran target                              │
│   Minimum [   100 ] KB   Maksimum [  300 ] KB│
│                                              │
│   Folder hasil: C:\...\Documents\PDF Shrink  │
│   [ Ubah ]                                   │
│                                              │
│   ▓▓▓▓▓▓▓▓▓░░░░░░░░  Memproses 2 dari 3      │
│                                              │
│   [        Kompres        ]  [ Buka Folder ] │
└──────────────────────────────────────────────┘
```

### 5.2 Aturan komponen

| Elemen | Perilaku |
|---|---|
| Area drop | Menerima drag-and-drop file `.pdf`. File non-PDF ditolak dengan pesan inline, bukan popup. |
| Tombol "Pilih File" | Dialog multi-select, filter `PDF files (*.pdf)`. |
| Daftar file | Menampilkan nama + ukuran asli (KB). Tombol `✕` menghapus baris. Maksimum 20 file per batch. |
| Input Minimum | Hanya angka bulat. Default `0` (artinya: tanpa batas bawah). |
| Input Maksimum | Hanya angka bulat. Default `500`. Wajib > 0. |
| Validasi | `maks > min`. Jika tidak, tombol Kompres nonaktif dan label merah muncul: "Ukuran maksimum harus lebih besar dari minimum." |
| Folder hasil | Default `%USERPROFILE%\Documents\PDF Shrink`. Dibuat otomatis jika belum ada. Disimpan di `config.json`. |
| Tombol Kompres | Nonaktif saat daftar kosong atau validasi gagal. Saat berjalan, berubah jadi "Batalkan". |
| Progress | Progress bar keseluruhan + label `Memproses N dari M`. |
| Hasil per file | Setelah selesai, baris berubah: `laporan.pdf  1.842 KB → 287 KB  ✔`. Gagal: `✖ tidak bisa mencapai target (min. 412 KB)`. |

### 5.3 Gaya visual
- Tema: `customtkinter.set_appearance_mode("System")`, warna aksen default biru.
- Font: Segoe UI, 12pt untuk teks, 16pt semibold untuk judul.
- Tanpa ikon kustom selain ikon aplikasi. Tanpa splash screen.
- Tanpa dialog modal kecuali dialog file/folder bawaan sistem.

### 5.4 Threading
Kompresi berjalan di `threading.Thread` terpisah. UI **tidak boleh** membeku. Update progress dikirim ke main thread lewat `queue.Queue` + `root.after(100, ...)`.

---

## 6. Logika Kompresi (inti produk)

### 6.1 Strategi bertingkat
Proses berhenti di tingkat pertama yang menghasilkan ukuran ≤ `max_kb`.

**Tingkat 0 — Lossless rewrite**
- `pikepdf.open(src)` → `save(dst, compress_streams=True, object_stream_mode=ObjectStreamMode.generate, linearize=True)`
- Hapus metadata tidak perlu, `/Info` opsional, thumbnail tersemat, dan objek tak terpakai.
- Deduplikasi stream gambar identik (hash SHA-256 isi stream; XObject yang sama dipakai ulang).

**Tingkat 1 — Rekompresi gambar (tanpa downsampling)**
- Iterasi semua `XObject` bertipe `/Image`.
- Ekstrak ke Pillow, simpan ulang sebagai JPEG dengan `quality = q`.
- Lewati gambar dengan luas < 10.000 piksel, dan gambar bertipe `/ImageMask` (1-bit) — untuk 1-bit gunakan CCITT Group 4 / JBIG2 bawaan jika sudah ada, jangan diubah ke JPEG.
- Gambar dengan alpha channel dikonversi ke RGB di atas latar putih hanya jika `SMask` tidak membawa informasi penting; jika ragu, lewati.

**Tingkat 2 — Downsampling + rekompresi**
- Turunkan resolusi efektif gambar ke `dpi` target, dengan resampling `Image.LANCZOS`.
- DPI efektif dihitung dari ukuran piksel gambar dibagi ukuran tampilnya di halaman (dari matriks CTM di content stream; jika sulit dihitung, gunakan pendekatan lebar halaman sebagai proksi dan catat di kode).

**Tingkat 3 — Gagal**
- Jika ukuran terkecil yang bisa dicapai masih > `max_kb`, kembalikan status gagal beserta ukuran terkecil yang tercapai. **Jangan** menyimpan file hasil yang melanggar batas, kecuali pengguna memilih opsi "simpan hasil terbaik" (§6.5).

### 6.2 Pencarian parameter (binary search)
Parameter dicari dalam ruang kombinasi `(quality, dpi)` yang diurutkan dari kualitas tertinggi ke terendah:

```
LADDER = [
    (95, None), (85, None), (75, None),
    (85, 200), (75, 200), (65, 200),
    (75, 150), (65, 150), (55, 150),
    (65, 120), (55, 120),
    (55,  96), (45,  96),
    (40,  72),
]
```

Algoritma:
1. Jalankan Tingkat 0. Jika hasil ≤ `max_kb`, selesai.
2. Lakukan **binary search pada indeks LADDER**: cari indeks terkecil `i` yang menghasilkan ukuran ≤ `max_kb`.
3. Maksimum **8 percobaan render** per file (batas keras, cegah proses berjam-jam).
4. Setiap percobaan ditulis ke file sementara di `%TEMP%`, bukan ke memori, untuk PDF besar.
5. Hapus semua file sementara di `finally`, termasuk saat dibatalkan.

### 6.3 Menghormati batas minimum
`min_kb` adalah **batas bawah kualitas**, bukan target padding.
- Dari semua kandidat yang ≤ `max_kb`, pilih kandidat dengan ukuran **terbesar** yang masih ≤ `max_kb` (kualitas terbaik).
- Jika kandidat terpilih < `min_kb`, mundur satu tingkat ke kualitas lebih tinggi selama masih ≤ `max_kb`.
- **DILARANG** menambah byte sampah/padding hanya untuk memenuhi `min_kb`. Jika tetap tidak tercapai, tampilkan status informatif: `✔ 87 KB (di bawah minimum — sumber memang kecil)` dan tetap simpan filenya.

### 6.4 Kasus khusus
| Kondisi | Perilaku |
|---|---|
| PDF sumber sudah ≤ `max_kb` | Tetap jalankan Tingkat 0. Jika hasil lebih besar dari sumber, salin file asli apa adanya. |
| PDF terenkripsi berkata sandi | Minta sandi via input inline satu baris. Jika salah/kosong → lewati dengan status `✖ terkunci sandi`. |
| PDF rusak / bukan PDF | Lewati, status `✖ file tidak valid`, batch tetap lanjut. |
| PDF berisi form (AcroForm) | Pertahankan field form. Jangan flatten kecuali pengguna mencentang "Ratakan formulir" (opsional, v1.1). |
| PDF bertanda tangan digital | Peringatkan di daftar: kompresi akan membatalkan tanda tangan. Tetap proses jika pengguna lanjut. |
| PDF hanya teks (tanpa gambar) | Tingkat 1–2 tidak berdampak. Jika masih > `max_kb`, laporkan gagal dengan alasan `dokumen berbasis teks — sudah minimum`. |
| File > 200 MB | Tetap diproses, tapi tampilkan peringatan waktu proses. |

### 6.5 Penamaan file keluaran
`{nama-asli}_compressed.pdf`. Jika sudah ada, tambahkan ` (2)`, ` (3)`, dst. **Tidak pernah menimpa file sumber.**

---

## 7. Struktur Proyek

```
pdf-shrink/
├── src/
│   └── pdfshrink/
│       ├── __init__.py
│       ├── __main__.py          # entry point
│       ├── app.py               # window utama CustomTkinter
│       ├── widgets/
│       │   ├── drop_zone.py
│       │   ├── file_list.py
│       │   └── size_inputs.py
│       ├── core/
│       │   ├── compressor.py    # orkestrasi tingkat 0–3
│       │   ├── ladder.py        # LADDER + binary search
│       │   ├── images.py        # ekstraksi & rekompresi XObject
│       │   ├── pdfio.py         # buka/simpan/validasi pikepdf
│       │   └── models.py        # dataclass: Job, Result, Settings
│       ├── config.py            # baca/tulis config.json
│       └── errors.py
├── tests/
│   ├── fixtures/                # PDF uji (scan, teks, form, terenkripsi, rusak)
│   ├── test_ladder.py
│   ├── test_compressor.py
│   ├── test_images.py
│   └── test_no_network.py
├── build.spec                   # konfigurasi PyInstaller
├── requirements.txt
├── README.md
├── LIMITATIONS.md
└── pyproject.toml
```

### 7.1 Kontrak antarmodul (wajib, agar GUI dan core terpisah bersih)

```python
# core/models.py
@dataclass(frozen=True)
class Settings:
    min_kb: int
    max_kb: int
    output_dir: Path

@dataclass
class Job:
    src: Path
    original_bytes: int
    password: str | None = None

@dataclass
class Result:
    job: Job
    status: Literal["ok", "below_min", "failed", "skipped"]
    output: Path | None
    final_bytes: int | None
    attempts: int
    message: str

# core/compressor.py
def compress_one(
    job: Job,
    settings: Settings,
    on_progress: Callable[[float], None],
    cancel: threading.Event,
) -> Result: ...

def compress_batch(
    jobs: list[Job],
    settings: Settings,
    on_file_done: Callable[[Result], None],
    on_progress: Callable[[int, int], None],
    cancel: threading.Event,
) -> list[Result]: ...
```

`core/` **tidak boleh** mengimpor apa pun dari `customtkinter` atau `tkinter`. Ini diuji (§10.4).

---

## 8. Penyimpanan Konfigurasi

`%APPDATA%\PDFShrink\config.json`:

```json
{
  "version": 1,
  "output_dir": "C:\\Users\\nama\\Documents\\PDF Shrink",
  "last_min_kb": 0,
  "last_max_kb": 500,
  "appearance": "System"
}
```

Jika file rusak atau tidak ada, pakai default tanpa menampilkan error.

---

## 9. Penanganan Error & Logging

- Log ditulis ke `%APPDATA%\PDFShrink\logs\app.log`, rotasi 5 file × 1 MB.
- Log **tidak boleh** memuat isi dokumen. Hanya: nama file, ukuran, parameter, durasi, jenis error.
- Semua exception di worker thread ditangkap; satu file gagal tidak menghentikan batch.
- Crash tak tertangani di main thread: tampilkan pesan singkat + lokasi file log.

---

## 10. Kriteria Penerimaan (Acceptance Criteria)

Agent dianggap selesai jika **semua** poin berikut terpenuhi dan dapat dibuktikan.

### 10.1 Fungsional
- [ ] AC-1 — Scan 300 DPI 10 halaman (~8 MB) dengan `max_kb = 500` menghasilkan file ≤ 500 KB dan masih terbaca.
- [ ] AC-2 — Rentang `min=100, max=300`: hasil berada di 100–300 KB bila memungkinkan; jika tidak, status jelas.
- [ ] AC-3 — File sumber tidak pernah dimodifikasi atau dihapus (diverifikasi lewat hash sebelum & sesudah).
- [ ] AC-4 — Batch 10 file berjalan sampai selesai meski 2 di antaranya rusak.
- [ ] AC-5 — Tombol "Batalkan" menghentikan proses dalam < 2 detik dan membersihkan file sementara.
- [ ] AC-6 — Validasi `min ≥ max` memblokir tombol Kompres.
- [ ] AC-7 — PDF teks murni yang tak bisa dikecilkan menghasilkan pesan gagal yang informatif, bukan crash.

### 10.2 Performa
- [ ] AC-8 — PDF 20 MB, 50 halaman selesai dalam < 60 detik pada mesin 4-core tanpa GPU.
- [ ] AC-9 — Penggunaan RAM puncak < 1 GB untuk file 200 MB (bukti: proses per halaman/stream, bukan muat seluruh file ke memori).
- [ ] AC-10 — UI tetap responsif (bisa digeser/diklik) selama kompresi berjalan.

### 10.3 Distribusi
- [ ] AC-11 — `pyinstaller build.spec` menghasilkan satu `PDFShrink.exe` yang berjalan di Windows 10 & 11 x64 **tanpa Python terpasang**.
- [ ] AC-12 — Ukuran `.exe` < 80 MB.
- [ ] AC-13 — Aplikasi berjalan normal dengan adapter jaringan dinonaktifkan.
- [ ] AC-14 — Berjalan dari folder tanpa hak admin (mis. `D:\portable\`).

### 10.4 Kualitas kode
- [ ] AC-15 — `pytest` hijau, cakupan `core/` ≥ 80%.
- [ ] AC-16 — Tes `test_no_network.py` memindai seluruh `src/` dan gagal bila menemukan impor `socket`, `requests`, `urllib.request`, `httpx`, atau `http.client`.
- [ ] AC-17 — Tes memastikan `core/` tidak mengimpor `tkinter`/`customtkinter`.
- [ ] AC-18 — `LIMITATIONS.md` berisi daftar jenis PDF yang tidak bisa dikompresi secara signifikan.

---

## 11. Rencana Eksekusi untuk AI Agent

Kerjakan berurutan. Setiap milestone harus lolos tesnya sebelum lanjut, dan di-commit terpisah.

| # | Milestone | Keluaran | Definisi selesai |
|---|---|---|---|
| M1 | Kerangka proyek | Struktur folder, `requirements.txt`, `pyproject.toml`, `models.py` | `pip install -r requirements.txt` sukses; `pytest` jalan (0 tes) |
| M2 | Core CLI | `compressor.py`, `ladder.py`, `images.py`, `pdfio.py` + CLI `python -m pdfshrink.core --in x.pdf --max 300` | AC-1, AC-2, AC-7 lolos lewat CLI, tanpa GUI |
| M3 | Fixtures & tes | 6 PDF uji + `test_*.py` | AC-15, AC-16, AC-17 lolos |
| M4 | GUI | `app.py` + `widgets/` | AC-6, AC-10 lolos; alur §3 bisa dijalankan manual |
| M5 | Threading & pembatalan | Worker thread, queue, tombol Batalkan | AC-4, AC-5 lolos |
| M6 | Config & logging | `config.py`, logging berotasi | Setelan bertahan setelah restart |
| M7 | Packaging | `build.spec`, `README.md`, `LIMITATIONS.md` | AC-11 s.d. AC-14 lolos |

**Aturan kerja untuk agent:**
1. Jangan menulis GUI sebelum M2 lolos. Kualitas kompresi adalah inti produk; GUI hanya pembungkus.
2. Jangan mengganti tumpukan teknologi di §4 tanpa mencatat alasannya di `LIMITATIONS.md`.
3. Jangan menambahkan fitur di luar §2.2.
4. Buat PDF fixture secara programatik (mis. dengan `reportlab` sebagai dev-dependency) agar repo tidak bergantung pada file biner eksternal.
5. Setelah setiap milestone, laporkan: apa yang dibangun, tes mana yang lolos, dan keputusan teknis yang diambil.

---

## 12. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| pikepdf saja tak cukup agresif untuk target sangat kecil | Target tidak tercapai di sebagian PDF | Dokumentasikan di `LIMITATIONS.md`; jangan diam-diam pakai Ghostscript |
| Perhitungan DPI efektif dari CTM kompleks | Downsampling salah, gambar terlalu kabur/besar | Mulai dengan pendekatan proksi lebar halaman; uji dengan fixture scan |
| PyInstaller `--onefile` memicu false positive antivirus | Distribusi terhambat | Sediakan juga mode `--onedir` di `build.spec` |
| SMask/transparansi rusak saat rekompresi | Dokumen tampak salah | Lewati gambar bertransparansi jika ragu; tambahkan tes visual |

---

## 13. Ide untuk Versi Berikutnya (di luar v1.0)
- Pratinjau halaman pertama sebelum/sesudah kompresi.
- Preset cepat: "Lampiran email 2 MB", "Unggah portal 500 KB".
- Ratakan formulir (opsional).
- Antarmuka CLI resmi untuk pemakaian batch terjadwal.
- Berkas terjemahan (i18n) ID/EN.
