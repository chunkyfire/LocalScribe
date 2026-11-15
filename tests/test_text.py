import sys; sys.path.insert(0,".")
from diktat import engine
cfg={"dictionary":{"Lipaze":"Lipase"},"snippets":{"mit freundlichen Grüßen":"Mit freundlichen Grüßen\nCem Özel"},"commands":{"neue Zeile":"\n","neuer Absatz":"\n\n"},"trailing_space":True}
tests=["Die Lipaze ist erhöht. Neue Zeile. das Kreatinin liegt bei 1,4.","Erster Punkt, neuer Absatz, zweiter Punkt.","Vielen Dank. Mit freundlichen Grüßen.","Eine neue Zeilenangabe bleibt stehen.",""]
for t in tests: print(repr(engine.postprocess(t,cfg)))
import numpy as np
a=np.random.randn(16000*70).astype(np.float32)*0.1; a[16000*28:16000*29]=0
print([round(len(c)/16000,1) for c in engine.split_long(a)])
