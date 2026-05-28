import numpy as np
import copy 
import pickle 
import uuid
from typing import List, Dict, Optional
from pydantic import BaseModel
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware





app = FastAPI(title="Island Tournament Evolutionary API")

# --- KONFIGURACJA CORS (Kluczowa dla połączenia z Next.js) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # W produkcji zmień na konkretny adres URL z Vercela
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GLOBALNE PRZECHOWALNIE DANYCH IN-MEMORY (Zamiast bazy danych na start) ---
SIMULATIONS = {}   # Przechowuje postęp aktywnych i ukończonych symulacji
SAVED_NETWORKS = {} # Przechowuje boty, które użytkownik zdecydował się zapisać

# --- MODELE PYDANTIC (Walidacja struktur JSON wejścia/wyjścia) ---
class SimulationParams(BaseModel):
    liczba_wysp: int = 5
    wielkosc_wyspy: int = 40
    liczba_epok: int = 100
    co_ile_kolonizacja: int = 10

class NetworkSaveRequest(BaseModel):
    name: str
    weights: Dict[str, List]

class GameStepRequest(BaseModel):
    player_move: int  # 1 lub -1
    bot_move: int    # 1 lub -1
    stan_wewnetrzny: List[List[float]] # Macierz 1x4 stanu agenta
    weights: Dict[str, List]

class CustomTournamentRequest(BaseModel):
    selected_network_ids: List[str]
    static_bots: List[str] # np. ["AllC", "AllD", "Grudger"]

# --- TWOJA LOGIKA SIECI I AGENTA ---
np.random.seed(0)

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

class Agent():
    def __init__(self):
        self.wrodzony_stan = np.random.randn(1,4) * 0.1
        self.stan_wewnetrzny = np.copy(self.wrodzony_stan) 
        self.wagi_wejscia_rekurencyjne = np.random.randn(4,4) * 0.1
        self.wagi_wejscia = np.random.randn(2,4) * 0.1
        self.bias_wejscia = np.random.randn(1,4) * 0.1        
        self.wagi_wyjscia = np.random.randn(4,1) * 0.1
        self.bias_wyjscia = np.random.randn(1,1) * 0.1  
        
        self.struktura_wag = ['wrodzony_stan', 'wagi_wejscia_rekurencyjne', 
                              'wagi_wejscia', 'bias_wejscia', 
                              'wagi_wyjscia', 'bias_wyjscia']

    def resetuj_pamiec(self):
        self.stan_wewnetrzny = np.copy(self.wrodzony_stan)

    def krok(self, x):
        self.stan_wewnetrzny = np.tanh(np.dot(x, self.wagi_wejscia) + 
                                       np.dot(self.stan_wewnetrzny, self.wagi_wejscia_rekurencyjne) + 
                                       self.bias_wejscia)
        return sigmoid((np.dot(self.stan_wewnetrzny, self.wagi_wyjscia) + self.bias_wyjscia))

    def mutuj(self, tempo_mutacji=0.03, szansa_na_mutacje_wagi=0.2):
        for nazwa_wagi in self.struktura_wag:
            waga = getattr(self, nazwa_wagi)
            maska_mutacji = np.random.rand(*waga.shape) < szansa_na_mutacje_wagi
            szum = np.random.randn(*waga.shape) * tempo_mutacji
            setattr(self, nazwa_wagi, waga + (maska_mutacji * szum))

    def sklonuj(self):
        nowy = Agent()
        for nazwa_wagi in self.struktura_wag:
            setattr(nowy, nazwa_wagi, np.copy(getattr(self, nazwa_wagi)))
        return nowy 

    def krzyzuj_z(self, partner):
        potomek = Agent()
        for nazwa_wagi in self.struktura_wag:
            waga_rodzic1 = getattr(self, nazwa_wagi)
            waga_rodzic2 = getattr(partner, nazwa_wagi)
            maska = np.random.rand(*waga_rodzic1.shape) > 0.5
            setattr(potomek, nazwa_wagi, np.where(maska, waga_rodzic1, waga_rodzic2))
        return potomek

