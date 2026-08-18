"""PUSAT KONFIGURASI — registry setting bisnis (Fase 39).

Masalah yang diperbaiki: aturan bisnis (masa keep unit, persentase DP, potongan
pembatalan, hari toleransi cicilan, tarif PPh, dst) tersebar sebagai ANGKA MATI di kode
atau tidak ada sama sekali. Akibatnya kebijakan tidak bisa diubah tanpa deploy dan tidak
ada jejak siapa mengubah apa.

Aturan modul ini:
  1. DEFAULTS ada di KODE — sistem tetap jalan walau koleksi `settings` kosong.
  2. DB hanya menyimpan yang DIUBAH (override), berlapis: org → project → cluster.
  3. Setting `sensitive` WAJIB alasan saat diubah; semua perubahan masuk `history`.
  4. Nilai divalidasi (tipe, min/max, pilihan) — setting salah tidak boleh merusak sistem.

Angka default yang berasal dari dokumen legal owner (SPR Cash/Cash Bertahap/KPR + SPKT)
ditandai `src="DOC"` supaya jelas mana yang punya dasar dokumen dan mana yang usulan sistem.
"""
import logging
import time

from core_utils import new_id, now_iso
from db import db, ORG_ID

logger = logging.getLogger("sipro.settings")

SCOPES = ("org", "project", "cluster")
TYPES = ("int", "pct", "money", "bool", "str", "enum", "list", "obj")
_CACHE = {"at": 0.0, "rows": {}}
_TTL = 3.0


def _d(key, value, type_, group, label, help_, *, impact="", sensitive=False, minimum=None,
       maximum=None, options=None, src="SISTEM"):
    return {
        "key": key, "value": value, "type": type_, "group": group, "label": label,
        "help": help_, "impact": impact, "sensitive": sensitive, "min": minimum,
        "max": maximum, "options": options or [], "source": src,
    }


