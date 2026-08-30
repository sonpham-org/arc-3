"""q467 Spectrum Lineage -- track causal ancestry while packets trade appearance."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PRISM,PACKET,TRAIL,SELECT,ANCESTOR,BAD=11,0,15,9,10,12,14,8
LEVELS=[
 {"name":"First Split","ancestor":1,"ops":(1,)},
 {"name":"Appearance Swap","ancestor":2,"ops":(3,1)},
 {"name":"Merged Trail","ancestor":3,"ops":(1,2,3)},
 {"name":"Geometry Transfer","ancestor":2,"ops":(4,1,3,2)},
 {"name":"Relational Prism","ancestor":1,"ops":(1,3,4,2,1)},
 {"name":"Spectrum Lineage","ancestor":3,"ops":(3,1,4,2,3,1)}]
def evolve(tokens,a):
 t=[list(x) for x in tokens]
 if a==1:
  mask,color=t.pop(0);t.extend([[mask,(color+1)%4],[mask,(color+3)%4]])
 elif a==2 and len(t)>=2:
  one=t.pop(0);two=t.pop(0);t.insert(0,[one[0]|two[0],(one[1]+two[1])%4])
 elif a==3:
  colors=[x[1] for x in t][1:]+[t[0][1]]
  for x,c in zip(t,colors):x[1]=c
 elif a==4:t.reverse()
 return tuple((x[0],x[1]) for x in t)
def result(x):
 t=((1,0),(2,1),(4,2))
 for a in x["ops"]:t=evolve(t,a)
 return t
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=GALLERY;f[10:20,26:38]=PRISM
  for i,(mask,color) in enumerate(g.tokens):
   x=7+i*12;f[27:34,x:x+9]=PACKET+color%3;f[35:38,x:x+min(mask,7)*2]=TRAIL
  f[48:52,8:8+g.selection*13]=SELECT;f[54:58,8:8+LEVELS[g.level_index]["ancestor"]*13]=ANCESTOR
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q467(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.tokens=((1,0),(2,1),(4,2));self.selection=0;self.bad=False;self.target=result(LEVELS[0])
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q467",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.tokens=((1,0),(2,1),(4,2));self.selection=0;self.bad=False;self.target=result(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.tokens=evolve(self.tokens,a)
  elif a==5:self.selection=(self.selection+1)%4
  elif a==6:
   if self.tokens==self.target and self.selection==x["ancestor"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
