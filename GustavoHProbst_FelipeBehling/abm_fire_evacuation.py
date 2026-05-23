"""
===========================================================================
  ABM de Evacuação em Situação de Incêndio
  Formalismo completo — Seções 1-4 do modelo matemático
  
  Baseado em:
    Gwynne et al. (2021) | Korhonen & Hostikka (2020)
    Lovreglio et al. (2022) | Wang et al. (2023)
    Pelechano et al. (2020) | Zheng et al. (2021)
    Chen et al. (2023) | Al Sadoon et al. (2025)
    Starbuck et al. (2024) | Hui et al. (2024)
===========================================================================
"""

from __future__ import annotations
import numpy as np
from numpy.typing import NDArray
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple
import heapq
import warnings

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# SECÃO 1 ▸ DEFINIÇÃO DO AGENTE
# ─────────────────────────────────────────────────────────────────────────────

class BehaviorState(Enum):
    """
    Máquina de estados comportamental do agente.
    Equação (1.2) — Gwynne et al. (2021)
    """
    PRE_ALARM      = "pre_alarm"
    ALERT          = "alert"
    EVACUATING     = "evacuating"
    INCAPACITATED  = "incapacitated"
    SAFE           = "safe"


@dataclass
class Agent:
    """
    Vetor de estado completo do agente i:
      Ψ_i(t) = (físico, cognitivo, social/decisional)
    Equação (1.1) — Gwynne et al. (2021)
    """
    # ── Identificação ──────────────────────────────────────────────────────
    id: int

    # ── Atributos Físicos ──────────────────────────────────────────────────
    position:     NDArray[np.float64]      # x_i(t)  ∈ R³  [m]
    velocity:     NDArray[np.float64]      # v_i(t)  ∈ R³  [m/s]
    mass:         float = 75.0            # m_i     [kg]
    radius:       float = 0.30            # r_i     [m]
    v_max:        float = 1.34            # v_i^max [m/s] — Gwynne et al. (2021)

    # ── Atributos Cognitivos ───────────────────────────────────────────────
    state:         BehaviorState = BehaviorState.PRE_ALARM   # s_i(t)
    panic:         float = 0.0            # p_i(t)  ∈ [0,1] — Pelechano et al. (2020)
    risk_percept:  float = 0.0            # ρ_i(t)  ∈ [0,1]
    familiarity:   NDArray[np.float64] = field(
                       default_factory=lambda: np.zeros(4))  # f_i(e) ∈ {0,1}^|E|
    pre_evac_time: float = 0.0            # τ_i ~ LogN(μ,σ²) [s]

    # ── Atributos Sociais e Decisional ────────────────────────────────────
    group_id:      int = -1               # G_i
    social_ties:   Dict[int, float] = field(default_factory=dict)  # w_ij ∈ [0,1]
    target_exit:   int = 0               # e_i*(t)
    route:         List[int] = field(default_factory=list)  # ℓ_i(t)

    # ── Internos ──────────────────────────────────────────────────────────
    evac_time:     float = -1.0
    _last_rev_t:   float = 0.0
    _memory_rho:   float = 0.0

    def __post_init__(self):
        if not isinstance(self.position, np.ndarray):
            self.position = np.array(self.position, dtype=float)
        if not isinstance(self.velocity, np.ndarray):
            self.velocity = np.array(self.velocity, dtype=float)

    # ── Eq. 3.10: Velocidade desejada modulada pelo pânico ────────────────
    @property
    def desired_speed(self) -> float:
        """v_i^0(t) = v_i^max * (1 + κ*p_i(t))  — Pelechano et al. (2020)"""
        kappa = 0.3
        return min(self.v_max * (1.0 + kappa * self.panic), 2.5)

    @property
    def is_active(self) -> bool:
        return self.state not in (BehaviorState.INCAPACITATED, BehaviorState.SAFE)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 2 ▸ AMBIENTE E CAMPO DE AMEAÇA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FireFields:
    """
    Campos de saída do FDS interpolados na grade ABM.
    Equação (2.7) — Korhonen & Hostikka (2020)

    F(x,t) = (T, C_CO, Φ, q̇)
    """
    shape: Tuple[int, int]            # (Nx, Ny)
    dx:    float = 0.5               # resolução espacial [m]

    def __post_init__(self):
        Nx, Ny = self.shape
        self.temperature     = np.full((Nx, Ny), 20.0)   # T [°C]
        self.co_concentration = np.zeros((Nx, Ny))       # C_CO [ppm]
        self.smoke_density   = np.zeros((Nx, Ny))        # Φ [m⁻¹]
        self.heat_release    = np.zeros((Nx, Ny))        # q̇ [kW/m²]

    def update_from_fds(self, fds_data: Dict[str, NDArray]) -> None:
        """Ingesta campos do FDS — acoplamento Hui et al. (2024)"""
        self.temperature      = fds_data.get("T",    self.temperature)
        self.co_concentration = fds_data.get("CO",   self.co_concentration)
        self.smoke_density    = fds_data.get("Phi",  self.smoke_density)
        self.heat_release     = fds_data.get("qdot", self.heat_release)

    def compute_risk_field(
        self,
        w_T: float = 0.4,
        w_CO: float = 0.35,
        w_Phi: float = 0.25,
    ) -> NDArray[np.float64]:
        """
        Campo de risco composto R(x,t).
        Equação (2.8) — Chen et al. (2023)

        R = ω_T * T̂ + ω_CO * Ĉ_CO + ω_Φ * Φ̂
        """
        T_incap, T_0   = 60.0,  20.0
        CO_incap       = 1400.0            # ppm
        Phi_incap      = 10.0             # m⁻¹

        T_hat   = np.clip((self.temperature - T_0) / (T_incap - T_0), 0, 1)
        CO_hat  = np.clip(self.co_concentration / CO_incap,            0, 1)
        Phi_hat = np.clip(self.smoke_density    / Phi_incap,           0, 1)

        return w_T * T_hat + w_CO * CO_hat + w_Phi * Phi_hat   # ∈ [0,1]