# ---------------------------------------------------------------- DEFAULTS
DEFAULTS: dict = {d["key"]: d for d in [
    # ============ reservasi / keep unit ============
    _d("reservation.max_active_per_lead", 1, "int", "reservasi",
       "Maksimum unit aktif per lead",
       "Berapa unit yang boleh dipegang satu calon pembeli pada waktu yang sama.",
       impact="Menaikkan nilai ini membuat stok unit tampak habis padahal dipegang satu orang.",
       sensitive=True, minimum=1, maximum=5),
    _d("reservation.hold_days", 7, "int", "reservasi", "Masa keep unit (hari)",
       "Lama unit dipegang sebelum otomatis dilepas bila tidak ada kelanjutan.",
       impact="Terlalu panjang = unit mati; terlalu pendek = pembeli serius kehilangan unit.",
       minimum=1, maximum=90, src="DOC"),
    _d("reservation.override_roles", ["sales_manager", "super_admin"], "list", "reservasi",
       "Peran yang boleh override batas reservasi",
       "Hanya peran ini yang boleh melewati batas 1 unit per lead, dan wajib beralasan.",
       sensitive=True),
    _d("reservation.require_booking_fee_before_spr", True, "bool", "reservasi",
       "Booking fee wajib sebelum SPR",
       "SPR tidak bisa diterbitkan sebelum booking fee tercatat.", sensitive=True, src="DOC"),
    # ============ lead ============
    _d("lead.won_trigger", "spr_signed", "enum", "lead", "Pemicu lead menjadi Customer",
       "Peristiwa yang mengubah lead menjadi customer (akhir lifecycle lead).",
       impact="Menentukan kapan proses legal berpindah ke domain Customer.",
       sensitive=True, options=["booking_fee_verified", "spr_signed", "ppjb_signed", "ajb_signed"]),
    # ============ SLA & umur tahap (Fase 41) ============
    # Ambang ini DULU angka mati di komponen frontend (72 jam di daftar Lead, 48 di Tugas &
    # Komplain, 168 di Deal, 336 di Pembeli, 720 di AR). Sekarang satu tempat, dan
    # `stage_clock.resync()` memberlakukannya ke baris yang sudah ada. Nilai 0 = tahap akhir
    # (tidak ada janji waktu) — UI menulis "tanpa SLA", bukan "dalam SLA".
    _d("lead.sla_hours", {"acquisition": 0.25, "nurturing": 48, "appointment": 72,
                          "booking": 168, "spr": 168, "won": 0, "lost": 0, "recycle": 0,
                          "default": 72}, "obj", "sla",
       "SLA tindak lanjut lead per tahap (jam)",
       "Batas waktu tindak lanjut tiap tahap lead; lewat batas memicu eskalasi ke supervisor."),
    _d("deal.sla_hours", {"reserved": 72, "booked": 720, "completed": 0, "cancelled": 0,
                          "default": 168}, "obj", "sla",
       "SLA tiap status deal (jam)",
       "Reservasi wajib berlanjut ke booking; booking wajib berlanjut ke PPJB/akad."),
    _d("task.sla_hours", {"open": 24, "in_progress": 48, "submitted": 24, "snoozed": 72,
                          "done": 0, "cancelled": 0, "default": 48}, "obj", "sla",
       "SLA tiap status tugas (jam)",
       "Batas wajar tugas menganggur pada satu status (di luar SLA jobdesk per tugas)."),
    _d("complaint.sla_hours", {"open": 24, "in_progress": 48, "resolved": 0, "closed": 0,
                               "default": 48}, "obj", "sla",
       "SLA tiap status komplain (jam)",
       "Batas wajar komplain menganggur pada satu status sebelum dianggap terlambat."),
    _d("customer.sla_hours", {"draft": 72, "submitted": 48, "verified": 0, "rejected": 0,
                              "default": 336}, "obj", "sla",
       "SLA verifikasi berkas pembeli (jam)",
       "Batas waktu berkas KYC pembeli menganggur pada satu status."),
    _d("ar.sla_hours", {"unpaid": 720, "partial": 720, "paid": 0, "default": 720}, "obj", "sla",
       "SLA tagihan (AR) per status (jam)",
       "Batas wajar tagihan belum lunas sebelum masuk penanganan penagihan."),
    _d("document.sla_hours", {"draft": 72, "finalized": 168, "signed": 0, "default": 168},
       "obj", "sla", "SLA dokumen per status (jam)",
       "Batas wajar dokumen menganggur sebelum difinalkan / ditandatangani."),
    _d("lead.required_demography", [], "list", "lead", "Data demografi wajib",
       "Field demografi yang wajib lengkap sebelum SPR diterbitkan."),
    _d("slik.gate", "before_spr", "enum", "lead", "Kapan BI/SLIK checking diwajibkan",
       "BI Checking berjalan di menu terpisah; ini hanya menentukan titik wajibnya.",
       options=["off", "before_booking", "before_spr"], sensitive=True),
    # ============ booking fee ============
    _d("booking_fee.default_amount", 1000000, "money", "booking_fee",
       "Booking fee default (Rp)",
       "Nominal booking fee bawaan; bisa ditimpa per proyek/cluster.", src="DOC"),
    _d("booking_fee.refund_bi_fail_pct", 100, "pct", "booking_fee",
       "Refund bila BI Checking tidak memenuhi (%)",
       "Persentase pengembalian booking fee bila hasil BI/SLIK tidak sesuai kriteria KPR.",
       sensitive=True, minimum=0, maximum=100, src="DOC"),
    _d("booking_fee.refund_kpr_rejected_pct", 50, "pct", "booking_fee",
       "Refund bila KPR ditolak bank (%)",
       "Persentase pengembalian booking fee bila pengajuan KPR ditolak bank.",
       sensitive=True, minimum=0, maximum=100, src="DOC"),
    _d("booking_fee.forfeit_no_clarity_days", 7, "int", "booking_fee",
       "Hangus bila tidak ada kejelasan (hari)",
       "Hari kalender sejak BI Checking lolos; tanpa kejelasan berkas, booking fee hangus.",
       sensitive=True, minimum=1, maximum=60, src="DOC"),
    # ============ skema pembayaran ============
    _d("payment.cash.dp_pct", 80, "pct", "pembayaran", "DP cash keras (%)",
       "Pembayaran tahap pertama; pembangunan mulai setelah DP diterima.",
       minimum=0, maximum=100, sensitive=True, src="DOC"),
    _d("payment.cash.payoff_days_after_completion", 30, "int", "pembayaran",
       "Batas pelunasan setelah progres 100% (hari)",
       "Hari kalender sejak pemberitahuan penyelesaian pembangunan.", src="DOC"),
    _d("payment.cash.payoff_grace_days", 7, "int", "pembayaran",
       "Perpanjangan pelunasan (hari)", "Toleransi tambahan sebelum transaksi bisa dibatalkan.",
       src="DOC"),
    _d("payment.staged.dp_pct", 80, "pct", "pembayaran", "DP cash bertahap (%)",
       "Pembayaran tahap pertama pada skema cash bertahap.", minimum=0, maximum=100, src="DOC"),
    _d("payment.staged.installment_count", 6, "int", "pembayaran", "Jumlah cicilan pelunasan",
       "Sisa pembayaran dicicil sebanyak ini (bulanan).", minimum=1, maximum=60, src="DOC"),
    _d("payment.staged.due_day", 7, "int", "pembayaran", "Tanggal jatuh tempo cicilan",
       "Tanggal setiap bulan saat cicilan wajib dibayar.", minimum=1, maximum=28, src="DOC"),
    _d("payment.staged.grace_day", 20, "int", "pembayaran", "Batas akhir toleransi (tanggal)",
       "Lewat tanggal ini cicilan dinyatakan menunggak.", minimum=1, maximum=28, src="DOC"),
    _d("payment.staged.arrears_months_to_cancel", 2, "int", "pembayaran",
       "Tunggakan sebelum bisa dibatalkan (bulan)",
       "Berurutan maupun akumulatif; setelah ini developer berhak membatalkan sepihak.",
       sensitive=True, minimum=1, maximum=12, src="DOC"),
    _d("payment.kpr.dp_pct", 0, "pct", "pembayaran", "DP KPR default (%)",
       "Uang muka default skema KPR (contoh dokumen: 0%).", minimum=0, maximum=100, src="DOC"),
    # ============ pembatalan & refund ============
    _d("cancellation.cut_before_build_pct", 35, "pct", "pembatalan",
       "Potongan bila batal sebelum pembangunan (%)",
       "Dipotong dari total pembayaran yang sudah diterima.",
       sensitive=True, minimum=0, maximum=100, src="DOC"),
    _d("cancellation.cut_during_build_pct", 50, "pct", "pembatalan",
       "Potongan bila batal saat pembangunan berjalan (%)",
       "Dipotong dari total pembayaran yang sudah diterima.",
       sensitive=True, minimum=0, maximum=100, src="DOC"),
    _d("cancellation.refund_requires_resale", True, "bool", "pembatalan",
       "Refund menunggu unit terjual kembali",
       "Pengembalian dana dilakukan setelah unit dibatalkan terjual ke pihak lain.",
       sensitive=True, src="DOC"),
    # ============ legal ============
    _d("legal.shgb_months_after_ajb", 6, "int", "legal", "Sertifikat (SHGB) diserahkan (bulan)",
       "Perkiraan waktu penyerahan sertifikat sejak AJB/PPJB notaris.", src="DOC"),
    _d("retention.months", 3, "int", "legal", "Masa retensi bangunan (bulan)",
       "Masa retensi/garansi bangunan setelah akad atau AJB.", minimum=0, maximum=36),
    # ============ KPR ============
    _d("kpr.use_appraisal_step", True, "bool", "kpr", "Pakai tahap survei & appraisal bank",
       "Bila dimatikan, alur KPR langsung dari pengajuan ke SP3K."),
    _d("kpr.sla_days", {"berkas_lengkap": 7, "diajukan_ke_bank": 14, "appraisal": 7,
                        "sp3k": 14, "akad_kredit": 7}, "obj", "kpr",
       "SLA tiap tahap KPR (hari)", "Batas waktu tiap tahap sebelum dianggap tersangkut."),
    # ============ add-on / spek tambahan ============
    _d("addon.require_spkt_for_excess_land", True, "bool", "addon",
       "Kelebihan tanah wajib SPKT",
       "Add-on kelebihan tanah tidak sah tanpa Surat Pernyataan Kelebihan Tanah.",
       sensitive=True, src="DOC"),
    _d("addon.excess_land_must_be_paid_before_akad", True, "bool", "addon",
       "Kelebihan tanah lunas sebelum akad",
       "Akad kredit/AJB diblokir bila biaya kelebihan tanah belum lunas.",
       sensitive=True, src="DOC"),
    _d("addon.excess_land_price_per_m2", 2000000, "money", "addon",
       "Harga list kelebihan tanah (Rp/m²)",
       "Harga daftar; harga disepakati diisi per unit saat reservasi dan boleh berbeda.",
       src="DOC"),
    _d("addon.excess_land_discount_needs_approval", True, "bool", "addon",
       "Harga nego kelebihan tanah butuh persetujuan",
       "Bila harga disepakati di bawah harga list, butuh persetujuan manajer."),
    # ============ mitra ============
    _d("partner.enabled", True, "bool", "mitra", "Aktifkan modul mitra",
       "Mematikan ini menyembunyikan menu mitra dan menolak lead bersumber mitra."),
    _d("partner.require_contract_active", True, "bool", "mitra", "Kontrak mitra wajib aktif",
       "Lead & fee ditolak bila kontrak mitra kedaluwarsa.", sensitive=True),
    _d("partner.attribution_model", "first_touch", "enum", "mitra", "Model atribusi lead mitra",
       "Menentukan mitra mana yang berhak atas lead yang dikirim lebih dari satu mitra.",
       options=["first_touch", "last_touch", "manual_review"], sensitive=True),
    _d("partner.lead_dedup_window_days", 30, "int", "mitra", "Jendela dedup lead mitra (hari)",
       "Lead sama dalam rentang ini dianggap milik mitra pertama.", minimum=1, maximum=365),
    _d("partner.auto_create_fee", True, "bool", "mitra", "Buat tagihan fee otomatis",
       "Fee dibuat otomatis saat pemicu tercapai (status menunggu persetujuan)."),
    _d("partner.fee_needs_approval", True, "bool", "mitra", "Fee wajib disetujui finance",
       "Tanpa persetujuan, fee tidak menjadi utang dan tidak dijurnal.", sensitive=True),
    _d("partner.max_fee_pct_of_price", 5, "pct", "mitra", "Pagar wajar fee (% harga)",
       "Fee di atas ambang ini butuh persetujuan owner.", minimum=0, maximum=100),
    _d("partner.tax_pph21_rate", 2.5, "pct", "mitra", "Tarif PPh 21 mitra perorangan (%)",
       "Default umum; WAJIB dikonfirmasi bagian pajak perusahaan.",
       sensitive=True, minimum=0, maximum=50),
    _d("partner.tax_pph23_rate", 2, "pct", "mitra", "Tarif PPh 23 mitra badan (%)",
       "Default umum; WAJIB dikonfirmasi bagian pajak perusahaan.",
       sensitive=True, minimum=0, maximum=50),
    _d("partner.portal_enabled", False, "bool", "mitra", "Aktifkan portal mitra",
       "Mitra bisa login OTP untuk melihat lead & fee miliknya."),
    # ============ dokumen ============
    _d("docnum.scope", "per_project", "enum", "dokumen", "Cakupan nomor dokumen",
       "Counter nomor dokumen dihitung global, per proyek, atau per proyek per bulan.",
       options=["global", "per_project", "per_project_month"], sensitive=True),
    _d("docnum.reset_policy", "yearly", "enum", "dokumen", "Reset nomor dokumen",
       "Kapan counter nomor dokumen dimulai dari 1 lagi.",
       options=["never", "yearly", "monthly"], sensitive=True),
    _d("docnum.width", 4, "int", "dokumen", "Lebar digit nomor",
       "Contoh lebar 4 = 0001; dokumen contoh owner memakai 4 digit (5201).",
       minimum=1, maximum=8),
    _d("doc.require_verification_default", True, "bool", "dokumen",
       "Dokumen baru wajib diverifikasi",
       "Dokumen yang diunggah berstatus menunggu verifikasi sebelum dianggap sah."),
    # ============ anggaran & target ============
    # Fase 45: bawaannya MATI (sengaja, keputusan pemilik saat fase ini dikerjakan).
    # Alasannya jujur: dokumen biaya yang sudah ada dibuat SEBELUM master anggaran ada, jadi
    # menyalakan kewajiban ini sejak hari pertama akan menolak pekerjaan orang tanpa mereka
    # punya kesempatan merapikan data. Urutan yang dipakai: susun item anggaran → rapikan
    # daftar "biaya belum terpetakan" (`GET /api/budget/unmapped`) → baru nyalakan ini.
    _d("budget.enforce_cost_ref", False, "bool", "anggaran",
       "Dokumen biaya wajib memilih item anggaran",
       "Bila MATI: dokumen biaya baru boleh tanpa item anggaran, tetapi muncul di laporan "
       "'biaya belum terpetakan'. Bila MENYALA: PO/tagihan/kas bon/jurnal baru DITOLAK tanpa "
       "item anggaran, sehingga realisasi RAB & overbudget tidak perlu menebak.",
       impact="Menyalakan ini menambah satu field wajib pada semua form biaya baru. "
              "Rapikan dulu laporan 'biaya belum terpetakan'.",
       sensitive=True),
    _d("budget.alert_pct", 90, "pct", "anggaran", "Ambang peringatan anggaran (%)",
       "Saat realisasi+komitmen mencapai ambang ini, peringatan dikirim.",
       minimum=50, maximum=100),
    _d("target.default_method", "linear_remaining", "enum", "anggaran", "Metode target default",
       "Metode perhitungan target bulanan untuk proyek baru.",
       options=["linear_remaining", "s_curve", "manual", "velocity_forecast", "revenue_first"]),
    # ============ konstruksi & izin ============
    _d("permit.block_build_without", [], "list", "konstruksi",
       "Izin yang memblokir mulai bangun",
       "Kosong = hanya peringatan. Isi kode izin (mis. PBG) untuk memblokir. Izin dicari "
       "berjenjang: unit → blok → cluster → proyek; izin yang sudah kedaluwarsa tidak "
       "dihitung sebagai ada.",
       impact="Menyalakan ini bisa menghentikan pekerjaan yang sudah berjalan di lapangan. "
              "Rapikan dulu daftar izin per objek di tab Dokumen & Izin."),
    _d("build.require_dp_before_start", False, "bool", "konstruksi",
       "Mulai bangun butuh DP terbayar",
       "Sesuai SPR: pembangunan dimulai setelah pembayaran tahap pertama diterima. "
       "Bawaan MATI (Fase 46) = sistem hanya MEMPERINGATKAN dan memaksa pelaksana "
       "mengakui peringatan + menulis alasan yang tercatat. Bila MENYALA, tombol "
       "'Mulai bangun' benar-benar DITOLAK sampai termin pertama terbayar.",
       impact="Menyalakan ini menghentikan mulai bangun untuk unit yang termin "
              "pertamanya belum terbayar atau belum punya rencana bayar.",
       sensitive=True, src="DOC"),
    # ============ Fase 47A — rekonsiliasi bank ============
    _d("bank.match_amount_tolerance", 0, "money", "bank",
       "Toleransi selisih nominal saat mencocokkan",
       "Selisih rupiah yang masih dianggap 'nominal sama' saat sistem MENGUSULKAN kandidat "
       "(mis. biaya transfer Rp 6.500 yang dipotong bank). Bawaan 0 = harus sama persis. "
       "Toleransi hanya memengaruhi USULAN; keputusan tetap milik manusia.",
       impact="Menaikkan nilai ini membuat usulan lebih longgar — risiko salah cocok naik.",
       minimum=0, maximum=1000000),
    _d("bank.match_date_window_days", 7, "int", "bank",
       "Jendela tanggal pencarian kandidat (hari)",
       "Seberapa jauh sistem mencari dokumen di sekitar tanggal mutasi saat mengusulkan "
       "pencocokan.", minimum=1, maximum=90),
    # ============ Fase 47C — penawaran & diskon ============
    _d("quotation.discount_max_pct_sales", 2, "pct", "penawaran",
       "Batas diskon tanpa persetujuan manajer (%)",
       "Diskon sampai persen ini boleh diberikan sales sendiri; di atasnya penawaran WAJIB "
       "disetujui manajer sales/direksi beserta alasannya.",
       impact="Menaikkan batas ini memperbesar wewenang diskon sales tanpa persetujuan.",
       minimum=0, maximum=100, src="DOC"),
    _d("quotation.validity_days", 7, "int", "penawaran", "Masa berlaku penawaran (hari)",
       "Setelah lewat, penawaran otomatis dinyatakan kedaluwarsa dan harus direvisi — harga "
       "lama tidak boleh dipakai diam-diam.", minimum=1, maximum=90),
    # ============ Fase 47D — upah harian ============
    _d("labor.overtime_multiplier", 1.5, "pct", "upah", "Pengali upah lembur",
       "Tarif lembur = (upah harian ÷ jam kerja normal) × pengali ini.",
       minimum=1, maximum=5, src="DOC"),
    _d("labor.normal_hours_per_day", 8, "int", "upah", "Jam kerja normal per hari",
       "Dipakai menghitung tarif per jam untuk lembur.", minimum=4, maximum=12),
    # ============ tampilan ============
    _d("ui.table_page_size", 25, "int", "tampilan", "Baris per halaman tabel",
       "Jumlah baris default pada semua tabel daftar.", minimum=10, maximum=200),
]}