# --- FUNKCJE POMOCNICZE (Konwersja Agent <-> JSON Serializowalny Słownik) ---
def serialize_agent(agent: Agent) -> Dict[str, List]:
    return {nazwa: getattr(agent, nazwa).tolist() for nazwa in agent.struktura_wag}

def deserialize_agent(weights_dict: Dict[str, List]) -> Agent:
    agent = Agent()
    for nazwa in agent.struktura_wag:
        setattr(agent, nazwa, np.array(weights_dict[nazwa]))
    return agent

# --- TWOJE FUNKCJE ROZGRYWKI I TESTÓW ---
def rozegraj_gre(agent1, agent2, liczba_rund=100):
    agent1.resetuj_pamiec()
    agent2.resetuj_pamiec()
    wynik_agenta1, wynik_agenta2, ilosc_wspolprac = 0, 0, 0
    ostatni_ruch_agenta1, ostatni_ruch_agenta2 = 1, 1
    
    for _ in range(liczba_rund):
        wejscie_agenta1 = np.array([[ostatni_ruch_agenta1, ostatni_ruch_agenta2]])
        wejscie_agenta2 = np.array([[ostatni_ruch_agenta2, ostatni_ruch_agenta1]])
        
        praw_ruchu_agenta1 = agent1.krok(wejscie_agenta1).item()
        praw_ruchu_agenta2 = agent2.krok(wejscie_agenta2).item()
        
        ruch_agenta1 = 1 if praw_ruchu_agenta1 >= 0.5 else -1
        ruch_agenta2 = 1 if praw_ruchu_agenta2 >= 0.5 else -1
        
        if ruch_agenta1 == 1 and ruch_agenta2 == 1:
            wynik_agenta1 += 3; wynik_agenta2 += 3; ilosc_wspolprac += 2
        elif ruch_agenta1 == -1 and ruch_agenta2 == 1:
            wynik_agenta1 += 5; wynik_agenta2 += 0; ilosc_wspolprac += 1
        elif ruch_agenta1 == 1 and ruch_agenta2 == -1:
            wynik_agenta1 += 0; wynik_agenta2 += 5; ilosc_wspolprac += 1
        elif ruch_agenta1 == -1 and ruch_agenta2 == -1:
            wynik_agenta1 += 1; wynik_agenta2 += 1

        ostatni_ruch_agenta1, ostatni_ruch_agenta2 = ruch_agenta1, ruch_agenta2
        
    return wynik_agenta1, wynik_agenta2, ilosc_wspolprac, liczba_rund

def test_bota_laboratoryjnego(agent, typ_bota, liczba_rund=30):
    agent.resetuj_pamiec()
    ostatni_ruch_agenta, ostatni_ruch_bota = 1, 1
    ruchy_agenta_historia = []
    grudger_aktywny = False
    
    for r_idx in range(liczba_rund):
        wejscie_agenta = np.array([[ostatni_ruch_agenta, ostatni_ruch_bota]])
        praw_ruchu = agent.krok(wejscie_agenta).item()
        ruch_agenta = 1 if praw_ruchu >= 0.5 else -1
        ruchy_agenta_historia.append('C' if ruch_agenta == 1 else 'D')
        
        if typ_bota == 'AllC': ruch_bota = 1
        elif typ_bota == 'AllD': ruch_bota = -1
        elif typ_bota == 'Grudger':
            if ruch_agenta == -1: grudger_aktywny = True
            ruch_bota = -1 if grudger_aktywny else 1
        elif typ_bota == 'Alternator': ruch_bota = 1 if r_idx % 2 == 0 else -1
        elif typ_bota == 'Joss':
            ruch_bota = ostatni_ruch_agenta
            if np.random.rand() < 0.10: ruch_bota = -1
        elif typ_bota == 'SneakyPacifist': ruch_bota = -1 if r_idx == 0 else 1
            
        ostatni_ruch_agenta, ostatni_ruch_bota = ruch_agenta, ruch_bota
        
    return "".join(ruchy_agenta_historia)

