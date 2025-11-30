from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from motor_deterministico import *


@dataclass
class RegionLevelState:
    board_before: List[Optional[int]]
    region_label: str
    candidates: List[List[int]]
    next_idx: int
    value_fixed: Optional[List[int]] = None


class LevelEngineRegions:
    """
    Variante do LevelEngine que faz o backtracking escolhendo permutações
    inteiras de uma região por vez. Cada nível considera todos os candidatos
    de uma região (ordem determinada por heurística MRV de regiões), aplica o
    motor determinístico e retrocede caso nenhum candidato sirva.
    """

    def __init__(self, width, height, layout, givens):
        self.w, self.h = width, height
        self.N = width * height
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
        self.regions: Dict[str, List[int]] = {}
        for i, ch in enumerate(layout):
            self.regions.setdefault(ch, []).append(i)

        self.neigh: Dict[int, List[int]] = {}
        for i in range(self.N):
            r, c = i2rc(i, width)
            ns = []
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < height and 0 <= cc < width:
                        ns.append(rc2i(rr, cc, width))
            self.neigh[i] = ns

        self.givens_mask = [v is not None for v in self.board]
        self.det_set: set[int] = set()
        self.guess_set: set[int] = set()
        self.levels: List[RegionLevelState] = []
        self.backtracks = 0
        self.nodes_visited = 0
        self.max_depth = 0


    # ---- verificações básicas ----
    def compute_domains(self, board):
        doms = [set() for _ in range(self.N)]
        for i in range(self.N):
            if board[i] is not None:
                doms[i] = {board[i]}
            else:
                size = len(self.regions[self.layout[i]])
                poss = set(range(1, size + 1))
                for j in self.regions[self.layout[i]]:
                    v = board[j]
                    if v is not None:
                        poss.discard(v)
                for n in self.neigh[i]:
                    v = board[n]
                    if v is not None:
                        poss.discard(v)
                doms[i] = poss
        return doms

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

    def violates_constraints(self, board) -> bool:
        for ch, cells in self.regions.items():
            vals = [board[i] for i in cells if board[i] is not None]
            if len(vals) != len(set(vals)):
                return True
        for i in range(self.N):
            v = board[i]
            if v is None:
                continue
            for n in self.neigh[i]:
                if n < i:
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

    # ---- geração das permutações / MRV de região ----
    def _region_candidates(self, board, label) -> List[List[int]]:
        cells = self.regions[label]
        size = len(cells)
        available = set(range(1, size + 1))
        assigned: Dict[int, int] = {}

        # aplica valores já definidos
        for idx in cells:
            val = board[idx]
            if val is not None:
                if val in assigned.values() or val not in available:
                    return []
                assigned[idx] = val
                available.discard(val)
                for n in self.neigh[idx]:
                    if n not in cells and board[n] == val:
                        return []

        pending = [idx for idx in cells if idx not in assigned]
        if not pending:
            # região completa não precisa de candidatos
            return []

        assignments: List[List[int]] = []

        def backtrack(pos: int, used: set[int], partial: Dict[int, int]):
            if pos == len(pending):
                merged = []
                for idx in cells:
                    if idx in assigned:
                        merged.append(assigned[idx])
                    else:
                        merged.append(partial[idx])
                assignments.append(merged)
                return
            cell = pending[pos]
            for val in sorted(available - used):
                conflict = False
                for n in self.neigh[cell]:
                    if n not in cells:
                        nval = board[n]
                        if nval is not None and nval == val:
                            conflict = True
                            break
                if conflict:
                    continue
                partial[cell] = val
                used.add(val)
                backtrack(pos + 1, used, partial)
                used.remove(val)
                del partial[cell]

        backtrack(0, set(), {})
        return assignments

    def select_region(self, board) -> Tuple[Optional[str], Dict[str, List[List[int]]]]:
        region_candidates: Dict[str, List[List[int]]] = {}
        for ch, cells in self.regions.items():
            if any(board[i] is None for i in cells):
                cands = self._region_candidates(board, ch)
                region_candidates[ch] = cands
        selectable = [(label, cands) for label, cands in region_candidates.items() if cands]
        if not selectable:
            return None, region_candidates
        best_label, best_cands = min(selectable, key=lambda item: len(item[1]))
        return best_label, region_candidates

    # ---- commit / ciclo de nível ----
    def _commit_region(self, base_board, label, assignment) -> Tuple[bool, List[int], List[Optional[int]], bool, Dict]:
        cells = self.regions[label]
        test_board = base_board[:]
        for idx, val in zip(cells, assignment):
            test_board[idx] = val
        if self.violates_constraints(test_board):
            return False, [], base_board, False, {
                "type": "contradiction_region",
                "region": label,
                "assignment": assignment,
                "reason": "immediate_violation",
            }

        solver = DeterministicSolver(self.w, self.h, self.layout, test_board)
        new_board, _, _, deterministic_counter = solver.solve()
        for regra, count in deterministic_counter.items():
            self.deterministic_counter[regra] += count

        if self.has_contradiction(new_board):
            return False, [], base_board, False, {
                "type": "contradiction_region",
                "region": label,
                "assignment": assignment,
                "reason": "after_rules",
            }

        cell_set = set(cells)
        det_new = [
            i for i, (b, a) in enumerate(zip(base_board, new_board))
            if b is None and a is not None and i not in cell_set
        ]
        fully = self.is_complete_and_valid(new_board)
        return True, det_new, new_board, fully, {
            "type": "commit_region",
            "region": label,
            "assignment": assignment,
        }

    def one_level(self) -> Tuple[str, Dict]:
        if self.is_complete_and_valid(self.board):
            return "solved", {"new_det": [], "level": len(self.levels), "events": [{"type": "solved"}]}

        base_board = self.board[:]
        
        region_label, region_map = self.select_region(base_board)
        events = []

        # contradição imediata se alguma região obrigatória sem candidatos
        zero_cands = [label for label, cands in region_map.items() if not cands and any(base_board[i] is None for i in self.regions[label])]
        if zero_cands:
            events.append({"type": "no_region_candidate", "regions": zero_cands})
            return self._backtrack(events)

        if region_label is None:
            # não há regiões com lacunas: ou resolvido ou insatisfatível
            if self.is_complete_and_valid(self.board):
                return "solved", {"new_det": [], "level": len(self.levels), "events": [{"type": "solved"}]}
            return self._backtrack([{"type": "unsat_state"}])

        cand_list = region_map[region_label]
        total_bros = len(cand_list)
        events.append({
            "type": "region_mrv",
            "region": region_label,
            "candidate_count": total_bros,
            "cells": self.regions[region_label],
        })

        for k, assignment in enumerate(cand_list):
            self.nodes_visited += 1
            self.max_depth = max(self.max_depth, len(self.levels) + 1)

            ok, det_new, new_board, fully, ev = self._commit_region(base_board, region_label, assignment)
            if not ok:
                events.append(ev)
                continue

            self.board = new_board
            for idx in det_new:
                if not self.givens_mask[idx]:
                    self.det_set.add(idx)
            for idx in self.regions[region_label]:
                if not self.givens_mask[idx]:
                    self.guess_set.add(idx)

            self.levels.append(RegionLevelState(
                board_before=base_board,
                region_label=region_label,
                candidates=cand_list,
                next_idx=k + 1,
                value_fixed=assignment[:],
            ))
            if det_new:
                events.append({"type": "det_fills", "count": len(det_new), "indices": det_new})
            return "level_committed", {
                "region": region_label,
                "new_det": det_new,
                "level": len(self.levels),
                "assignment": assignment,
                "brother_pos": (k + 1, total_bros),
                "fully": fully,
                "events": events + [ev],
            }

        return self._backtrack(events)

    def _backtrack(self, events) -> Tuple[str, Dict]:
        while self.levels:
            self.max_depth = max(self.max_depth, len(self.levels))
            top = self.levels.pop()
            prev_board = self.board[:]
            self.backtracks += 1
            self.board = top.board_before[:]

            reverted = [i for i, (a, b) in enumerate(zip(prev_board, self.board)) if a != b]
            for idx in reverted:
                if idx in self.det_set and not self.givens_mask[idx]:
                    self.det_set.discard(idx)
            for idx in self.regions[top.region_label]:
                if idx in self.guess_set:
                    self.guess_set.discard(idx)

            events.append({
                "type": "rollback_region",
                "region": top.region_label,
                "reverted": reverted,
            })

            j = len(top.candidates)
            for k in range(top.next_idx, j):
                assignment = top.candidates[k]
                ok, det_new2, new_board2, fully2, ev2 = self._commit_region(top.board_before, top.region_label, assignment)
                if not ok:
                    events.append(ev2)
                    continue

                self.board = new_board2
                for idx in det_new2:
                    if not self.givens_mask[idx]:
                        self.det_set.add(idx)
                for idx in self.regions[top.region_label]:
                    if not self.givens_mask[idx]:
                        self.guess_set.add(idx)

                self.levels.append(RegionLevelState(
                    board_before=top.board_before,
                    region_label=top.region_label,
                    candidates=top.candidates,
                    next_idx=k + 1,
                    value_fixed=assignment[:],
                ))
                if det_new2:
                    events.append({"type": "det_fills", "count": len(det_new2), "indices": det_new2})
                return "level_committed", {
                    "region": top.region_label,
                    "new_det": det_new2,
                    "level": len(self.levels),
                    "assignment": assignment,
                    "brother_pos": (k + 1, j),
                    "fully": fully2,
                    "reverted": reverted,
                    "events": events + [ev2],
                }

        events.append({"type": "unsat"})
        return "unsat", {"region": None, "new_det": [], "level": 0, "events": events}

    # ---- métricas ----
    def det_count(self) -> int:
        return len(self.det_set)

    def guess_count(self) -> int:
        return len(self.guess_set)

    def givens_count(self) -> int:
        return sum(1 for v in self.givens_mask if v)

    def filled_total(self) -> int:
        return sum(1 for v in self.board if v is not None)
