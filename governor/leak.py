def fit(hist):
    """Fit memory use over time and return its rate in MB/minute and R-squared."""
    n = len(hist)
    ts, ys = [p[0] for p in hist], [p[1] for p in hist]
    mt, my = sum(ts) / n, sum(ys) / n
    sxx = sum((t - mt) ** 2 for t in ts)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((t - mt) * (y - my) for t, y in zip(ts, ys))
    if sxx == 0 or syy == 0:
        return 0.0, 0.0
    return sxy / sxx * 60, (sxy * sxy) / (sxx * syy)

def forecast(hist, free_mb):
    rate, r2 = fit(hist)
    eta = free_mb / rate if rate > 0 else None
    return rate, r2, eta
