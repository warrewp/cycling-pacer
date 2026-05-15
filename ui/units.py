KG_PER_LB = 0.453592
M_PER_FT = 0.3048
KM_PER_MI = 1.60934


def kg_to_lb(kg): return kg / KG_PER_LB
def lb_to_kg(lb): return lb * KG_PER_LB
def m_to_ft(m): return m / M_PER_FT
def ft_to_m(ft): return ft * M_PER_FT
def km_to_mi(km): return km / KM_PER_MI
def mi_to_km(mi): return mi * KM_PER_MI
def kmh_to_mph(kmh): return kmh / KM_PER_MI
def mph_to_kmh(mph): return mph * KM_PER_MI
def c_to_f(c): return c * 9 / 5 + 32
def f_to_c(f): return (f - 32) * 5 / 9
