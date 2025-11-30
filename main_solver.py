# suguru_niveis_bt_SUMARY2_multi.py
# Python 3.x + tkinter
# Estratégia por nível: CHUTE (MRV, 1 valor) -> aplica regras determinísticas até travar.
# Destaques (mantidos):
# - Pencil marks (candidatos)
# - MRV em amarelo antes do chute
# - Badges "B{k}" para chutes confirmados (persistentes após redraw)
# - Rollback visual imediato (removendo badge do nível desfeito)
# - Checagens de restrição (regiões e vizinhos)
# - Painel de histórico (contradições/rollback/commits/deduções)
# - Contador de determinísticas EXATO (decrementa no rollback)
# - Auto-run: aplica REGRAS primeiro; se travar, faz 1 NÍVEL (BT + Regras)
# - ***ATUALIZAÇÕES***:
#   * Removido resumo final que redimensionava e repetia estatísticas
#   * Persistência correta dos badges de backtracking
#   * Autorun ajustado para "regras primeiro"
#   * SUPORTE A MÚLTIPLOS TAMANHOS (6x6, 8x8, 12x10, 15x10, 15x10 n=6)
#   * Seletor de arquivo de instâncias + redimensionamento automático do tabuleiro
#   * Pencil marks até 6 candidatos (p/ variantes com regiões de tamanho 6)

import tkinter as tk
import os

method = 'regiao'

if method == 'regiao':
    from gui_regions import *
else:
    from gui import *

def guess_initial_size_label(path: str) -> str:
    nm = os.path.basename(path).lower()
    if "6x6" in nm: return "6x6"
    if "8x8" in nm: return "8x8"
    if "12x10" in nm and "n6" not in nm: return "12x10"
    if "15x10n6" in nm: return "15x10 n=6"
    if "15x10" in nm: return "15x10"
    return "8x8"

def main():
    # tenta um arquivo padrão inicial (8x8)
    default_path = DEFAULT_FILES.get("8x8", "SUG_15x10_v12.txt")
    try:
        puzzles = load_puzzles(default_path)
    except Exception:
        puzzles = []
    root = tk.Tk()
    size_label = guess_initial_size_label(default_path)
    app = SuguruLevelsGUI(root, puzzles, initial_size_label=size_label, initial_path=default_path)
    root.mainloop()

if __name__ == "__main__":
    main()