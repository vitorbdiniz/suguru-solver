# =========================
# Parsing do arquivo
# =========================

def decode_givens(code: str, width: int, height: int):
    out = []
    for ch in code.strip():
        if ch.isalpha():
            blanks = ord(ch.lower()) - ord('a') + 1
            out.extend([None] * blanks)
        elif ch.isdigit():
            out.append(int(ch))
    expected = width * height
    if len(out) != expected:
        out = (out + [None]*expected)[:expected]
    return out

def parse_answer(ans: str, width: int, height: int):
    digits = [int(ch) for ch in ans.strip() if ch.isdigit()]
    expected = width * height
    if len(digits) != expected:
        digits = (digits + [0]*expected)[:expected]
    return digits

def load_puzzles(path: str):
    puzzles = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 6:
                parts = line.strip().split()
                if len(parts) < 6:
                    continue
                name, w, h, giv, layout, ans = parts[:6]
                comment = " ".join(parts[6:]) if len(parts) > 6 else ""
            else:
                name, w, h, giv, layout, ans = parts[:6]
                comment = parts[6] if len(parts) > 6 else ""
            width = int(w); height = int(h)
            givens = decode_givens(giv, width, height)
            answer = parse_answer(ans, width, height)
            region_avg_size, n_regions = get_region_size(answer)
            puzzles.append({
                "name": name, "width": width, "height": height,
                "givens": givens, "layout": layout, "answer": answer, "comment": comment,
                'region_avg_size': region_avg_size, 'n_regions':n_regions
            })
    return puzzles



def infer_region_sizes(counts):
    result = {}
    # adiciona o 0 implícito para n+1 = max+1
    max_n = max(counts.keys())
    counts = {n: counts.get(n, 0) for n in range(1, max_n + 2)}
    counts[max_n + 1] = 0  # nenhuma região de tamanho maior que o máximo

    for n in range(1, max_n + 1):
        diff = counts[n] - counts[n + 1]
        if diff > 0:
            result[n] = diff
    return result


def get_region_size(answer):  
    counter = {}
    
    for a in answer:
        if a not in counter:
            counter[a] = 1
        else:
            counter[a] += 1
    region_sizes = infer_region_sizes(counter)

    s = 0
    for value, n in region_sizes.items():
        s += value*n
    region_avg_size = s/ sum(region_sizes.values())
    n_regions = max(counter.values())
    return region_avg_size, n_regions

