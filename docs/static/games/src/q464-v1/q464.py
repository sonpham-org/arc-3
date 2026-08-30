"""q464 Tessera Lineage -- preserve ancestry through folds and interrupt an autonomous seam macro."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TESSERA,SEAM,ANCESTOR,WINDOW,CLAIM,BAD=11,7,15,12,14,10,13,8
LEVELS=[
 {"name":"First Fold","ancestor":0,"period":4,"window":1,"plan":(3,4)},{"name":"Split Seam","ancestor":1,"period":5,"window":3,"plan":(1,3,3,4)},
 {"name":"Merged Mosaic","ancestor":2,"period":6,"window":2,"plan":(2,3,4,1)},{"name":"Topology Macro","ancestor":3,"period":7,"window":4,"plan":(3,3,3,3,4)},
 {"name":"Lineage Window","ancestor":1,"period":8,"window":6,"plan":(1,2,3,3,3,3,4)},{"name":"Tessera Lineage","ancestor":2,"period":9,"window":7,"plan":(2,1,3,3,3,3,3,4)}]
def transform(o,a):
 o=[set(v) for v in o]
 if a==1:o[0],o[-1]=o[-1],o[0]
 elif a==2:o[1]|=o[0];o=o[1:]+o[:1]
 return tuple(frozenset(v) for v in o)
def simulate(x):
 o=tuple(frozenset((i,)) for i in range(4));phase=0;caught=False
 for a in x["plan"]:
  if a in (1,2):o=transform(o,a);phase=(phase+1)%x["period"]
  elif a==3:phase=(phase+1)%x["period"]
  else:caught|=phase==x["window"]
 return o,phase,caught,min(i for i,v in enumerate(o) if x["ancestor"] in v)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MOSAIC
  for i,lineage in enumerate(g.lineages):
   x=7+i*14;f[12:27,x:x+10]=TESSERA
   for j,_ in enumerate(sorted(lineage)):f[29+j*3:31+j*3,x:x+10]=ANCESTOR
  f[43:47,8:8+g.phase*5]=SEAM;f[49:53,8:29 if g.caught else 16]=WINDOW;f[55:59,8:8+g.claim*12]=CLAIM
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q464(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.lineages=tuple(frozenset((i,)) for i in range(4));self.phase=self.claim=0;self.caught=False;self.history=[];self.target=(self.lineages,0,False,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q464",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.lineages=tuple(frozenset((i,)) for i in range(4));self.phase=self.claim=0;self.caught=False;self.history=[];self.target=simulate(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2):self.lineages=transform(self.lineages,a);self.phase=(self.phase+1)%x["period"];self.history.append(a)
  elif a==3:self.phase=(self.phase+1)%x["period"];self.history.append(a)
  elif a==4:self.caught|=self.phase==x["window"];self.history.append(a)
  elif a==5:self.claim=(self.claim+1)%4
  elif a==6:
   if tuple(self.history)==x["plan"] and (self.lineages,self.phase,self.caught)==self.target[:3] and self.caught and self.claim==self.target[3]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
