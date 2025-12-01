import time
from puzzles import load_puzzles
from solver_regiao import LevelEngineRegions
from motor_deterministico import DeterministicSolver

import pandas as pd

DEFAULT_FILES = {
    "6x6":      "./tabuleiros/SUG_6x6_v12.txt",
    "8x8":      "./tabuleiros/SUG_8x8_v12.txt",
    #"12x10":    "./tabuleiros/SUG_12x10_v12.txt",
    "15x10n=6":"./tabuleiros/SUG_15x10n6_v12.txt",
    "15x10":    "./tabuleiros/SUG_15x10_v12.txt",
}



def is_solved(board):
    return None not in board


def solve_suguru_textmode(puzzle, setup='8x8'):
    """
    Resolve um puzzle Suguru em modo texto, sem interface gráfica.
    Usa o motor determinístico e, opcionalmente, o solver com backtracking (LevelEngine).
    """


    width, height = puzzle['width'], puzzle['height']
    layout = puzzle['layout']
    givens = puzzle['givens']

    # inicia o motor de níveis (backtracking controlado)
    engine = LevelEngineRegions(width, height, layout, givens)

    start_time = time.perf_counter()

    det = DeterministicSolver(width, height, engine.layout, engine.board)
    det.solve()
    engine.board = det.board[:]  # atualiza estado

    solved = is_solved(engine.board)

    while not solved:
        engine.one_level()
        solved = is_solved(engine.board)

    elapsed = time.perf_counter() - start_time

    n_given = len([g for g in givens if g is not None])
    try:
        size = int(setup.split('x')[0]) * int(setup.split('x')[1])
    except:
        size = 150

    for k in det.counter:
        engine.deterministic_counter[k] += det.counter[k]

    return pd.Series({
        'id': puzzle['name'],
        'tabuleiro': setup,
        'size': size,
        'numero_regioes':puzzle['n_regions'],
        'tamanho_medio_regiao':puzzle['region_avg_size'],
        'dificuldade': puzzle['difficulty'],
        'dicas':n_given,

        'tempo': elapsed,
        'nos_visitados': engine.nodes_visited,
        'profundidade_maxima': engine.max_depth,
        'total_podas': sum(engine.deterministic_counter.values()),
        'backtracks': engine.backtracks,
        'resolvido': solved,
        **engine.deterministic_counter
    })


def solve_all_sugurus(limit=None, backtracking_method='regiao'):
    results = None
    for setup in DEFAULT_FILES:
        i = 0
        filepath = DEFAULT_FILES[setup]
        puzzles = load_puzzles(filepath)  # lê o arquivo padrão de puzzles
        setup_finalizado = False
        print(setup)
        while not setup_finalizado:
            print(f'{setup} - {i}')
            try:
                puzzle = puzzles[i]
                res = solve_suguru_textmode(puzzle, setup=setup)
                if results is None:
                    results = pd.DataFrame(columns=res.index)
                results.loc[f'{setup}_{puzzle["name"]}'] = res
                i+=1
                if limit is not None and i == limit:
                    setup_finalizado = True 
            except IndexError as e:
               setup_finalizado = True
            results.to_csv(f'./results/backtracking_{backtracking_method}.csv')

if __name__ == "__main__":
    limit=None
    solve_all_sugurus(limit, backtracking_method='region')