GROUP_LABELS = {
    "reservasi": "Reservasi & Keep Unit", "lead": "Lead & Lifecycle",
    "sla": "SLA & Umur Tahap (Aging)",
    "booking_fee": "Booking Fee", "pembayaran": "Skema Pembayaran",
    "pembatalan": "Pembatalan & Refund", "legal": "Legal & Retensi", "kpr": "KPR",
    "addon": "Spek Tambahan (Add-on)", "mitra": "Mitra / Pihak Ketiga",
    "dokumen": "Dokumen & Penomoran", "anggaran": "Anggaran & Target",
    "konstruksi": "Konstruksi & Izin", "bank": "Rekonsiliasi Bank",
    "penawaran": "Penawaran & Diskon", "upah": "Upah Harian Tenaga Kerja",
    "tampilan": "Tampilan",
}


# ---------------------------------------------------------------- validasi nilai
def coerce(spec: dict, value):
    """Ubah & validasi nilai sesuai tipe setting. Melempar ValueError bila tidak sah."""
    t = spec["type"]
    if t in ("int", "money"):
        try:
            value = int(float(value))
        except (TypeError, ValueError):
            raise ValueError(f"{spec['label']}: harus berupa angka bulat.")
    elif t == "pct":
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{spec['label']}: harus berupa angka persen.")
    elif t == "bool":
        if isinstance(value, str):
            value = value.strip().lower() in ("1", "true", "ya", "on")
        value = bool(value)
    elif t == "enum":
        value = str(value)
        if spec.get("options") and value not in spec["options"]:
            raise ValueError(f"{spec['label']}: pilihan tidak valid "
                             f"({', '.join(spec['options'])}).")
    elif t == "list":
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        if not isinstance(value, list):
            raise ValueError(f"{spec['label']}: harus berupa daftar.")
    elif t == "obj":
        if not isinstance(value, dict):
            raise ValueError(f"{spec['label']}: harus berupa objek.")
    else:
        value = str(value)
    if spec.get("min") is not None and isinstance(value, (int, float)) and value < spec["min"]:
        raise ValueError(f"{spec['label']}: minimum {spec['min']}.")
    if spec.get("max") is not None and isinstance(value, (int, float)) and value > spec["max"]:
        raise ValueError(f"{spec['label']}: maksimum {spec['max']}.")
    return value


