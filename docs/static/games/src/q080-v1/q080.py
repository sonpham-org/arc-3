"""q080 Regime Cart -- move a radius of altered physical law through the board."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TRACK,CELL,CART,PLUS,MINUS,TARGET,CURSOR,BAD=7,1,10,12,14,8,15,11,6
LEVELS=[
 {"name":"Carry the Rule","start":[0,0,0],"mod":4,"radius":0,"plan":[5,4,5]},
 {"name":"Invert Locally","start":[1,0,2,0],"mod":5,"radius":0,"plan":[1,5,4,4,1,5]},
 {"name":"Moving Radius","start":[0,1,0,2],"mod":5,"radius":1,"plan":[5,4,4,1,5]},
 {"name":"Compose Regimes","start":[2,0,1,0,3],"mod":6,"radius":1,"plan":[1,5,4,4,1,5]},
 {"name":"Transport the Law","start":[0,2,1,3,0,1],"mod":6,"radius":1,"plan":[5,4,4,1,5,4,4,1,5]},
 {"name":"Regime Cart","start":[1,0,3,2,0,4],"mod":7,"radius":2,"plan":[1,5,4,4,1,5,4,4,5]}]
def derive(level):
 v=list(level["start"]);cart=0;regime=1
 for z in level["plan"]:
  if z==1:regime=-regime
  elif z==3:cart=(cart-1)%len(v)
  elif z==4:cart=(cart+1)%len(v)
  elif z==5:v=[(x+regime)%level["mod"] if abs(i-cart)<=level["radius"] else x for i,x in enumerate(v)]
 return v
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=TRACK;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):x=7+i*(50//n);f[23:39,x:x+8]=CELL;f[34-v*2:37,x+2:x+6]=PLUS if g.regime>0 else MINUS;f[15:18,x:x+t+2]=TARGET;f[43:47,x:x+8]=CART if abs(i-g.cart)<=g.radius else TRACK
  f[50:53,7+g.cart*(50//n):15+g.cart*(50//n)]=CURSOR
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q080(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=[];self.mod=self.radius=self.cart=0;self.regime=1;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q080",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.target=derive(s);self.mod=s["mod"];self.radius=s["radius"];self.cart=0;self.regime=1;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.regime=-self.regime
  elif z==3:self.cart=(self.cart-1)%len(self.values)
  elif z==4:self.cart=(self.cart+1)%len(self.values)
  elif z==5:self.values=[(x+self.regime)%self.mod if abs(i-self.cart)<=self.radius else x for i,x in enumerate(self.values)]
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
