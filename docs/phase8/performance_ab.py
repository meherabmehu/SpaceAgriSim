"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'method': 'Isolated A/B on the same machine: git worktree at fe6bbe2 versus the Phase 8 branch, fresh '
           'process per tree, TestClient, 40 iterations after one warm-up call.',
 'endpoint': 'GET /api/models',
 'baseline': {'commit': 'fe6bbe2',
              'medianMs': 17.97,
              'cacheAfterTwoCalls': 'CacheInfo(hits=0, misses=10, maxsize=4, currsize=4)'},
 'after': {'commit': '266c200',
           'medianMs': 4.55,
           'cacheAfterTwoCalls': 'CacheInfo(hits=6, misses=6, maxsize=6, currsize=6)'},
 'speedup': 3.9,
 'attribution': 'Direct. The baseline shows misses=10 and hits=0 across two registry passes, i.e. all five '
                'artifacts re-read and re-hashed on every call with one evicted each time. The branch shows '
                'each of six artifacts loaded exactly once and then reused.',
 'endpointsWithoutAttributableChange': {'note': 'Measured in isolation in both trees, /api/simulate is 5.33 '
                                                'ms at baseline and 5.14 ms after, which is within '
                                                'run-to-run noise. Earlier full-sequence runs showed '
                                                'apparently large differences for /api/compare and '
                                                '/api/simulate; re-measuring each endpoint in a fresh '
                                                'process showed those were ordering artefacts of the '
                                                'measurement harness, not effects of the change. No claim is '
                                                'made for those endpoints.',
                                        'isolatedSimulateMs': {'baseline': 5.33, 'after': 5.14},
                                        'isolatedOptimizeMs': {'baseline': 147.18, 'after': 148.62}}}