# ---------------------------------------------------------------- pembacaan
async def _rows(org_id: str) -> dict:
    """Semua override tersimpan, dikelompokkan per key (dengan cache pendek)."""
    now = time.time()
    if now - _CACHE["at"] < _TTL and org_id in _CACHE["rows"]:
        return _CACHE["rows"][org_id]
    out: dict = {}
    async for row in db.settings.find({"org_id": org_id}, {"_id": 0}):
        out.setdefault(row["key"], []).append(row)
    _CACHE["rows"][org_id] = out
    _CACHE["at"] = now
    return out


def invalidate():
    _CACHE["at"] = 0.0
    _CACHE["rows"] = {}


async def get(key: str, *, org_id: str = ORG_ID, project_id: str = None,
              cluster_id: str = None):
    """Nilai efektif: cluster → project → org → default kode."""
    spec = DEFAULTS.get(key)
    if not spec:
        raise KeyError(f"Setting tidak dikenal: {key}")
    rows = (await _rows(org_id)).get(key) or []
    by = {(r.get("scope"), r.get("scope_id")): r.get("value") for r in rows}
    for scope, sid in (("cluster", cluster_id), ("project", project_id), ("org", org_id)):
        if sid and (scope, sid) in by:
            return by[(scope, sid)]
    return spec["value"]