# --- ASYNCHRONICZNE ZADANIE TŁA DLA TURNIEJU ---
def background_island_tournament(task_id: str, params: SimulationParams):
    liczba_wysp = params.liczba_wysp
    wielkosc_wyspy = params.wielkosc_wyspy
    liczba_epok = params.liczba_epok
    co_ile_kolonizacja = params.co_ile_kolonizacja

    wyspy = [[Agent() for _ in range(wielkosc_wyspy)] for _ in range(liczba_wysp)]
    najlepszy_globalny_agent = None
    najwyzszy_globalny_fitness = -1

    for numer_epoki in range(liczba_epok):
        globalna_ilosc_wspolprac = 0
        globalna_ilosc_ruchow = 0
        sredni_fitness_wysp = []
        nowe_wyspy = []

        for w_idx in range(liczba_wysp):
            populacja_wyspy = wyspy[w_idx]
            wyszukane_punkty = np.zeros(wielkosc_wyspy)
            wyszukane_ruchy = np.zeros(wielkosc_wyspy)

            for i in range(wielkosc_wyspy):
                for j in range(i + 1, wielkosc_wyspy):
                    p1, p2, wspolprace, ruchy = rozegraj_gre(populacja_wyspy[i], populacja_wyspy[j])
                    wyszukane_punkty[i] += p1; wyszukane_ruchy[i] += ruchy
                    wyszukane_punkty[j] += p2; wyszukane_ruchy[j] += ruchy
                    globalna_ilosc_wspolprac += wspolprace
                    globalna_ilosc_ruchow += ruchy

            fitness_wyspy = wyszukane_punkty / wyszukane_ruchy
            sredni_fitness_wysp.append(float(np.mean(fitness_wyspy)))

            max_lokalny_idx = np.argmax(fitness_wyspy)
            if fitness_wyspy[max_lokalny_idx] > najwyzszy_globalny_fitness:
                najwyzszy_globalny_fitness = float(fitness_wyspy[max_lokalny_idx])
                najlepszy_globalny_agent = populacja_wyspy[max_lokalny_idx].sklonuj()

            nowa_populacja_wyspy = []
            najlepszy_lokalny = populacja_wyspy[np.argmax(fitness_wyspy)].sklonuj()
            nowa_populacja_wyspy.append(najlepszy_lokalny)

            def selekcja_turniejowa_lokalna():
                c1, c2 = np.random.choice(wielkosc_wyspy, size=2, replace=False)
                return populacja_wyspy[c1] if fitness_wyspy[c1] > fitness_wyspy[c2] else populacja_wyspy[c2]

            while len(nowa_populacja_wyspy) < wielkosc_wyspy:
                r1 = selekcja_turniejowa_lokalna(); r2 = selekcja_turniejowa_lokalna()
                dziecko = r1.krzyzuj_z(r2) if np.random.rand() < 0.7 else r1.sklonuj()
                dziecko.mutuj(tempo_mutacji=0.03, szansa_na_mutacje_wagi=0.2)
                nowa_populacja_wyspy.append(dziecko)
                
            nowe_wyspy.append(nowa_populacja_wyspy)
            
        wyspy = nowe_wyspy

        # Obsługa kolonizacji
        if numer_epoki > 0 and numer_epoki % co_ile_kolonizacja == 0:
            najlepsza_wyspa = np.argmax(sredni_fitness_wysp)
            najgorsza_wyspa = np.argmin(sredni_fitness_wysp)
            if najlepsza_wyspa != najgorsza_wyspa:
                for i in range(wielkosc_wyspy):
                    klon = wyspy[najlepsza_wyspa][i].sklonuj()
                    klon.mutuj(tempo_mutacji=0.05, szansa_na_mutacje_wagi=0.3)
                    wyspy[najgorsza_wyspa][i] = klon

        # Zapisywanie logów do słownika, z którego Next.js pobiera dane
        procent_wspolpracy = (globalna_ilosc_wspolprac / (globalna_ilosc_ruchow * 2)) * 100
        
        # Generowanie profilu psychologicznego na żywo co 5 epok
        profil_lab = {}
        if numer_epoki % 5 == 0 and najlepszy_globalny_agent is not None:
            profil_lab = {
                "AllC": test_bota_laboratoryjnego(najlepszy_globalny_agent, 'AllC'),
                "AllD": test_bota_laboratoryjnego(najlepszy_globalny_agent, 'AllD'),
                "Grudger": test_bota_laboratoryjnego(najlepszy_globalny_agent, 'Grudger'),
                "Alternator": test_bota_laboratoryjnego(najlepszy_globalny_agent, 'Alternator'),
                "Joss": test_bota_laboratoryjnego(najlepszy_globalny_agent, 'Joss'),
                "SneakyPacifist": test_bota_laboratoryjnego(najlepszy_globalny_agent, 'SneakyPacifist'),
            }

        # Aktualizacja stanu globalnego dla frontendu
        SIMULATIONS[task_id]["current_epoch"] = numer_epoki
        SIMULATIONS[task_id]["history"].append({
            "epoch": numer_epoki,
            "avg_fitness_per_island": [round(f, 3) for f in sredni_fitness_wysp],
            "global_cooperation": round(procent_wspolpracy, 2),
            "highest_fitness": round(najwyzszy_globalny_fitness, 3),
            "profile": profil_lab if profil_lab else SIMULATIONS[task_id]["history"][-1]["profile"] if len(SIMULATIONS[task_id]["history"]) > 0 else {}
        })

    # Koniec symulacji
    SIMULATIONS[task_id]["status"] = "COMPLETED"
    if najlepszy_globalny_agent is not None:
        SIMULATIONS[task_id]["best_agent_weights"] = serialize_agent(najlepszy_globalny_agent)


