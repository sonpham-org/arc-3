"""q173 Density Drift -- shape particle distributions with gradient barriers."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,BIN,PARTICLE,TARGET,CURSOR,BAD=14,0,1,9,6,12,8
LEVELS=[
 {"name":"One Drift","start":[3,0],"target":[2,1],"ops":[(0,1)]},
 {"name":"Balance Cloud","start":[4,0,0],"target":[2,1,1],"ops":[(0,1),(0,2)]},
 {"name":"Gradient Chain","start":[5,0,0],"target":[2,2,1],"ops":[(0,1),(1,2),(0,2)]},
 {"name":"Barrier Shape","start":[4,2,0,0],"target":[2,1,2,1],"ops":[(0,2),(1,3),(0,1),(2,3)]},
 {"name":"Cloud Profile","start":[6,0,1,0],"target":[2,2,1,2],"ops":[(0,1),(0,2),(1,3),(2,3),(0,3)]},
 {"name":"Density Drift","start":[7,0,0,1],"target":[2,2,2,2],"ops":[(0,1),(0,2),(0,3),(1,2),(2,3),(3,1)]}]
def drift(values,op):
 a,b=op;o=list(values);src,dst=(a,b) if o[a]>o[b] else (b,a)
 if o[src]-o[dst]>=2:o[src]-=1;o[dst]+=1
 return tuple(o)
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=LAB;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=10+i*(45//n);f[14:45,x:x+9]=BIN
   for j in range(v):f[41-j*4:44-j*4,x+2:x+7]=PARTICLE
   f[10:13,x:x+min(9,t*3)]=TARGET
  for i in range(len(g.ops)):f[49:53,6+i*8:12+i*8]=CURSOR if i==g.cursor else BIN
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q173(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.ops=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q173",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=tuple(s["target"]);self.ops=list(map(tuple,s["ops"]));self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.ops)
  elif a==4:self.cursor=(self.cursor+1)%len(self.ops)
  elif a==5:self.values=drift(self.values,self.ops[self.cursor])
  elif a==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
