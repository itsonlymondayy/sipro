// offlineSync — MESIN ANTREAN kerja lapangan (Fase 35).
//
// Aturan yang dijaga di sini:
//  * Aksi & foto tersimpan dulu di perangkat, terkirim sendiri saat jaringan kembali.
//  * Tidak ada pengajuan DOBEL: setiap pekerjaan antrean punya `client_ref` dan backend
//    memutar ulang hasil lama bila ref itu sudah pernah diterima.
//  * Antrean tidak pernah berbohong: kalau server MENOLAK (mis. gerbang mutu terkunci),
//    statusnya jadi "ditolak" beserta alasan asli server — bukti TIDAK dihapus.
import api from "@/services/apiClient";
import * as odb from "@/utils/offlineDb";

const listeners = new Set();
let flushing = false;

const uid = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
const iso = () => new Date().toISOString();

// Label antrean TIDAK ditulis di sini: kamus datanya ada di SSOT `/api/reference`
// (grup `offline_queue_kind` & `offline_queue_status`) dan dibaca lewat useReference()
// di panel antrean, supaya tidak ada dua versi label untuk hal yang sama.

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function ping() {
  listeners.forEach((f) => {
    try { f(); } catch { /* pendengar rusak tidak boleh menghentikan antrean */ }
  });
}

export function isOnline() {
  return typeof navigator === "undefined" ? true : navigator.onLine !== false;
}

/** Simpan foto di perangkat; kembalikan id lokal `local:<id>` untuk dipakai UI. */
export async function storePhoto({ blob, name, type, ownerId, watermark, geo }) {
  const id = `local:${uid()}`;
  await odb.putBlob({ id, blob, name: name || "foto.jpg", type: type || "image/jpeg",
    owner_id: ownerId || null, watermark: watermark || null, geo: geo || null,
    created_at: iso() });
  return id;
}

export function isLocalPhoto(id) {
  return String(id || "").startsWith("local:");
}

export async function queueSubmit({ item, note, checklist, geo, photos }) {
  const job = {
    id: uid(), kind: "build_submit", client_ref: `q-${uid()}`,
    item_id: item.id, unit_code: item.unit_code, step_code: item.step_code,
    name: item.name, payload: { note, checklist: checklist || [], geo: geo || null },
    photos: photos || [], status: "pending", attempts: 0, last_error: null,
    created_at: iso(),
  };
  await odb.putJob(job);
  ping();
  return job;
}

export async function queueStart(item) {
  const job = {
    id: uid(), kind: "build_start", client_ref: `q-${uid()}`,
    item_id: item.id, unit_code: item.unit_code, step_code: item.step_code,
    name: item.name, payload: {}, photos: [], status: "pending", attempts: 0,
    last_error: null, created_at: iso(),
  };
  await odb.putJob(job);
  ping();
  return job;
}

export async function list() {
  if (!odb.supported()) return [];
  try { return await odb.listJobs(); } catch { return []; }
}

export async function remove(id) {
  await odb.deleteJob(id);
  ping();
}

export async function retry(id) {
  const job = await odb.getJob(id);
  if (!job) return;
  await odb.putJob({ ...job, status: "pending", last_error: null });
  ping();
  return flush({ force: true });
}

async function uploadPhotos(job) {
  const ids = [];
  for (const pid of job.photos || []) {
    if (!isLocalPhoto(pid)) { ids.push(pid); continue; }
    const rec = await odb.getBlob(pid);
    if (!rec) continue;                       // sudah terunggah pada percobaan sebelumnya
    const fd = new FormData();
    fd.append("file", rec.blob, rec.name);
    fd.append("owner_type", "build");
    if (rec.owner_id) fd.append("owner_id", rec.owner_id);
    if (rec.watermark) fd.append("watermark", rec.watermark);
    if (rec.geo?.lat && rec.geo?.lng) {
      fd.append("lat", rec.geo.lat);
      fd.append("lng", rec.geo.lng);
      if (rec.geo.accuracy) fd.append("accuracy", rec.geo.accuracy);
      if (rec.geo.captured_at) fd.append("captured_at", rec.geo.captured_at);
    }
    const res = await api.post("/files/upload", fd);
    const newId = res.data?.data?.id;
    if (!newId) throw new Error("Server tidak mengembalikan id berkas.");
    ids.push(newId);
    // Ganti id lokal dengan id nyata SEKARANG supaya percobaan berikutnya tidak
    // mengunggah foto yang sama dua kali (bukti ganda = audit kotor).
    const swapped = (job.photos || []).map((p) => (p === pid ? newId : p));
    await odb.putJob({ ...job, photos: swapped });
    job.photos = swapped;
    await odb.deleteBlob(pid);
  }
  return ids;
}

async function send(job) {
  const ids = await uploadPhotos(job);
  if (job.kind === "build_submit") {
    await api.post(`/build/items/${job.item_id}/submit`, {
      note: job.payload.note,
      photo_file_ids: ids,
      geo: job.payload.geo || null,
      checklist: job.payload.checklist || [],
      client_ref: job.client_ref,
    });
    return;
  }
  if (job.kind === "build_start") {
    await api.post(`/build/items/${job.item_id}/start`);
  }
}

/** Kirim seluruh antrean. Aman dipanggil berkali-kali (tidak tumpang tindih). */
export async function flush() {
  if (flushing || !isOnline() || !odb.supported()) return { sent: 0, failed: 0 };
  flushing = true;
  let sent = 0;
  let failed = 0;
  try {
    const jobs = (await list()).filter((j) => j.status === "pending");
    for (const job of jobs) {
      await odb.putJob({ ...job, status: "sending", last_error: null });
      ping();
      try {
        await send(job);
        await odb.deleteJob(job.id);
        sent += 1;
      } catch (e) {
        const status = e?.response?.status;
        const detail = e?.response?.data?.detail || e?.message || "Gagal mengirim.";
        const fresh = (await odb.getJob(job.id)) || job;
        if (status && status >= 400 && status < 500) {
          // Server menolak dengan ALASAN (aturan Fase 31/32 tetap berlaku): tampilkan
          // apa adanya, jangan buang buktinya.
          await odb.putJob({ ...fresh, status: "rejected", last_error: detail,
            attempts: (fresh.attempts || 0) + 1 });
        } else {
          await odb.putJob({ ...fresh, status: "pending", last_error: detail,
            attempts: (fresh.attempts || 0) + 1 });
        }
        failed += 1;
        ping();
        if (!isOnline()) break;
      }
    }
  } finally {
    flushing = false;
    ping();
  }
  return { sent, failed };
}
