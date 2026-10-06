# PDF Shrink

Aplikasi desktop Windows **100% offline** untuk mengompresi file PDF ke ukuran target (min/max KB) tanpa kehilangan keterbacaan teks.

---

## Fitur Utama

| Fitur | Keterangan |
|-------|-----------|
| 🗜️ Kompresi pintar | Strategi bertingkat (Tier 0–3): lossless rewrite → rekompresi gambar → downsampling |
| 📏 Target presisi | Tentukan rentang min–max KB yang diinginkan |
| 🔒 100% offline | Tidak ada koneksi internet, tidak ada telemetri, tidak ada cloud |
| 📦 Portabel | Satu file `.exe`, tidak memerlukan instalasi |
| 📂 Batch processing | Hingga 20 file PDF sekaligus |
| 🔑 PDF terenkripsi | Mendukung PDF berpassword (prompt inline) |
| ↩️ Sumber aman | File asli tidak pernah dimodifikasi |

---

## Persyaratan Sistem

- **OS:** Windows 10 / 11 x64
- **Python:** Tidak diperlukan (distribusi `.exe`)
- **Ruang disk:** ~80 MB untuk file exe
- **RAM:** ~150 MB saat kompresi batch

---

## Cara Penggunaan (GUI)

1. Jalankan `PDFShrink.exe`
2. Seret file PDF ke area drop, atau klik **Pilih File**
3. Isi **Minimum KB** dan **Maksimum KB** (target ukuran output)
4. Klik **Kompres**
5. Hasil tersimpan di folder output yang dipilih

> **Tip:** Tombol **Kompres** aktif hanya jika min < max dan ada file dalam daftar.
> Klik **Batalkan** kapan saja untuk menghentikan proses.

---

## Cara Penggunaan (CLI)

```bash
# Kompres satu file ke maksimum 300 KB
python -m pdfshrink --in dokumen.pdf --max 300

# Kompres ke rentang 100–300 KB, output ke folder khusus
python -m pdfshrink --in dokumen.pdf --min 100 --max 300 --out ./hasil

# Kompres beberapa file sekaligus
python -m pdfshrink --in a.pdf b.pdf c.pdf --max 500

# Jalankan mode GUI
python -m pdfshrink --gui
```

---

## Build dari Source

### Prasyarat

```bash
# Python 3.11+ diperlukan
python --version

# Install dependensi
pip install -r requirements.txt
pip install -e ".[dev]"
```

### Menjalankan Aplikasi

```bash
python -m pdfshrink          # Mode CLI (perlu --in dan --max)
python -m pdfshrink --gui    # Mode GUI
```

### Menjalankan Tes

```bash
pytest                        # Semua tes
pytest tests/ -v              # Verbose
pytest --cov=pdfshrink        # Dengan laporan coverage
```

### Build Executable

```bash
pip install pyinstaller
pyinstaller build.spec
# Hasil: dist/PDFShrink.exe (onefile) atau dist/PDFShrink/ (onedir)
```

---

## Struktur Proyek

```
pdf-compressor/
├── src/pdfshrink/
│   ├── core/          # Engine kompresi (pure Python, no GUI)
│   │   ├── models.py      # Settings, Job, Result dataclasses
│   │   ├── pdfio.py       # PDF buka/simpan/validasi
│   │   ├── images.py      # Ekstraksi & rekompresi gambar
│   │   ├── ladder.py      # 14-level quality ladder, binary search
│   │   └── compressor.py  # Orkestrasi Tier 0–3
│   ├── widgets/       # Komponen GUI CustomTkinter
│   ├── app.py         # Main window
│   ├── config.py      # Konfigurasi & logging
│   └── __main__.py    # Entry point CLI/GUI
├── tests/             # 124 unit tests
├── build.spec         # Konfigurasi PyInstaller
├── requirements.txt
└── pyproject.toml
```

---

## Keterbatasan

Lihat [LIMITATIONS.md](LIMITATIONS.md) untuk daftar keterbatasan yang diketahui.

---

## Lisensi

MIT — bebas digunakan, dimodifikasi, dan didistribusikan.
