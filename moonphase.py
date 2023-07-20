from math import *
from datetime import datetime, timedelta

# Constants for the Sun and the Moon at julian date 1980-01-00
TO_RAD = 2*pi/360
TO_DEG = 1/TO_RAD
MAfactor = 0.9856473321
Elonge = 278.83354
Elongp = 282.596403
Eccent = 0.016718
Eccent2 = 1.016860112
Mlfactor = 13.1763966
Mmlong = 64.975464
MMfactor = 0.1114041
Mmlongp = 349.383063
Mlnode = 151.950429
MNfactor = 0.0529539
Evfactor = 1.2739
Aefactor = 0.1858
A3factor = 0.37
mEcfactor = 6.2886
A4factor = 0.214
Vfactor = 0.6583
NPfactor = 0.16
CosMinc = 0.995970321  # COS(TO_RAD*5.145396)
SinMinc = 8.9683442e-2  # SIN(TO_RAD*5.145396)
Synmonth = 29.53058868
# Was 1e-6 in initial algorithm, but we only have simple precision floats
EPSILON = 1e-6


def jd2000(dtlocal):
    """Computes the number of Julian days elapsed since 2000-01-01 12:00 local time for
    given local datetime."""
    dtutc = dtlocal - timedelta(hours=dtlocal.hour)
    year = dtutc.year - 2000
    jd = 365 * year + (year + 3) // 4 + 275 * dtutc.month // 9 - ((dtutc.month + 9) // 12) * (1 + ((year % 4) + 2) // 3) + dtutc.day - 31
    hour = dtlocal.hour + dtlocal.minute / 60.0 + dtlocal.second / 3600.0
    return jd + hour / 24.0


def computeMoonPhase():
    # 7306=days elapsed between 2000-01-01 and 1980-01-00=1979-12-31
    jd = jd2000(datetime.now()) + 7306
    N = MAfactor * jd
    N = N - N // 360 * 360.0
    M = N + Elonge - Elongp
    M = M - M // 360 * 360.0
    M = TO_RAD * M
    Ec = M
    delta = Ec - Eccent * sin(Ec) - M
    Ec = Ec - delta / (1 - Eccent * cos(Ec))
    while abs(delta) <= EPSILON:
        delta = Ec - Eccent * sin(Ec) - M
        Ec = Ec - delta / (1 - Eccent * cos(Ec))

    Ec = Eccent2 * tan(Ec / 2.0)
    Ec = 2 * TO_DEG * atan(Ec)
    Ls = Ec + Elongp
    Ls = Ls - Ls // 360 * 360.0
    ml = Mlfactor * jd + Mmlong
    ml = ml - ml // 360 * 360.0
    MM = ml - MMfactor * jd - Mmlongp
    MM = MM - MM // 360 * 360.0
    MN = Mlnode - MNfactor * jd
    Ev = Evfactor * sin(TO_RAD * (2 * (ml - Ls) - MM))
    Ae = Aefactor * sin(M)
    A3 = A3factor * sin(M)
    MmP = MM + Ev - Ae - A3
    mEc = mEcfactor * sin(TO_RAD * MmP)
    A4 = A4factor * sin(TO_RAD * 2 * MmP)
    lP = ml + Ev + mEc - Ae + A4
    V = Vfactor * sin(TO_RAD * 2 * (lP - Ls))
    lPP = lP + V
    NP = MN - NPfactor * sin(M)
    y = sin(TO_RAD * (lPP - NP)) * CosMinc
    x = cos(TO_RAD * (lPP - NP))
    Lm = TO_DEG * atan2(y, x) + NP
    BM = TO_DEG * asin(sin(TO_RAD * (lPP - NP)) * SinMinc)
    moonage = lPP - Ls
    moonage = moonage - moonage // 360 * 360.0
    if moonage < 0:
        moonage = moonage + 360.0
    moonphase = 0.5 - cos(TO_RAD * moonage) / 2.0

    return Synmonth * moonage / 360.0


# Test the function
#moon_phase = computeMoonPhase()
#print(f"The current moon phase is approximately {moon_phase:.2%}")
