import sys, wave, array, math
def env(path, hop=480):
    w = wave.open(path); a = array.array('h', w.readframes(w.getnframes())); w.close()
    return [10*math.log10(sum(x*x for x in a[i:i+hop])/hop/32768**2 + 1e-12) for i in range(0, len(a)-hop, hop)]
for path in sys.argv[1:]:
    e = env(path); peak = max(e); slopes = []; i = 5
    while i < len(e) - 40:
        if e[i] > peak - 20 and max(e[i+1:i+4]) < e[i] and e[i+25] < e[i] - 15:
            seg = e[i:i+30]
            t5 = next((k for k, v in enumerate(seg) if v < seg[0]-5), None); t25 = next((k for k, v in enumerate(seg) if v < seg[0]-25), None)
            if t5 is not None and t25 is not None and t25 > t5: slopes.append(20/((t25-t5)*0.01))
            i += 30
        else: i += 1
    slopes.sort(); med = slopes[len(slopes)//2] if slopes else float('nan')
    print(f"{path}: {len(slopes)} finales · RT60 aprox {60/med:.2f} s")
