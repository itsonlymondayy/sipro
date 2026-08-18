{
  "product": {
    "name": "SIPRO",
    "tagline": "Property Development Operating System — Slack tapi ERP",
    "language": "id-ID",
    "design_personality": {
      "keywords": [
        "modern SaaS",
        "light-first",
        "tenang",
        "padat-informasi namun lapang",
        "guided",
        "audit-ready",
        "mobile-first untuk lapangan",
        "desktop-rich untuk back-office"
      ],
      "anti_patterns": [
        "glassmorphism/backdrop-blur",
        "gradient gelap/saturated",
        "layout serba center",
        "menu modul sebagai landing",
        "tabel tanpa empty/loading/error",
        "ikon emoji"
      ]
    }
  },

  "information_architecture": {
    "north_star": "Buka aplikasi = melihat 'Hari Saya' (Work Hub), bukan menu modul.",
    "principles": [
      "Flow-based, bukan module-based (pintu masuk = pekerjaan).",
      "Role-tailored home + navigasi config-driven.",
      "Progressive disclosure: detail muncul on-demand sesuai peran.",
      "Wayfinding kuat: breadcrumb + Process Timeline lintas-modul.",
      "Aksi terjadi di konteks data (drawer/sidepanel), minim pindah halaman.",
      "Status data jujur: loading/empty/error di semua area data (gate ux_audit.py)."
    ],
    "app_shell": {
      "layout": {
        "desktop": "Sidebar kiri (grouped) + TopBar + Content area; panel kanan opsional untuk detail/context.",
        "mobile": "Bottom sheet/drawer untuk nav; TopBar ringkas; content full-width; panel kanan menjadi sheet." 
      },
      "topbar": {
        "structure": [
          "kicker (nama area/role)",
          "judul halaman",
          "global search (Command)",
          "notifikasi",
          "profil + switch role (dev-only)"
        ],
        "behavior": [
          "TopBar sticky pada desktop untuk halaman data-dense.",
          "Search membuka Command palette (⌘K / Ctrl+K)."
        ]
      },
      "sidebar": {
        "rules": [
          "Config-driven groups (Work, Penjualan, Proyek, Keuangan, Dokumen, Admin).",
          "Item 'Segera Hadir' tampil disabled dengan badge 'Segera Hadir' (jujur).",
          "Active state jelas + indikator lokasi (breadcrumb)."
        ]
      }
    },
    "role_homes": {
      "sales": {
        "title": "Hari Saya",
        "primary_blocks": [
          "KPI strip (lead baru, follow-up due, appointment hari ini, deal aktif, komisi MTD)",
          "Task Inbox (Terlambat/Hari ini/Akan datang/Menunggu saya) + SLA countdown",
          "Next-Best-Action cards",
          "Quick actions (Buat appointment, Kirim template WA, Cek unit)"
        ]
      },
      "sales_manager": {
        "title": "Performa Tim",
        "primary_blocks": [
          "KPI strip (SLA tim, lead masuk, appointment, booking, win rate)",
          "Funnel + leaderboard + mission",
          "Approval inbox",
          "Task Inbox (tim)"
        ]
      },
      "finance": {
        "title": "Keuangan",
        "primary_blocks": [
          "AR aging buckets",
          "Cash-flow projection",
          "AP/retensi due",
          "Worklist penagihan"
        ]
      },
      "project": {
        "title": "Proyek",
        "primary_blocks": [
          "Kurva-S (plan vs aktual) + deviasi",
          "Termin due + QC gate",
          "Punch list (defect open)",
          "Material opname alert"
        ]
      },
      "owner": {
        "title": "Control Tower",
        "primary_blocks": [
          "Penjualan hari/MTD",
          "Kas + AR/AP ringkas",
          "Approval pending",
          "Progress proyek + RevRec vs Contract Liability"
        ]
      }
    },
    "wayfinding": {
      "breadcrumb": {
        "rule": "Selalu tampil untuk halaman detail (Lead/Deal/Unit/Project/Doc).",
        "pattern": "Home > Penjualan > Lead > {Nama Lead}"
      },
      "process_timeline": {
        "rule": "Tampilkan rantai dokumen/proses di record kunci (Lead/Deal/Unit/Work Package).",
        "examples": [
          "Lead → Appointment → SPR → PPJB → KPR → BAST → AJB → Komisi",
          "BoQ/RAB → SPK → Termin → QC → Change Order → BAST → Retensi"
        ]
      }
    }
  },

  "visual_system": {
    "typography": {
      "font_pairing": {
        "heading": {
          "family": "Space Grotesk",
          "fallback": "ui-sans-serif, system-ui",
          "notes": "Heading terasa modern & premium tanpa vibe iOS-glass."
        },
        "body": {
          "family": "Inter",
          "fallback": "ui-sans-serif, system-ui",
          "notes": "Body sangat readable untuk data-dense."
        },
        "mono": {
          "family": "Roboto Mono",
          "usage": "ID transaksi, nomor dokumen, kode unit"
        }
      },
      "tailwind_usage": {
        "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
        "h2": "text-base md:text-lg font-medium text-muted-foreground",
        "body": "text-sm md:text-base leading-6",
        "small": "text-xs text-muted-foreground",
        "numbers": "tabular-nums"
      }
    },

    "color_system": {
      "brand_intent": "Trust + clarity (finance-safe), dengan aksen teal untuk 'guided action' dan amber untuk 'deadline/SLA'.",
      "tokens_css_variables": {
        "note": "Gunakan HSL tokens ala shadcn, tapi ganti nilai default agar lebih matang. Hindari gradient gelap/saturated.",
        "light": {
          "--background": "36 33% 98%",
          "--foreground": "222 47% 11%",
          "--card": "0 0% 100%",
          "--card-foreground": "222 47% 11%",
          "--popover": "0 0% 100%",
          "--popover-foreground": "222 47% 11%",

          "--primary": "196 84% 34%",
          "--primary-foreground": "0 0% 100%",

          "--secondary": "210 20% 96%",
          "--secondary-foreground": "222 47% 11%",

          "--muted": "210 20% 96%",
          "--muted-foreground": "215 16% 40%",

          "--accent": "174 55% 92%",
          "--accent-foreground": "196 84% 20%",

          "--destructive": "0 72% 52%",
          "--destructive-foreground": "0 0% 100%",

          "--border": "214 20% 90%",
          "--input": "214 20% 90%",
          "--ring": "196 84% 34%",

          "--radius": "0.75rem",

          "--chart-1": "196 84% 34%",
          "--chart-2": "28 90% 55%",
          "--chart-3": "152 55% 38%",
          "--chart-4": "222 47% 35%",
          "--chart-5": "0 72% 52%"
        },
        "dark_ready": {
          "note": "Opsional. Jangan pakai background transparan dengan teks gelap. Pastikan AA.",
          "--background": "222 47% 7%",
          "--foreground": "210 40% 98%",
          "--card": "222 47% 9%",
          "--card-foreground": "210 40% 98%",
          "--popover": "222 47% 9%",
          "--popover-foreground": "210 40% 98%",

          "--primary": "196 84% 45%",
          "--primary-foreground": "222 47% 7%",

          "--secondary": "217 19% 16%",
          "--secondary-foreground": "210 40% 98%",

          "--muted": "217 19% 16%",
          "--muted-foreground": "215 20% 70%",

          "--accent": "196 40% 18%",
          "--accent-foreground": "196 84% 70%",

          "--destructive": "0 62% 40%",
          "--destructive-foreground": "210 40% 98%",

          "--border": "217 19% 16%",
          "--input": "217 19% 16%",
          "--ring": "196 84% 45%"
        }
      },
      "semantic_status_tokens": {
        "note": "StatusPill wajib pakai kelas status-* agar konsisten lintas domain.",
        "classes": {
          "status-available": "bg-emerald-50 text-emerald-800 border-emerald-200",
          "status-holding": "bg-amber-50 text-amber-900 border-amber-200",
          "status-reserved": "bg-sky-50 text-sky-800 border-sky-200",
          "status-booked": "bg-indigo-50 text-indigo-800 border-indigo-200",
          "status-sold": "bg-slate-100 text-slate-800 border-slate-200",

          "status-overdue": "bg-rose-50 text-rose-800 border-rose-200",
          "status-due-today": "bg-amber-50 text-amber-900 border-amber-200",
          "status-on-track": "bg-emerald-50 text-emerald-800 border-emerald-200",

          "status-simulation": "bg-zinc-50 text-zinc-700 border-zinc-200"
        }
      },
      "gradients_and_texture": {
        "rule": "Gradien hanya untuk background section dekoratif (maks 20% viewport). Tidak untuk area baca/tabel.",
        "allowed_examples": [
          "bg-[radial-gradient(1200px_circle_at_20%_0%,hsl(var(--accent))_0%,transparent_55%)]",
          "bg-[linear-gradient(135deg,rgba(13,148,136,0.10)_0%,rgba(2,132,199,0.06)_45%,transparent_70%)]"
        ],
        "noise": {
          "usage": "Tambahkan noise halus di background app shell agar tidak flat.",
          "css_snippet": ".app-noise{background-image:url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"160\" height=\"160\"><filter id=\"n\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"0.8\" numOctaves=\"3\" stitchTiles=\"stitch\"/></filter><rect width=\"160\" height=\"160\" filter=\"url(%23n)\" opacity=\"0.035\"/></svg>');}"
        }
      }
    },

    "spacing_grid": {
      "system": "4pt base (Tailwind default).",
      "layout_gutters": {
        "mobile": "px-4",
        "tablet": "px-6",
        "desktop": "px-8"
      },
      "content_width": {
        "rule": "Untuk halaman baca panjang (dokumen/portal), batasi lebar konten.",
        "class": "max-w-6xl"
      }
    },

    "radius_elevation": {
      "radius": {
        "card": "rounded-xl",
        "button": "rounded-lg",
        "pill": "rounded-full"
      },
      "shadows": {
        "card": "shadow-sm hover:shadow-md",
        "floating_panel": "shadow-lg",
        "focus": "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      }
    },

    "motion": {
      "principles": [
        "Micro-interactions wajib: hover, pressed, focus, loading.",
        "Gunakan durasi pendek (120–180ms) untuk UI; 220–320ms untuk panel/drawer.",
        "Hormati prefers-reduced-motion."
      ],
      "tailwind_patterns": {
        "button": "transition-colors duration-150",
        "card_hover": "transition-shadow duration-200",
        "drawer": "data-[state=open]:animate-in data-[state=closed]:animate-out"
      },
      "recommended_library": {
        "name": "framer-motion",
        "why": "Untuk animasi masuk TaskCard/NBA, reorder Kanban, dan panel transitions yang halus.",
        "install": "npm i framer-motion",
        "usage_note": "Gunakan hanya pada area yang butuh (jangan global)."
      }
    }
  },

  "component_library": {
    "component_path": {
      "shadcn_ui": "/app/frontend/src/components/ui",
      "primary_components": [
        "button.jsx",
        "badge.jsx",
        "card.jsx",
        "tabs.jsx",
        "table.jsx",
        "skeleton.jsx",
        "drawer.jsx",
        "sheet.jsx",
        "dialog.jsx",
        "breadcrumb.jsx",
        "command.jsx",
        "scroll-area.jsx",
        "resizable.jsx",
        "separator.jsx",
        "tooltip.jsx",
        "popover.jsx",
        "calendar.jsx",
        "progress.jsx",
        "sonner.jsx"
      ]
    },

    "patterns_to_build": {
      "note": "Semua contoh untuk React .js (bukan .tsx). Semua elemen interaktif & info kritis wajib data-testid (kebab-case).",

      "MetricCard": {
        "purpose": "KPI strip di Role-Home.",
        "composition": ["Card", "Badge", "Tooltip"],
        "layout": "Grid 2 kolom mobile → 5 kolom desktop.",
        "classes": "rounded-xl border bg-card p-4",
        "data_testid": ["metric-card", "metric-card-value", "metric-card-label"]
      },

      "StatusPill": {
        "purpose": "Status domain (unit, task, invoice, window WA, SIMULASI).",
        "composition": ["Badge"],
        "rules": [
          "Gunakan kelas status-* dari semantic_status_tokens.",
          "Ukuran kecil, tabular-nums untuk angka (mis. H-3)."
        ],
        "data_testid": ["status-pill"]
      },

      "DataTable": {
        "purpose": "Tabel ERP (finance/material/opname) dengan state lengkap.",
        "composition": ["Table", "Skeleton", "Pagination"],
        "rules": [
          "Header sticky untuk tabel panjang.",
          "Kolom uang rata kanan + tabular-nums.",
          "Selisih/variance negatif sorot (bg-rose-50)."
        ],
        "states": {
          "loading": "Skeleton rows",
          "empty": "EmptyState edukatif + CTA",
          "error": "Alert + tombol coba lagi"
        },
        "data_testid": ["data-table", "data-table-retry-button"]
      },

      "DetailDrawer_or_SidePanel": {
        "purpose": "Progressive disclosure: detail record + aksi terpandu tanpa pindah halaman.",
        "composition": ["Drawer (mobile)", "Sheet (desktop)", "Tabs"],
        "rules": [
          "Mobile: Drawer dari bawah.",
          "Desktop: Sheet dari kanan (w-\"480px\" atau resizable).",
          "Header panel selalu menampilkan: nama record + status + CTA utama."
        ],
        "data_testid": ["detail-panel", "detail-panel-close-button"]
      },

      "Timeline_ProcessTimeline": {
        "purpose": "Rantai dokumen lintas-modul (Lead→...→Komisi).",
        "composition": ["Separator", "Badge", "Tooltip"],
        "rules": [
          "Step clickable (deep-link).",
          "Step state: done/current/blocked.",
          "Tampilkan due date & gate (mis. PPJB ≤30 hari)."
        ],
        "data_testid": ["process-timeline"]
      },

      "TaskCard": {
        "purpose": "Unit utama Work Hub.",
        "composition": ["Card", "Button", "Badge", "Tooltip"],
        "fields": ["judul", "tipe", "prioritas", "related record chip", "SLA countdown", "CTA guided"],
        "interaction": [
          "Klik card membuka DetailDrawer.",
          "CTA utama menjalankan guided action (form) dan auto-log activity.",
          "Snooze membuka Popover preset (1 jam, besok, minggu depan)."
        ],
        "data_testid": [
          "task-card",
          "task-card-open-button",
          "task-card-complete-button",
          "task-card-snooze-button",
          "task-card-sla"
        ]
      },

      "ActivityItem": {
        "purpose": "Feed item (system-event + komentar + @mention + thread).",
        "composition": ["Avatar", "Card", "Button", "Textarea"],
        "rules": [
          "System-event tampil lebih ringkas (ikon + teks).",
          "Komentar mendukung @mention (Command/Popover).",
          "Thread: collapsible replies."
        ],
        "data_testid": ["activity-item", "activity-reply-button", "activity-mention-input"]
      },

      "NBACard": {
        "purpose": "Next-Best-Action (1–3 aksi) di Home & record detail.",
        "composition": ["Card", "Button", "Badge"],
        "rules": [
          "Selalu ada alasan singkat (why) + dampak (impact).",
          "CTA satu klik membuka guided flow.",
          "Auto-expire bila sudah tidak relevan."
        ],
        "data_testid": ["nba-card", "nba-card-primary-action"]
      },

      "Stepper_SPR_PPJB": {
        "purpose": "Checkout legal (reservasi/SPR/PPJB) dengan gate.",
        "composition": ["Tabs atau custom stepper + Progress"],
        "rules": [
          "Step label Bahasa Indonesia baku.",
          "Tampilkan prasyarat sebagai checklist.",
          "Step blocked menampilkan alasan + CTA untuk memenuhi syarat."
        ],
        "data_testid": ["legal-stepper"]
      },

      "KanbanBoard": {
        "purpose": "Lead pipeline & task board.",
        "composition": ["ScrollArea", "Card", "Badge"],
        "recommended_library": {
          "name": "@dnd-kit/core",
          "install": "npm i @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities",
          "why": "Drag-drop yang stabil untuk Kanban (lebih ringan dari react-beautiful-dnd)."
        },
        "rules": [
          "Kolom fixed width (w-72) + horizontal scroll di mobile.",
          "Card ringkas: nama, skor, SLA, owner.",
          "Drop action memicu confirm bila stage sensitif (human-in-the-loop)."
        ],
        "data_testid": ["kanban-board", "kanban-column", "kanban-card"]
      },

      "OmnichannelInbox_3Column": {
        "purpose": "WhatsApp Inbox in-app (list | thread | context).",
        "layout": {
          "desktop": "Resizables: left 320px, center fluid, right 360px.",
          "mobile": "Stack: list → thread; context jadi Sheet dari kanan/bawah."
        },
        "composition": ["Resizable", "ScrollArea", "Tabs", "Textarea", "Button", "Badge"],
        "key_ui": [
          "Badge window 24 jam (aktif/perlu template)",
          "Composer: text + template picker + attachment",
          "Panel konteks: stage + NBA + tombol 'Majukan stage'",
          "Catatan internal (is_internal) + @mention"
        ],
        "data_testid": [
          "inbox-conversation-list",
          "inbox-thread",
          "inbox-composer-input",
          "inbox-send-button",
          "inbox-window-badge",
          "inbox-context-panel",
          "inbox-advance-stage-button"
        ]
      },

      "ChatBubble_and_Composer": {
        "purpose": "Bubble in/out + status sent/delivered/read + media.",
        "rules": [
          "Bubble max-w-[78%] agar readable.",
          "Gunakan warna netral (in: bg-muted, out: bg-accent) — bukan hijau WA literal.",
          "Status kecil (text-xs) + tabular-nums untuk jam."
        ],
        "data_testid": ["chat-bubble", "chat-composer"]
      },

      "ProgressBar_Weighted": {
        "purpose": "Progress konstruksi berbobot (phase/task).",
        "composition": ["Progress", "Tooltip"],
        "rules": [
          "Tampilkan plan vs actual (dua bar) bila tersedia.",
          "Deviasi negatif sorot amber/rose.",
          "Klik membuka breakdown fase."
        ],
        "data_testid": ["weighted-progress"]
      },

      "KurvaS_Chart": {
        "purpose": "Kurva-S plan vs aktual.",
        "recommended_library": {
          "name": "recharts",
          "install": "npm i recharts",
          "why": "Chart cepat untuk dashboard; cocok untuk line/area plan vs actual."
        },
        "rules": [
          "Gunakan grid halus + tooltip jelas.",
          "Legend ringkas.",
          "Empty state: jelaskan cara input baseline plan."
        ],
        "data_testid": ["kurva-s-chart"]
      },

      "AgingBucketCards": {
        "purpose": "AR aging buckets (0–30, 31–60, 61–90, >90).",
        "composition": ["Card", "Button"],
        "rules": [
          "Klik bucket memfilter tabel worklist.",
          "Angka rata kanan + tabular-nums.",
          "Bucket >90 hari gunakan status-overdue."
        ],
        "data_testid": ["aging-bucket"]
      },

      "SignaturePad": {
        "purpose": "Tanda tangan digital (canvas) untuk dokumen.",
        "recommended_library": {
          "name": "signature_pad",
          "install": "npm i signature_pad",
          "why": "Canvas signature sederhana dan stabil."
        },
        "rules": [
          "Sediakan tombol: Bersihkan, Simpan.",
          "Tampilkan preview sebelum finalize.",
          "Mobile: area tanda tangan minimal tinggi 180px."
        ],
        "data_testid": ["signature-pad", "signature-clear-button", "signature-save-button"]
      },

      "PhotoPin": {
        "purpose": "Foto ber-lokasi untuk QC/punch list.",
        "composition": ["Card", "AspectRatio", "Badge"],
        "rules": [
          "Tampilkan metadata: waktu, lokasi (jika ada), unit/proyek.",
          "Klik membuka viewer (Dialog) + carousel."
        ],
        "data_testid": ["photo-pin"]
      },

      "EmptyState": {
        "purpose": "Empty state edukatif + CTA (wajib untuk semua area data).",
        "composition": ["Card", "Button"],
        "rules": [
          "Judul: apa yang kosong.",
          "Deskripsi: kenapa penting.",
          "CTA: aksi pertama (mis. 'Hubungkan WhatsApp', 'Tambah baseline Kurva-S').",
          "Jika fitur belum live, tampilkan badge 'SIMULASI'."
        ],
        "data_testid": ["empty-state", "empty-state-primary-cta"]
      }
    }
  },

  "layout_blueprints": {
    "work_hub": {
      "desktop_layout": "2 kolom: kiri Task Inbox (60%) + kanan NBA/Activity (40%).",
      "mobile_layout": "Tabs: Tugas | Aktivitas | Rekomendasi; Task detail via Drawer.",
      "task_groups": ["Terlambat", "Hari ini", "Akan datang", "Menunggu saya"],
      "sla_visual": {
        "rule": "SLA countdown selalu terlihat pada task yang punya sla_due_at.",
        "colors": "On-track=emerald, due-today=amber, overdue=rose"
      }
    },
    "record_detail": {
      "structure": [
        "Header: nama + status + CTA utama",
        "Process Timeline (horizontal scroll di mobile)",
        "Tabs: Ringkasan | Aktivitas | Chat | Dokumen",
        "SidePanel: NBA + atribut penting (progressive disclosure)"
      ]
    },
    "inbox": {
      "desktop": "3 kolom resizable (list | thread | context).",
      "mobile": "List → Thread; Context via Sheet; Composer sticky bottom.",
      "window_24h": "Badge jelas: 'Sesi aktif' vs 'Perlu template'."
    },
    "kanban": {
      "desktop": "Horizontal scroll container; kolom w-72; header sticky.",
      "mobile": "Swipe horizontal; quick filter chips di atas."
    },
    "finance_tables": {
      "rules": [
        "Kolom uang rata kanan + tabular-nums.",
        "Gunakan zebra halus (bg-muted/30) untuk keterbacaan.",
        "Row hover hanya ubah bg (bukan transform)."
      ]
    },
    "field_mobile": {
      "rules": [
        "CTA utama selalu reachable (sticky bottom bar) untuk aksi lapangan: 'Tambah foto', 'Buat defect', 'Submit opname'.",
        "Form input besar, label jelas, minim dropdown panjang.",
        "Offline-ready nanti: tampilkan indikator koneksi + queue (fase lanjut)."
      ]
    },
    "customer_portal": {
      "tone": "lebih hangat & reassuring, tetap modern SaaS.",
      "layout": "Single-column max-w-3xl; progress + foto + jadwal bayar + dokumen + komplain.",
      "cta": "Komplain / Ajukan pertanyaan (SLA terlihat)."
    }
  },

  "states_and_feedback": {
    "global_rules": [
      "Setiap area data wajib punya: loading, empty (edukatif + CTA), error (jelas + retry).",
      "Gunakan Sonner untuk toast (success/error) — jangan toast custom.",
      "Untuk aksi penting (advance stage, bayar, sign): gunakan AlertDialog konfirmasi."
    ],
    "loading": {
      "pattern": "Skeleton sesuai bentuk konten (bukan spinner tengah).",
      "data_testid": ["loading-skeleton"]
    },
    "empty": {
      "pattern": "EmptyState dengan CTA + link dokumentasi singkat.",
      "data_testid": ["empty-state"]
    },
    "error": {
      "pattern": "Alert dengan pesan Bahasa Indonesia baku + tombol 'Coba lagi'.",
      "data_testid": ["error-alert", "error-retry-button"]
    }
  },

  "accessibility": {
    "wcag": "AA",
    "rules": [
      "Kontras teks minimal AA (hindari teks abu terlalu muda).",
      "Focus ring selalu terlihat (gunakan --ring).",
      "Target sentuh minimal 44px untuk mobile.",
      "Gunakan aria-label untuk ikon-only buttons.",
      "Hormati prefers-reduced-motion."
    ],
    "numbers_finance": {
      "rules": [
        "Format Rupiah (IDR) konsisten.",
        "Gunakan tabular-nums.",
        "Rata kanan di tabel.",
        "Tampilkan minus/overdue dengan warna semantic (rose) + ikon kecil (lucide)."
      ]
    }
  },

  "image_urls": {
    "note": "SIPRO adalah ERP; minim foto. Gunakan ilustrasi ringan untuk empty state & portal. Jika butuh, gunakan Lottie (opsional) atau SVG internal.",
    "categories": [
      {
        "category": "empty_state_illustrations",
        "description": "Ilustrasi netral (dokumen, checklist, chat) untuk empty state edukatif.",
        "urls": []
      },
      {
        "category": "customer_portal_hero",
        "description": "Foto perumahan/cluster Indonesia untuk portal publik (opsional).",
        "urls": []
      }
    ]
  },

  "implementation_notes_for_main_agent": {
    "css_files_to_update": [
      "/app/frontend/src/index.css",
      "/app/frontend/src/App.css"
    ],
    "token_application": [
      "Ganti tokens :root di index.css sesuai tokens_css_variables.light.",
      "Hapus styling CRA default di App.css (App-header gelap) dan ganti dengan utilitas Tailwind di komponen.",
      "Tambahkan class helper untuk noise background (app-noise) dan gunakan hanya di shell background (bukan card)."
    ],
    "data_testid_policy": {
      "rule": "Semua elemen interaktif & info kritis wajib data-testid kebab-case.",
      "examples": [
        "data-testid=\"work-hub-task-complete-button\"",
        "data-testid=\"finance-ar-aging-total\"",
        "data-testid=\"inbox-send-button\""
      ]
    },
    "mocking_policy": {
      "rule": "Jika integrasi WA/Ads belum live, UI wajib menandai 'SIMULASI' menggunakan StatusPill status-simulation.",
      "do_not": "Jangan tampilkan seolah live."
    }
  },

  "General UI UX Design Guidelines": "    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals."
}