async def get_many(keys, *, org_id: str = ORG_ID, project_id: str = None,
                   cluster_id: str = None) -> dict:
    return {k: await get(k, org_id=org_id, project_id=project_id, cluster_id=cluster_id)
            for k in keys}


async def get_group(group: str, *, org_id: str = ORG_ID, project_id: str = None) -> dict:
    keys = [k for k, s in DEFAULTS.items() if s["group"] == group]
    return await get_many(keys, org_id=org_id, project_id=project_id)


async def listing(*, org_id: str = ORG_ID, group: str = None, project_id: str = None,
                  q: str = None) -> list:
    """Daftar setting untuk UI: spec + nilai efektif + asal nilai + jejak terakhir."""
    rows = await _rows(org_id)
    out = []
    for key, spec in DEFAULTS.items():
        if group and spec["group"] != group:
            continue
        if q and q.lower() not in (key + " " + spec["label"] + " " + spec["help"]).lower():
            continue
        stored = rows.get(key) or []
        by = {(r.get("scope"), r.get("scope_id")): r for r in stored}
        row = None
        origin = "default"
        if project_id and ("project", project_id) in by:
            row, origin = by[("project", project_id)], "project"
        elif ("org", org_id) in by:
            row, origin = by[("org", org_id)], "org"
        item = dict(spec)
        item["group_label"] = GROUP_LABELS.get(spec["group"], spec["group"])
        item["default_value"] = spec["value"]
        item["value"] = row["value"] if row else spec["value"]
        item["origin"] = origin
        item["updated_by"] = (row or {}).get("updated_by")
        item["updated_at"] = (row or {}).get("updated_at")
        item["history_count"] = len((row or {}).get("history") or [])
        item["overrides"] = [{"scope": r.get("scope"), "scope_id": r.get("scope_id"),
                             "value": r.get("value")} for r in stored]
        out.append(item)
    out.sort(key=lambda x: (x["group"], x["key"]))
    return out