class NavigationGraph:
    """
    Grafo de navegação BIM dinâmico.
    Equações (2.4)-(2.6) — Wang et al. (2023)

    G_nav = (V, E_arco, W(t))
    """
    def __init__(self):
        self.nodes: Dict[int, NDArray] = {}        # {node_id: (x,y,z)}
        self.adj:   Dict[int, List[int]] = {}       # lista de adjacência
        self.base_dist: Dict[Tuple[int,int], float] = {}   # d_uv

    def add_node(self, nid: int, pos: NDArray) -> None:
        self.nodes[nid] = np.array(pos, dtype=float)
        if nid not in self.adj:
            self.adj[nid] = []

    def add_edge(self, u: int, v: int, bidirectional: bool = True) -> None:
        d = float(np.linalg.norm(self.nodes[u] - self.nodes[v]))
        self.base_dist[(u, v)] = d
        self.adj[u].append(v)
        if bidirectional:
            self.base_dist[(v, u)] = d
            self.adj[v].append(u)

    def edge_weight(
        self,
        u: int, v: int,
        risk_field: NDArray,
        crowd_density: NDArray,
        grid_dx: float = 0.5,
        alpha_psi: float = 3.0,
        beta_psi:  float = 2.0,
        rho_jam:   float = 5.0,
    ) -> float:
        """
        W_uv(t) = d_uv * ψ_fogo * ψ_crowd
        Equação (2.5) — Wang et al. (2023)
        """
        d_uv = self.base_dist.get((u, v), 1e9)

        # Risco médio no segmento uv
        pos_u = self.nodes[u]
        r_uv  = risk_field[
            int(pos_u[0] / grid_dx) % risk_field.shape[0],
            int(pos_u[1] / grid_dx) % risk_field.shape[1],
        ]
        rho_uv = crowd_density[
            int(pos_u[0] / grid_dx) % crowd_density.shape[0],
            int(pos_u[1] / grid_dx) % crowd_density.shape[1],
        ]

        psi_fire  = 1.0 + alpha_psi * r_uv
        psi_crowd = 1.0 + beta_psi  * (rho_uv / max(rho_jam, 1e-6))

        return d_uv * psi_fire * psi_crowd

    def shortest_path(
        self,
        start: int,
        goal:  int,
        risk_field: NDArray,
        crowd_density: NDArray,
    ) -> List[int]:
        """
        Dijkstra sobre grafo com pesos dinâmicos.
        Equação (3.21) — Hui et al. (2024)

        ℓ_i*(t) = argmin_{ℓ: x_i → e_i*} Σ_{(u,v)∈ℓ} W_uv(t)
        """
        dist   = {n: float('inf') for n in self.nodes}
        prev   = {n: None         for n in self.nodes}
        dist[start] = 0.0
        pq = [(0.0, start)]

        while pq:
            d_u, u = heapq.heappop(pq)
            if u == goal:
                break
            if d_u > dist[u]:
                continue
            for v in self.adj.get(u, []):
                w   = self.edge_weight(u, v, risk_field, crowd_density)
                alt = dist[u] + w
                if alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u
                    heapq.heappush(pq, (alt, v))

        # Reconstrói caminho
        path, cur = [], goal
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        return list(reversed(path))


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 3.1 ▸ PERCEPÇÃO
# ─────────────────────────────────────────────────────────────────────────────

