"""q177 Pressure Web -- pump connected chambers without rupturing gradient limits."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PLANT,CHAMBER,PRESSURE,TARGET,MEMBRANE,CURSOR,BAD=11,1,3,9,14,12,15,8
LEVELS=[
 {"name":"One Membrane","start":[3,0],"cap":4,"edges":[(0,1)],"plan":[1]},
 {"name":"Balance Gradient","start":[3,1,0],"cap":4,"edges":[(0,1),(1,2)],"plan":[1,4,1]},
 {"name":"Pressure Detour","start":[4,0,1],"cap":4,"edges":[(0,1),(1,2),(0,2)],"plan":[1,4,4,1]},
 {"name":"Connected Chambers","start":[3,2,1,0],"cap":4,"edges":[(0,1),(1,2),(2,3),(0,3)],"plan":[1,4,1,4,1]},
 {"name":"Avoid Rupture","start":[4,1,1,0],"cap":4,"edges":[(0,1),(1,2),(2,3),(0,3),(0,2)],"plan":[1,4,4,1,4,1]},
 {"name":"Pressure Web","start":[4,2,0,1,0],"cap":4,"edges":[(0,1),(0,2),(1,3),(2,3),(3,4),(1,4)],"plan":[1,4,1,4,4,1,4,4,1]}]
def pump(vals,edge,reverse,cap):
 a,b=edge
 if reverse:a,b=b,a
 out=list(vals)
 if out[a] and out[b]<cap:out[a]-=1;out[b]+=1
 return tuple(out)
def derive(level):
 v=tuple(level["start"]);c=0
 for z in level["plan"]:
  if z==3:c=(c-1)%len(level["edges"])
  elif z==4:c=(c+1)%len(level["edges"])
  elif z in (1,2):v=pump(v,level["edges"][c],z==2,level["cap"])
 return v
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=PLANT;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):x=7+i*(50//n);f[19:42,x:x+8]=CHAMBER;f[36-v*4:39,x+2:x+6]=PRESSURE;f[13:16,x:x+t*2]=TARGET
  for i in range(len(g.edges)):f[47:50,7+i*8:13+i*8]=CURSOR if i==g.cursor else MEMBRANE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q177(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.edges=[];self.cap=self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q177",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=derive(s);self.edges=list(map(tuple,s["edges"]));self.cap=s["cap"];self.cursor=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2):self.values=pump(self.values,self.edges[self.cursor],z==2,self.cap)
  elif z==3:self.cursor=(self.cursor-1)%len(self.edges)
  elif z==4:self.cursor=(self.cursor+1)%len(self.edges)
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