# ---------------------------------------------------------------- penulisan
async def set_value(key: str, value, *, actor: str, reason: str = None,
                    org_id: str = ORG_ID, scope: str = "org", scope_id: str = None) -> dict:
    spec = DEFAULTS.get(key)
    if not spec:
        raise ValueError(f"Setting tidak dikenal: {key}")
    if scope not in SCOPES:
        raise ValueError(f"Scope tidak valid: {scope}")
    scope_id = scope_id or (org_id if scope == "org" else None)
    if not scope_id:
        raise ValueError("scope_id wajib untuk scope project/cluster.")
    if spec.get("sensitive") and not (reason or "").strip():
        raise ValueError(f"'{spec['label']}' adalah setting sensitif — alasan wajib diisi.")
    value = coerce(spec, value)
    ts = now_iso()
    existing = await db.settings.find_one(
        {"org_id": org_id, "key": key, "scope": scope, "scope_id": scope_id}, {"_id": 0})
    entry = {"at": ts, "by": actor, "from": (existing or {}).get("value", spec["value"]),
             "to": value, "reason": (reason or "").strip() or None}
    if existing:
        await db.settings.update_one(
            {"org_id": org_id, "key": key, "scope": scope, "scope_id": scope_id},
            {"$set": {"value": value, "updated_by": actor, "updated_at": ts},
             "$push": {"history": {"$each": [entry], "$slice": -50}}})
    else:
        await db.settings.insert_one({
            "id": new_id(), "org_id": org_id, "key": key, "scope": scope, "scope_id": scope_id,
            "value": value, "type": spec["type"], "group": spec["group"],
            "updated_by": actor, "updated_at": ts, "created_at": ts, "history": [entry]})
    invalidate()
    logger.info("Setting %s (%s:%s) = %s oleh %s", key, scope, scope_id, value, actor)
    return {"key": key, "value": value, "scope": scope, "scope_id": scope_id, "entry": entry}