def compute_visibility_distance(
    smoke_density: float,
    illuminance_factor: float = 3.0,
) -> float:
    """
    Lei de Beer-Lambert: d_vis(Φ) = C_s / Φ
    Equação (3.2) — Korhonen & Hostikka (2020)
    """
    phi = max(smoke_density, 1e-6)
    return illuminance_factor / phi


def perceive_risk(
    agent: Agent,
    risk_field: NDArray,
    grid_dx: float,
    lambda_mem: float = 0.15,
) -> float:
    """
    ρ_i(t) = média do risco no campo de visão + memória.
    Equação (3.3)

    ρ_i(t) = (1/|V_i|) ∫_{V_i} R(x,t) dx + λ_mem * ρ_i(t-Δt)
    """
    ix = int(agent.position[0] / grid_dx) % risk_field.shape[0]
    iy = int(agent.position[1] / grid_dx) % risk_field.shape[1]
    r  = 3   # raio do campo de visão em células

    x0, x1 = max(0, ix-r), min(risk_field.shape[0], ix+r+1)
    y0, y1 = max(0, iy-r), min(risk_field.shape[1], iy+r+1)
    local   = risk_field[x0:x1, y0:y1]

    rho_instant = float(np.mean(local)) if local.size > 0 else 0.0
    return rho_instant + lambda_mem * agent._memory_rho


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 3.2 ▸ DINÂMICA DE PÂNICO
# ─────────────────────────────────────────────────────────────────────────────

