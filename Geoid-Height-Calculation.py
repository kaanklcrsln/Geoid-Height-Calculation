import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Station:
    """Represents a geodetic station with coordinates and heights."""
    x: float
    y: float
    h: float
    H: Optional[float] = None

    @property
    def N(self) -> float:
        return self.h - self.H if self.H is not None else None

class GeodeticNetwork:

    
    def __init__(self, stations: List[Station]):
        self.stations = stations
        self.x_mean = np.mean([s.x for s in stations])
        self.y_mean = np.mean([s.y for s in stations])
        self.coefficients = None
        self.m0 = None

    def fit(self) -> None:
        """Fit polynomial surface to known stations."""
        x_norm = np.array([(s.x - self.x_mean) / 1000 for s in self.stations])
        y_norm = np.array([(s.y - self.y_mean) / 1000 for s in self.stations])
        
        A = np.column_stack([
            np.ones(len(self.stations)),
            x_norm, y_norm,
            x_norm**2, x_norm*y_norm, y_norm**2,
            x_norm**3, x_norm**2*y_norm, x_norm*y_norm**2, y_norm**3
        ])
        
        L = np.array([s.N for s in self.stations]).reshape(-1, 1)
        self.coefficients = np.linalg.solve(A.T @ A, A.T @ L)
        v = A @ self.coefficients - L
        self.m0 = np.sqrt((v.T @ v) / (len(L) - len(self.coefficients))).item()

    def predict(self, station: Station) -> float:
        """Predict geoid undulation for a new station."""
        if self.coefficients is None:
            raise ValueError("Model must be fitted before prediction")
        
        x_norm = (station.x - self.x_mean) / 1000
        y_norm = (station.y - self.y_mean) / 1000
        
        A = np.array([1, x_norm, y_norm, x_norm**2, x_norm*y_norm, y_norm**2,
                     x_norm**3, x_norm**2*y_norm, x_norm*y_norm**2, y_norm**3])
        return float(A @ self.coefficients)

def main():
    # Known stations
    known_stations = [
        Station(531121.569, 4171060.477, 1223.482, 1188.611),
        Station(522139.007, 4175249.228, 986.836, 952.226),
        Station(521965.772, 4177055.988, 929.367, 894.796),
        Station(525985.901, 4181645.566, 888.526, 853.816),
        Station(527321.854, 4177938.485, 1008.752, 973.975),
        Station(532702.166, 4184439.027, 915.429, 880.430),
        Station(531409.083, 4183177.180, 918.169, 883.249),
        Station(528687.730, 4181432.714, 928.932, 894.141),
        Station(530800.931, 4182399.516, 927.869, 892.995),
        Station(524599.277, 4181624.668, 889.236, 854.547),
        Station(530080.624, 4174023.790, 1190.143, 1155.250),
        Station(527448.386, 4180150.776, 933.986, 899.226),
        Station(522187.785, 4180966.223, 883.935, 849.251),
        Station(523840.797, 4181543.848, 891.823, 857.109),
        Station(533721.734, 4172811.346, 1260.599, 1225.547),
        Station(530128.716, 4182144.569, 930.177, 895.307),
        Station(533041.683, 4170351.896, 1253.464, 1218.518),
        Station(518442.199, 4174291.701, 892.537, 858.126),
        Station(532328.018, 4170762.774, 1229.461, 1194.539),
        Station(530030.643, 4172850.093, 1256.650, 1221.744)
    ]

    # New stations to predict
    new_stations = [
        Station(526000.000, 4178400.000, 925.354),
        Station(526560.000, 4178000.000, 966.368)
    ]

    # Process
    network = GeodeticNetwork(known_stations)
    network.fit()
    
    results = []
    for station in new_stations:
        N = network.predict(station)
        station.H = station.h - N
        results.append({
            'X': station.x,
            'Y': station.y,
            'h': station.h,
            'N': N,
            'H': station.H
        })

    # Output
    print("\nModel Coefficients:", network.coefficients.flatten())
    print("Model RMS Error (m0):", network.m0)
    print("\nNew Station Results:")
    print(pd.DataFrame(results))

if __name__ == "__main__":
    main()


# In[ ]:




