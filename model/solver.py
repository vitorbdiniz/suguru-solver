from typing import List, Dict, Optional, Tuple
from motor_deterministico import *
from dataclasses import dataclass

@dataclass
class LevelState:
    board_before: List[Optional[int]]
    cell: int
    candidates: List[int]
    next_idx: int
    value_fixed: Optional[int] = None


class LevelEngine:
    def __init__(self, width, height, layout, givens):
        self.w, self.h = width, height
        self.N = width*height
        self.layout = layout
        self.board = givens[:]
        self.deterministic_counter = {
            'assign_from_singletons': 0,
            'hidden_single': 0,
            'naked_pairs': 0,
            'hidden_pairs': 0,
            'naked_triples': 0,
            'hidden_triples': 0,
        }

        self.regions = {}
        for i,ch in enumerate(layout):
            self.regions.setdefault(ch, []).append(i)
        self.neigh = {}
        for i in range(self.N):
            r,c = i2rc(i, width); ns=[]
            for dr in (-1,0,1):
                for dc in (-1,0,1):
                    if dr==0 and dc==0: continue
                    rr,cc = r+dr, c+dc
                    if 0<=rr<height and 0<=cc<width: ns.append(rc2i(rr,cc,width))
            self.neigh[i]=ns

        # autoria das casas
        self.givens_mask = [v is not None for v in self.board]
        self.det_set: set[int] = set()     # por regras (atual)
        self.guess_set: set[int] = set()   # por backtracking (níveis)

        self.levels: List[LevelState] = []
        self.backtracks = 0

    # --- domínios / MRV / checks ---

    def compute_domains(self, board):
        doms = [set() for _ in range(self.N)]
        for i in range(self.N):
            if board[i] is not None:
                doms[i] = {board[i]}
            else:
                size = len(self.regions[self.layout[i]])
                poss = set(range(1, size+1))
                for j in self.regions[self.layout[i]]:
                    v = board[j]
                    if v is not None: poss.discard(v)
                for n in self.neigh[i]:
                    v = board[n]
                    if v is not None: poss.discard(v)
                doms[i] = poss
        return doms

    def violates_constraints(self, board) -> bool:
        # duplicatas na região
        for ch, cells in self.regions.items():
            vals = [board[i] for i in cells if board[i] is not None]
            if len(vals) != len(set(vals)):
                return True
        # vizinhos iguais
        for i in range(self.N):
            v = board[i]
            if v is None: continue
            for n in self.neigh[i]:
                if n < i:  # evita dupla contagem
                    continue
                if board[n] == v:
                    return True
        return False

    def is_complete_and_valid(self, board) -> bool:
        if any(v is None for v in board):
            return False
        return not self.violates_constraints(board)

    def has_contradiction(self, board) -> bool:
        if self.violates_constraints(board):
            return True
        doms = self.compute_domains(board)
        for i in range(self.N):
            if board[i] is None and len(doms[i]) == 0:
                return True
        return False

    def select_mrv_cell(self, board) -> Optional[int]:
        doms = self.compute_domains(board)
        best=None; blen=10**9
        for i in range(self.N):
            if board[i] is None:
                l=len(doms[i])
                if l==0:
                    return i
                if l<blen:
                    blen=l; best=i
        return best

    # --- botão "Resolver (Regras Det)" ---
    def apply_rules(self) -> Tuple[List[int], bool]:
        before = self.board[:]
        solver = DeterministicSolver(self.w, self.h, self.layout, self.board)
        final, _, _, deterministic_counter = solver.solve()
        for regra in deterministic_counter.keys():
            self.deterministic_counter[regra] += deterministic_counter[regra]
        self.board = final
        new_idxs = [i for i,(b,a) in enumerate(zip(before, final)) if b is None and a is not None]
        for i in new_idxs:
            if not self.givens_mask[i]:
                self.det_set.add(i)
        fully = self.is_complete_and_valid(self.board)
        return new_idxs, fully

    # --- ciclo de 1 nível (BT + Regras) ---
    def _commit_try(self, base_board, cell, val) -> Tuple[bool, List[int], List[Optional[int]], bool, dict]:
        test_board = base_board[:]
        test_board[cell] = val
        if self.violates_constraints(test_board):
            return False, [], base_board, False, {"type":"contradiction","cell":cell,"value":val,"reason":"immediate_violation"}

        solver = DeterministicSolver(self.w, self.h, self.layout, test_board)
        new_board, _, _, deterministic_counter = solver.solve()
        for regra in deterministic_counter.keys():
            self.deterministic_counter[regra] += deterministic_counter[regra]
        if self.has_contradiction(new_board):
            return False, [], base_board, False, {"type":"contradiction","cell":cell,"value":val,"reason":"after_rules"}

        det_new = [i for i,(b,a) in enumerate(zip(base_board, new_board)) if b is None and a is not None and i!=cell]
        fully = self.is_complete_and_valid(new_board)
        return True, det_new, new_board, fully, {"type":"commit","cell":cell,"value":val}


    def one_level(self) -> Tuple[str, Dict]:
        if self.is_complete_and_valid(self.board):
            return "solved", {"new_det": [], "level": len(self.levels), "events": [{"type": "solved"}]}

        cell = self.select_mrv_cell(self.board)
        if cell is None:
            return "unsat", {"new_det": [], "level": len(self.levels), "events": [{"type": "unsat"}]}

        base_board = self.board[:]
        doms = self.compute_domains(base_board)
        cand_list = sorted(doms[cell])
        total_bros = len(cand_list)

        events = []
        events.append({"type": "mrv", "cell": cell, "cands": cand_list})

        # tenta candidatos (irmãos)
        for k, val in enumerate(cand_list):
            ok, det_new, new_board, fully, ev = self._commit_try(base_board, cell, val)
            if not ok:
                events.append(ev)
                continue
            self.board = new_board
            for i in det_new:
                if not self.givens_mask[i]:
                    self.det_set.add(i)
            self.guess_set.add(cell)

            self.levels.append(LevelState(
                board_before=base_board,
                cell=cell,
                candidates=cand_list,
                next_idx=k + 1,
                value_fixed=val
            ))
            if det_new:
                events.append({"type": "det_fills", "count": len(det_new), "indices": det_new})
            return "level_committed", {
                "probe_cell": cell,
                "new_det": det_new,
                "level": len(self.levels),
                "cell": cell,
                "value": val,
                "brother_pos": (k + 1, total_bros),
                "fully": fully,
                "events": events + [ev]
            }

        # se nenhum candidato funcionou → retroceder
        return self._backtrack(events)


    def _backtrack(self, events) -> Tuple[str, Dict]:
        """Realiza o retrocesso (backtracking) quando todos os candidatos falham."""
        while self.levels:
            top = self.levels.pop()

            prev_board = self.board[:]
            self.backtracks += 1
            self.board = top.board_before[:]

            reverted = [i for i, (a, b) in enumerate(zip(prev_board, self.board)) if a != b]
            for i in reverted:
                if i in self.det_set and not self.givens_mask[i]:
                    self.det_set.discard(i)
            if top.cell in self.guess_set:
                self.guess_set.discard(top.cell)

            events.append({"type": "rollback", "reverted": reverted, "from_cell": top.cell})

            j = len(top.candidates)
            for k in range(top.next_idx, j):
                val = top.candidates[k]
                ok, det_new2, new_board2, fully2, ev2 = self._commit_try(top.board_before, top.cell, val)
                if not ok:
                    events.append(ev2)
                    continue

                self.board = new_board2
                for i in det_new2:
                    if not self.givens_mask[i]:
                        self.det_set.add(i)
                self.guess_set.add(top.cell)

                self.levels.append(LevelState(
                    board_before=top.board_before,
                    cell=top.cell,
                    candidates=top.candidates,
                    next_idx=k + 1,
                    value_fixed=val
                ))
                if det_new2:
                    events.append({"type": "det_fills", "count": len(det_new2), "indices": det_new2})
                return "level_committed", {
                    "probe_cell": top.cell,
                    "new_det": det_new2,
                    "level": len(self.levels),
                    "cell": top.cell,
                    "value": val,
                    "brother_pos": (k + 1, j),
                    "fully": fully2,
                    "reverted": reverted,
                    "events": events + [ev2]
                }

        # se todos os níveis foram esgotados
        events.append({"type": "unsat"})
        return "unsat", {"probe_cell": None, "new_det": [], "level": 0, "events": events}

    # ---------- métricas para UI ----------
    def det_count(self) -> int:
        return len(self.det_set)

    def guess_count(self) -> int:
        return len(self.guess_set)

    def givens_count(self) -> int:
        return sum(1 for v in self.givens_mask if v)

    def filled_total(self) -> int:
        return sum(1 for v in self.board if v is not None)

