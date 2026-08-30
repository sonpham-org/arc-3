"""q154 Reservoir Crowd -- transfer populations under fluid-like conservation and capacity."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,ROOM,CROWD,CAP,TARGET,CURSOR,BAD=10,0,1,6,3,14,12,8
LEVELS=[
 {"name":"One Transfer","start":[3,0],"target":[2,1],"caps":[3,2],"ops":[(0,1)]},
 {"name":"Capacity","start":[4,0,0],"target":[2,1,1],"caps":[4,1,2],"ops":[(0,1),(0,2)]},
 {"name":"Crowd Chain","start":[5,0,0],"target":[2,2,1],"caps":[5,3,2],"ops":[(0,1),(1,2),(0,2)]},
 {"name":"Full Room","start":[4,2,0],"target":[2,2,2],"caps":[4,2,3],"ops":[(0,2),(1,2),(0,1)]},
 {"name":"Reservoir Analogy","start":[6,0,1,0],"target":[2,2,1,2],"caps":[6,3,2,2],"ops":[(0,1),(0,3),(1,2),(2,3)]},
 {"name":"Reservoir Crowd","start":[7,0,0,1],"target":[2,2,2,2],"caps":[7,3,3,3],"ops":[(0,1),(0,2),(0,3),(1,2),(2,3)]}]
def move(vals,caps,op):
 a,b=op;o=list(vals)
 if o[a] and o[b]<caps[b]:o[a]-=1;o[b]+=1
 return tuple(o)
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=HALL;n=len(g.values)
  for i,(v,t,c) in enumerate(zip(g.values,g.target,g.caps)):
   x=9+i*(47//n);f[15:44,x:x+9]=ROOM;f[15:18,x:x+c]=CAP
   for j in range(v):f[40-j*4:43-j*4,x+2:x+7]=CROWD
   f[11:14,x:x+t*3]=TARGET
  for i in range(len(g.ops)):f[48:52,6+i*9:13+i*9]=CURSOR if i==g.cursor else ROOM
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q154(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.caps=self.ops=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q154",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=tuple(s["target"]);self.caps=list(s["caps"]);self.ops=list(map(tuple,s["ops"]));self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.ops)
  elif a==4:self.cursor=(self.cursor+1)%len(self.ops)
  elif a==5:self.values=move(self.values,self.caps,self.ops[self.cursor])
  elif a==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
