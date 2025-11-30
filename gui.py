import os
import re


import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import itertools
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

from puzzles import *
from motor_deterministico import *
from solver import *


DEFAULT_FILES = {
    "6x6":      "./tabuleiros/SUG_6x6_v12.txt",
    "8x8":      "./tabuleiros/SUG_8x8_v12.txt",
    "12x10":    "./tabuleiros/SUG_12x10_v12.txt",
    "15x10":    "./tabuleiros/SUG_15x10_v12.txt",
    "15x10 n=6":"./tabuleiros/SUG_15x10n6_v12.txt",
}

class SuguruLevelsGUI:
    def __init__(self, root, initial_puzzles, initial_size_label="8x8", initial_path=None):
        self.root = root
        self.root.title("Suguru: BT por região + Regras")

        self.puzzles = initial_puzzles
        self.current = None
        self.width = 8
        self.height = 8
        self.layout = None
        self.engine: Optional[LevelEngine] = None
        self.board = None
        self.givens_mask = None
        self.regions = None

        # badges persistentes por célula
        self.level_badges: Dict[int, int] = {}
        self.autorun_flag = False
        self.delay_ms = 50

        # UI raiz
        main = ttk.Frame(root, padding=8)
        main.pack(fill="both", expand=True)

        # ===== TOPO: controles de tamanho/arquivo =====
        toolbar = ttk.Frame(main)
        toolbar.pack(fill="x", pady=(0,6))

        ttk.Label(toolbar, text="Tamanho:").pack(side="left")
        self.size_var = tk.StringVar(value=initial_size_label)
        self.size_combo = ttk.Combobox(toolbar, width=10, textvariable=self.size_var,
                                       values=list(DEFAULT_FILES.keys()), state="readonly")
        self.size_combo.pack(side="left", padx=6)
        self.size_combo.bind("<<ComboboxSelected>>", self.on_size_change)

        ttk.Label(toolbar, text="Arquivo:").pack(side="left", padx=(16,4))
        self.path_var = tk.StringVar(value=initial_path or DEFAULT_FILES.get(initial_size_label, "SUG_8x8_v12.txt"))
        self.path_entry = ttk.Entry(toolbar, width=38, textvariable=self.path_var)
        self.path_entry.pack(side="left")
        ttk.Button(toolbar, text="Abrir outro arquivo…", command=self.pick_file).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Recarregar", command=self.reload_from_path).pack(side="left")

        # ===== Esquerda: lista + histórico =====
        left = ttk.Frame(main)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Puzzles").pack(anchor="w")
        self.listbox = tk.Listbox(left, height=14, width=30)
        self.listbox.pack(fill="y")
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        # Ir para ID
        goto = ttk.Frame(left)
        goto.pack(pady=6, fill="x")
        ttk.Label(goto, text="Ir para ID:").pack(side="left")
        self.id_entry = ttk.Entry(goto, width=8)
        self.id_entry.pack(side="left", padx=4)
        ttk.Button(goto, text="Ir", command=self.go_to_id).pack(side="left")
        self.id_entry.bind("<Return>", lambda e: self.go_to_id())

        # HISTÓRICO
        ttk.Label(left, text="Histórico").pack(anchor="w", pady=(8,2))
        hist_frame = ttk.Frame(left)
        hist_frame.pack(fill="both", expand=True)
        self.history = tk.Text(hist_frame, height=18, width=30, wrap="word")
        self.history.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(hist_frame, orient="vertical", command=self.history.yview)
        sb.pack(side="right", fill="y")
        self.history.configure(yscrollcommand=sb.set)
        self.history.tag_configure("mrv", foreground="#6c757d")
        self.history.tag_configure("try", foreground="#343a40")
        self.history.tag_configure("det", foreground="#198754")
        self.history.tag_configure("commit", foreground="#0d6efd")
        self.history.tag_configure("rollback", foreground="#fd7e14")
        self.history.tag_configure("contradiction", foreground="#dc3545", font=("Arial", 10, "bold"))
        self.history.tag_configure("done", foreground="#20c997")

        hist_btns = ttk.Frame(left)
        hist_btns.pack(fill="x", pady=4)
        ttk.Button(hist_btns, text="Limpar histórico", command=self.clear_history).pack(side="left")
        ttk.Button(hist_btns, text="Salvar histórico", command=self.save_history).pack(side="right")

        # ===== Direita: tabuleiro + controles =====
        right = ttk.Frame(main)
        right.pack(side="right", fill="both", expand=True)

        # canvas + dimensões dinâmicas
        self.canvas = tk.Canvas(right, width=520, height=520, bg="white", highlightthickness=0)
        self.canvas.pack(pady=4)
        self.margin = 20
        self.cell_size = 60  # recalculado a cada puzzle

        controls = ttk.Frame(right)
        controls.pack(fill="x", pady=6)

        self.btn_det = ttk.Button(controls, text="Resolver (Regras Det)", command=self.apply_det_rules)
        self.btn_det.grid(row=0, column=0, padx=4)

        self.btn_one = ttk.Button(controls, text="1 Nível (BT + Regras)", command=self.run_one_level)
        self.btn_one.grid(row=0, column=1, padx=4)

        self.btn_auto = ttk.Button(controls, text="Auto-run", command=self.autorun_start)
        self.btn_auto.grid(row=0, column=2, padx=4)

        self.btn_stop = ttk.Button(controls, text="Parar", command=self.autorun_stop)
        self.btn_stop.grid(row=0, column=3, padx=4)

        self.btn_reset = ttk.Button(controls, text="Resetar", command=self.reset_board)
        self.btn_reset.grid(row=0, column=4, padx=4)

        # Velocidade
        self.min_delay = 5
        self.max_delay = 250
        self.speed_scale = ttk.Scale(controls, from_=0, to=100, value=50, orient="horizontal", command=self.on_speed)
        ttk.Label(controls, text="Velocidade").grid(row=0, column=5, padx=(20,4))
        self.speed_scale.grid(row=0, column=6, padx=4, sticky="ew")
        controls.columnconfigure(6, weight=1)

        # Status
        self.status = tk.StringVar(value="Selecione um puzzle.")
        ttk.Label(right, textvariable=self.status).pack(anchor="w", pady=(4,0))

        # carrega lista inicial
        self.populate_listbox()

        # auto-seleciona primeiro
        if self.puzzles:
            self.listbox.selection_set(0)
            self.on_select()

    # ---------- suporte multi-arquivo/tamanho ----------

    def recompute_cell_size(self):
        # tenta caber dentro de ~720px em cada dimensão
        target = 720
        s_w = (target - 2*self.margin) / max(1, self.width)
        s_h = (target - 2*self.margin) / max(1, self.height)
        self.cell_size = int(max(22, min(60, s_w, s_h)))  # limites razoáveis

    def on_size_change(self, event=None):
        size_label = self.size_var.get()
        default_path = DEFAULT_FILES.get(size_label, "")
        if default_path:
            # só substitui se o usuário não customizou manualmente outro caminho para esse tamanho
            self.path_var.set(default_path if os.path.exists(default_path) or True else self.path_var.get())
        self.reload_from_path()

    def pick_file(self):
        path = filedialog.askopenfilename(
            title="Abrir arquivo de instâncias",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")]
        )
        if not path:
            return
        self.path_var.set(path)
        self.reload_from_path()

    def reload_from_path(self):
        path = self.path_var.get().strip()
        if not path:
            messagebox.showerror("Erro", "Informe um caminho de arquivo.")
            return
        try:
            puzzles = load_puzzles(path)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao ler {path}:\n{e}")
            return

        self.puzzles = puzzles
        self.populate_listbox()
        if self.puzzles:
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(0)
            self.on_select()
            self.log(f"Arquivo carregado: {os.path.basename(path)}", "mrv")
        else:
            self.clear_history()
            self.log("Arquivo sem puzzles válidos.", "contradiction")

    def populate_listbox(self):
        self.listbox.delete(0, "end")
        pat_work = re.compile(r'work=(\d+)')
        for p in self.puzzles:
            m = pat_work.search(p.get("comment",""))
            work = f" (work={m.group(1)})" if m else ""
            self.listbox.insert("end", f'{p["name"]}{work}')

    # ---------- histórico ----------

    def log(self, text: str, tag: Optional[str]=None):
        self.history.insert("end", text + "\n", (tag,) if tag else ())
        self.history.see("end")

    def clear_history(self):
        self.history.delete("1.0", "end")

    def save_history(self):
        path = filedialog.asksaveasfilename(
            title="Salvar histórico",
            defaultextension=".log",
            filetypes=[("Log", "*.log"), ("Texto", "*.txt"), ("Todos", "*.*")]
        )
        if not path:
            return
        try:
            content = self.history.get("1.0", "end-1c")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("OK", f"Histórico salvo em:\n{path}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar histórico:\n{e}")

    # ---------- navegação ID ----------

    def go_to_id(self):
        raw = self.id_entry.get().strip()
        if not raw:
            return
        if raw.lower().startswith("suguru-"):
            raw = raw.split("-",1)[1]
        if not raw.isdigit():
            messagebox.showerror("ID inválido", "Digite apenas o número (ex.: 42) ou 'Suguru-42'.")
            return
        target = int(raw)
        pat = re.compile(r'.*-(\d+)$')
        for idx,p in enumerate(self.puzzles):
            m = pat.match(p["name"])
            if m and int(m.group(1))==target:
                self.listbox.selection_clear(0,"end")
                self.listbox.selection_set(idx)
                self.listbox.see(idx)
                self.on_select()
                return
        messagebox.showinfo("Não encontrado", f"Não encontrei 'Suguru-{target}'.")

    # ---------- helpers UI ----------

    def on_speed(self, val):
        try:
            v = float(val)
        except:
            v = 50.0
        self.delay_ms = int(self.max_delay - (self.max_delay - self.min_delay) * (v / 100.0))

    def set_status(self, text):
        self.status.set(text)

    def _build_regions(self):
        self.regions = {}
        for i, ch in enumerate(self.layout):
            self.regions.setdefault(ch, []).append(i)

    def flash_cell(self, idx, color="#fff3b0", ms=120):
        r, c = i2rc(idx, self.width)
        s = self.cell_size; m = self.margin
        x1 = m + c*s; y1 = m + r*s
        x2 = x1 + s;  y2 = y1 + s
        rect = self.canvas.create_rectangle(x1+2, y1+2, x2-2, y2-2, fill=color, outline="")
        self.root.update_idletasks()
        self.root.after(ms, lambda: self.canvas.delete(rect))

    def draw_board(self):
        # recalcula tamanho da célula p/ caber confortavelmente
        self.recompute_cell_size()

        self.canvas.delete("all")
        s = self.cell_size
        m = self.margin
        W = m*2 + s*self.width
        H = m*2 + s*self.height
        self.canvas.config(width=W, height=H)

        # finas internas
        for r in range(self.height):
            for c in range(self.width):
                x1 = m + c*s
                y1 = m + r*s
                x2 = x1 + s
                y2 = y1 + s
                if c>0:
                    self.canvas.create_line(x1, y1, x1, y2, fill="#cccccc", width=1)
                if r>0:
                    self.canvas.create_line(x1, y1, x2, y1, fill="#cccccc", width=1)
        # borda externa grossa
        self.canvas.create_rectangle(m, m, m+s*self.width, m+s*self.height, width=3)

        # bordas de regiões grossas
        for r in range(self.height):
            for c in range(self.width):
                i = rc2i(r,c,self.width)
                ch = self.layout[i]
                x1 = m + c*s; y1 = m + r*s
                x2 = x1 + s;  y2 = y1 + s
                if c==0 or self.layout[i-1]!=ch:
                    self.canvas.create_line(x1, y1, x1, y2, width=3)
                if c==self.width-1 or self.layout[i+1]!=ch:
                    self.canvas.create_line(x2, y1, x2, y2, width=3)
                if r==0 or self.layout[i-self.width]!=ch:
                    self.canvas.create_line(x1, y1, x2, y1, width=3)
                if r==self.height-1 or self.layout[i+self.width]!=ch:
                    self.canvas.create_line(x1, y2, x2, y2, width=3)

        for i, v in enumerate(self.board):
            self.draw_value(i, v, tentative=False)

        self.redraw_badges()
        self.redraw_pencilmarks()

    def draw_value(self, idx, val, tentative=False, color_override=None):
        r, c = i2rc(idx, self.width)
        s = self.cell_size; m = self.margin
        x = m + c*s + s/2
        y = m + r*s + s/2
        self.canvas.delete(f"text_{idx}")
        if val is None:
            return
        color = color_override or ("#444444" if self.givens_mask[idx] else ("#888888" if tentative else "#000000"))
        self.canvas.create_text(x, y, text=str(val), font=("Arial", int(s*0.45), "bold"),
                                fill=color, tags=f"text_{idx}")

    def set_badge_level(self, idx, level_k: Optional[int]):
        # persistência de estado
        if level_k is None:
            self.level_badges.pop(idx, None)
        else:
            self.level_badges[idx] = level_k

        # redesenha apenas essa célula
        self.canvas.delete(f"badge_{idx}")
        if level_k is None:
            return
        r, c = i2rc(idx, self.width)
        s = self.cell_size; m = self.margin
        x1 = m + c*s + 6
        y1 = m + r*s + 10
        self.canvas.create_text(x1, y1, text=f"B{level_k}", anchor="w",
                                font=("Arial", max(10, int(s*0.22)), "bold"),
                                fill="#0d6efd", tags=f"badge_{idx}")

    def redraw_badges(self):
        # limpa tudo e repinta do dicionário persistido
        for i in range(self.width*self.height):
            self.canvas.delete(f"badge_{i}")
        for idx, lvl in self.level_badges.items():
            self.set_badge_level(idx, lvl)

    def redraw_pencilmarks(self):
        for i in range(self.width * self.height):
            self.canvas.delete(f"pencil_{i}")

        doms = self.engine.compute_domains(self.board) if self.engine else [set() for _ in range(self.width*self.height)]
        s = self.cell_size; m = self.margin
        font_sz = max(8, int(s*0.18))

        # posições para 1..6 (grade 3x2)
        pos_map = {
            1:(0,0), 2:(1,0), 3:(2,0),
            4:(0,1), 5:(1,1), 6:(2,1),
        }

        for i in range(self.width*self.height):
            if self.board[i] is not None:
                continue
            if self.givens_mask[i]:
                continue
            r, c = i2rc(i, self.width)
            x0 = m + c*s
            y0 = m + r*s
            for d in sorted(doms[i]):
                if d not in pos_map:
                    # para regiões maiores que 6 (improvável aqui), omite visual de pencil extra
                    continue
                px, py = pos_map[d]
                dx = (s/8) + px*(s/3)   # leve ajuste p/ caber 3x2
                dy = (s/8) + py*(s/2.6)
                self.canvas.create_text(
                    x0 + dx, y0 + dy, text=str(d),
                    font=("Arial", font_sz),
                    fill="#b0b0b0",
                    tags=f"pencil_{i}",
                    anchor="center"
                )

    # ---------- eventos ----------

    def on_select(self, event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.current = self.puzzles[sel[0]]
        self.width  = self.current["width"]
        self.height = self.current["height"]
        self.layout = self.current["layout"]

        self.engine = LevelEngine(self.width, self.height, self.layout, self.current["givens"])
        self.board = self.engine.board
        self.givens_mask = [v is not None for v in self.board]
        self._build_regions()
        self.level_badges.clear()
        self.autorun_flag = False
        self.draw_board()
        self.clear_history()
        self.log(f"Carregado: {self.current['name']}", "mrv")
        self.update_status("Pronto.")

    def reset_board(self):
        if not self.current: return
        self.engine = LevelEngine(self.width, self.height, self.layout, self.current["givens"])
        self.board = self.engine.board
        self.givens_mask = [v is not None for v in self.board]
        self.level_badges.clear()
        self.autorun_flag = False
        self.draw_board()
        self.clear_history()
        self.log("Tabuleiro resetado.", "mrv")
        self.update_status("Tabuleiro resetado.")

    def update_status(self, extra=""):
        det_now = self.engine.det_count() if self.engine else 0
        guess_now = self.engine.guess_count() if self.engine else 0
        givens_now = self.engine.givens_count() if self.engine else 0
        filled = self.engine.filled_total() if self.engine else 0
        lvl = len(self.engine.levels) if self.engine else 0
        bt = self.engine.backtracks if self.engine else 0
        msg = (f"Dicas: {givens_now} | Det: {det_now} | BT: {guess_now} | "
               f"Preenchidas: {filled}/{self.width*self.height} | Nível BT: {lvl} | Retrocessos: {bt}")
        if extra: msg += f" — {extra}"
        self.set_status(msg)

    # ---------- rollback visual ----------

    def apply_rollback_visual(self, reverted_indices: List[int]):
        if not reverted_indices:
            return
        for i in reverted_indices:
            self.canvas.delete(f"text_{i}")
            v = self.engine.board[i]
            if v is not None:
                self.draw_value(i, v, tentative=False)
        self.redraw_pencilmarks()
        for i in reverted_indices:
            self.flash_cell(i, color="#ffe3e3", ms=90)

    # ---------- ações ----------

    def animate_new_dets(self, indices: List[int]):
        if indices:
            self.log(f"Deduções determinísticas: +{len(indices)}", "det")
        for i in indices:
            self.draw_value(i, self.engine.board[i], tentative=False, color_override="#000000")
            self.flash_cell(i, "#ddffdd", ms=80)
            self.root.update()
            self.root.after(self.delay_ms)
        self.redraw_pencilmarks()

    def color_guess_cell(self, cell_idx: int, level_k: int, val: int):
        self.draw_value(cell_idx, val, tentative=False, color_override="#0d6efd")
        self.set_badge_level(cell_idx, level_k)
        self.root.update()
        self.redraw_pencilmarks()
        r,c = i2rc(cell_idx, self.width)
        self.log(f"Nível {level_k} fixado em ({r+1},{c+1}) = {val}", "commit")

    def highlight_probe_cell(self, idx: Optional[int], cand_list: Optional[List[int]]=None):
        if idx is None:
            return
        self.flash_cell(idx, color="#fff3b0", ms=160)
        r,c = i2rc(idx, self.width)
        if cand_list is not None:
            self.log(f"MRV ({r+1},{c+1}) candidatos: {cand_list}", "mrv")
        else:
            self.log(f"MRV em ({r+1},{c+1})", "mrv")

    def apply_det_rules(self):
        if not self.engine: return
        new_idxs, fully = self.engine.apply_rules()
        self.board = self.engine.board
        self.animate_new_dets(new_idxs)
        self.redraw_pencilmarks()
        if fully:
            self.update_status("Resolvido por regras determinísticas.")
        else:
            self.update_status("Regras aplicadas (manual).")

    def process_events_log(self, events: List[dict]):
        for ev in events or []:
            t = ev.get("type")
            if t == "mrv":
                cell = ev.get("cell")
                cands = ev.get("cands", [])
                if cell is not None:
                    self.highlight_probe_cell(cell, cands)
            elif t == "contradiction":
                cell = ev.get("cell"); val = ev.get("value")
                r,c = i2rc(cell, self.width) if cell is not None else ("?","?")
                reason = ev.get("reason","")
                self.log(f"Contradição em candidato ({r+1},{c+1})={val} [{reason}]", "contradiction")
            elif t == "rollback":
                rev = ev.get("reverted", [])
                from_cell = ev.get("from_cell")
                self.log(f"Rollback: revertidas {len(rev)} casas", "rollback")
                # remove badge do nível desfeito
                if from_cell is not None:
                    self.set_badge_level(from_cell, None)
            elif t == "det_fills":
                cnt = ev.get("count",0)
                self.log(f"Deduções determinísticas: +{cnt}", "det")
            elif t == "commit":
                cell = ev.get("cell"); val = ev.get("value")
                r,c = i2rc(cell, self.width) if cell is not None else ("?","?")
                self.log(f"Commit candidato ({r+1},{c+1})={val}", "commit")
            elif t == "solved":
                self.log("Resolvido.", "done")
            elif t == "unsat":
                self.log("Sem solução (unsat).", "contradiction")

    def run_one_level(self):
        if not self.engine: return

        # pré-visualização do MRV atual
        probe = self.engine.select_mrv_cell(self.engine.board)
        if probe is not None:
            pre_doms = self.engine.compute_domains(self.engine.board)
            self.highlight_probe_cell(probe, sorted(pre_doms[probe]))

        status, info = self.engine.one_level()
        self.board = self.engine.board

        self.process_events_log(info.get("events", []))

        reverted = info.get("reverted", [])
        if reverted:
            self.apply_rollback_visual(reverted)

        new_det = info.get("new_det", [])
        self.animate_new_dets(new_det)

        if status == "solved":
            self.update_status("Resolvido.")
            self.draw_board()  # badges persistem
            return
        if status == "unsat":
            self.update_status("Sem solução (esgotou alternativas).")
            return
        if status == "level_committed":
            cell = info["cell"]
            val  = info["value"]
            level_k = info["level"]
            i,j = info["brother_pos"]
            self.color_guess_cell(cell, level_k, val)
            self.flash_cell(cell, "#dde7ff", ms=120)
            extra = f"Nível {level_k} fixado ({i}/{j})."
            if info.get("fully"):
                extra += " (tabuleiro completo após regras)"
            self.update_status(extra)

    # ---------- Auto-run ----------

    def autorun_start(self):
        if not self.engine: return
        if self.autorun_flag: return
        self.autorun_flag = True
        self.update_status("Auto-run iniciado.")
        self._autorun_tick()

    def autorun_stop(self):
        self.autorun_flag = False
        self.update_status("Auto-run parado.")

    def _autorun_tick(self):
        if not self.autorun_flag: return

        # (0) REGRAS DETERMINÍSTICAS PRIMEIRO
        new_idxs, fully = self.engine.apply_rules()
        self.board = self.engine.board
        if new_idxs:
            self.animate_new_dets(new_idxs)
            self.redraw_pencilmarks()
            if fully:
                self.log("Auto: resolvido por regras determinísticas.", "done")
                self.update_status("Auto: resolvido.")
                self.draw_board()  # badges persistem
                return
            self.root.after(self.delay_ms, self._autorun_tick)
            return

        # (1) TRAVOU -> 1 nível (BT + Regras)
        status, info = self.engine.one_level()
        self.board = self.engine.board

        self.process_events_log(info.get("events", []))

        reverted = info.get("reverted", [])
        if reverted:
            self.apply_rollback_visual(reverted)

        new_det = info.get("new_det", [])
        self.animate_new_dets(new_det)

        if status == "level_committed":
            print(info)
            cell = info["cell"]; val = info["value"]; level_k = info["level"]
            i,j = info["brother_pos"]
            self.color_guess_cell(cell, level_k, val)
            self.flash_cell(cell, "#dde7ff", ms=80)
            extra = f"Auto: nível {level_k} fixado ({i}/{j})."
            if info.get("fully"):
                extra += " (completo)"
            self.update_status(extra)
        elif status == "solved":
            self.log("Auto: resolvido.", "done")
            self.update_status("Auto: resolvido.")
            self.draw_board()  # badges persistem
            return
        elif status == "unsat":
            self.log("Auto: sem solução (unsat).", "contradiction")
            self.update_status("Auto: sem solução (esgotou alternativas).")
            return

        self.root.after(self.delay_ms, self._autorun_tick)
