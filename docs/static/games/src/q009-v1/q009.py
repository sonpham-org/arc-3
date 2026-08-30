"""q009 Peripheral Current -- focused objects freeze while peripheral objects flow."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,POOL,FLOW,FOCUS,TARGET,RADIUS,CURSOR,BAD=12,10,9,14,6,15,11,8
LEVELS=[
 {"name":"Freeze the Center","n":3,"mod":4,"start":[0,0,0],"plan":[5,2,5]},
 {"name":"Move Focus","n":3,"mod":5,"start":[1,0,2],"plan":[3,5,2,3,5]},
 {"name":"Boundary Control","n":4,"mod":5,"start":[0,1,2,3],"plan":[5,2,3,5,2,5]},
 {"name":"Selective Current","n":4,"mod":6,"start":[2,0,4,1],"plan":[3,5,2,5,3,2,5]},
 {"name":"Wide Attention","n":5,"mod":6,"start":[0,2,1,4,3],"plan":[5,2,3,5,2,2,3,5]},
 {"name":"Peripheral Current","n":5,"mod":7,"start":[1,5,0,3,2],"plan":[3,5,2,3,5,2,5,2,3,5]}]
def derive(level):
 a=list(level["start"]);focus=radius=0;n=level["n"]
 for z in level["plan"]:
  if z==1:focus=(focus-1)%n
  elif z==2:focus=(focus+1)%n
  elif z==3:radius=1-radius
  elif z==5:a=[(p+1)%level["mod"] if min((i-focus)%n,(focus-i)%n)>radius else p for i,p in enumerate(a)]
 return a
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=POOL;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=8+i*(48//n);f[18:42,x:x+8]=FLOW;f[36-v*3:39,x+2:x+6]=FOCUS if i==g.focus else FLOW;f[12:15,x:x+t+2]=TARGET
   if min((i-g.focus)%n,(g.focus-i)%n)<=g.radius:f[44:48,x:x+8]=RADIUS
   if i==g.focus:f[51:54,x:x+8]=CURSOR
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q009(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=[];self.mod=self.focus=self.radius=0;self.budget=36;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q009",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.target=derive(s);self.mod=s["mod"];self.focus=self.radius=0;self.budget=36;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.budget-=1;n=len(self.values)
  if z==1:self.focus=(self.focus-1)%n
  elif z==2:self.focus=(self.focus+1)%n
  elif z==3:self.radius=1-self.radius
  elif z==5:self.values=[(p+1)%self.mod if min((i-self.focus)%n,(self.focus-i)%n)>self.radius else p for i,p in enumerate(self.values)]
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  if self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
