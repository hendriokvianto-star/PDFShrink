# Keterbatasan PDF Shrink v1.0

Dokumen ini mencatat keterbatasan yang diketahui dari PDF Shrink. Baca sebelum melaporkan masalah.

---

## 1. PDF Berbasis Teks Tidak Dapat Dikompres Secara Signifikan

**Masalah:** PDF yang hanya berisi teks (tanpa gambar) sudah sangat efisien. PDF Shrink tidak dapat mengompresnya secara berarti.

**Perilaku:** Aplikasi akan menampilkan pesan:
> "✖ dokumen berbasis teks — sudah minimum"

**Solusi alternatif:** Tidak ada. Kompresi teks PDF memerlukan Ghostscript (tidak disertakan) atau konversi format.

---

## 2. Kalkulasi DPI Menggunakan Proxy Lebar Halaman

**Masalah:** DPI gambar di dalam PDF dihitung menggunakan lebar halaman sebagai proxy, bukan matriks transformasi penuh (CTM — Current Transformation Matrix).

**Dampak:**
- Gambar yang dirotasi, di-scale non-uniform, atau diposisikan miring mungkin dihitung DPI-nya tidak akurat
- Downsampling bisa jadi lebih agresif atau lebih konservatif dari yang diharapkan
- Hasil kompresi untuk PDF dengan layout kompleks mungkin tidak optimal

**Tidak terpengaruh:** PDF scan standar (1 gambar per halaman, orientasi normal).

---

## 3. Tanpa Ghostscript — Kompresi Lebih Terbatas

**Masalah:** PDF Shrink menggunakan pikepdf + Pillow tanpa Ghostscript. Ghostscript mampu kompresi lebih agresif melalui rendering ulang halaman penuh.

**Dampak:**
- Beberapa PDF "keras" (embedded fonts besar, content streams tidak efisien) tidak bisa dikecilkan ke target
- PDF dengan banyak font subset besar tidak terpengaruh oleh kompresi gambar
- Target `--max` yang sangat kecil (< 50 KB) mungkin tidak tercapai untuk dokumen kompleks

**Perilaku:** Jika target tidak tercapai setelah 8 percobaan, aplikasi menampilkan:
> "✖ tidak bisa mencapai target (N KB)"

---

## 4. Keterbatasan Drag-and-Drop

**Masalah:** Drag-and-drop bergantung pada dukungan sistem operasi Windows melalui `TkinterDnD2` atau mekanisme natif tkinter.

**Dampak:**
- Drag-and-drop dari beberapa aplikasi pihak ketiga (misal: 7-Zip, WinRAR) mungkin tidak berfungsi
- Drag-and-drop dari Windows Explorer bekerja normal
- Workaround: gunakan tombol "Pilih File" sebagai alternatif

---

## 5. Batch Processing Dibatasi 20 File

**Masalah:** Antarmuka GUI dirancang untuk maksimum 20 file per sesi.

**Dampak:** Lebih dari 20 file tidak dapat ditambahkan sekaligus via GUI.

**Solusi alternatif:** Gunakan CLI untuk batch besar:
```bash
python -m pdfshrink --in *.pdf --max 500
```

---

## 6. PDF dengan Form Interaktif (AcroForm)

**Masalah:** PDF yang berisi form interaktif (AcroForm, XFA) dikompres secara konservatif — hanya gambar yang direkompresi, struktur form dipertahankan.

**Dampak:** Kompresi pada PDF form mungkin lebih kecil dari yang diharapkan karena data form tidak disentuh.

---

## 7. PDF Berpassword — Hanya Input Manual

**Masalah:** PDF terenkripsi memerlukan input password manual via dialog inline. Tidak ada dukungan batch untuk PDF dengan password berbeda-beda.

**Dampak:** Jika 5 file terenkripsi dalam satu batch, setiap file akan meminta password secara terpisah.

---

## 8. Ukuran Exe ~70–80 MB

**Masalah:** Distribusi satu file `.exe` mencakup Python runtime, pikepdf, Pillow, dan CustomTkinter — menghasilkan ukuran ~70–80 MB.

**Ini bukan bug:** Ini adalah konsekuensi dari distribusi mandiri (tanpa memerlukan instalasi Python).

---

## Keterbatasan yang Bukan Masalah Kami

| Kondisi | Perilaku |
|---------|---------|
| File PDF tidak ditemukan | Pesan error jelas, proses berlanjut ke file berikutnya |
| File bukan PDF | Dilewati dengan pesan "file tidak valid" |
| File corrupt/rusak | Dilewati dengan pesan error, tidak crash |
| Disk penuh saat menyimpan output | Error ditangkap, dilaporkan ke log |
| PDF sudah lebih kecil dari target | Disalin apa adanya, dilaporkan sebagai sukses |
