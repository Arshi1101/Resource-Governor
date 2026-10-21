import math

class Baseline:
    def __init__(self, alpha, warmup):
        self.alpha, self.warmup = alpha, warmup
        self.n, self.mean, self.m2, self.var = 0, 0.0, 0.0, 0.0

    @property
    def ready(self):
        return self.n >= self.warmup

    @property
    def std(self):
        return math.sqrt(self.var)

    def update(self, x):
        self.n += 1
        d = x - self.mean
        if self.n <= self.warmup:
            self.mean += d / self.n
            self.m2 += d * (x - self.mean)
            self.var = self.m2 / max(self.n - 1, 1)
        else:
            self.mean += self.alpha * d
            self.var = (1 - self.alpha) * (self.var + self.alpha * d * d)
