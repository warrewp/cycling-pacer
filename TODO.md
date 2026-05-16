# CyclingPacer — Future Improvements

## Wind input simplification
Replace wind speed + direction inputs with a simple dropdown: Calm (2mph effective), Light breeze (4mph), Windy (7mph), Very windy (10mph). Based on the physics that effective headwind on a loop course ≈ 1/3 of ambient wind speed. Default of 0 wind gives unrealistically fast times.

## Per-segment air density
Currently a single air density (rho) value is computed from the start elevation and used for all segments. Should compute rho per segment based on each segment's actual elevation from the GPX data. Matters on mountain courses with significant elevation range (e.g., Leadville) but negligible on flat/rolling courses like Mid South.
