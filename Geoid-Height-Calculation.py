import numpy as np
import pandas as pd

DEG = [(0, 0), (1, 0), (0, 1), (2, 0), (1, 1), (0, 2), (3, 0), (2, 1), (1, 2), (0, 3)]


def design(x, y, x0, y0):
    """3. derece polinom yuzeyi icin katsayilar matrisi (km'ye normalize koordinatlar)."""
    u, v = (np.asarray(x) - x0) / 1000, (np.asarray(y) - y0) / 1000
    return np.column_stack([u**i * v**j for i, j in DEG])


def main():
    known = pd.read_csv("known_stations.csv")
    new = pd.read_csv("new_stations.csv")

    x0, y0 = known.x.mean(), known.y.mean()
    A = design(known.x, known.y, x0, y0)
    L = (known.h - known.H).values          # N = h - H

    c, *_ = np.linalg.lstsq(A, L, rcond=None)
    v = A @ c - L
    m0 = np.sqrt(v @ v / (len(L) - len(c)))

    new["N"] = design(new.x, new.y, x0, y0) @ c
    new["H"] = new.h - new.N

    print("\nModel Coefficients:", c)
    print("Model RMS Error (m0):", m0)
    print("\nNew Station Results:")
    print(new)


if __name__ == "__main__":
    main()
