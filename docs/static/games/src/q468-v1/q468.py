"""q468 Escapement Lineage -- probe a fault while tracking ancestry through gear transforms."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,TRAIL,PROBE,OUTCOME,SELECT,BAD=4,3,1,14,10,12,15,9,8
LEVELS=[
 {"name":"First Ancestor","fault":1,"probes":1,"ancestor":1,"ops":(1,)},
 {"name":"Passive Ambiguity","fault":2,"probes":2,"ancestor":2,"ops":(3,1)},
 {"name":"Merged Weight","fault":3,"probes":1,"ancestor":3,"ops":(1,2,3)},
 {"name":"Chosen Intervention","fault":2,"probes":3,"ancestor":2,"ops":(3,1,2,1)},
 {"name":"Nested Gear Trail","fault":1,"probes":2,"ancestor":1,"ops":(1,3,2,1,3)},
 {"name":"Escapement Lineage","fault":3,"probes":3,"ancestor":3,"ops":(3,1,2,3,1,2)}]
def evolve(tokens,a):
 t=[list(x) for x in tokens]
 if a==1:
  mask,color=t.pop(0);t.extend([[mask,(color+1)%4],[mask,(color+2)%4]])
 elif a==2 and len(t)>=2:
  p=t.pop(0);q=t.pop(0);t.insert(0,[p[0]|q[0],(p[1]+q[1])%4])
 elif a==3:
  colors=[x[1] for x in t][::-1]
  for x,c in zip(t,colors):x[1]=c
 return tuple((x[0],x[1]) for x in t)
def target(x):
 t=((1,0),(2,1),(4,2))
 for a in x["ops"]:t=evolve(t,a)
 return t
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i,(mask,color) in enumerate(g.tokens):x=7+i*12;f[12:22,x:x+9]=GEAR;f[24:31,x:x+9]=WEIGHT+color%2;f[33:36,x:x+min(mask,7)*2]=TRAIL
  f[43:46,8:8+g.probe*12]=PROBE;f[48:51,8:8+g.outcome*12]=OUTCOME;f[54:58,8:8+g.selection*13]=SELECT
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q468(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.tokens=((1,0),(2,1),(4,2));self.probe=self.outcome=self.selection=0;self.bad=False;self.target=target(LEVELS[0])
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q468",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.tokens=((1,0),(2,1),(4,2));self.probe=self.outcome=self.selection=0;self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.tokens=evolve(self.tokens,a)
  elif a==4:self.probe=(self.probe+1)%4;self.outcome=(x["fault"]*self.probe+sum(mask for mask,_ in self.tokens))%4
  elif a==5:self.selection=(self.selection+1)%4
  elif a==6:
   expected=(x["fault"]*(x["probes"]%4)+sum(mask for mask,_ in self.target))%4
   if self.tokens==self.target and self.probe==x["probes"]%4 and self.outcome==expected and self.selection==x["ancestor"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