def update_panic(
    agent:   Agent,
    agents:  List[Agent],
    rho_i:   float,
    alpha_p: float = 0.25,
    gamma_p: float = 0.10,
    delta_p: float = 0.05,
    dt:      float = 0.1,
) -> float:
    """
    Dinâmica de pânico com contágio social.
    Equação (3.5) — Pelechano et al. (2020)

    dp_i/dt = α_p·ρ_i(t) + γ_p·p̄_{G_i}(t) - δ_p·p_i(t)

    Integração de Euler: p_i(t+Δt) = p_i(t) + Δt * dp/dt
    """
    # Pânico médio do grupo (contágio social)
    group_members = [a for a in agents
                     if a.group_id == agent.group_id and a.id != agent.id
                     and a.is_active]
    p_group_mean  = (np.mean([a.panic for a in group_members])
                     if group_members else 0.0)

    dp_dt = (alpha_p * rho_i
             + gamma_p * p_group_mean
             - delta_p * agent.panic)

    p_new = agent.panic + dt * dp_dt
    return float(np.clip(p_new, 0.0, 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 3.3 ▸ MODELO DE ESCOLHA DISCRETA (MNL)
# ─────────────────────────────────────────────────────────────────────────────

def compute_exit_utilities(
    agent:        Agent,
    exits:        Dict[int, NDArray],   # {exit_id: posição [m]}
    smoke_exits:  Dict[int, float],     # Φ̂ médio no caminho
    crowd_exits:  Dict[int, int],       # N de agentes por saída
    social_inf:   Dict[int, float],     # SI_ie = fração do grupo → e
    beta_d:   float = -0.012,
    beta_f:   float =  1.85,
    beta_phi: float = -2.43,
    beta_rho: float = -0.60,
    beta_soc: float =  0.78,
) -> Dict[int, float]:
    """
    Utilidade percebida da saída e pelo agente i.
    Equação (3.6) — Lovreglio et al. (2022) [calibrado em VR]

    U_ie = β_d·D_ie + β_f·f_i(e) + β_Φ·Φ̂_ie + β_ρ·N_ie + β_soc·SI_ie + ε_ie
    """
    utilities = {}
    for eid, epos in exits.items():
        D_ie  = float(np.linalg.norm(agent.position[:2] - epos[:2]))
        f_ie  = float(agent.familiarity[eid]) if eid < len(agent.familiarity) else 0.0
        Phi   = smoke_exits.get(eid, 0.0)
        N_ie  = crowd_exits.get(eid, 0)
        SI_ie = social_inf.get(eid, 0.0)

        # Erro Gumbel (garante propriedade IIA do MNL)
        eps   = np.random.gumbel(0, 0.5)

        utilities[eid] = (beta_d   * D_ie
                        + beta_f   * f_ie
                        + beta_phi * Phi
                        + beta_rho * N_ie
                        + beta_soc * SI_ie
                        + eps)
    return utilities


def mnl_exit_choice(utilities: Dict[int, float]) -> int:
    """
    Escolha de saída via Modelo Logit Multinomial.
    Equação (3.7) — Lovreglio et al. (2022)

    P(e_i* = e | t) = exp(U_ie) / Σ_k exp(U_ik)
    """
    eids    = list(utilities.keys())
    u_vals  = np.array([utilities[e] for e in eids])

    # Estabilidade numérica: subtrai o máximo antes do softmax
    u_shift = u_vals - u_vals.max()
    probs   = np.exp(u_shift) / np.exp(u_shift).sum()

    return int(np.random.choice(eids, p=probs))


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 3.4 ▸ MODELO DE FORÇA SOCIAL
# ─────────────────────────────────────────────────────────────────────────────

def social_force(
    agent:       Agent,
    agents:      List[Agent],
    walls:       List[NDArray],
    risk_field:  NDArray,
    grid_dx:     float,
    A_s:  float = 2000.0,    # [N]   — força social
    B_s:  float = 0.08,      # [m]   — alcance
    lam:  float = 0.50,      # anisotropia
    k_n:  float = 120000.0,  # [N/m] — contato normal
    k_t:  float = 240000.0,  # [N/(m/s)] — fricção tangencial
    eta_f: float = 500.0,    # [N]  — repulsão do fogo
    kappa_g: float = 150.0,  # [N]  — coesão de grupo
    d_coh: float = 2.0,      # [m]  — raio de coesão
    tau:  float = 0.50,      # [s]  — tempo de relaxação
) -> NDArray[np.float64]:
    """
    Equação de movimento — Modelo de Força Social.
    Equação (3.9) — Pelechano et al. (2020)

    m_i·dv_i/dt = f_desejo + Σ f_social + Σ f_parede + f_grupo + f_fogo
    """
    F_total = np.zeros(3)

    # ── f_desire: Equação (3.10) ──────────────────────────────────────────
    if len(agent.route) >= 1:
        # Direção desejada: vetor até o próximo nó da rota
        tgt = agent.route[0]
        if not isinstance(tgt, np.ndarray):
            tgt = np.array(tgt, dtype=float)
        # Garantir 3 dimensões
        if tgt.shape[0] == 2:
            tgt = np.append(tgt, 0.0)
        delta    = tgt - agent.position
        dist     = np.linalg.norm(delta)
        e_hat    = delta / dist if dist > 1e-6 else np.zeros(3)
        f_desire = agent.mass * (agent.desired_speed * e_hat - agent.velocity) / tau
        F_total += f_desire

    # ── f_social + f_contact: Equações (3.11)–(3.13) ─────────────────────
    for other in agents:
        if other.id == agent.id or not other.is_active:
            continue
        n_vec   = agent.position - other.position
        dist_ij = np.linalg.norm(n_vec)
        if dist_ij < 1e-6:
            continue
        n_hat    = n_vec / dist_ij
        r_ij     = agent.radius + other.radius

        # Anisotropia (campo visual) — Eq. (3.12)
        cos_phi  = np.dot(-n_hat[:2], agent.velocity[:2] /
                          (np.linalg.norm(agent.velocity[:2]) + 1e-9))
        Lambda   = lam + (1 - lam) * (1 + cos_phi) / 2

        # Repulsão psicológica — Eq. (3.11)
        f_ij = A_s * np.exp((r_ij - dist_ij) / B_s) * n_hat * Lambda

        F_total[:len(f_ij)] += f_ij[:3] if len(f_ij) >= 3 else np.pad(f_ij, (0, 3-len(f_ij)))

        # Contato físico (sobreposição) — Eq. (3.13)
        if dist_ij < r_ij:
            overlap   = r_ij - dist_ij
            t_hat     = np.array([-n_hat[1], n_hat[0], 0.0])
            dv_t      = np.dot(other.velocity - agent.velocity, t_hat)
            f_contact = k_n * overlap * n_hat - k_t * overlap * dv_t * t_hat
            F_total  += f_contact

    # ── f_fire: repulsão do campo de risco — Eq. (3.14) ──────────────────
    ix = int(agent.position[0] / grid_dx) % risk_field.shape[0]
    iy = int(agent.position[1] / grid_dx) % risk_field.shape[1]

    grad_R = np.zeros(3)
    if ix > 0 and ix < risk_field.shape[0]-1:
        grad_R[0] = (risk_field[ix+1, iy] - risk_field[ix-1, iy]) / (2 * grid_dx)
    if iy > 0 and iy < risk_field.shape[1]-1:
        grad_R[1] = (risk_field[ix, iy+1] - risk_field[ix, iy-1]) / (2 * grid_dx)

    # Coef. racional: (1 - p_i) reduz com pânico crescente
    f_fire  = -eta_f * (1.0 - agent.panic) * grad_R
    F_total += f_fire

    # ── f_group: coesão de grupo — Eq. (3.15) ────────────────────────────
    for other in agents:
        w_ij = agent.social_ties.get(other.id, 0.0)
        if w_ij < 1e-6 or not other.is_active:
            continue
        delta  = other.position - agent.position
        dist_g = np.linalg.norm(delta)
        if dist_g > d_coh and dist_g > 1e-6:
            f_group  = w_ij * kappa_g * (delta / dist_g)
            F_total += f_group

    return F_total


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 3.5 ▸ AUTÔMATO CELULAR PARA ESCADARIAS
# ─────────────────────────────────────────────────────────────────────────────

class StaircaseCA:
    """
    Autômato Celular para escadarias.
    Equações (3.16)–(3.20) — Zheng et al. (2021)
    """
    FREE     = 0
    OCCUPIED = 1
    BLOCKED  = 2

    def __init__(self, shape: Tuple[int, int], exits: List[Tuple[int,int]]):
        self.shape   = shape
        self.exits   = exits
        self.grid    = np.zeros(shape, dtype=int)
        self.S       = self._compute_static_floor_field()  # Eq. (3.16)
        self.D       = np.zeros(shape, dtype=float)        # Eq. (3.17)

    def _compute_static_floor_field(self) -> NDArray[np.float64]:
        """
        Campo de piso estático via Dijkstra sobre grade CA.
        Equação (3.16): S_c = min_{e ∈ E_CA} d_CA(c, c_e)
        """
        dist = np.full(self.shape, np.inf)
        pq   = []
        for ex, ey in self.exits:
            dist[ex, ey] = 0.0
            heapq.heappush(pq, (0.0, ex, ey))

        while pq:
            d, x, y = heapq.heappop(pq)
            if d > dist[x, y]:
                continue
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                nx, ny = x+dx, y+dy
                if 0 <= nx < self.shape[0] and 0 <= ny < self.shape[1]:
                    step = 1.0 if dx == 0 or dy == 0 else np.sqrt(2)
                    alt  = dist[x, y] + step
                    if alt < dist[nx, ny]:
                        dist[nx, ny] = alt
                        heapq.heappush(pq, (alt, nx, ny))
        return dist

    def update_dynamic_floor(
        self,
        delta_D: float = 0.05,
        alpha_D: float = 0.10,
    ) -> None:
        """
        Difusão e decaimento do campo de piso dinâmico.
        Equação (3.17):
        D_c(k+1) = D_c(k) * (1-δ_D) * (1-α_D) + α_D * média(D_{c'})
        """
        D_new = np.zeros_like(self.D)
        for x in range(self.shape[0]):
            for y in range(self.shape[1]):
                neighbors = []
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < self.shape[0] and 0 <= ny < self.shape[1]:
                        neighbors.append(self.D[nx, ny])
                neigh_mean = np.mean(neighbors) if neighbors else 0.0
                D_new[x, y] = (self.D[x, y] * (1 - delta_D) * (1 - alpha_D)
                                + alpha_D * neigh_mean)
        self.D = D_new

    def transition_probabilities(
        self,
        x: int, y: int,
        risk_field: NDArray,
        k_S: float = 2.0,
        k_D: float = 1.0,
        k_R: float = 1.5,
    ) -> Dict[Tuple[int,int], float]:
        """
        Probabilidade de transição celular.
        Equação (3.18) — Zheng et al. (2021)

        P(c→c') = ξ_c' * exp(k_S*S_{c'} + k_D*D_{c'} - k_R*R_{c'})
                  ─────────────────────────────────────────────────────
                  Σ_{c''∈N(c)} ξ_{c''} * exp(k_S*S_{c''} + k_D*D_{c''} - k_R*R_{c''})
        """
        raw = {}
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x+dx, y+dy
            if not (0 <= nx < self.shape[0] and 0 <= ny < self.shape[1]):
                continue
            xi = 1.0 if self.grid[nx, ny] == self.FREE else 0.0   # célula disponível
            if xi < 1e-6:
                continue

            # S usa sinal negativo pois menor distância = melhor
            r_val = float(risk_field[
                nx % risk_field.shape[0],
                ny % risk_field.shape[1],
            ])
            score = np.exp(-k_S * self.S[nx, ny]
                           + k_D * self.D[nx, ny]
                           - k_R * r_val)
            raw[(nx, ny)] = xi * score

        total = sum(raw.values())
        if total < 1e-9:
            return {}
        return {cell: v / total for cell, v in raw.items()}

    def stair_speed(
        self,
        v0:     float,
        panic:  float,
        eta_0:  float = 0.80,
        eta_min: float = 0.40,
    ) -> float:
        """
        Velocidade em escadaria modulada pelo pânico.
        Equação (3.20)

        v_escada = v_0 * η(p_i) = v_0 * [η_0 - (η_0 - η_min)*p_i]
        """
        eta = eta_0 - (eta_0 - eta_min) * panic
        return v0 * eta


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 4 ▸ LOOP PRINCIPAL DE SIMULAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

class FireEvacuationABM:
    """
    Motor principal do ABM de Evacuação em Incêndio.
    Arquitetura de loop temporal com 3 frequências aninhadas.
    Hui et al. (2024), Starbuck et al. (2024)
    """
    def __init__(
        self,
        agents:    List[Agent],
        fire:      FireFields,
        graph:     NavigationGraph,
        stair_ca:  StaircaseCA,
        exits:     Dict[int, NDArray],
        t_alarm:   float = 30.0,
        # Passos temporais
        dt_abm:    float = 0.10,
        dt_dt:     float = 1.00,
        dt_fds:    float = 0.50,
        dt_route:  float = 5.00,
        # Incapacitação
        rho_incap: float = 0.80,
    ):
        self.agents    = agents
        self.fire      = fire
        self.graph     = graph
        self.stair_ca  = stair_ca
        self.exits     = exits
        self.t_alarm   = t_alarm
        self.dt_abm    = dt_abm
        self.dt_dt     = dt_dt
        self.dt_fds    = dt_fds
        self.dt_route  = dt_route
        self.rho_incap = rho_incap

        # Estado de tempo dos sub-loops
        self._t_fds   = 0.0
        self._t_dt    = 0.0
        self._t_route = 0.0
        self.t        = 0.0

        # Campos computados
        self.risk_field    = np.zeros(fire.shape)
        self.crowd_density = np.zeros(fire.shape)

        # KPIs de saída — Starbuck et al. (2024)
        self.log_evac_times: List[float] = []
        self.n_incapacitated = 0

    # ─── Utilidades privadas ──────────────────────────────────────────────
    def _compute_crowd_density(self) -> NDArray:
        """Kernel gaussiano — Equação (2.12)"""
        dx     = self.fire.dx
        Nx, Ny = self.fire.shape
        rho    = np.zeros((Nx, Ny))
        sigma  = 1.5  # [m]
        for a in self.agents:
            if not a.is_active:
                continue
            ix = int(a.position[0] / dx)
            iy = int(a.position[1] / dx)
            for di in range(-3, 4):
                for dj in range(-3, 4):
                    ni, nj = ix+di, iy+dj
                    if 0 <= ni < Nx and 0 <= nj < Ny:
                        d2  = (di*dx)**2 + (dj*dx)**2
                        rho[ni, nj] += np.exp(-d2 / (2*sigma**2))
        return rho

    def _update_behavior_state(self, agent: Agent) -> None:
        """
        Transições da máquina de estados.
        Equação (1.2) — Gwynne et al. (2021)
        """
        if agent.state == BehaviorState.PRE_ALARM and self.t >= self.t_alarm:
            agent.state = BehaviorState.ALERT

        elif agent.state == BehaviorState.ALERT:
            if self.t >= self.t_alarm + agent.pre_evac_time:
                agent.state = BehaviorState.EVACUATING

        # Incapacitação pelo campo de risco
        if agent.state == BehaviorState.EVACUATING:
            if agent.risk_percept >= self.rho_incap:
                agent.state     = BehaviorState.INCAPACITATED
                self.n_incapacitated += 1

    def _check_exit_arrival(self, agent: Agent) -> bool:
        """Verifica chegada à saída (raio de captura 1 m)"""
        for eid, epos in self.exits.items():
            if np.linalg.norm(agent.position[:2] - epos[:2]) < 1.0:
                agent.state      = BehaviorState.SAFE
                agent.evac_time  = self.t
                self.log_evac_times.append(self.t)
                return True
        return False

    def _should_revisit_exit(self, agent: Agent, theta_R: float = 0.05) -> bool:
        """Critério de reavaliação de saída — Hui et al. (2024)"""
        dt_since_rev = self.t - agent._last_rev_t
        delta_R      = abs(agent.risk_percept - agent._memory_rho)
        return dt_since_rev >= 10.0 or delta_R > theta_R

    # ─── Loop principal ───────────────────────────────────────────────────
    def run(self, t_max: float = 300.0) -> Dict:
        """
        Loop temporal principal com 3 frequências aninhadas.
        Seção 4 — Pseudocódigo principal do ABM.

        L1: FDS         (Δt_FDS  ≈ 0.5 s)
        L2: Gêmeo Digital (Δt_DT ≈ 1.0 s)
        L3: ABM agentes   (Δt_ABM ≈ 0.1 s)
        """
        print(f"  Iniciando simulação: {len(self.agents)} agentes, T_max={t_max}s")

        while self.t < t_max:
            n_active = sum(1 for a in self.agents if a.is_active)
            if n_active == 0:
                print(f"  Todos evacuados / incapacitados em t={self.t:.1f}s")
                break

            # ── L1: Atualização FDS ───────────────────────────────────────
            if self.t >= self._t_fds + self.dt_fds:
                fds_data       = self._mock_fds_step()      # ← Interface FDS real
                self.fire.update_from_fds(fds_data)
                self.risk_field = self.fire.compute_risk_field()  # Eq. 2.8
                self._t_fds    = self.t

            # ── L2: Gêmeo Digital ─────────────────────────────────────────
            if self.t >= self._t_dt + self.dt_dt:
                self.crowd_density = self._compute_crowd_density()  # Eq. 2.12
                self.stair_ca.update_dynamic_floor()                # Eq. 3.17
                # Atualização de pesos do grafo
                if self.t >= self._t_route + self.dt_route:
                    self._update_graph_weights()   # Eq. 2.5
                    self._t_route = self.t
                self._t_dt = self.t

            # ── L3: Loop de agentes ───────────────────────────────────────
            for agent in self.agents:

                # 3a: Estado comportamental
                self._update_behavior_state(agent)
                if not agent.is_active:
                    continue

                # 3b: Percepção
                phi_local        = self.fire.smoke_density[
                    int(agent.position[0] / self.fire.dx) % self.fire.shape[0],
                    int(agent.position[1] / self.fire.dx) % self.fire.shape[1],
                ]
                d_vis            = compute_visibility_distance(phi_local)  # Eq. 3.2
                agent.risk_percept = perceive_risk(
                    agent, self.risk_field, self.fire.dx)                  # Eq. 3.3
                agent._memory_rho  = agent.risk_percept

                # 3c: Pânico
                agent.panic = update_panic(
                    agent, self.agents, agent.risk_percept,
                    dt=self.dt_abm)                                        # Eq. 3.5

                # 3d: Escolha de saída (MNL)
                if agent.state == BehaviorState.EVACUATING:
                    if self._should_revisit_exit(agent):
                        smoke_exits = {eid: 0.1 for eid in self.exits}
                        crowd_exits = {eid: 5   for eid in self.exits}
                        social_inf  = {eid: 0.3 for eid in self.exits}
                        utils       = compute_exit_utilities(
                            agent, self.exits,
                            smoke_exits, crowd_exits, social_inf)          # Eq. 3.6
                        agent.target_exit  = mnl_exit_choice(utils)       # Eq. 3.7
                        agent._last_rev_t  = self.t

                    # 3e: Planejamento de rota (Dijkstra dinâmico)
                    if not agent.route:
                        epos     = self.exits.get(agent.target_exit,
                                                  list(self.exits.values())[0])
                        agent.route = [epos[:2]]   # simplificado: vetor direto

                    # 3f: Forças sociais & atualização de posição
                    F = social_force(
                        agent, self.agents, [],
                        self.risk_field, self.fire.dx)                     # Eq. 3.9

                    acc          = F / agent.mass
                    v_new        = agent.velocity + acc * self.dt_abm
                    speed        = np.linalg.norm(v_new)
                    if speed > agent.v_max:
                        v_new *= agent.v_max / speed
                    agent.velocity  = v_new
                    agent.position += agent.velocity * self.dt_abm

                # 3h: Verificação de incapacitação (já feita em state update)
                # 3i: Chegada à saída
                self._check_exit_arrival(agent)

            self.t = round(self.t + self.dt_abm, 6)

        return self._compute_kpis()

    def _update_graph_weights(self) -> None:
        """Atualiza pesos das arestas com risco e densidade atuais."""
        for (u, v) in list(self.graph.base_dist.keys()):
            _ = self.graph.edge_weight(u, v, self.risk_field, self.crowd_density)

    def _mock_fds_step(self) -> Dict[str, NDArray]:
        """Substituto do FDS para testes; substituir pela API real do FDS+Evac."""
        Nx, Ny = self.fire.shape
        spread = min(self.t / 300.0, 1.0)
        cx, cy = Nx // 4, Ny // 2
        xx, yy = np.meshgrid(np.arange(Nx), np.arange(Ny), indexing='ij')
        dist2  = (xx - cx)**2 + (yy - cy)**2
        T_new  = 20.0 + 200.0 * spread * np.exp(-dist2 / (10 + 50*spread))
        Phi_new= 5.0  * spread * np.exp(-dist2 / (15 + 60*spread))
        CO_new = 800  * spread * np.exp(-dist2 / (20 + 70*spread))
        return {"T": T_new, "Phi": Phi_new, "CO": CO_new,
                "qdot": np.zeros((Nx, Ny))}

    def _compute_kpis(self) -> Dict:
        """
        Indicadores-chave de desempenho.
        Starbuck et al. (2024)
        """
        safe_times = self.log_evac_times
        rset       = max(safe_times) if safe_times else self.t
        aset       = 120.0  # do FDS (exemplo)
        return {
            "RSET_s"         : round(rset, 2),
            "ASET_s"         : aset,
            "Safety_margin_s": round(aset - rset, 2),
            "N_safe"         : len(safe_times),
            "N_incapacitated": self.n_incapacitated,
            "N_total"        : len(self.agents),
            "Mean_evac_time" : round(float(np.mean(safe_times)), 2) if safe_times else None,
            "Std_evac_time"  : round(float(np.std(safe_times)),  2) if safe_times else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# INICIALIZAÇÃO E DEMONSTRAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

def create_demo_scenario(n_agents: int = 20, seed: int = 42) -> FireEvacuationABM:
    """
    Cria cenário de demonstração: corredor 20×10m com 2 saídas.
    """
    rng = np.random.default_rng(seed)

    # ── Agentes ───────────────────────────────────────────────────────────
    agents = []
    for i in range(n_agents):
        pos     = np.array([rng.uniform(5, 15), rng.uniform(1, 9), 0.0])
        agent   = Agent(
            id          = i,
            position    = pos,
            velocity    = np.zeros(3),
            mass        = rng.uniform(60, 90),
            radius      = rng.uniform(0.25, 0.35),
            v_max       = rng.normal(1.34, 0.20),
            panic       = 0.0,
            familiarity = (rng.random(4) > 0.5).astype(float),
            pre_evac_time = np.exp(rng.normal(np.log(20), 0.5)),  # LogN(20s, ...)
            group_id    = i // 3,
        )
        agents.append(agent)

    # Laços sociais intra-grupo
    for a in agents:
        for b in agents:
            if a.id != b.id and a.group_id == b.group_id:
                a.social_ties[b.id] = rng.uniform(0.3, 0.7)

    # ── Ambiente ──────────────────────────────────────────────────────────
    fire  = FireFields(shape=(40, 20), dx=0.5)
    exits = {
        0: np.array([0.0,  5.0, 0.0]),
        1: np.array([20.0, 5.0, 0.0]),
    }

    # Grafo de navegação simples
    graph = NavigationGraph()
    nodes = {
        0: [10.0, 5.0, 0.0], 1: [0.5, 5.0, 0.0], 2: [19.5, 5.0, 0.0],
        3: [5.0,  5.0, 0.0], 4: [15.0, 5.0, 0.0],
    }
    for nid, pos in nodes.items():
        graph.add_node(nid, pos)
    for u, v in [(0,3),(3,1),(0,4),(4,2),(3,4)]:
        graph.add_edge(u, v)

    stair_ca = StaircaseCA(shape=(10, 5), exits=[(0, 2), (9, 2)])

    return FireEvacuationABM(
        agents    = agents,
        fire      = fire,
        graph     = graph,
        stair_ca  = stair_ca,
        exits     = exits,
        t_alarm   = 10.0,
        dt_abm    = 0.10,
        dt_fds    = 0.50,
        dt_dt     = 1.00,
        dt_route  = 5.00,
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  ABM de Evacuação em Incêndio — Demonstração")
    print("=" * 60)

    sim = create_demo_scenario(n_agents=20)
    kpis = sim.run(t_max=200.0)

    print("\n  ── Indicadores de Desempenho ──────────────────────")
    for k, v in kpis.items():
        print(f"    {k:25s}: {v}")
    print("=" * 60)
