import React, { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { MessagesSquare, Send, Zap, Clock, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import StatusPill from "@/components/patterns/StatusPill";
import EmptyState from "@/components/patterns/EmptyState";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import InboxContextPanel from "@/components/omni/InboxContextPanel";
import { cn } from "@/lib/utils";
import { fromNow, formatDateTimeWIB } from "@/utils/formatters";
import api from "@/services/apiClient";
import { INBOX } from "@/constants/testIds";

const FILTERS = [
  { v: "all", l: "Semua", tid: INBOX.filterAll },
  { v: "mine", l: "Saya", tid: INBOX.filterMine },
  { v: "unanswered", l: "Belum dibalas", tid: INBOX.filterUnanswered },
];

export default function InboxPage() {
  const [convs, setConvs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [activeId, setActiveId] = useState(null);
  const [thread, setThread] = useState(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [tmplCode, setTmplCode] = useState("");
  const endRef = useRef(null);

  const loadConvs = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await api.get("/inbox", { params: { filter } });
      const rows = res.data.data || [];
      setConvs(rows);
      setActiveId((cur) => (cur && rows.some((c) => c.id === cur)) ? cur : (rows[0]?.id || null));
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat percakapan.");
    } finally { setLoading(false); }
  }, [filter]);

  const loadThread = useCallback(async (id) => {
    if (!id) { setThread(null); return; }
    try {
      const res = await api.get(`/inbox/${id}`);
      setThread(res.data.data);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch { toast.error("Gagal memuat pesan."); }
  }, []);

  useEffect(() => { loadConvs(); }, [loadConvs]);
  useEffect(() => { if (activeId) loadThread(activeId); else setThread(null); }, [activeId, loadThread]);
  useEffect(() => {
    api.get("/wa-templates").then((r) => setTemplates(r.data.data || [])).catch(() => {});
  }, []);

  const windowOpen = thread?.conversation?.window_open;

  const refresh = () => { loadThread(activeId); loadConvs(); };

  const send = async (direction) => {
    if (!text.trim() || !activeId) return;
    setBusy(true);
    try {
      await api.post(`/inbox/${activeId}/messages`, { body: text, direction });
      setText("");
      await loadThread(activeId);
      if (direction === "in") toast.success("Pesan masuk (simulasi) — automation rule diproses.");
      loadConvs();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal mengirim pesan."); }
    finally { setBusy(false); }
  };

  const sendTemplate = async () => {
    if (!tmplCode || !activeId) { toast.error("Pilih template terlebih dahulu."); return; }
    setBusy(true);
    try {
      await api.post(`/inbox/${activeId}/messages`, { body: "", direction: "out", template_code: tmplCode });
      setTmplCode("");
      toast.success("Template terkirim (simulasi).");
      await loadThread(activeId);
      loadConvs();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal mengirim template."); }
    finally { setBusy(false); }
  };

  return (
    <div data-testid={INBOX.page} className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <MessagesSquare className="h-5 w-5 text-primary" />
        <h1 className="font-heading text-xl font-semibold">Inbox WhatsApp</h1>
        <StatusPill status="simulation" />
        <div className="ml-auto flex gap-1">
          {FILTERS.map((f) => (
            <Button key={f.v} data-testid={f.tid} size="sm"
              variant={filter === f.v ? "default" : "outline"} onClick={() => setFilter(f.v)}>
              {f.l}
            </Button>
          ))}
        </div>
      </div>

      {loading ? <LoadingCards count={3} /> : error ? <ErrorState message={error} onRetry={loadConvs} /> :
        !convs.length ? (
          <EmptyState icon={MessagesSquare} title="Belum ada percakapan"
            description="Percakapan muncul saat ada lead masuk via WhatsApp (simulasi). Coba 'Simulasi Lead Masuk' di halaman Lead." />
        ) : (
          <div className="grid gap-4 md:grid-cols-4">
            {/* Conversation list */}
            <div className="space-y-2 md:col-span-1">
              {convs.map((c) => (
                <button key={c.id} data-testid={INBOX.convItem} onClick={() => setActiveId(c.id)}
                  className={cn("w-full rounded-xl border bg-card p-3 text-left transition-colors",
                    activeId === c.id ? "border-primary ring-1 ring-primary/30" : "hover:bg-secondary")}>
                  <div className="flex items-center justify-between">
                    <p className="truncate font-medium">{c.contact_name || c.contact_phone}</p>
                    {c.unread ? <span className="rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-foreground">{c.unread}</span> : null}
                  </div>
                  <p className="text-xs text-muted-foreground">{c.contact_phone}</p>
                  <div className="mt-1 flex items-center gap-2">
                    <span className={cn("inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium",
                      c.window_open ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700")}>
                      <Clock className="h-3 w-3" /> {c.window_open ? "Sesi aktif" : "Perlu template"}
                    </span>
                    {c.last_direction === "in" ? <span className="text-[10px] font-medium text-amber-600">Belum dibalas</span> : null}
                  </div>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {c.last_message_at ? fromNow(c.last_message_at) : "Belum ada pesan"}
                  </p>
                </button>
              ))}
            </div>

            {/* Thread */}
            <div data-testid={INBOX.thread} className="flex h-[560px] flex-col rounded-xl border bg-card md:col-span-2">
              {thread ? (
                <>
                  <div className="flex items-center justify-between border-b px-4 py-2.5">
                    <div>
                      <p className="font-medium">{thread.conversation.contact_name || thread.conversation.contact_phone}</p>
                      <p className="text-xs text-muted-foreground">{thread.conversation.contact_phone}</p>
                    </div>
                    <span data-testid={INBOX.windowBadge} className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                      windowOpen ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700")}>
                      <Clock className="h-3.5 w-3.5" /> {windowOpen ? "Sesi 24 jam aktif" : "Sesi tertutup"}
                    </span>
                  </div>
                  <div className="flex-1 space-y-2.5 overflow-y-auto p-4">
                    {thread.messages.map((m) => (
                      <div key={m.id} className={cn("flex", m.direction === "out" ? "justify-end" : "justify-start")}>
                        <div className={cn("max-w-[75%] rounded-2xl px-3 py-2 text-sm",
                          m.direction === "out" ? "bg-primary text-primary-foreground" : "bg-secondary")}>
                          {m.is_template ? (
                            <span className="mb-1 inline-block rounded bg-black/10 px-1.5 text-[10px] font-semibold uppercase">Template</span>
                          ) : null}
                          <p className="whitespace-pre-line">{m.body}</p>
                          <p className={cn("mt-1 text-[10px]", m.direction === "out" ? "text-primary-foreground/70" : "text-muted-foreground")}>
                            {formatDateTimeWIB(m.created_at)}
                          </p>
                        </div>
                      </div>
                    ))}
                    <div ref={endRef} />
                  </div>
                  <div className="border-t p-3">
                    {!windowOpen ? (
                      <div className="mb-2 flex items-center gap-1.5 rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-700">
                        <ShieldAlert className="h-3.5 w-3.5" /> Sesi 24 jam tertutup — mulai dengan template WA pra-approved.
                      </div>
                    ) : null}
                    <div className="mb-2 flex items-center gap-2">
                      <Select value={tmplCode} onValueChange={setTmplCode}>
                        <SelectTrigger data-testid={INBOX.templatePick} className="h-9">
                          <SelectValue placeholder="Kirim template…" />
                        </SelectTrigger>
                        <SelectContent>
                          {templates.map((t) => <SelectItem key={t.id} value={t.code}>{t.name}</SelectItem>)}
                        </SelectContent>
                      </Select>
                      <Button data-testid={INBOX.templateBtn} size="sm" variant="secondary"
                        onClick={sendTemplate} disabled={busy || !tmplCode}>Kirim Template</Button>
                    </div>
                    <Textarea data-testid={INBOX.messageInput} rows={2}
                      placeholder={windowOpen ? "Ketik balasan…" : "Sesi tertutup — gunakan template di atas"}
                      value={text} onChange={(e) => setText(e.target.value)} disabled={!windowOpen && true} />
                    <div className="mt-2 flex justify-between gap-2">
                      <Button data-testid={INBOX.simulateInbound} variant="outline" size="sm"
                        onClick={() => send("in")} disabled={busy || !text.trim()}>
                        <Zap className="mr-1.5 h-4 w-4" /> Kirim sbg Pesan Masuk
                      </Button>
                      <Button data-testid={INBOX.sendBtn} size="sm" onClick={() => send("out")}
                        disabled={busy || !text.trim() || !windowOpen}>
                        <Send className="mr-1.5 h-4 w-4" /> Balas
                      </Button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
                  Pilih percakapan
                </div>
              )}
            </div>

            {/* Context panel (lead + NBA) */}
            <div className="md:col-span-1">
              {thread ? (
                <InboxContextPanel leadId={thread.conversation.lead_id}
                  conversationId={thread.conversation.id} onChanged={refresh} />
              ) : (
                <div className="rounded-xl border bg-card p-4 text-sm text-muted-foreground">Konteks lead tampil di sini.</div>
              )}
            </div>
          </div>
        )}
    </div>
  );
}
