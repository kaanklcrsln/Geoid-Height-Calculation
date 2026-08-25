"""Geoider - arazi yuzeyi uzerinde nokta ekleme ve yukseklik farki hesaplama arayuzu."""
import importlib
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from scipy.interpolate import griddata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
design = importlib.import_module("Geoid-Height-Calculation").design

GRID = 160          # yuzey enterpolasyonu icin izgara cozunurlugu
PICK_PX = 12        # bir noktayi "secili" saymak icin piksel toleransi


class Geoider(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Geoider")
        self.geometry("1180x760")
        self.minsize(940, 620)

        self.points = pd.DataFrame(columns=["ad", "x", "y", "h"])
        self.selection = []          # secili nokta indeksleri (en fazla 2)
        self.geoid = None            # (katsayilar, x0, y0, m0) - geoid modeli varsa

        self._build_ui()
        self._load_default_data()

    # ---------------------------------------------------------------- arayuz
    def _build_ui(self):
        root = ttk.Panedwindow(self, orient="horizontal")
        root.pack(fill="both", expand=True, padx=8, pady=8)

        # --- sol: arazi gorseli
        left = ttk.Frame(root)
        root.add(left, weight=3)

        self.fig = Figure(figsize=(7, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=left)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, left)
        self.toolbar.update()
        self.canvas.mpl_connect("button_press_event", self._on_click)

        # --- sag: kontrol paneli
        right = ttk.Frame(root)
        root.add(right, weight=2)

        # girdi kutulari
        inp = ttk.LabelFrame(right, text="Girdi - Nokta Ekle")
        inp.pack(fill="x", padx=6, pady=(0, 6))

        self.e_ad = self._field(inp, "Ad", 0)
        self.e_x = self._field(inp, "X (dogu, m)", 1)
        self.e_y = self._field(inp, "Y (kuzey, m)", 2)
        self.e_h = self._field(inp, "Yukseklik h (m)", 3)
        self.e_h.bind("<Return>", lambda _e: self.add_point())

        btns = ttk.Frame(inp)
        btns.grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=6)
        ttk.Button(btns, text="Ekle", command=self.add_point).pack(side="left")
        ttk.Button(btns, text="Sec", command=self.select_typed).pack(side="left", padx=4)
        ttk.Button(btns, text="Sil", command=self.delete_selected).pack(side="left")
        ttk.Button(btns, text="Secimi Temizle",
                   command=self.clear_selection).pack(side="left", padx=4)

        ttk.Label(
            inp,
            text="Ipucu: haritaya sol tikla konum al, sag tikla nokta sec (2 nokta).",
            foreground="#555", wraplength=340, justify="left",
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6))
        inp.columnconfigure(1, weight=1)

        # nokta listesi
        lst = ttk.LabelFrame(right, text="Noktalar")
        lst.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree = ttk.Treeview(
            lst, columns=("ad", "x", "y", "h"), show="headings", height=9,
            selectmode="extended",
        )
        for col, txt, w in [("ad", "Ad", 70), ("x", "X", 95),
                            ("y", "Y", 105), ("h", "h (m)", 80)]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="w" if col == "ad" else "e")
        self.tree.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(lst, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # cikti kutusu
        out = ttk.LabelFrame(right, text="Cikti - Yukseklik Farki")
        out.pack(fill="x", padx=6, pady=6)
        self.txt = tk.Text(out, height=12, wrap="word", font=("Consolas", 9))
        self.txt.pack(fill="both", expand=True, padx=6, pady=6)
        self.txt.configure(state="disabled")

        # alt butonlar
        bar = ttk.Frame(right)
        bar.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(bar, text="Fark Hesapla", command=self.compute).pack(side="left")
        ttk.Button(bar, text="CSV Yukle", command=self.load_csv).pack(side="left", padx=4)
        ttk.Button(bar, text="CSV Kaydet", command=self.save_csv).pack(side="left")

        self.status = tk.StringVar(value="Hazir")
        ttk.Label(self, textvariable=self.status, relief="sunken",
                  anchor="w").pack(fill="x", side="bottom")

    def _field(self, parent, label, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=3)
        e = ttk.Entry(parent)
        e.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
        return e

    # ----------------------------------------------------------------- veri
    def _load_default_data(self):
        """Repodaki known_stations.csv varsa arazi zemini olarak yukle, geoid modelini kur."""
        path = os.path.join(HERE, "known_stations.csv")
        try:
            known = pd.read_csv(path)
        except Exception:
            self._log("known_stations.csv bulunamadi. Nokta ekleyerek baslayin.")
            self.redraw()
            return

        self.points = pd.DataFrame({
            "ad": [f"N{i + 1}" for i in range(len(known))],
            "x": known.x, "y": known.y, "h": known.h,
        })

        if "H" in known:                      # geoid modelini kur (N = h - H)
            x0, y0 = known.x.mean(), known.y.mean()
            A = design(known.x, known.y, x0, y0)
            L = (known.h - known.H).values
            c, *_ = np.linalg.lstsq(A, L, rcond=None)
            v = A @ c - L
            m0 = np.sqrt(v @ v / (len(L) - len(c)))
            self.geoid = (c, x0, y0, m0)
            self._log(f"Geoid modeli kuruldu ({len(known)} nokta, m0 = {m0:.4f} m).")

        self.refresh_table()
        self.redraw()
        self.status.set(f"{len(self.points)} nokta yuklendi")

    def geoid_N(self, x, y):
        """Verilen konumda geoid ondulasyonu N; model yoksa None."""
        if self.geoid is None:
            return None
        c, x0, y0, _ = self.geoid
        return float(design(np.atleast_1d(x), np.atleast_1d(y), x0, y0) @ c)

    # ------------------------------------------------------------- cizim
    def redraw(self):
        self.ax.clear()
        p = self.points

        if len(p) >= 4:      # yuzeyi enterpole et
            xi = np.linspace(p.x.min(), p.x.max(), GRID)
            yi = np.linspace(p.y.min(), p.y.max(), GRID)
            X, Y = np.meshgrid(xi, yi)
            Z = griddata((p.x, p.y), p.h, (X, Y), method="cubic")
            near = griddata((p.x, p.y), p.h, (X, Y), method="nearest")
            Z = np.where(np.isnan(Z), near, Z)      # disbukey govde disini doldur

            im = self.ax.contourf(X, Y, Z, levels=24, cmap="terrain")
            cs = self.ax.contour(X, Y, Z, levels=12, colors="k",
                                 linewidths=0.4, alpha=0.5)
            self.ax.clabel(cs, inline=True, fontsize=6, fmt="%.0f")
            if getattr(self, "_cbar", None) is None:
                self._cbar = self.fig.colorbar(im, ax=self.ax, label="Yukseklik h (m)")
            else:
                self._cbar.update_normal(im)
        elif len(p):
            self.ax.text(0.5, 0.5, "Yuzey icin en az 4 nokta gerekli",
                         ha="center", transform=self.ax.transAxes, color="#777")

        if len(p):
            self.ax.scatter(p.x, p.y, c="white", s=34, edgecolors="black",
                            zorder=3, linewidths=0.8)
            for _, r in p.iterrows():
                self.ax.annotate(r.ad, (r.x, r.y), textcoords="offset points",
                                 xytext=(5, 4), fontsize=7, zorder=4)

        # secili noktalar ve aralarindaki cizgi
        if self.selection:
            s = p.loc[self.selection]
            self.ax.scatter(s.x, s.y, s=170, facecolors="none", edgecolors="red",
                            linewidths=2, zorder=5)
            if len(self.selection) == 2:
                self.ax.plot(s.x, s.y, "r--", lw=1.6, zorder=5)

        self.ax.set_xlabel("X (m)")
        self.ax.set_ylabel("Y (m)")
        self.ax.set_title("Arazi Yuzeyi")
        self.ax.set_aspect("equal", adjustable="datalim")
        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ------------------------------------------------------------ etkilesim
    def _on_click(self, ev):
        if ev.inaxes is not self.ax or ev.xdata is None:
            return
        if self.toolbar.mode:                 # zoom/pan aktifken tiklamayi yoksay
            return

        if ev.button == 3:                    # sag tik -> sec
            self._pick_near(ev)
        elif ev.button == 1:                  # sol tik -> koordinati forma tasi
            self.e_x.delete(0, "end")
            self.e_x.insert(0, f"{ev.xdata:.3f}")
            self.e_y.delete(0, "end")
            self.e_y.insert(0, f"{ev.ydata:.3f}")
            if not self.e_ad.get().strip():
                self.e_ad.insert(0, f"P{len(self.points) + 1}")
            self.status.set("Konum alindi - yukseklik girip Ekle'ye basin")
            self.e_h.focus_set()

    def _pick_near(self, ev):
        """Tiklanan piksele en yakin noktayi secime ekle/cikar."""
        if self.points.empty:
            return
        px = self.ax.transData.transform(np.c_[self.points.x, self.points.y])
        d = np.hypot(px[:, 0] - ev.x, px[:, 1] - ev.y)
        i = int(np.argmin(d))
        if d[i] > PICK_PX:
            return
        idx = self.points.index[i]
        if idx in self.selection:
            self.selection.remove(idx)
        else:
            self.selection = (self.selection + [idx])[-2:]
        self._sync_tree_selection()
        self.redraw()
        self.status.set(f"Secili: {len(self.selection)} nokta")

    def _on_tree_select(self, _ev):
        sel = [int(i) for i in self.tree.selection()][-2:]
        if sel != self.selection:
            self.selection = sel
            self.redraw()

    def _sync_tree_selection(self):
        self.tree.selection_set([str(i) for i in self.selection])

    # -------------------------------------------------------------- eylemler
    def add_point(self):
        try:
            x, y, h = float(self.e_x.get()), float(self.e_y.get()), float(self.e_h.get())
        except ValueError:
            messagebox.showerror("Geoider", "X, Y ve yukseklik sayisal olmali.")
            return
        ad = self.e_ad.get().strip() or f"P{len(self.points) + 1}"
        i = int(self.points.index.max()) + 1 if len(self.points) else 0
        self.points.loc[i] = [ad, x, y, h]

        for e in (self.e_ad, self.e_h):
            e.delete(0, "end")
        self.refresh_table()
        self.redraw()
        self.status.set(f"{ad} eklendi ({len(self.points)} nokta)")

    def select_typed(self):
        """Formdaki X,Y'ye en yakin noktayi secime ekler."""
        try:
            x, y = float(self.e_x.get()), float(self.e_y.get())
        except ValueError:
            messagebox.showerror("Geoider", "Once X ve Y girin.")
            return
        if self.points.empty:
            return
        idx = np.hypot(self.points.x - x, self.points.y - y).idxmin()
        if idx not in self.selection:
            self.selection = (self.selection + [idx])[-2:]
        self._sync_tree_selection()
        self.redraw()
        self.status.set(f"Secili: {len(self.selection)} nokta")

    def delete_selected(self):
        if not self.selection:
            return
        self.points = self.points.drop(index=self.selection)
        self.selection = []
        self.refresh_table()
        self.redraw()
        self.status.set(f"Silindi ({len(self.points)} nokta kaldi)")

    def clear_selection(self):
        self.selection = []
        if self.tree.selection():
            self.tree.selection_remove(*self.tree.selection())
        self.redraw()
        self.status.set("Secim temizlendi")

    def compute(self):
        if len(self.selection) != 2:
            messagebox.showinfo("Geoider", "Tam olarak 2 nokta secin.")
            return
        a = self.points.loc[self.selection[0]]
        b = self.points.loc[self.selection[1]]

        dx, dy = b.x - a.x, b.y - a.y
        yatay = float(np.hypot(dx, dy))
        dh = b.h - a.h
        egim = dh / yatay * 100 if yatay else float("nan")

        lines = [
            f"A: {a.ad}   X={a.x:.3f}  Y={a.y:.3f}  h={a.h:.3f} m",
            f"B: {b.ad}   X={b.x:.3f}  Y={b.y:.3f}  h={b.h:.3f} m",
            "-" * 46,
            f"Yatay mesafe       : {yatay:12.3f} m",
            f"Elipsoidal fark dh : {dh:12.3f} m",
            f"Egim               : {egim:12.3f} %",
        ]

        Na = self.geoid_N(a.x, a.y)
        if Na is not None:
            Nb = self.geoid_N(b.x, b.y)
            Ha, Hb = a.h - Na, b.h - Nb
            lines += [
                "-" * 46,
                f"N(A) = {Na:8.3f} m     H(A) = {Ha:10.3f} m",
                f"N(B) = {Nb:8.3f} m     H(B) = {Hb:10.3f} m",
                f"Ortometrik fark dH : {Hb - Ha:12.3f} m",
                f"Model m0           : {self.geoid[3]:12.4f} m",
            ]
        else:
            lines += ["", "(Geoid modeli yok - sadece elipsoidal fark)"]

        self._log("\n".join(lines), clear=True)
        self.status.set(f"{a.ad} - {b.ad}: dh = {dh:.3f} m")

    # ------------------------------------------------------------------ i/o
    def load_csv(self):
        f = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Tumu", "*.*")])
        if not f:
            return
        try:
            df = pd.read_csv(f)
            missing = {"x", "y", "h"} - set(df.columns)
            if missing:
                raise ValueError(f"eksik sutun: {', '.join(sorted(missing))}")
            if "ad" not in df:
                df["ad"] = [f"N{i + 1}" for i in range(len(df))]
            self.points = df[["ad", "x", "y", "h"]].reset_index(drop=True)
            self.selection = []
            self.refresh_table()
            self.redraw()
            self.status.set(f"{len(self.points)} nokta yuklendi")
        except Exception as exc:
            messagebox.showerror("Geoider", f"CSV okunamadi:\n{exc}")

    def save_csv(self):
        f = filedialog.asksaveasfilename(defaultextension=".csv",
                                         filetypes=[("CSV", "*.csv")])
        if f:
            self.points.to_csv(f, index=False)
            self.status.set(f"Kaydedildi: {f}")

    # -------------------------------------------------------------- yardimci
    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for i, r in self.points.iterrows():
            self.tree.insert("", "end", iid=str(i),
                             values=(r.ad, f"{r.x:.3f}", f"{r.y:.3f}", f"{r.h:.3f}"))

    def _log(self, text, clear=False):
        self.txt.configure(state="normal")
        if clear:
            self.txt.delete("1.0", "end")
        self.txt.insert("end", text + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")


if __name__ == "__main__":
    Geoider().mainloop()
