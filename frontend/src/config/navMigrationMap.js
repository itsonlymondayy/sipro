// navMigrationMap.js — PETA MENU LAMA -> BARU (Fase 40c).
//
// Ini bukan dokumentasi tempelan: isinya dipakai LANGSUNG oleh dialog "Peta Menu Baru" di
// sidebar, sehingga pemakai lama bisa mencari nama menu yang ia hafal dan langsung dibawa ke
// tempat barunya. Satu baris = satu fitur; `to` WAJIB rute yang benar-benar ada (dijaga gate
// `scripts/verify_ia_v2.py`), jadi peta ini tidak bisa membusuk diam-diam.
export const NAV_MIGRATION = [
  { old: "Deal & Unit", now: "CRM › Customer & Kontrak → tab “Deal & Unit”",
    to: "/customers?hub=deal",
    why: "Unit, deal, pembeli, dan dokumennya adalah SATU alur bisnis." },
  { old: "Customer & KPR", now: "CRM › Customer & Kontrak → tab “Pembeli”",
    to: "/customers?hub=pembeli",
    why: "Satu pintu untuk pembeli; profil lengkap ada di halaman /customers/:id." },
  { old: "Lead", now: "CRM › Pipeline Lead", to: "/leads",
    why: "Nama menu disamakan dengan isinya (pipeline), profil di /leads/:id." },
  { old: "Inbox WA", now: "CRM › Percakapan (WA)", to: "/inbox",
    why: "Istilah “percakapan” dipakai konsisten dengan template & playbook WA." },
  { old: "Automasi & Channel", now: "Marketing › Automasi & Channel", to: "/automation",
    why: "Domain marketing dipisah dari CRM penjualan." },
  { old: "Proyek & Unit", now: "Proyek › Master Proyek", to: "/projects",
    why: "Struktur proyek→cluster→blok→unit; Unit 360 di /units/:id." },
  { old: "Progres & Mutu", now: "Proyek › Pembangunan → tab “Progres & Mutu”",
    to: "/build?hub=progres", why: "Empat menu pembangunan dilebur jadi satu hub bertab." },
  { old: "Kalender Jadwal", now: "Proyek › Pembangunan → tab “Kalender Jadwal”",
    to: "/build?hub=kalender", why: "Jadwal & progres dibaca bergantian; jangan pindah menu." },
  { old: "Buku Harian & Punch", now: "Proyek › Pembangunan → tab “Buku Harian & Punch”",
    to: "/build?hub=lapangan", why: "Laporan lapangan menempel pada konteks pembangunan." },
  { old: "Kalibrasi Jadwal", now: "Proyek › Pembangunan → tab “Kalibrasi Jadwal”",
    to: "/build?hub=kalibrasi", why: "Kalibrasi = tindak lanjut dari analitik jadwal." },
  { old: "(baru)", now: "Proyek › Pembangunan → tab “Papan Unit”",
    to: "/build?hub=unit",
    why: "Tabel unit LINTAS proyek: cari/filter status bangun (mis. semua unit QC hold)." },
  { old: "Perizinan & Dokumen", now: "Dokumen → tab “Perizinan”", to: "/documents?hub=perizinan",
    why: "Daftar global izin masuk Dokumen; izin per objek tetap di Unit 360 & Proyek." },
  { old: "Site Plan & Showroom", now: "Proyek › Site Plan", to: "/site-plan",
    why: "Satu baris menu untuk penjualan & proyek (dulu muncul dua kali)." },
  { old: "Work Hub", now: "Kerja › Tugas & Papan Divisi", to: "/tasks",
    why: "Nama menu memakai bahasa Indonesia & menyebut isinya." },
  { old: "Kas Bon", now: "Keuangan › Kas Bon", to: "/petty-cash",
    why: "Pengeluaran kas berada satu grup dengan keuangan lain." },
  { old: "Marketing Fee", now: "CRM › Mitra & Fee → tab “Tagihan Fee”",
    to: "/partners?hub=tagihan",
    why: "Tagihan fee tidak berdiri sendiri: ia lahir dari aturan fee mitra (Fase 42). "
      + "Rute /marketing-fee tetap hidup sebagai alias." },
  { old: "Master Agen", now: "CRM › Mitra & Fee → tab “Master Mitra”",
    to: "/partners?hub=mitra",
    why: "Master agen menjadi master MITRA: kontrak, aturan fee, atribusi lead, analitik." },
];

/** Fitur yang BELUM dibangun — ditampilkan jujur (bukan menu kosong). */
export const NAV_SOON = [
  { label: "Kampanye & Biaya Iklan", where: "Marketing", when: "Fase 44" },
  { label: "Atribusi & CAPI", where: "Marketing", when: "Fase 44" },
  { label: "Analitik & BI", where: "Analitik & BI", when: "Fase 45" },
];