# --- PUNKTY KOŃCOWE (ENDPOINTY API) ---

@app.get("/")
def home():
    return {"message": "Algorytmy Ewolucyjne IPD - API działa stabilnie."}

# 1. Zlecenie symulacji w tle
@app.post("/api/simulation/start")
def start_simulation(params: SimulationParams, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    SIMULATIONS[task_id] = {
        "status": "RUNNING",
        "current_epoch": 0,
        "total_epochs": params.liczba_epok,
        "history": [],
        "best_agent_weights": None
    }
    background_tasks.add_task(background_island_tournament, task_id, params)
    return {"task_id": task_id, "status": "RUNNING"}

# 2. Sprawdzanie postępu symulacji przez Next.js (Polling)
@app.get("/api/simulation/status/{task_id}")
def get_simulation_status(task_id: str):
    if task_id not in SIMULATIONS:
        raise HTTPException(status_code=404, detail="Nie znaleziono symulacji o podanym ID")
    return SIMULATIONS[task_id]

# 3. Zapisanie wybranego agenta do bazy danych
@app.post("/api/networks")
def save_network(req: NetworkSaveRequest):
    network_id = str(uuid.uuid4())
    SAVED_NETWORKS[network_id] = {
        "id": network_id,
        "name": req.name,
        "weights": req.weights
    }
    return {"message": "Sieć zapisana pomyślnie", "network_id": network_id}

# 4. Pobranie listy zapisanych botów
@app.get("/api/networks")
def get_networks():
    # Zwracamy listę bez ciężkich wag, tylko ID i nazwy dla ładnego menu rozwijanego
    return [{"id": net["id"], "name": net["name"]} for net in SAVED_NETWORKS.values()]

# 5. Pełne profilowanie psychologiczne zapisanego bota
@app.get("/api/networks/{network_id}/profile")
def profile_saved_network(network_id: str):
    if network_id not in SAVED_NETWORKS:
        raise HTTPException(status_code=404, detail="Nie znaleziono sieci")
    
    agent = deserialize_agent(SAVED_NETWORKS[network_id]["weights"])
    bots = ['AllC', 'AllD', 'Grudger', 'Alternator', 'Joss', 'SneakyPacifist']
    results = {}
    
    for bot in bots:
        results[bot] = test_bota_laboratoryjnego(agent, bot, liczba_rund=30)
        
    return {
        "network_id": network_id,
        "name": SAVED_NETWORKS[network_id]["name"],
        "profiles": results
    }

# 6. Rozgrywka Krok po Kroku (Stateless - Człowiek vs Bot)
@app.post("/api/game/step")
def play_game_step(req: GameStepRequest):
    # Odtwarzamy agenta z wag nadesłanych z frontendu
    agent = deserialize_agent(req.weights)
    # Wstrzykujemy mu stan wewnętrzny z poprzedniej rundy przesłany z frontu
    agent.stan_wewnetrzny = np.array(req.stan_wewnetrzny)
    
    # Wejście dla sieci: [Ruch gracza, Ostatni ruch bota]
    wejscie = np.array([[req.player_move, req.bot_move]])
    
    # Wykonanie kroku sieci
    praw_ruchu = agent.krok(wejscie).item()
    bot_decision = 1 if praw_ruchu >= 0.5 else -1
    
    return {
        "bot_move": bot_decision,
        "new_stan_wewnetrzny": agent.stan_wewnetrzny.tolist() # Zwracamy zaktualizowany stan do Next.js
    }





import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# --- POŁĄCZENIE Z NEON TECH ---
# Wklej tu swój Connection String z Neona (lub pobieraj go z os.environ)
DATABASE_URL = "postgresql://neondb_owner:npg_ai1lc9UvBXHF@ep-autumn-sunset-aq8g2syc-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_db_connection():
    # RealDictCursor sprawia, że Postgres zwraca dane jako ładne słowniki Pythonowe
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """Tworzy tabelę w bazie Neon, jeśli jeszcze nie istnieje"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_networks (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            weights JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

# Odpalamy inicjalizację bazy przy starcie FastAPI
init_db()


# --- PODMIENIONE ENDPOINTY BAZODANOWE ---

# 3. Zapisanie wybranego agenta do bazy danych Neon
@app.post("/api/networks")
def save_network(req: NetworkSaveRequest):
    network_id = str(uuid.uuid4())
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Konwertujemy słownik wag na string JSON, aby wszedł do kolumny JSONB
        weights_json = json.dumps(req.weights)
        
        cur.execute(
            "INSERT INTO saved_networks (id, name, weights) VALUES (%s, %s, %s);",
            (network_id, req.name, weights_json)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"message": "Sieć zapisana w Neon Tech!", "network_id": network_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")

# 4. Pobranie listy zapisanych botów z bazy Neon
@app.get("/api/networks")
def get_networks():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Pobieramy tylko ID i nazwę, żeby nie ciągnąć ciężkich wag bez potrzeby
        cur.execute("SELECT id, name FROM saved_networks ORDER BY created_at DESC;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")

# 5. Pełne profilowanie psychologiczne zapisanego bota z bazy Neon
@app.get("/api/networks/{network_id}/profile")
def profile_saved_network(network_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, weights FROM saved_networks WHERE id = %s;", (network_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="Nie znaleziono sieci o podanym ID")
        
        # Odtwarzamy agenta z JSONB z bazy danych
        agent = deserialize_agent(row["weights"])
        bots = ['AllC', 'AllD', 'Grudger', 'Alternator', 'Joss', 'SneakyPacifist']
        results = {}
        
        for bot in bots:
            results[bot] = test_bota_laboratoryjnego(agent, bot, liczba_rund=30)
            
        return {
            "network_id": network_id,
            "name": row["name"],
            "profiles": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd: {str(e)}")