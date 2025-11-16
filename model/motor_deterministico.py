import itertools


def rc2i(r, c, w): return r * w + c
def i2rc(i, w): return divmod(i, w)


class DeterministicSolver:
    def __init__(self, width, height, layout, initial):
        self.w = width
        self.h = height
        self.N = self.w * self.h
        self.layout = layout
        self.board = initial[:]
        self.regions = {}
        self.counter = {
            'assign_from_singletons': 0,
            'hidden_single': 0,
            'naked_pairs': 0,
            'hidden_pairs': 0,
            'naked_triples': 0,
            'hidden_triples': 0,
        }

        for i, ch in enumerate(layout):
            self.regions.setdefault(ch, []).append(i)
        self.neigh = {}
        for i in range(self.N):
            r, c = i2rc(i, self.w)
            ns = []
            for dr in (-1,0,1):
                for dc in (-1,0,1):
                    if dr==0 and dc==0: continue
                    rr, cc = r+dr, c+dc
                    if 0<=rr<self.h and 0<=cc<self.w:
                        ns.append(rc2i(rr,cc,self.w))
            self.neigh[i] = ns
        self.cands = [set() for _ in range(self.N)]
        self._init_candidates()

    def _init_candidates(self):
        for i in range(self.N):
            ch = self.layout[i]
            n = len(self.regions[ch])
            if self.board[i] is not None:
                self.cands[i] = {self.board[i]}
            else:
                poss = set(range(1, n+1))
                for j in self.regions[ch]:
                    v = self.board[j]
                    if v is not None: poss.discard(v)
                for nbh in self.neigh[i]:
                    v = self.board[nbh]
                    if v is not None: poss.discard(v)
                self.cands[i] = poss

    def _elim(self, i, v):
        if v in self.cands[i] and len(self.cands[i])>1:
            self.cands[i].remove(v)
            return True
        return False

    def _propagate_singleton(self, i):
        v = next(iter(self.cands[i]))
        for j in self.regions[self.layout[i]]:
            if j!=i: self._elim(j, v)
        for n in self.neigh[i]:
            self._elim(n, v)

    def _assign_from_singletons(self):
        changed = False
        for i in range(self.N):
            if len(self.cands[i]) == 1 and self.board[i] is None:
                self.board[i] = next(iter(self.cands[i]))
                self.counter['assign_from_singletons'] += 1
                changed = True
        return changed

    def _hidden_single(self):
        changed = False
        for ch, cells in self.regions.items():
            n = len(cells)
            for d in range(1, n + 1):
                occ = [i for i in cells if d in self.cands[i]]
                if len(occ) == 1:
                    i = occ[0]
                    if len(self.cands[i]) > 1:
                        self.cands[i] = {d}
                        if self.board[i] is None:
                            self.board[i] = d
                            self.counter['hidden_single'] += 1
                            changed = True
        return changed

    def _naked_pairs(self):
        changed = False
        for ch, cells in self.regions.items():
            pairs = {}
            for i in cells:
                if len(self.cands[i]) == 2:
                    key = tuple(sorted(self.cands[i]))
                    pairs.setdefault(key, []).append(i)
            for key, idxs in pairs.items():
                if len(idxs) == 2:
                    digits = set(key)
                    for j in cells:
                        if j not in idxs:
                            for d in digits:
                                if self._elim(j, d):
                                    self.counter['naked_pairs'] += 1
                                    changed = True
        return changed

    def _hidden_pairs(self):
        changed = False
        for ch, cells in self.regions.items():
            n = len(cells)
            occ = {d: [i for i in cells if d in self.cands[i]] for d in range(1, n + 1)}
            for d1, d2 in itertools.combinations(range(1, n + 1), 2):
                s = set(occ[d1]) | set(occ[d2])
                if len(s) == 2:
                    for i in s:
                        newset = self.cands[i] & {d1, d2}
                        if newset != self.cands[i]:
                            self.cands[i] = set(newset)
                            self.counter['hidden_pairs'] += 1
                            changed = True
        return changed

    def _naked_triples(self):
        changed = False
        for ch, cells in self.regions.items():
            for triple in itertools.combinations(cells, 3):
                union = set().union(*(self.cands[i] for i in triple))
                if 1 < len(union) == 3:
                    for j in cells:
                        if j not in triple:
                            for d in union:
                                if self._elim(j, d):
                                    self.counter['naked_triples'] += 1
                                    changed = True
        return changed

    def _hidden_triples(self):
        changed = False
        for ch, cells in self.regions.items():
            n = len(cells)
            occ = {d: [i for i in cells if d in self.cands[i]] for d in range(1, n + 1)}
            for trio in itertools.combinations(range(1, n + 1), 3):
                occ_union = set().union(*(set(occ[d]) for d in trio))
                if len(occ_union) == 3:
                    for i in occ_union:
                        newset = self.cands[i] & set(trio)
                        if newset != self.cands[i]:
                            self.cands[i] = set(newset)
                            self.counter['hidden_triples'] += 1
                            changed = True
        return changed

    def solve(self):
        changed=True
        while changed:
            changed=False
            if self._assign_from_singletons(): 
                changed=True
            
            for i in range(self.N):
                if len(self.cands[i])==1:
                    self._propagate_singleton(i)

            if self._hidden_single(): 
                changed=True
            if self._assign_from_singletons(): 
                changed=True
            for i in range(self.N):
                if len(self.cands[i])==1:
                    self._propagate_singleton(i)

            if self._naked_pairs(): 
                changed=True
            if self._hidden_pairs(): 
                changed=True
            if self._naked_triples(): 
                changed=True
            if self._hidden_triples(): 
                changed=True
            if self._assign_from_singletons(): 
                changed=True

        solved = sum(1 for v in self.board if v is not None)
        return self.board[:], solved, (solved==self.N), self.counter

