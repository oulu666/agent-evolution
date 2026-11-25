"""Executable noninjectivity witness for the frozen CSV projection."""
from pilot import create,emit,read,restore,encode
pairs=0
for seed in range(12):
    w=create(seed); c=emit(w); rows,a=read(w)
    alternate='0.00' if a['format']!='0.00' else '"USD "0.00'
    y=restore(c,encode(dict(a,format=alternate)))
    assert read(y)[0]==rows
    assert emit(y)==c
    assert read(y)[1]['format']!=a['format']
    pairs+=1
print(pairs,'identical actual CSV byte streams have distinct required display formats')