async def reset(key: str, *, actor: str, org_id: str = ORG_ID, scope: str = "org",
                scope_id: str = None) -> dict:
    spec = DEFAULTS.get(key)
    if not spec:
        raise ValueError(f"Setting tidak dikenal: {key}")
    scope_id = scope_id or (org_id if scope == "org" else None)
    res = await db.settings.delete_one(
        {"org_id": org_id, "key": key, "scope": scope, "scope_id": scope_id})
    invalidate()
    return {"key": key, "removed": res.deleted_count, "value": spec["value"]}


async def history(key: str, *, org_id: str = ORG_ID) -> list:
    rows = await db.settings.find({"org_id": org_id, "key": key}, {"_id": 0}).to_list(20)
    out = []
    for r in rows:
        for h in (r.get("history") or []):
            out.append({**h, "scope": r.get("scope"), "scope_id": r.get("scope_id")})
    out.sort(key=lambda x: x.get("at") or "", reverse=True)
    return out


async def groups_summary(*, org_id: str = ORG_ID) -> list:
    rows = await _rows(org_id)
    counts = {}
    for key, spec in DEFAULTS.items():
        g = counts.setdefault(spec["group"], {"group": spec["group"],
                                              "label": GROUP_LABELS.get(spec["group"], spec["group"]),
                                              "total": 0, "overridden": 0})
        g["total"] += 1
        if rows.get(key):
            g["overridden"] += 1
    return sorted(counts.values(), key=lambda x: x["label"])
